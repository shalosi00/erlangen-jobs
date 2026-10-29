#!/usr/bin/env python3
"""de_job_score.py - score the filtered Erlangen job set with the career-ops rubric (one LLM pass).

Rubric dimensions (career-ops methodology, adapted):
  match (role vs generic mid/senior SW/AI profile), growth, comp signal, red flags
Input (default): the newest erlangen_jobs_final_*.csv produced by erlangen_pipeline.py
  (already pre-filtered: no Ausbildung/Senior/Fremdberuf, <=30d fresh, rail corridor).
Fallbacks: any --input file, or newest erlangen_master_*.json, or germany_jobs_*.json.
Output: ranking printed to stdout; --out <file.json> saves it (default: download/erlangen_top10_scored.json).
"""
import argparse, csv, glob, json, os, subprocess, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOAD = os.path.join(BASE, "download")

SYSTEM = (
    "You are a pragmatic German tech job market analyst. Score jobs 1-10 for a "
    "generic mid/senior software/AI engineer profile (English-speaking, Nuremberg/"
    "Erlangen area, hybrid ok, ~70-90k EUR expectation, prefers product companies "
    "over bodyshops, values modern stacks and AI work). Penalize: unclear roles, "
    "government/admin postings, pure PHP/legacy, staffing agencies. Reward: AI/ML "
    "product work, modern stack, published salary, known tech companies. Output "
    "STRICT JSON only: [{\"title\":..., \"company\":..., \"score\":int, "
    "\"reason\":\"<=14 words\", \"url\":...}] - exactly 10 items, best first. "
    "No markdown fences."
)

def find_input(explicit):
    if explicit:
        return explicit
    for pattern in (
        os.path.join(DOWNLOAD, "erlangen_jobs_final_*.csv"),
        os.path.join(DOWNLOAD, "erlangen_master_*.json"),
        os.path.join(DOWNLOAD, "germany_jobs_*.json"),
    ):
        files = sorted(glob.glob(pattern))
        if files:
            return files[-1]
    raise SystemExit("no input job file found (run erlangen_pipeline.py first)")

def load_jobs(path):
    rows = []
    if path.endswith(".csv"):
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        rows = json.load(open(path))
    return rows

def main():
    ap = argparse.ArgumentParser(description="Score filtered job set (top 10)")
    ap.add_argument("--input", default=None, help="job CSV/JSON (default: newest final CSV)")
    ap.add_argument("--out", default=os.path.join(DOWNLOAD, "erlangen_top10_scored.json"))
    ap.add_argument("--seed", type=int, default=30, help="how many diverse rows to send")
    args = ap.parse_args()

    path = find_input(args.input)
    jobs = load_jobs(path)
    print(f"scoring seed from: {path} ({len(jobs)} rows)")

    # diverse seed: dedupe by company, keep corridor-closest first (CSV is pre-sorted)
    seen, seed = set(), []
    for j in jobs:
        c = j.get("company")
        if c in seen:
            continue
        seen.add(c)
        lo, hi = j.get("min_amount"), j.get("max_amount")
        compact = {k: j.get(k) for k in ("title", "company", "location", "job_url",
                                          "job_url_direct", "date_posted")}
        compact["pay"] = (f"{j.get('currency', 'EUR')} {lo}-{hi}" if lo else "not listed")
        seed.append(compact)
        if len(seed) >= args.seed:
            break

    prompt = ("Rank these German tech job listings for the profile. Listings:\n"
              + json.dumps(seed, ensure_ascii=False)[:11000])
    tmp = "/tmp/de_score.json"
    ranked = None
    for attempt in range(1, 4):                       # self-healing LLM call
        r = subprocess.run(["z-ai", "chat", "-p", prompt, "-s", SYSTEM, "-o", tmp],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            print(f"  llm attempt {attempt} failed: {r.stderr[-120:]} "
                  f"-> retrying with backoff", flush=True)
            time.sleep(4 * attempt)
            continue
        try:
            raw = open(tmp).read()
            data = json.loads(raw)
            cand = data["choices"][0]["message"]["content"]
            cand = cand.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
            ranked = json.loads(cand)
            break
        except (json.JSONDecodeError, KeyError, IndexError, OSError) as e:
            print(f"  llm attempt {attempt}: bad response ({e}) -> retrying",
                  flush=True)
            time.sleep(4 * attempt)
    if ranked is None:
        raise SystemExit("llm failed after 3 attempts (no retry left)")
    items = ranked
    json.dump(items, open(args.out, "w"), indent=1, ensure_ascii=False)
    print(f"top {len(items)} -> {args.out}\n")
    for i, it in enumerate(items, 1):
        print(f"{i:2}. [{it['score']}/10] {it['title']} @ {it['company']} - {it['reason']}")
        print(f"     {it.get('url', '')[:100]}")

if __name__ == "__main__":
    main()
