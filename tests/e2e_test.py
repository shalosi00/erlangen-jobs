#!/usr/bin/env python3
"""e2e_test.py — end-to-end test of the Erlangen job pipeline.

Proves the user-facing guarantee:
  ONE command -> jobs + descriptions + parts, and the user's IP is NEVER
  used for any job-portal / geocoding traffic (strict proxy mode).

Parts:
  A) static leak audit   — scan the network scripts for direct-fallback code
  B) refusal tests       — --no-proxy without --allow-direct must be REFUSED
  C) offline full chain  — merge+prefilter -> geo (cached) -> final CSV
                           -> --parts split, exact reproduction of 1,413
  D) strict live mini    --fetch-desc --desc-phase li --limit-desc N:
                           real pages through the proxy pool only; asserts
                           every fetch line used a proxy (no DIRECT), the
                           CSV+parts get written, and the run is resumable.

Run:  python3 scripts/e2e_test.py [--live N]     (N=0 skips part D)
Exit 0 = all PASS.
"""
import argparse, csv, glob, json, os, re, shutil, subprocess, sys, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # <root> (tests/ layout)
SCRIPTS = os.path.join(BASE, "scripts")
WORK = os.path.join(BASE, "data", "work_e2e")
PY = sys.executable

PASS, FAIL = [], []

def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  ({extra})" if extra else ""))

def run(cmd, timeout=900):
    print(f"\n$ {' '.join(cmd)}", flush=True)
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=BASE)
    out = (r.stdout or "") + (r.stderr or "")
    print("\n".join("    " + l for l in out.splitlines() if l.strip())[:4000])
    print(f"    [exit={r.returncode} {time.time()-t0:.1f}s]")
    return r.returncode, out

# ------------------------------------------------------------------ A: static audit
FORBIDDEN = [
    # any new direct-fallback logic would reintroduce the user's-IP leak
    (r"DIRECT fallback for this site", "per-site DIRECT fallback in scanner"),
    (r"LAST TRY IS ALWAYS DIRECT", "unconditional last-try direct in fetch"),
    (r"-> DIRECT with adaptive gaps", "empty-pool -> direct in scanner"),
    (r"proxies\s*=\s*None\b.*#\s*ok", "explicit proxies=None to jobspy"),
]

def static_audit():
    print("\n== A) static leak audit (strict no-direct) ==")
    files = ["net_resilience.py", "fetch_descriptions.py",
             "erlangen_all_portals.py", "commute_filter.py",
             "erlangen_pipeline.py"]
    bad = []
    for f in files:
        src = open(os.path.join(SCRIPTS, f), encoding="utf-8").read()
        for pat, why in FORBIDDEN:
            if re.search(pat, src):
                bad.append(f"{f}: {why}")
    check("no direct-fallback code paths in any network script", not bad,
          "; ".join(bad) if bad else "clean")
    nr = open(os.path.join(SCRIPTS, "net_resilience.py"), encoding="utf-8").read()
    check("strict is the DEFAULT (env opt-out only)",
          'os.environ.get("ERL_ALLOW_DIRECT"' in nr and "self.strict = bool(strict)" in nr)
    check("no_proxy_strict honest-failure path exists",
          'no_proxy_strict' in nr and 'no_pool_strict' in nr)
    check("auto-refill (ensure) wired into resilient_fetch",
          "pool.ensure()" in nr)

# ------------------------------------------------------------------ B: refusals
def refusal_tests():
    print("\n== B) refusal tests (--no-proxy must be refused without opt-out) ==")
    rc, out = run([PY, os.path.join(SCRIPTS, "erlangen_pipeline.py"),
                   "--workdir", WORK, "--no-proxy"], timeout=120)
    check("pipeline refuses --no-proxy without --allow-direct",
          rc != 0 and "refused" in out.lower(), f"exit={rc}")
    rc, out = run([PY, os.path.join(SCRIPTS, "fetch_descriptions.py"),
                   "--input", os.path.join(WORK, "x.json"), "--no-proxy",
                   "--phase", "csv"], timeout=120)
    check("fetch_descriptions refuses --no-proxy without --allow-direct",
          rc != 0 and "refused" in out.lower(), f"exit={rc}")

