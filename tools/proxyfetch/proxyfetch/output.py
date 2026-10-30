"""Output writers: JSON/CSV artifacts and the human console table.

* JSON is written with ``ensure_ascii=False`` + indent 2 (agent-friendly).
* CSV defaults to semicolon + UTF-8 BOM so Excel opens it double-click clean.
* Writes are atomic (tmp + os.replace) -- interrupted runs leave no half files.
"""
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

from .logutil import Logger


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def _dynamic_columns(items: list[dict]) -> list[str]:
    """Ordered union of item keys -- for recipes without fixed columns."""
    cols: list[str] = []
    for it in items:
        for k in it:
            if k not in cols:
                cols.append(k)
    return cols


def write_outputs(items: list[dict], payload: dict, out_dir: Path | str,
                  name: str, recipe, delimiter: str = ";") -> dict[str, str]:
    """Write ``<name>_live_<date>.json`` and ``.csv``; return their paths."""
    out_dir = Path(out_dir)
    stamp = time.strftime("%Y-%m-%d")
    base = out_dir / f"{name}_live_{stamp}"

    doc = dict(payload)
    doc["items"] = items
    doc["count"] = len(items)
    _atomic_write(base.with_suffix(".json"),
                  json.dumps(doc, ensure_ascii=False, indent=2))

    columns = list(recipe.csv_columns) or _dynamic_columns(items)
    rows = _csv_rows(items, columns)
    buf = []
    import io
    sio = io.StringIO()
    w = csv.writer(sio, delimiter=delimiter)
    w.writerow(columns)
    w.writerows(rows)
    # UTF-8 BOM so Excel auto-detects the encoding.
    _atomic_write(base.with_suffix(".csv"), "\ufeff" + sio.getvalue())
    return {"json": str(base.with_suffix(".json")), "csv": str(base.with_suffix(".csv"))}


def _csv_rows(items: list[dict], columns) -> list[list]:
    rows = []
    for i, it in enumerate(items, 1):
        row = []
        for col in columns:
            if col == "rank":
                row.append(i)
            else:
                val = it.get(col, "")
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                row.append("" if val is None else val)
        rows.append(row)
    return rows


def print_table(items: list[dict], payload: dict, logger: Logger,
                limit: int = 10) -> None:
    """Console summary table (stdout channel of the logger is stderr; the
    table is intentionally part of the log stream so stdout stays clean)."""
    meta = payload.get("meta", {})
    logger.raw("=" * 74)
    logger.raw(f" RESULTS: {payload.get('count', len(items))} item(s) "
               f"| pages: {meta.get('pages_fetched', 0)} "
               f"| proxies used: {len(meta.get('proxies_used', []))} "
               f"| pool-refresh: {'yes' if meta.get('pool_refreshed') else 'no'}")
    if meta.get("browser_proof"):
        bp = meta["browser_proof"]
        logger.raw(f" browser proof: {bp.get('proxy')} | {str(bp.get('title'))[:50]}")
    logger.raw(f" TOP {min(limit, len(items))}:")
    for i, it in enumerate(items[:limit], 1):
        logger.raw(f"  {i:>2}. {recipe_row(it)}")
    logger.raw("=" * 74)


def recipe_row(item: dict) -> str:
    price = item.get("price_eur")
    if price is None and "km" not in item:
        # generic rendering for non-car items: show the first fields
        parts = []
        for k, v in item.items():
            if k in ("jsonld",):
                continue
            s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v or "")
            s = s.replace("\n", " ")
            if s:
                parts.append(f"{k}={s[:30]}")
            if len(parts) >= 4:
                break
        return " | ".join(parts) if parts else "(item)"
    price_s = f"EUR {price:,}" if isinstance(price, int) else "n/a"
    km = item.get("km")
    km_s = f"{km:,} km" if isinstance(km, int) else "n/a"
    title = f"{item.get('title', '')} {item.get('version', '')}".strip()[:38]
    city = (item.get("city") or "")[:18]
    year = (item.get("year") or "")[:6]
    return f"{price_s:>12} | {year:<6} | {km_s:>12} | {title} | {city}"
