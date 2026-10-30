"""Persistent user preferences -- set once, remembered by every future run.

Stored at ``<state_dir>/config.json`` (default ``~/.proxyfetch/config.json``),
written atomically (tmp + rename) and validated on the way in. Managed via
the CLI::

    proxyfetch config set engine aiohttp
    proxyfetch config get engine
    proxyfetch config list
    proxyfetch config unset engine

Resolution order for configurable settings:
CLI flag > environment (``PROXYFETCH_ENGINE``, ``PROXYFETCH_CONCURRENCY``) >
this file > built-in default. A corrupt file never crashes the tool: it is
quarantined as ``config.json.corrupt`` and defaults apply.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from . import errors

FILENAME = "config.json"

_SPEC: dict[str, tuple[Callable[[Any], Any], str, str]] = {
    # key: (normalizer, description, default-as-text)
    "engine": (
        lambda v: _choice(v, ("aiohttp", "threads")),
        "proxy-check engine: aiohttp (fast, default) or threads (stdlib)",
        "aiohttp",
    ),
    "concurrency": (
        lambda v: _bounded_int(v, 1, 2000),
        "max parallel probes (aiohttp cap; threads use min(100, this))",
        "300",
    ),
}


def _choice(v: Any, allowed: tuple[str, ...]) -> str:
    s = str(v).strip().lower()
    if s not in allowed:
        raise errors.ConfigError(
            f"invalid value {v!r} -- expected one of: {', '.join(allowed)}",
            hint="e.g. proxyfetch config set engine aiohttp")
    return s


def _bounded_int(v: Any, lo: int, hi: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise errors.ConfigError(f"invalid value {v!r} -- expected an integer")
    if not (lo <= n <= hi):
        raise errors.ConfigError(f"invalid value {v!r} -- expected {lo}..{hi}")
    return n


# ------------------------------------------------------------------ paths
def path(state_dir: Path | None = None) -> Path:
    if state_dir is None:
        from .config import default_state_dir
        state_dir = default_state_dir()
    return Path(state_dir).expanduser() / FILENAME


# ------------------------------------------------------------------ io
def load(state_dir: Path | None = None) -> dict:
    """Saved settings as a dict ({} when absent; corrupt files quarantined)."""
    p = path(state_dir)
    try:
        return {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items()
                if k in _SPEC}
    except FileNotFoundError:
        return {}
    except Exception:
        try:  # quarantine so the user can inspect what was there
            p.replace(p.with_suffix(".json.corrupt"))
        except OSError:
            pass
        return {}


def _save(values: dict, state_dir: Path | None) -> None:
    p = path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    os.replace(tmp, p)


# ------------------------------------------------------------------ api
def keys() -> tuple[str, ...]:
    return tuple(sorted(_SPEC))


def describe(key: str) -> str:
    return _SPEC[key][1]


def default_of(key: str) -> str:
    return _SPEC[key][2]


def defaults() -> dict:
    """Built-in defaults with proper types (JSON-safe)."""
    return {k: _SPEC[k][0](_SPEC[k][2]) for k in _SPEC}


def validate(key: str, value: Any) -> Any:
    """Normalize ``value`` for ``key``; raise ConfigError when invalid."""
    if key not in _SPEC:
        raise errors.ConfigError(
            f"unknown setting {key!r} -- available: {', '.join(keys())}",
            hint="proxyfetch config list shows what can be set")
    return _SPEC[key][0](value)


def set_value(key: str, value: Any, state_dir: Path | None = None) -> Any:
    """Persist one setting (set once, remembered). Returns the saved value."""
    saved = validate(key, value)
    values = load(state_dir)
    values[key] = saved
    _save(values, state_dir)
    return saved


def unset_value(key: str, state_dir: Path | None = None) -> None:
    """Remove one setting; the built-in default applies again."""
    if key not in _SPEC:
        raise errors.ConfigError(
            f"unknown setting {key!r} -- available: {', '.join(keys())}")
    values = load(state_dir)
    values.pop(key, None)
    _save(values, state_dir)
