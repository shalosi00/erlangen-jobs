#!/usr/bin/env bash
# Task 24: DAILY AUTOMATED JOB TASK — one scheduled entry point.
# Chain: atomicmail recover -> daily job pull -> per-job enrichment
#        (WHERE/WHEN/employer/contacts) -> daily summary -> email to skorry
# Scheduled daily 07:00 Atlantic/Reykjavik via platform cron (Task 24).
# Run manually anytime:  bash scripts/run_daily_task.sh [--quick]
#   --quick  skips the proxy re-validation (~4 min saved)
set -uo pipefail
cd "$(dirname "$0")/.."
PY=/home/z/.venv/bin/python
LOG=logs/daily_task_$(date +%Y%m%d-%H%M).log
mkdir -p logs data/enriched

exec 9>logs/.daily_task.lock
if ! flock -n 9; then
  echo "daily_task: another run in progress — aborting" | tee -a "$LOG"; exit 1
fi

echo "[1/6] atomicmail recover (pre-email ritual)" | tee -a "$LOG"
python3 scripts/atomicmail_recover.py >>"$LOG" 2>&1 \
  || echo "  recover failed (email may still work — continuing)" | tee -a "$LOG"

echo "[2/6] daily job pull" | tee -a "$LOG"
if [[ "${1:-}" == "--quick" ]]; then
  bash scripts/daily_jobpull.sh >>"$LOG" 2>&1
else
  bash scripts/daily_jobpull.sh --with-proxies >>"$LOG" 2>&1
fi
rc=$?
[[ $rc -ne 0 ]] && echo "  jobpull rc=$rc (continuing with existing corpus)" | tee -a "$LOG"

echo "[3/6] per-job enrichment (WHERE/WHEN/employer/contacts)" | tee -a "$LOG"
$PY scripts/enrich_jobs.py >>"$LOG" 2>&1 || echo "  enrich FAILED" | tee -a "$LOG"

echo "[4/6] daily summary" | tee -a "$LOG"
$PY scripts/daily_summary.py --enrich latest > logs/summary_latest.txt 2>&1 \
  || echo "  summary FAILED" | tee -a "$LOG"
head -40 logs/summary_latest.txt | tee -a "$LOG"

echo "[5/6] email briefing to skorry@atomicmail.io" | tee -a "$LOG"
SUMMARY_MD=$(ls -t download/daily/*/daily_summary_*.md 2>/dev/null | head -1)
ENRICH_CSV=$(ls -t data/enriched/jobs_enriched_*.csv 2>/dev/null | head -1)
GOLD_CSV=$(ls -t data/enriched/direct_employers_*.csv 2>/dev/null | head -1)
if [[ -x scripts/atomicmail_send_daily.py ]]; then
  python3 scripts/atomicmail_send_daily.py "$SUMMARY_MD" "$ENRICH_CSV" "$GOLD_CSV" >>"$LOG" 2>&1 \
    && echo "  email delivered" | tee -a "$LOG" \
    || echo "  email FAILED (see $LOG)" | tee -a "$LOG"
else
  echo "  atomicmail_send_daily.py missing — skip" | tee -a "$LOG"
fi

echo "[6/6] done" | tee -a "$LOG"
echo "daily task complete: $(date -u +%FT%TZ)" | tee -a "$LOG"