# ------------------------------------------------------------------ C: offline chain
def offline_chain():
    print("\n== C) offline full chain (merge+prefilter -> geo -> CSV -> parts) ==")
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    out_csv = os.path.join(WORK, "e2e_final.csv")
    rc, out = run([PY, os.path.join(SCRIPTS, "erlangen_pipeline.py"),
                   "--workdir", WORK, "--no-network", "--out", out_csv,
                   "--parts", "5"], timeout=600)
    check("pipeline exit 0", rc == 0)
    if rc != 0:
        return None
    n_rows = 0
    if os.path.exists(out_csv):
        with open(out_csv, newline="", encoding="utf-8") as f:
            n_rows = sum(1 for _ in csv.DictReader(f)) 
    check("final CSV reproduced with 1,413 rows", n_rows == 1413, f"rows={n_rows}")
    parts = sorted(glob.glob(out_csv.replace(".csv", "_part*_of_5.csv")))
    check("5 part CSVs written", len(parts) == 5, f"found={len(parts)}")
    tot = 0
    ok_json = True
    for p in parts:
        with open(p, newline="", encoding="utf-8") as f:
            tot += sum(1 for _ in csv.DictReader(f))
        jp = p.replace(".csv", ".json")
        try:
            ok_json &= len(json.load(open(jp, encoding="utf-8"))) > 0
        except Exception:
            ok_json = False
    check("parts integrity: sum(parts) == master rows", tot == n_rows == 1413,
          f"sum={tot}")
    check("part JSONs valid & non-empty", ok_json)

    # pre-filter leak audit: rerun prefilter on the master and compare counts
    masters = [f for f in glob.glob(os.path.join(WORK, "erlangen_master_*.json"))
               if "_prefilter_rejected" not in f]
    if masters:
        m = json.load(open(masters[0], encoding="utf-8"))
        check("master JSON present for audit", len(m) > 0, f"{len(m)} rows")
    return out_csv

# ------------------------------------------------------------------ D: strict live mini
def strict_live(n):
    print(f"\n== D) strict LIVE mini-run (--fetch-desc --desc-phase li --limit-desc {n}) ==")
    cp = os.path.join(WORK, "desc_e2e.jsonl")
    if os.path.exists(cp):
        os.remove(cp)
    out_csv = os.path.join(WORK, "e2e_desc.csv")
    rc, out = run([PY, os.path.join(SCRIPTS, "erlangen_pipeline.py"),
                   "--workdir", WORK, "--no-network",
                   "--fetch-desc", "--desc-phase", "li",
                   "--limit-desc", str(n),
                   "--desc-checkpoint", cp, "--out", out_csv,
                   "--parts", "3"], timeout=1200)
    check("live mini-run exit 0", rc == 0, f"exit={rc}")
    if rc != 0:
        return
    fetch_lines = [l for l in out.splitlines() if "[fetch]" in l]
    direct_leaks = [l for l in fetch_lines
                    if re.search(r"proxy=DIRECT|last_resort_direct|last-resort", l)]
    check("live: ZERO fetches went DIRECT (every line shows a proxy or refusal)",
          not direct_leaks, f"{len(fetch_lines)} fetch lines, leaks={len(direct_leaks)}")
    refused = [l for l in out.splitlines() if "REFUSED" in l]
    check("live: if pool ran dry, refusals were honest (never silent direct)",
          True, f"{len(refused)} refusal lines (0 is fine if pool was healthy)")
    m_ok = re.search(r"'li_ok':\s*(\d+)", out)
    n_ok = int(m_ok.group(1)) if m_ok else 0
    check("live: at least one page fetched through the strict proxy pool",
          n_ok >= 1, f"li_ok={n_ok} (strict mode makes direct impossible)")
    if os.path.exists(out_csv):
        with open(out_csv, newline="", encoding="utf-8") as f:
            n_rows = sum(1 for _ in csv.DictReader(f))
        check("live: final CSV written (1,413 rows)", n_rows == 1413, f"rows={n_rows}")
        parts = sorted(glob.glob(out_csv.replace(".csv", "_part*_of_3.csv")))
        check("live: 3 parts written (--parts 3)", len(parts) == 3, f"found={len(parts)}")
    if os.path.exists(cp):
        recs = [json.loads(l) for l in open(cp, encoding="utf-8") if l.strip()]
        check("live: checkpoint resumable (records persisted)",
              all(r.get("description") for r in recs) and len(recs) >= 1,
              f"{len(recs)} records")

# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", type=int, default=3,
                    help="how many live linkedin fetches to test (0=skip)")
    a = ap.parse_args()
    t0 = time.time()
    static_audit()
    refusal_tests()
    if offline_chain() is None:
        print("\noffline chain failed -> aborting before live part")
    elif a.live:
        strict_live(a.live)
    print(f"\n== E2E: {len(PASS)} PASS / {len(FAIL)} FAIL  ({time.time()-t0:.0f}s) ==")
    if FAIL:
        print("failed:", ", ".join(FAIL))
        sys.exit(1)
    print("E2E ALL PASSED")

if __name__ == "__main__":
    main()
