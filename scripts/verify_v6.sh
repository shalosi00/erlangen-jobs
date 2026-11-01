#!/usr/bin/env bash
# Verify all 3 backup mirrors by re-downloading and hashing.
set -u
V=/tmp/v6verify; mkdir -p $V; rm -f $V/*
TARGET=cad0d21e3f2a9cc25b672d584a7dfe0f01ee2538e4eecbf30acd9ac0445953ef
UA="asha-jobtoolkit/1.0 (+git bundle backup)"

ver() {
  local name="$1" url="$2" extra="${3:-}"
  curl -sSL -m 400 -A "$UA" $extra -o "$V/$name.bundle" \
    -w "$name: http=%{http_code} type=%{content_type} bytes=%{size_download} speed=%{speed_download}B/s\n" "$url"
  local h; h=$(sha256sum "$V/$name.bundle" | cut -d' ' -f1)
  if [ "$h" = "$TARGET" ]; then echo "$name: HASH OK ($h)"; else echo "$name: HASH MISMATCH got=$h"; fi
  rm -f "$V/$name.bundle"
}

ver x0at "https://x0.at/V9xX.bundle" &
P1=$!
ver litterbox "https://litter.catbox.moe/rrubg4.bundle" &
P2=$!
ver filebin "https://filebin.net/ashajobtoolkit-v6/asha-jobtoolkit-20261014-v6.bundle" &
P3=$!
wait $P1 $P2 $P3
echo "verify-done $(date -u +%FT%TZ)"
