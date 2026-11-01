"""CLI: python -m pipeline fetch|sources

fetch  — run all (or selected) live sources, apply hard filters, dedupe, write
         CSV+JSON+rejected-audit + a run log. Exit 0 if >=1 source OK, 2 if all failed.
sources— print the full aggregator catalog (55+ sources) with status/access method.
"""
import argparse, os, sys, time, traceback, re, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from pipeline.core import (FetchCtx, Job, SourceResult, SourceError, classify_job,
                           dedupe, write_outputs, norm_txt)
from pipeline.sources import SOURCES, GEO_SCOPE, RUN_ORDER
from pipeline import catalog
from pipeline import geo
from pipeline import history as history_mod
from pipeline import digest as digest_mod

from pathlib import Path

# Repo root derived from this file (pipeline/ lives one level below) — works
# for the deployment sandbox AND for fresh clones (a hardcoded /home/z/... made
# clones write logs/runs into unrelated directories).
BASE = str(Path(__file__).resolve().parent.parent)
LOG_DIR = str(Path(BASE) / "logs")
RUNS_DIR = str(Path(BASE) / "data" / "runs")

# strict 0-transfer whitelist around Erlangen — GENERATED from the verified GTFS
# analysis (data/geo/transit_whitelist.json, F1). The old hand-typed NEAR_RX
# accepted 1-transfer towns (Neumarkt/Feucht/Altdorf/Schwabach/Zirndorf) and
# missed ~20 whitelisted ones (Coburg 47min, Lichtenfels, Haßfurt, ...).

# WAF/proxy/rate-limited sources never parallelized (F14); the rest are
# independent JSON/RSS/HTML fetches that profit from a small thread pool.
SEQ_ALWAYS = {"ba", "indeed", "linkedin", "xing", "kimeta", "stellenanzeigen"}

def build_ctx(args) -> FetchCtx:
    keys = {k: os.environ.get(k) for k in
            ("ADZUNA_APP_ID", "ADZUNA_APP_KEY", "JOOBLE_API_KEY", "CAREERJET_AFFID",
             "WHATJOBS_PUBLISHER_KEY") if os.environ.get(k)}
    return FetchCtx(
        query=args.query, city=args.city, radius=args.radius, days=args.days,
        timeout=args.timeout, sleep=args.polite, deep=not args.fast,
        max_pages=args.max_pages, max_per_source=args.max_per_source, keys=keys,
        near_re=geo.zero_xfer_rx(),
        cutoff=(datetime.now(timezone.utc) - timedelta(days=args.days)).date().isoformat(),
    )

def geo_keep(ctx, source_id: str, j: Job) -> bool:
    """Country-scope sources: keep only rows mentioning a 50-km whitelisted town."""
    if GEO_SCOPE.get(source_id) == "query":
        return True
    blob = f"{j.city} {j.location_raw} {j.description[:1500]} {j.title}"
    return bool(ctx.near_re.search(blob))

def date_ok(ctx, j: Job) -> bool:
    if not j.date_posted:
        return True          # unknown date -> keep, sortable column exists
    return j.date_posted >= ctx.cutoff

