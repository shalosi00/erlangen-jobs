#!/usr/bin/env bash
# setup.sh — one-shot bootstrap for erlangen-jobs (works on Linux/macOS, any directory).
#   1. creates a local virtualenv (.venv)
#   2. installs the 3 dependencies
#   3. runs the offline self-test (33 networking unit tests, no internet needed)
# Idempotent: safe to re-run any time.
set -e
cd "$(dirname "$0")"

echo "==> erlangen-jobs setup"
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found (need Python 3.9+)"; exit 1; }
PYV=$(python3 -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
echo "    python: $PYV"

if [ ! -d .venv ]; then
  echo "==> creating virtualenv .venv"
  python3 -m venv .venv
else
  echo "==> virtualenv .venv already present (reuse)"
fi

echo "==> installing dependencies (python-jobspy, pandas, requests)"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

echo "==> offline self-test (unit tests, no internet required)"
.venv/bin/python tests/test_net_resilience.py | tail -3

echo
echo "Setup OK. Next steps:"
echo "  .venv/bin/python scripts/erlangen_pipeline.py --sweep   # 1st run: scrape portals (never your IP)"
echo "  .venv/bin/python scripts/erlangen_pipeline.py --fetch-desc --parts 5"
echo "  or simply:  bash run.sh --sweep"
