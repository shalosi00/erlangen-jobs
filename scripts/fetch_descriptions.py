#!/usr/bin/env python3
"""
fetch_descriptions.py — visit every job page, collect FULL Stellenbeschreibung.

Strategies (fast, script-based, resumable):
  1. REUSE      descriptions already in the dataset (jobspy had fetched some)
  2. LINKEDIN   public page https://www.linkedin.com/jobs/view/<id>
                -> full description server-rendered in div.show-more-less-html__markup
  3. INDEED     re-run jobspy searches (same queries as sweep); the GraphQL search
                response carries description.html for every hit -> match by jk=key
  4. DIRECT     fetch job_url_direct (employer ATS): JSON-LD JobPosting -> meta
                description -> largest text block
  Anything still missing is reported honestly (no fake filler).

Checkpoint: data/work/descriptions.jsonl (one {job_url, source, description} per
line) — the script can be killed and re-run at any time, progress is kept.

Self-adaptive networking (net_resilience): STRICT proxy rotation with health
tracking (the user's IP is NEVER used for job pages), UA rotation, AIMD
pacing per host-class, classified retries (429/403/999 -> rotate+backoff,
404 -> give up, 5xx -> soft retry), auto proxy re-harvest when the pool runs
dry.  If no proxy can be obtained the affected pages fail HONESTLY — no
silent direct fallback (--allow-direct is the explicit opt-out).

Usage:
  python3 scripts/fetch_descriptions.py                 # all phases
  python3 scripts/fetch_descriptions.py --phase li      # only linkedin
  python3 scripts/fetch_descriptions.py --limit 5       # smoke test
  python3 scripts/fetch_descriptions.py --write-csv     # regenerate final CSV sorted by date
  python3 scripts/fetch_descriptions.py --proxy-refresh # harvest free proxies first
  python3 scripts/fetch_descriptions.py --allow-direct  # opt-out of strict no-IP mode

Output CSV: download/erlangen_jobs_final_<date>.csv — WITH description column,
sorted by date_posted (newest first), tiebreak by commute distance.
"""
import argparse, csv, glob, html, json, os, random, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html.parser import HTMLParser

import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "data", "work")
DOWNLOAD = os.path.join(BASE, "download")
CHECKPOINT = os.path.join(WORK, "descriptions.jsonl")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import net_resilience as nr

# ------------------------------------------------------------------ html -> text
class _TextExtract(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "section", "tr"}
    SKIP = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip_depth = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)

def html_to_text(raw):
    p = _TextExtract()
    try:
        p.feed(raw)
        p.close()
    except Exception:
        return raw
    txt = "".join(p.parts)
    txt = re.sub(r"[ \t\r\xa0]+", " ", txt)
    txt = re.sub(r"\n\s*\n\s*\n+", "\n\n", txt)
    return txt.strip()

def strip_tag_block(fragment):
    """Inner content of one matched div fragment -> text."""
    return html_to_text(fragment)

# ------------------------------------------------------------------ extraction helpers
RE_LI_MARKUP = re.compile(
    r'<div class="show-more-less-html__markup[^"]*"(?:\s[^>]*)?>(.*?)</div>\s*(?:</section>|<div class="show-more)',
    re.S)
RE_LD_JSON = re.compile(
    r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S)
RE_META_DESC = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.I | re.S)
RE_SCRIPT_TAGS = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.I | re.S)

def extract_linkedin(resp_text):
    m = RE_LI_MARKUP.search(resp_text)
    if not m or len(m.group(1)) < 100:
        return None
    return html_to_text(m.group(1))

def extract_jsonld_desc(resp_text):
    for m in RE_LD_JSON.finditer(resp_text):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for d in items:
            if isinstance(d, dict) and d.get("@type") in ("JobPosting", "SoftJob"):
                desc = d.get("description")
                if desc and len(str(desc)) > 100:
                    return html_to_text(str(desc)) if "<" in str(desc) else str(desc)
    return None

def extract_generic(resp_text):
    body = RE_SCRIPT_TAGS.sub(" ", resp_text)
    # largest single text run between block tags
    texts = re.split(r"<[^>]+>", body)
    texts = sorted((html.unescape(t).strip() for t in texts),
                   key=len, reverse=True)
    cand = next((t for t in texts if len(t) > 200 and " " in t), "")
    return cand or None

# ------------------------------------------------------------------ fetchers
# module-level net context, set by main()
_POOL = None
_PACER = nr.AdaptivePacer(base=0.8, min_d=0.35, max_d=30.0)

def seed_pacer(li_base):
    _PACER.seed("li", li_base)
    _PACER.seed("ats", max(0.4, li_base / 3))