def run_fetch(args):
    ctx = build_ctx(args)
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = f"{LOG_DIR}/pipeline_run_{ts}.log"
    logf = open(log_path, "w", encoding="utf-8")

    def log(msg):
        logf.write(msg + "\n")
        logf.flush()
        if args.verbose:
            print(msg)

    order = [s for s in RUN_ORDER if s in SOURCES]
    if args.sources:
        want = {s.strip().lower() for s in args.sources.split(",")}
        unknown = want - set(SOURCES)
        if unknown:
            print(f"unknown source id(s): {', '.join(sorted(unknown))}\n"
                  f"run `python -m pipeline sources` to list valid ids", file=sys.stderr)
            return 1
        order = [s for s in order if s in want]
    if args.exclude:
        order = [s for s in order if s not in {x.strip().lower() for x in args.exclude.split(",")}]

    # F14: optional small thread pool for the network-bound, non-WAF sources
    parallel = max(1, int(getattr(args, "parallel", 1) or 1))
    if parallel > 1:
        seq_order = [s for s in order if s in SEQ_ALWAYS]
        par_order = [s for s in order if s not in SEQ_ALWAYS]
    else:
        seq_order, par_order = order, []

    print(f"pipeline fetch: query='{ctx.query}' city={ctx.city} radius={ctx.radius}km "
          f"days={ctx.days} sources={len(order)} filters={'ON' if not args.no_filters else 'OFF'} "
          f"parallel={parallel if parallel > 1 else 'off'}")

    # F12: proxy pool health line — makes silent kimeta degradation visible
    try:
        from pipeline.proxy_pool import stats as pool_stats
        ps = pool_stats()
        age = ps.get("age_hours")
        warn = "  WARNING: pool stale (>8h) — consider refresh" if age and age > 8 else ""
        print(f"proxy pool: alive={ps.get('alive', 0)} per_target={ps.get('per_target', {})} "
              f"age={age if age is not None else '?'}h{warn}")
        log(f"proxy pool {json.dumps(ps)}")
    except Exception as e:
        print(f"proxy pool: unavailable ({type(e).__name__})")
    print(f"log: {log_path}\n")

    results: list[SourceResult] = []
    all_kept, all_rejected = [], []
    display_names: dict[str, set] = {}   # F10: sid -> Job.source display names

    def process(sid: str, raw_jobs):
        """Filter one source's raw output; runs in the MAIN thread always. (thread-safe)"""
        res = SourceResult(name=sid)
        kept, rejected = [], []
        res.count_raw = len(raw_jobs)
        if not raw_jobs:
            res.status = "EMPTY"
        else:
            for j in raw_jobs:
                if args.no_filters:
                    kept.append(j)
                    res.count_kept += 1
                    continue
                # date + geo pre-filters (cheap, not user's hard filters)
                if not date_ok(ctx, j):
                    rejected.append((j, "date>days"))
                    res.count_rejected += 1
                    continue
                if not geo_keep(ctx, sid, j):
                    rejected.append((j, "geo:not-0xfer"))
                    res.count_rejected += 1
                    continue
                j.description = (j.description or "")[:6000]
                if j.source:
                    display_names.setdefault(sid, set()).add(j.source)
                keep, reason = classify_job(j)
                if keep:
                    kept.append(j)
                    res.count_kept += 1
                else:
                    rejected.append((j, reason))
                    res.count_rejected += 1
        return res, kept, rejected

    def report(sid: str, res: SourceResult, t0: float):
        res.duration_s = round(time.time() - t0, 1)
        results.append(res)
        mark = {"OK": "+", "EMPTY": "o", "ERROR": "!", "SKIP": "-"}[res.status]
        print(f"  {mark} {sid:<12} {res.status:<6} raw={res.count_raw:<4} kept={res.count_kept:<4} "
              f"rej={res.count_rejected:<4} {res.duration_s:>6}s"
              + (f"  {res.error[:80]}" if res.error else ""))
        log(f"[{sid}] {res.status} raw={res.count_raw} kept={res.count_kept} "
            f"rej={res.count_rejected} {res.duration_s}s {res.error} {res.detail}")

    def run_seq(sid: str):
        t0 = time.time()
        try:
            res, kept, rejected = process(sid, SOURCES[sid](ctx))
            all_kept.extend(kept)
            all_rejected.extend(rejected)
        except SourceError as e:
            res = SourceResult(name=sid, status="ERROR", error=str(e),
                               detail=f"url={e.url} {e.detail}".strip(), http_status=e.http_status)
            log(f"[{sid}] ERROR {e}")
        except Exception as e:
            res = SourceResult(name=sid, status="ERROR",
                               error=f"{type(e).__name__}: {str(e)[:200]}",
                               detail="unexpected — traceback in log")
            log(f"[{sid}] UNEXPECTED {traceback.format_exc()}")
        report(sid, res, t0)

    def run_par_error(sid: str, e: Exception, t0: float):
        if isinstance(e, SourceError):
            res = SourceResult(name=sid, status="ERROR", error=str(e),
                               detail=f"url={e.url} {e.detail}".strip(),
                               http_status=getattr(e, "http_status", None))
            log(f"[{sid}] ERROR {e}")
        else:
            res = SourceResult(name=sid, status="ERROR",
                               error=f"{type(e).__name__}: {str(e)[:200]}",
                               detail="unexpected — traceback in log")
            log(f"[{sid}] UNEXPECTED {traceback.format_exc()}")
        report(sid, res, t0)

    # 1) WAF/proxy/rate-limited sources: always sequential, always first
    for sid in seq_order:
        run_seq(sid)
    # 2) the rest: fetch concurrently (worker threads), filter+report on main thread
    if par_order:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futs = {pool.submit(SOURCES[sid], ctx): sid for sid in par_order}
            for fut in as_completed(futs):
                sid = futs[fut]
                t0 = time.time()
                try:
                    res, kept, rejected = process(sid, fut.result())
                    all_kept.extend(kept)
                    all_rejected.extend(rejected)
                except Exception as e:          # SourceError or unexpected
                    run_par_error(sid, e, t0)
                    continue
                report(sid, res, t0)

    # merge + dedupe (also re-classifies merged rows that gained a description)
    final = dedupe(all_kept)
    kept_final = []
    for j in final:
        keep, reason = classify_job(j)
        if args.no_filters or keep:
            kept_final.append(j)
        else:
            # F5: post-merge filter hits used to vanish silently — they now land
            # in the rejected audit like every other filtered row.
            all_rejected.append((j, f"postmerge:{reason}"))
    final = kept_final
    # F1: transit classification for EVERY kept row (filterable/sortable column;
    # query-scoped sources keep 1-xfer/none rows but now carry the label)
    for j in final:
        try:
            j.transit = geo.classify_job_location(j)
        except Exception:
            j.transit = ""

    ok_n = sum(1 for r in results if r.status == "OK")
    err_n = sum(1 for r in results if r.status == "ERROR")
    skip_n = sum(1 for r in results if r.status == "SKIP")

    print("\n" + "=" * 78)
    print(f"{'SOURCE':<14} {'STATUS':<7} {'RAW':>5} {'KEPT':>5} {'TIME':>7}  DETAIL")
    print("-" * 78)
    for r in results:
        print(f"{r.name:<14} {r.status:<7} {r.count_raw:>5} {r.count_kept:>5} {r.duration_s:>6}s  "
              f"{(r.error or '')[:60]}{(r.detail or '')[:40]}")
    print("-" * 78)
    ft_known = sum(1 for j in final if not j.ft_unknown)
    juniors = sum(1 for j in final if j.junior_signal)
    print(f"unique postings after dedupe: {len(final)} "
          f"(fulltime-confirmed: {ft_known}, ft_unknown flagged: {len(final) - ft_known}, "
          f"junior_signal: {juniors})")
    print(f"filters: ausbildung/parttime/experience rejected: {len(all_rejected)} rows -> rejected.csv")
    if args.no_filters:
        print("NOTE: filters were OFF (--no-filters) — raw dump")

    slug = re.sub(r"[^a-z0-9]+", "-", f"{ctx.query}-{ctx.city}-{ctx.radius}km-{ctx.days}d".lower()).strip("-")
    out_paths = write_outputs(final, all_rejected, args.out, slug, quiet=args.quiet)
    log(f"SUMMARY unique={len(final)} raw={sum(r.count_raw for r in results)} "
        f"ok={ok_n} err={err_n} skip={skip_n} rejected={len(all_rejected)}")
    logf.close()

    # F11: persistent run manifest — links outputs to per-source stats, survives
    # log wipes (data/ is persisted); powers digest source-down correlation (F10)
    try:
        write_manifest(ts, ctx, results, slug, out_paths, len(final), len(all_rejected),
                       {k: sorted(v) for k, v in display_names.items()})
    except Exception as e:
        print(f"run manifest write failed (non-fatal): {type(e).__name__}: {e}", file=sys.stderr)

    # persist into the cross-run job memory (first_seen/last_seen + FTS)
    try:
        mem = history_mod.update(final)
        print(f"job memory: +{mem['fresh']} new, {mem['known']} re-seen, "
              f"{mem['total']} total")
    except Exception as e:
        print(f"job memory update failed (non-fatal): {type(e).__name__}: {e}",
              file=sys.stderr)

    if not args.quiet:
        print("\n--- top 15 by date ---")
        for j in sorted(final, key=lambda x: x.date_posted, reverse=True)[:15]:
            print(f"{j.date_posted or '????-??-??'} | {j.title[:56]:<56} | {j.company[:24]:<24} | "
                  f"{j.city[:16]:<16} | {j.source[:20]}{' | FT?' if j.ft_unknown else ''}")
    print(f"\nrun log: {log_path}")
    if ok_n == 0 and err_n + skip_n > 0:
        print("ALL SOURCES FAILED — see log + `python -m pipeline sources`", file=sys.stderr)
        return 2
    return 0

