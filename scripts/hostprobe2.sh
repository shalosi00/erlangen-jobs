#!/usr/bin/env bash
# Round 2: x0.at size limit, temp.sh correct syntax, catbox userhash, oshi -k, qu.ax, ufile.io, tmpsend
set -u
TD=$(mktemp -d)
SMALL="$TD/probe.bin"
MID="$TD/mid.bin"          # 12MB for x0.at limit test
head -c 32768 /dev/urandom > "$SMALL"
head -c 12582912 /dev/urandom > "$MID"
UA="asha-jobtoolkit/1.0 (+https://github.com/agent-backup)"
OUT=/home/z/my-project/data/backup_probe2.txt
: > "$OUT"

probe() {
  local name="$1"; shift
  local resp
  resp=$( "$@" 2>&1 )
  printf '=== %s\n%s\n---\n' "$name" "$(echo "$resp" | head -c 400)" >> "$OUT"
  echo "[$name] :: $(echo "$resp" | head -c 250)"
}

echo "== probe2 $(date -u +%FT%TZ) ==" | tee -a "$OUT"

# x0.at: fetch homepage to learn max size, then 12MB test
probe x0at-home curl -sS -m 20 -A "$UA" https://x0.at/ | head -c 1200
probe x0at-12MB curl -sS -m 90 -A "$UA" -F file=@"$MID" https://x0.at

# temp.sh correct syntax: PUT to root with trailing filename
probe tempsh-root curl -sS -m 45 --connect-timeout 8 -A "$UA" -T "$SMALL" https://temp.sh/

# catbox with empty userhash
probe catbox-uh curl -sS -m 45 --connect-timeout 8 -A "$UA" \
  -F reqtype=fileupload -F userhash= -F fileToUpload=@"$SMALL" \
  https://catbox.moe/user/api.php

# oshi.at with -k (cert verify failed in round 1)
probe oshi-k curl -sS -k -m 45 --connect-timeout 8 -A "$UA" -F f=@"$SMALL" https://oshi.at

# qu.ax (0x0-style, 1GB)
probe quax curl -sS -m 45 --connect-timeout 8 -A "$UA" \
  -F "files[]=@$SMALL" "https://qu.ax/upload.php?site=1"

# ufile.io anonymous API v1
probe ufile curl -sS -m 45 --connect-timeout 8 -A "$UA" \
  -F "file=@$SMALL" https://ufile.io/upload/v1

# tmpsend.com
probe tmpsend curl -sS -m 45 --connect-timeout 8 -A "$UA" -T "$SMALL" https://tmpsend.com/probe.bin

# litterbox again with 12MB to sanity-check bigger body + measure rough speed
probe litterbox-12MB curl -sS -m 120 --connect-timeout 8 -A "$UA" \
  -F reqtype=fileupload -F time=72h -F fileToUpload=@"$MID" \
  -w 'TIME=%{time_total}s SPEED=%{speed_upload}B/s' \
  https://litterbox.catbox.moe/resources/internals/api.php

echo "== done2 $(date -u +%FT%TZ) ==" | tee -a "$OUT"
