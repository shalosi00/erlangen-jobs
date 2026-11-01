#!/usr/bin/env bash
# Verify round 2: x0.at full (http1.1 + resume), litterbox ranged, filebin 2-step cookies.
set -u
V=/tmp/v6verify; mkdir -p $V; rm -f $V/*
B=/home/z/my-project/backups/asha-jobtoolkit-20261014-v6.bundle
TARGET=cad0d21e3f2a9cc25b672d584a7dfe0f01ee2538e4eecbf30acd9ac0445953ef
UA="asha-jobtoolkit/1.0"
REF1MB=$(head -c 1048576 "$B" | sha256sum | cut -d' ' -f1)
echo "local: size=$(stat -c%s "$B") first1MB=$REF1MB"

# --- x0.at: fresh full download over HTTP/1.1 ---
curl -sS --http1.1 -m 400 -A "$UA" -o "$V/x0.bundle" \
  -w 'x0at: http=%{http_code} bytes=%{size_download} speed=%{speed_download}B/s\n' \
  https://x0.at/V9xX.bundle || echo "x0at: curl exit $?"
H=$(sha256sum "$V/x0.bundle" 2>/dev/null | cut -d' ' -f1)
[ "$H" = "$TARGET" ] && echo "x0at: HASH OK" || echo "x0at: HASH MISMATCH ($H)"

# --- litterbox: HEAD + ranged GET 1MB ---
echo "-- litterbox --"
curl -sSI -m 60 --http1.1 -A "$UA" https://litter.catbox.moe/rrubg4.bundle | head -6
curl -sS -m 120 --http1.1 -A "$UA" -r 0-1048575 -o "$V/lit1mb" \
  -w 'litterbox: range http=%{http_code} bytes=%{size_download}\n' https://litter.catbox.moe/rrubg4.bundle || echo "litterbox: curl exit $?"
H=$(sha256sum "$V/lit1mb" 2>/dev/null | cut -d' ' -f1)
[ "$H" = "$REF1MB" ] && echo "litterbox: 1MB-RANGE HASH OK" || echo "litterbox: 1MB-RANGE MISMATCH ($H)"

# --- filebin: two-step cookie download ---
echo "-- filebin --"
J="$V/fb.jar"
curl -sS -m 60 -A "$UA" -c "$J" -o /dev/null -w 'filebin step1: %{http_code}\n' \
  https://filebin.net/ashajobtoolkit-v6/asha-jobtoolkit-20261014-v6.bundle
curl -sSL -m 400 -A "$UA" -b "$J" -c "$J" -o "$V/fb.bundle" \
  -w 'filebin step2: http=%{http_code} type=%{content_type} bytes=%{size_download}\n' \
  https://filebin.net/ashajobtoolkit-v6/asha-jobtoolkit-20261014-v6.bundle || echo "filebin: curl exit $?"
H=$(sha256sum "$V/fb.bundle" 2>/dev/null | cut -d' ' -f1)
[ "$H" = "$TARGET" ] && echo "filebin: HASH OK" || echo "filebin: HASH MISMATCH ($H)"
echo "verify2-done"
