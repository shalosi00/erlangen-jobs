"""Transit whitelist (F1, project-review 2026-10-14) — single source of truth for
the "0-transfer train from Erlangen, <= 60 min scheduled" rule.

Replaces the hand-typed NEAR_RX that contradicted the verified GTFS analysis in
both directions (accepted 1-transfer towns like Neumarkt/Feucht/Altdorf/Zirndorf,
missed ~20 whitelisted ones like Coburg 47min/Lichtenfels/Haßfurt).

Data: data/geo/transit_whitelist.json — transcribed from research/2-e/findings.md
§3.1 (29 municipalities + Erlangen, VGN GTFS 2026-06-24), §3.2 borderline
(61-65 min), §3.3 explicit exclusions. Regexes are GENERATED from the data at
import time — umlaut-tolerant (ü/u/ue, ö/oe, ß/ss), separator-flexible.

transit classifier values (column `transit` on every kept row):
  "0-xfer (NNmin)"    regular direct train, whitelisted
  "limited (NNmin)"   direct but IC61-only, ~2-4 trips/day (Kronach, Ansbach)
  "borderline (NNmin)" 61-65 min (Küps, Hersbruck, ...) — include only if cutoff softens
  "1-xfer"            verified 1-transfer (S2/S3 branches, Würzburg axis, ...)
  "none"              verified no rail (Herzogenaurach, Gräfenberg branch, ...)
  ">60min"            direct but fails the 60-min cutoff (Rödental, Sonneberg, ...)
  ""                  not in the verified data either way (unverified)

Hard filter (country-scoped sources only): keep rows whose location matches the
REGULAR 0-transfer set. Query/radius-scoped sources (BA/EURES/XING/kimeta/...)
keep every row — their server-side radius already bounds geography — and the
transit column makes the 1-transfer noise filterable/sortable for Asha.
"""
from __future__ import annotations
import json, re
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "geo" / "transit_whitelist.json"

_CACHE = None


def _frag(name: str) -> str:
    """Umlaut-tolerant, separator-flexible regex fragment for a place name."""
    out = []
    for ch in name.lower():
        if ch == "ü":
            out.append(r"(u|ü|ue)")
        elif ch == "ö":
            out.append(r"(o|ö|oe)")
        elif ch == "ä":
            out.append(r"(a|ä|ae)")
        elif ch == "ß":
            out.append(r"(ß|ss)")
        elif ch.isalnum():
            out.append(re.escape(ch))
        else:                       # dots, spaces, hyphens -> flexible separator
            prev = out[-1] if out else ""
            if not prev.endswith("*"):
                out.append(r"[\s.\-]*")
    frag = "".join(out)
    return frag or re.escape(name.lower())


def _rx_for(entry: dict) -> "re.Pattern":
    names = [entry["name"]] + entry.get("aliases", [])
    return re.compile(r"(?i)\b(?:%s)\b" % "|".join(_frag(n) for n in names))


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for section in ("whitelist", "borderline", "excluded_1xfer",
                        "excluded_no_rail", "excluded_far"):
            for e in raw[section]:
                e["_rx"] = _rx_for(e)
        raw["origin"]["_rx"] = _rx_for({"name": raw["origin"]["name"]})
        _CACHE = raw
    return _CACHE


def _plz_hit(entry: dict, plz: str) -> bool:
    return bool(plz) and any(plz.startswith(p) for p in entry.get("plz_prefixes", []))


def transit_for(blob: str, plz: str = "") -> str:
    """Classify a location blob (city + location_raw + title [+desc]) into a
    transit label. First verified match wins.

    Evaluation order matters: borderline/excluded entries are checked BEFORE
    the whitelist because their names CONTAIN whitelist names ("Coburg Nord"
    contains Coburg, "Altdorf bei Nürnberg" contains Nürnberg, "Neustadt
    b.Coburg" contains Coburg) — the more specific verdict must win. The
    no-rail list runs after the whitelist so district-station aliases
    ("Höchstadt-Marktzeuln") classify as 0-xfer while the bare ambiguous
    name ("Höchstadt") falls through to its verified no-rail default."""
    data = _load()
    blob = blob or ""
    origin = data["origin"]
    if origin["_rx"].search(blob) or _plz_hit(origin, plz):
        return "0-xfer (0min)"
    for e in data["borderline"]:
        if e["_rx"].search(blob):
            return f"borderline ({e['minutes']}min)"
    for e in data["excluded_1xfer"]:
        if e["_rx"].search(blob):
            return "1-xfer"
    for e in data["excluded_far"]:
        if e["_rx"].search(blob):
            return ">60min"
    for e in data["whitelist"]:
        limited = "limited" if e.get("limited") else "0-xfer"
        if e["_rx"].search(blob) or _plz_hit(e, plz):
            return f"{limited} ({e['minutes']}min)"
    for e in data["excluded_no_rail"]:
        if e["_rx"].search(blob):
            return "none"
    return ""


def classify_job_location(j) -> str:
    """Transit label for a Job: strict blob (city/location/title + PLZ) first,
    then wide blob (includes description, the old geo_keep signal) as fallback."""
    strict = f"{j.city} {j.location_raw} {j.title}"
    t = transit_for(strict, getattr(j, "plz", ""))
    if t:
        return t
    wide = f"{j.city} {j.location_raw} {(j.description or '')[:1500]} {j.title}"
    return transit_for(wide, getattr(j, "plz", ""))


def zero_xfer_rx() -> "re.Pattern":
    """Hard-filter regex: ONLY regular 0-transfer municipalities (limited
    IC61-only towns and 61-65min borderline towns deliberately excluded —
    they arrive via radius-scoped sources and stay filterable via `transit`)."""
    data = _load()
    frags = [_frag(data["origin"]["name"])]
    for e in data["whitelist"]:
        if not e.get("limited"):
            frags.extend(_frag(n) for n in [e["name"]] + e.get("aliases", []))
    return re.compile(r"(?i)\b(?:%s)\b" % "|".join(frags))
