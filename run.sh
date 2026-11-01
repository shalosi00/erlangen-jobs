#!/usr/bin/env bash
# run.sh — convenience wrapper: forwards ALL arguments to the pipeline.
#   bash run.sh --sweep                      # first run: scrape portals, then merge+filter
#   bash run.sh --fetch-desc --parts 5       # full run incl. descriptions, 5 part files
#   bash run.sh --fresh-days 14              # custom parameters
# Uses .venv if it exists, otherwise the system python3.
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
exec "$PY" scripts/erlangen_pipeline.py "$@"
