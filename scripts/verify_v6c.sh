#!/usr/bin/env bash
# x0.at: resumable full download (server cuts ~37MB/attempt) then full hash.
# filebin: head+tail ranged hash probes.
set -u
V=/tmp/v6verify; B=/home/z/my-project/backups/asha-jobtoolkit-20261014-v6.bundle
TARGET=cad0d21e3f2a9cc25b672d584a7dfe0f01ee2538e4eecbf30acd9ac0445953ef
UA="asha-jobtoolkit/1.0"
SZ=174370824

echo "== x0.at resume loop =="
X="$V/x0.bundle"; rm -f "$X"
for i in 1 2 3 4 5 6 7 8; do
  have=$(stat -c%s "$X" 2>/dev/null || echo 0)
  [ "$have" -ge "$SZ" ] && break
  echo "iter $i: have=$have"
  curl -sS --http1.1 -m 150 -A "$UA" -C - -o "$X" https://x0.at/V9xX.bundle
  rc=$?
  echo "  curl rc=$rc now=$(stat -c%s "$X" 2>/dev/null || echo 0)"
  [ "$rc" = "0" ] && break
done
have=$(stat -c%s "$X" 2>/dev/null || echo 0)
echo "x0.at final size=$have / $SZ"
if [ "$have" = "$SZ" ]; then
  H=$(sha256sum "$X" | cut -d' ' -f1)
  [ "$H" = "$TARGET" ] && echo "x0at: FULL HASH OK" || echo "x0at: FULL HASH MISMATCH ($H)"
else
  echo "x0at: INCOMPLETE after loop"
fi

echo "== filebin head/tail probes =="
J="$V/fb2.jar"
curl -sS -m 30 -A "$UA" -c "$J" -o /dev/null https://filebin.net/ashajobtoolkit-v6/asha-jobtoolkit-20261014-v6.bundle
FBURL=https://filebin.net/ashajobtoolkit-v6/asha-jobtoolkit-20261014-v6.bundle
# head 1MB
curl -sSL -m 90 -A "$UA" -b "$J" -r 0-1048575 -o "$V/fbhead" -w 'fb head http=%{http_code} bytes=%{size_download}\n' "$FBURL"
head -c 1048576 "$B" | sha256sum; sha256sum "$V/fbhead"
# tail 1MB
T0=$((SZ-1048576))
curl -sSL -m 90 -A "$UA" -b "$J" -r ${T0}- -o "$V/fbtail" -w 'fb tail http=%{http_code} bytes=%{size_download}\n' "$FBURL"
tail -c 1048576 "$B" | sha256sum; sha256sum "$V/fbtail"
echo "done $(date -u +%FT%TZ)"