def fetch_linkedin(job):
    m = re.search(r"/jobs/view/([^/?]+)", job.get("job_url") or "")
    if not m:
        return None, "no_li_id"
    url = f"https://www.linkedin.com/jobs/view/{m.group(1)}"
    r, info = nr.resilient_fetch(url, pool=_POOL, pacer=_PACER, cls="li", timeout=25)
    if r is None:
        return None, f"li_exhausted:{str(info.get('error'))[:40]}"
    if r.status_code == 429:
        return None, "li_429"
    if r.status_code != 200:
        return None, f"li_http_{r.status_code}"
    desc = extract_linkedin(r.text) or extract_jsonld_desc(r.text)
    return (desc, None) if desc else (None, "li_no_markup")

def fetch_direct(job):
    url = job.get("job_url_direct") or (job.get("job_url") if job.get("job_url") and
                                        "indeed.com" not in job["job_url"] and
                                        "linkedin.com" not in job["job_url"] else None)
    if not url:
        return None, "no_direct_url"
    r, info = nr.resilient_fetch(url, pool=_POOL, pacer=_PACER, cls="ats", timeout=20)
    if r is None:
        return None, f"direct_exhausted:{str(info.get('error'))[:40]}"
    if r.status_code != 200:
        return None, f"direct_http_{r.status_code}"
    desc = extract_jsonld_desc(r.text) or extract_generic(r.text)
    return (desc, None) if desc else (None, "direct_no_desc")

# ------------------------------------------------------------------ indeed re-search
def indeed_harvest(queries, log=print, pool=None):
    """Re-run jobspy indeed searches; return {jk: full_description}.

    STRICT: queries run ONLY through rotating proxies; when the pool is
    empty we try pool.ensure() (auto-harvest) once per query and otherwise
    SKIP the query — jobspy is never called without a proxy (your IP).
    Inter-query gap adapts: longer after failures, shorter after clean runs.
    """
    from jobspy import scrape_jobs
    found = {}
    gap = 6.0
    for i, q in enumerate(queries, 1):
        try:
            px = pool.as_list() if pool else None
            if not px:
                if pool is not None:
                    pool.ensure()
                    px = pool.as_list()
                if not px:
                    log(f"  indeed '{q}' SKIPPED: no healthy proxy "
                        f"(strict mode — your IP is never used)")
                    time.sleep(min(gap, 10.0))
                    continue
            df = scrape_jobs(site_name=["indeed"], search_term=q,
                             location="Erlangen, Germany", distance=31,
                             results_wanted=250, hours_old=1440,
                             country_indeed="Germany", verbose=0,
                             proxies=px)
            n = 0
            if df is not None and len(df):
                for _, r in df.iterrows():
                    url = str(r.get("job_url") or "")
                    m = re.search(r"[?&]jk=([^&]+)", url)
                    d = r.get("description")
                    if m and isinstance(d, str) and len(d) > 120:
                        key = m.group(1)
                        if key not in found or len(d) > len(found[key]):
                            found[key] = d
                            n += 1
            log(f"  indeed '{q}': +{n} descs (total {len(found)})"
                f" [px={len(px)}]")
            gap = max(4.0, gap * 0.8)          # clean run -> speed up gently
        except Exception as e:
            msg = str(e)[:120]
            log(f"  indeed '{q}' FAIL: {msg}")
            gap = min(90.0, gap * 2.0)         # failure -> back off hard
        time.sleep(gap)
    return found

# ------------------------------------------------------------------ checkpoint io
_lock = threading.Lock()

def load_checkpoint():
    done = {}
    if os.path.exists(CHECKPOINT):
        for line in open(CHECKPOINT, encoding="utf-8"):
            try:
                rec = json.loads(line)
                if rec.get("description") and len(rec["description"]) > 100:
                    done[rec["job_url"]] = rec
            except Exception:
                continue
    return done

