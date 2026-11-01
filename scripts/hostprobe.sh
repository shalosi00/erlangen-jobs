#!/usr/bin/env bash
# Probe file hosts that historically accept curl/agent uploads (no JS, no account).
# Tests with a 32KB file. Records HTTP code + response snippet.
set -u
TD=$(mktemp -d)
SMALL="$TD/probe.bin"
head -c 32768 /dev/urandom > "$SMALL"
UA="asha-jobtoolkit/1.0 (+https://github.com/agent-backup)"
OUT=/home/z/my-project/data/backup_probe.txt
mkdir -p /home/z/my-project/data
: > "$OUT"

probe() {
  local name="$1"; shift
  local code resp
  resp=$( "$@" 2>"$TD/$name.err" )
  code=$?
  local http
  http=$(tail -n1 "$TD/$name.err" 2>/dev/null)
  printf '=== %s | exit=%s\n%s\n---\n' "$name" "$code" "$(echo "$resp" | head -c 300)" >> "$OUT"
  echo "[$name] exit=$code :: $(echo "$resp" | head -c 200)"
}

echo "== host probe $(date -u +%FT%TZ) ==" | tee -a "$OUT"

# 1. bashupload.com — PUT, 50GB, 3 days
probe bashupload curl -sS -m 45 --connect-timeout 8 -A "$UA" -T "$SMALL" https://bashupload.com/probe.bin

# 2. temp.sh — PUT, 4GB, 3 days
probe tempsh curl -sS -m 45 --connect-timeout 8 -A "$UA" -T "$SMALL" https://temp.sh/probe.bin

# 3. litterbox.catbox.moe — POST multipart, 1GB, 72h
probe litterbox curl -sS -m 45 --connect-timeout 8 -A "$UA" \
  -F reqtype=fileupload -F time=72h -F fileToUpload=@"$SMALL" \
  https://litterbox.catbox.moe/resources/internals/api.php

# 4. catbox.moe — POST multipart, 200MB, permanent
probe catbox curl -sS -m 45 --connect-timeout 8 -A "$UA" \
  -F reqtype=fileupload -F fileToUpload=@"$SMALL" \
  https://catbox.moe/user/api.php

# 5. 0x0.st — POST, 512MB, months
probe 0x0st curl -sS -m 45 --connect-timeout 8 -A "$UA" -F file=@"$SMALL" https://0x0.st

# 6. envs.sh — POST (0x0 fork), 512MB
probe envssh curl -sS -m 45 --connect-timeout 8 -A "$UA" -F file=@"$SMALL" https://envs.sh

# 7. ttm.sh — POST (0x0 fork), 256MB
probe ttmsh curl -sS -m 45 --connect-timeout 8 -A "$UA" -F file=@"$SMALL" https://ttm.sh

# 8. x0.at — POST
probe x0at curl -sS -m 45 --connect-timeout 8 -A "$UA" -F file=@"$SMALL" https://x0.at

# 9. filebin.net — PUT binary into random bin, 6 days
BIN="ashabk$(date +%s)"
probe filebin curl -sS -m 45 --connect-timeout 8 -A "$UA" -X POST \
  -H "Content-Type: application/octet-stream" --data-binary @"$SMALL" \
  "https://filebin.net/${BIN}/probe.bin"

# 10. pixeldrain — anonymous PUT API
probe pixeldrain curl -sS -m 45 --connect-timeout 8 -A "$UA" -T "$SMALL" \
  "https://pixeldrain.com/api/file/probe.bin"

# 11. oshi.at — POST form, 5GB
probe oshiat curl -sS -m 45 --connect-timeout 8 -A "$UA" -F f=@"$SMALL" https://oshi.at

# 12. transfer.sh — PUT (classic agent host, often dead)
probe transfersh curl -sS -m 45 --connect-timeout 8 -A "$UA" -T "$SMALL" https://transfer.sh/probe.bin

echo "== done $(date -u +%FT%TZ) ==" | tee -a "$OUT"