def run_sources(args):
    catalog.print_catalog(only_fetchable=getattr(args, "only_fetchable", False))
    return 0

def write_manifest(ts, ctx, results, slug, out_paths, n_final, n_rejected, display_names=None):
    os.makedirs(RUNS_DIR, exist_ok=True)
    try:
        import subprocess
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE,
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        head = ""
    try:
        from pipeline.proxy_pool import stats as pool_stats
        pool = pool_stats()
    except Exception:
        pool = {}
    manifest = {
        "ts": ts,
        "git_head": head,
        "slug": slug,
        "query": ctx.query, "city": ctx.city, "radius": ctx.radius, "days": ctx.days,
        "ok_sources": sorted(r.name for r in results if r.status == "OK"),
        # F10: display names ("Talent.com", "Kimeta") as they appear in memory rows
        "ok_display_names": sorted({n for names in (display_names or {}).values() for n in names}),
        "not_ok_sources": [{"name": r.name, "status": r.status, "error": (r.error or "")[:120]}
                           for r in results if r.status != "OK"],
        "per_source": [asdict(r) for r in results],
        "outputs": list(out_paths),
        "unique_final": n_final, "rejected_total": n_rejected,
        "proxy_pool": pool,
    }
    path = f"{RUNS_DIR}/{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"run manifest: {path}")
    return path