def save_rec(rec):
    with _lock:
        with open(CHECKPOINT, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

# ------------------------------------------------------------------ main
def main():
    global CHECKPOINT
    ap = argparse.ArgumentParser(description="Collect full job descriptions")
    ap.add_argument("--input", default=os.path.join(WORK, "erlangen_commute_filtered_20261018_1526.json"))
    ap.add_argument("--phase", default="all", choices=["all", "li", "direct", "indeed", "csv"])
    ap.add_argument("--limit", type=int, default=0, help="only first N missing jobs (smoke)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--li-min", type=float, default=1.2, help="linkedin base pacing s (adaptive beyond this)")
    ap.add_argument("--li-max", type=float, default=2.8, help="kept for compat; pacer jitters automatically")
    ap.add_argument("--checkpoint", default=CHECKPOINT, help="descriptions.jsonl path (isolatable for tests)")
    ap.add_argument("--out", default=None, help="final CSV path (default download/erlangen_jobs_final_<date>.csv)")
    ap.add_argument("--proxy-file", default=os.path.join(BASE, "data", "proxies.txt"))
    ap.add_argument("--no-proxy", action="store_true",
                    help="disable proxy pool entirely — requires --allow-direct "
                         "(otherwise your IP would be exposed)")
    ap.add_argument("--allow-direct", action="store_true",
                    help="opt-out of strict no-IP mode: permit DIRECT fetches "
                         "as last resort (uses YOUR IP — not recommended)")
    ap.add_argument("--proxy-refresh", action="store_true", help="harvest+validate free proxies before starting")
    ap.add_argument("--proxy-min", type=int, default=5, help="min healthy proxies to keep trying rotation")
    ap.add_argument("--write-csv", action="store_true")
    args = ap.parse_args()

    CHECKPOINT = args.checkpoint

    # ---- self-adaptive network setup (strict: never the user's IP) -----
    global _POOL
    if args.no_proxy and not args.allow_direct:
        sys.exit("--no-proxy would expose your IP to job portals -> refused.\n"
                 "Use --allow-direct if you really want that (not recommended).")
    if args.no_proxy:
        os.environ["ERL_ALLOW_DIRECT"] = "1"   # explicit opt-out
        pool = None
        print("net: --no-proxy --allow-direct -> DIRECT allowed (YOUR IP!)")
    else:
        pool = nr.ProxyPool(state_file=nr.POOL_STATE)   # ONE shared pool state
        if args.proxy_refresh:
            pool.harvest(min_healthy=args.proxy_min)
        elif pool.healthy_count() < args.proxy_min:
            pool.ensure(min_healthy=args.proxy_min)      # self-adjusting refill
        if pool.healthy_count():
            v = pool.snapshot()["verified"]
            print(f"net: {v} verified proxies active "
                  f"(+{pool.healthy_count() - v} untested candidates, rotation ON, "
                  f"strict: your IP is never used)")
        else:
            print("net: NO healthy proxies -> strict mode: pages will fail "
                  "honestly instead of using your IP "
                  "(auto-harvest will keep retrying; --allow-direct to override)")
    _POOL, _PACER_got = nr.build(pool=pool)
    seed_pacer(max(0.5, args.li_min))

    jobs = json.load(open(args.input))
    print(f"jobs: {len(jobs)} from {os.path.basename(args.input)}")

    existing = load_checkpoint()
    print(f"checkpoint: {len(existing)} descriptions already saved")

    # ---- phase: linkedin (threaded); direct-only rows don't exist in this
    # dataset (791 li + 622 indeed), so "direct" here means li-failure fallback
    if args.phase in ("all", "li", "direct"):
        todo = []
        for j in jobs:
            u = j.get("job_url") or ""
            if u in existing:
                continue                       # checkpoint already has it
            if "linkedin.com" in u:
                todo.append((j, "li"))         # always refetch: full, untruncated
            elif "indeed.com" in u:
                if args.phase == "direct":     # last-resort sweep via job_url_direct
                    todo.append((j, "direct"))
            else:
                todo.append((j, "direct"))
        if args.limit:
            todo = todo[: args.limit]
        todo_li = [t for t in todo if t[1] == "li"]
        todo_dir = [t for t in todo if t[1] == "direct"]
        print(f"to fetch: {len(todo_li)} linkedin + {len(todo_dir)} direct")

        results = {"li_ok": 0, "li_fail": 0, "dir_ok": 0, "dir_fail": 0}
        fails = {}

        def work(item):
            job, strat = item
            if strat == "li":
                # pacing happens inside resilient_fetch (AIMD per host-class)
                desc, err = fetch_linkedin(job)
                return strat, job, desc, err
            desc, err = fetch_direct(job)
            return strat, job, desc, err

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(work, it) for it in todo_li + todo_dir]
            for i, fu in enumerate(as_completed(futs), 1):
                strat, job, desc, err = fu.result()
                if strat == "li":
                    if desc:
                        results["li_ok"] += 1
                    else:
                        results["li_fail"] += 1
                        fails.setdefault(err or "?", []).append(job.get("job_url"))
                        # immediate direct fallback
                        d2, e2 = fetch_direct(job)
                        if d2:
                            results["dir_ok"] += 1
                            save_rec({"job_url": job.get("job_url"), "url_direct": job.get("job_url_direct"),
                                      "source": "direct-fallback", "description": d2,
                                      "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
                        else:
                            results["dir_fail"] += 1
                            fails.setdefault("li+direct:" + (e2 or "?"), []).append(job.get("job_url"))
                else:
                    if desc:
                        results["dir_ok"] += 1
                    else:
                        results["dir_fail"] += 1
                        fails.setdefault(err or "?", []).append(job.get("job_url"))
                if desc:
                    save_rec({"job_url": job.get("job_url"), "url_direct": job.get("job_url_direct"),
                              "source": strat, "description": desc,
                              "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
                if i % 100 == 0:
                    print(f"  ...{i}/{len(todo_li) + len(todo_dir)} done {results}", flush=True)

        print("phase result:", results)
        top = sorted(fails.items(), key=lambda x: -len(x[1]))[:8]
        for err, urls in top:
            print(f"  fail {err}: {len(urls)}")

    # ---- phase: indeed re-search
    if args.phase in ("all", "indeed"):
        existing = load_checkpoint()
        have = set(existing) | {j.get("job_url") for j in jobs
                                if len(str(j.get("description") or "")) > 100
                                and "indeed.com" in (j.get("job_url") or "")}
        need = [j for j in jobs if "indeed.com" in (j.get("job_url") or "")
                and j.get("job_url") not in existing]
        if args.limit:
            need = need[: args.limit]
        print(f"indeed rows needing desc: {len(need)}")
        if need:
            QUERIES = ["", "engineer", "Ingenieur", "software", "developer", "IT",
                       "Entwickler", "data", "Vertrieb", "Kaufmännisch", "Praktikum",
                       "Werkstudent", "Techniker", "Medizin", "Logistik", "research",
                       "marketing", "finance"]
            found = indeed_harvest(QUERIES, pool=_POOL)
            print(f"indeed harvest: {len(found)} full descriptions")
            n_ok = 0
            for j in need:
                m = re.search(r"[?&]jk=([^&]+)", j.get("job_url") or "")
                if m and m.group(1) in found:
                    d = html_to_text(found[m.group(1)]) if "<" in found[m.group(1)] else found[m.group(1)]
                    save_rec({"job_url": j.get("job_url"), "url_direct": j.get("job_url_direct"),
                              "source": "indeed", "description": d,
                              "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
                    n_ok += 1
            print(f"indeed matched: {n_ok}/{len(need)}")

    # ---- phase: csv
    if args.phase in ("all", "csv") or args.write_csv:
        existing = load_checkpoint()
        out_rows = []
        for j in jobs:
            r = dict(j)
            desc = str(j.get("description") or "")
            src = "scrape"
            cp = existing.get(j.get("job_url"))
            if cp and len(cp["description"]) > len(desc):
                desc, src = cp["description"], cp["source"]
            elif desc and len(desc) >= 900:
                src = "scrape-trimmed"
            r["description"], r["description_source"] = desc, (src if desc else "MISSING")
            out_rows.append(r)
        have_desc = sum(1 for r in out_rows if len(r["description"]) > 100)
        print(f"\ncoverage: {have_desc}/{len(out_rows)} ({have_desc/len(out_rows)*100:.1f}%)")

        # sort: newest first, missing dates last, tiebreak commute distance
        def _km(r):
            v = (r.get("commute") or {}).get("erlangen_km", 999)
            return v if isinstance(v, (int, float)) else 999
        out_rows.sort(key=lambda r: (
            0 if r.get("date_posted") else 1,
            tuple(-int(x) for x in str(r.get("date_posted") or "0000-00-00")[:10].split("-")) if r.get("date_posted") else (0, 0, 0),
            _km(r),
        ))
        ts = date.today().strftime("%Y%m%d")
        out = args.out or os.path.join(DOWNLOAD, f"erlangen_jobs_final_{ts}.csv")
        cols = ["date_posted", "age_days", "title", "company", "location", "city",
                "direction", "station", "station_km", "erlangen_km", "line",
                "description_source", "description", "is_remote", "source_portal",
                "job_url", "job_url_direct"]
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in out_rows:
                c = r.get("commute", {})
                w.writerow([r.get("date_posted"), r.get("age_days"), r.get("title"),
                            r.get("company"), r.get("location"), c.get("city"),
                            c.get("direction"), c.get("nearest_station"),
                            c.get("station_km"), c.get("erlangen_km"), c.get("line"),
                            r.get("description_source"), r.get("description"),
                            r.get("is_remote"), r.get("source_portal"),
                            r.get("job_url"), r.get("job_url_direct")])
        print(f"CSV written: {out} ({len(out_rows)} rows, sorted by date desc)")

    nr.health_dump({"input": os.path.basename(args.input),
                    "phase": args.phase,
                    "proxy_mode": "off(direct allowed)" if args.no_proxy else
                                  (f"pool:{_POOL.healthy_count()} strict"
                                   if _POOL else "none-strict")})

if __name__ == "__main__":
    main()
