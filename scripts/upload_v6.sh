#!/usr/bin/env bash
# Upload v6 bundle to 3 agent-friendly hosts in parallel, then report.
B=/home/z/my-project/backups/asha-jobtoolkit-20261014-v6.bundle
LOG=/home/z/my-project/data/upload_logs
UA="asha-jobtoolkit/1.0 (+git bundle backup)"
mkdir -p "$LOG"; rm -f "$LOG"/*.txt

echo "start $(date -u +%FT%TZ) bundle=$(stat -c%s "$B") bytes" > "$LOG/main.log"

# 1. x0.at — ~71d retention, 1024MiB cap
curl -sS -m 570 -A "$UA" -F "file=@$B" https://x0.at \
  -w '\nMETA http=%{http_code} time=%{time_total}s speed=%{speed_upload}B/s\n' \
  > "$LOG/x0at.txt" 2>&1 &
P1=$!

# 2. litterbox.catbox.moe — 72h, 1GB cap
curl -sS -m 570 -A "$UA" -F reqtype=fileupload -F time=72h -F "fileToUpload=@$B" \
  https://litterbox.catbox.moe/resources/internals/api.php \
  -w '\nMETA http=%{http_code} time=%{time_total}s speed=%{speed_upload}B/s\n' \
  > "$LOG/litterbox.txt" 2>&1 &
P2=$!

# 3. filebin.net — 6d retention
curl -sS -m 570 -A "$UA" -X POST -H "Content-Type: application/octet-stream" \
  --data-binary @"$B" \
  "https://filebin.net/ashajobtoolkit-v6/asha-jobtoolkit-20261014-v6.bundle" \
  -w '\nMETA http=%{http_code} time=%{time_total}s speed=%{speed_upload}B/s\n' \
  > "$LOG/filebin.txt" 2>&1 &
P3=$!

wait $P1 $P2 $P3
echo "all-done $(date -u +%FT%TZ)" >> "$LOG/main.log"
echo "=== x0at ==="; cat "$LOG/x0at.txt"
echo "=== litterbox ==="; cat "$LOG/litterbox.txt"
echo "=== filebin ==="; head -c 600 "$LOG/filebin.txt"