def main(argv=None):
    ap = argparse.ArgumentParser(prog="pipeline", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="fetch jobs from all live sources")
    f.add_argument("--query", default="Fachinformatiker Systemintegration")
    f.add_argument("--city", default="Erlangen")
    f.add_argument("--radius", type=int, default=50)
    f.add_argument("--days", type=int, default=14)
    f.add_argument("--sources", default="", help="comma list (see `sources`); default: all live")
    f.add_argument("--exclude", default="")
    f.add_argument("--out", default=f"{BASE}/download")
    f.add_argument("--max-per-source", type=int, default=200)
    f.add_argument("--max-pages", type=int, default=2)
    f.add_argument("--timeout", type=int, default=25)
    f.add_argument("--polite", type=float, default=1.2, help="sleep between requests (s)")
    f.add_argument("--fast", action="store_true", help="skip BA per-job description fetch")
    f.add_argument("--no-filters", action="store_true", help="dump raw, no hard filters")
    f.add_argument("--no-geo", action="store_true", help="disable 50km client filter (country-scoped sources)")
    f.add_argument("--parallel", type=int, default=1,
                   help="thread pool for non-WAF sources (default 1 = sequential; 4-6 recommended)")
    f.add_argument("--quiet", action="store_true")
    f.add_argument("-v", "--verbose", action="store_true")
    f.set_defaults(func=run_fetch, no_geo=False)

    s = sub.add_parser("sources", help="print the aggregator catalog")
    s.add_argument("--only-fetchable", action="store_true")
    s.set_defaults(func=run_sources)

    h = sub.add_parser("history", help="cross-run job memory (SQLite + FTS)")
    hsub = h.add_subparsers(dest="history_cmd", required=True)
    hu = hsub.add_parser("update", help="upsert jobs_latest.json (or --infile)")
    hu.add_argument("--infile", default="")
    hsub.add_parser("new", help="postings first seen today")
    hsub.add_parser("gone", help="postings not re-seen today (likely expired)")
    hs = hsub.add_parser("search", help="full-text search the memory")
    hs.add_argument("q", default="")
    hsub.add_parser("stats", help="memory size summary")
    h.set_defaults(func=history_mod.cmd_history)

    d = sub.add_parser("digest", help="build daily digest; push via APPRISE_URL if set")
    d.set_defaults(func=digest_mod.cmd_digest)

    args = ap.parse_args(argv)
    if getattr(args, "no_geo", False):
        global GEO_SCOPE
        GEO_SCOPE = {k: "query" for k in GEO_SCOPE}   # disable client geo filter
    return args.func(args)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)
    except BrokenPipeError:
        # piped into `head`/`less` and the reader closed early — exit quietly
        sys.exit(0)
