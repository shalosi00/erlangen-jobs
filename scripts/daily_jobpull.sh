#!/usr/bin/env bash
# Daily job pull for Asha's FISI search — one command, full chain.
# Usage:
#   bash scripts/daily_jobpull.sh [--with-proxies]
#     --with-proxies  re-validate the free-proxy pool first (~4 min) — needed
#                     for kimeta freshness; skip if validated within hours
# Output: download/jobs_*.csv/.json + jobs_latest.* + rejected-audit CSV +
#         data/runs/<ts>.json manifest, mirrored to site/downloads/.
#
# Optional env (notification layer — apprise speaks 100+ services):
#   APPRISE_URL    ntfy://ntfy.sh/<topic> | tgram://<bot-token>/<chat-id> | mailtos://...
#   HC_PING_URL    healthchecks.io ping URL — dead-man's switch: curl'ed on
#                  SUCCESS only, so silence = something broke (free tier)
#
# F9 (project-review 2026-10-14): venv self-heal via requirements.txt (5 wipes
# documented), flock against overlapping runs, consistent step labels 0-6/6.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=/home/z/.venv/bin/python
LOG=logs/daily_jobpull_$(date +%Y%m%d-%H%M).log
mkdir -p logs

# F9: single-instance guard — overlapping runs would double-hit rate-limited sources
exec 9>logs/.daily_jobpull.lock
if ! flock -n 9; then
  echo "daily_jobpull: another run is already in progress — aborting" | tee -a "$LOG"
  exit 1
fi

echo "[0/5] venv check" | tee -a "$LOG"
if [[ ! -x "$PY" ]]; then
  echo "  venv missing entirely — recreating $PY" | tee -a "$LOG"
  python3 -m venv /home/z/.venv >>"$LOG" 2>&1 || { echo "VENV CREATE FAILED" | tee -a "$LOG"; exit 1; }
fi
if ! "$PY" -c "import jobspy, sqlite_utils, rapidfuzz, apprise, socks, requests, curl_cffi" >/dev/null 2>&1; then
  echo "  venv broken (expected after a sandbox wipe) — installing requirements.txt" | tee -a "$LOG"
  "$PY" -m pip install -q --upgrade pip >>"$LOG" 2>&1
  "$PY" -m pip install -q -r requirements.txt >>"$LOG" 2>&1 \
    || { echo "VENV RESTORE FAILED — see $LOG" | tee -a "$LOG"; exit 1; }
  echo "  venv restored from requirements.txt" | tee -a "$LOG"
else
  echo "  venv OK" | tee -a "$LOG"
fi

echo "[1/6] proxy pool" | tee -a "$LOG"
if [[ "${1:-}" == "--with-proxies" ]]; then
  $PY -m pipeline.proxy_pool refresh >>"$LOG" 2>&1 || echo "  pool refresh FAILED (continuing with cached pool)" | tee -a "$LOG"
else
  $PY -m pipeline.proxy_pool stats >>"$LOG" 2>&1
fi

echo "[2/6] pipeline fetch (hard filters ON, parallel=4)" | tee -a "$LOG"
$PY -m pipeline fetch --parallel 4 >>"$LOG" 2>&1
rc=$?
tail -n 16 "$LOG" | sed -n '1,14p'
if [[ $rc -ne 0 ]]; then echo "PIPELINE FAILED rc=$rc — see $LOG" | tee -a "$LOG"; exit 1; fi

echo "[3/6] mirror to site/downloads" | tee -a "$LOG"
LATEST=$(ls -t download/jobs_fachinformatiker-systemintegration-erlangen-50km-14d_*.csv 2>/dev/null | grep -v _rejected | head -1)
if [[ -z "$LATEST" ]]; then echo "  no output CSV found — fetch produced nothing?" | tee -a "$LOG"; exit 1; fi
LATESTJ=${LATEST%.csv}.json
LATESTR=${LATEST%.csv}_rejected.csv
cp -f "$LATEST" "$LATESTJ" "$LATESTR" download/jobs_latest.csv download/jobs_latest.json \
   site/downloads/ 2>>"$LOG" || echo "  mirror copy failed" | tee -a "$LOG"

echo "[4/6] digest + monitoring" | tee -a "$LOG"
$PY -m pipeline digest >>"$LOG" 2>&1 || echo "  digest step failed (non-fatal)" | tee -a "$LOG"
if [[ -n "${HC_PING_URL:-}" ]]; then
  curl -fsS -m 10 --retry 2 "$HC_PING_URL" >>"$LOG" 2>&1 \
    || echo "  healthchecks ping FAILED" | tee -a "$LOG"
fi

# Task 21: keep download/ in the documented layout (daily/YYYY-MM-DD, reports, tracker)
echo "[5/6] organize downloads" | tee -a "$LOG"
python3 "$(dirname "$0")/organize_downloads.py" --quiet >>"$LOG" 2>&1 \
  || echo "  organize step failed (non-fatal; layout drifts until fixed)" | tee -a "$LOG"

echo "[6/6] done" | tee -a "$LOG"
echo "done: $LATEST (log: $LOG)" | tee -a "$LOG"
