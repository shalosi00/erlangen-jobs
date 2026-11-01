"""Run configuration: one dataclass consumed by every stage.

CLI flags are the primary source; environment variables provide agent- and
CI-friendly overrides (prefix ``PROXYFETCH_``).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import errors

ENV_PREFIX = "PROXYFETCH_"


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(ENV_PREFIX + name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(ENV_PREFIX + name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise errors.ConfigError(
            f"environment variable {ENV_PREFIX + name}={raw!r} is not an integer")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(ENV_PREFIX + name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def default_state_dir() -> Path:
    """Winner-cache location: $PROXYFETCH_STATE_DIR or ~/.proxyfetch."""
    env = os.environ.get(ENV_PREFIX + "STATE_DIR")
    return Path(env).expanduser() if env else Path.home() / ".proxyfetch"


@dataclass
class Config:
    """Full pipeline configuration with battle-tested defaults."""

    # -- target ---------------------------------------------------------
    url: str = ""
    pages: int = 3
    name: str | None = None            # run name (output files); derived from host if None
    recipe: str = "auto"               # auto | generic | autoscout24

    # -- universal extraction (scrape ANY site) ---------------------------
    css_selector: str | None = None    # item selector -> css recipe
    fields: dict | None = None         # name -> CSS sub-selector (::text/::attr)
    json_key: str | None = None        # dot-path to items array in JSON responses
    table_index: int | None = None     # 1-based HTML table number (0/None = largest)
    page_template: str | None = None   # pagination with {n}, e.g. .../page-{n}.html
    parser: object | None = None       # custom callable(html, url) -> items (library mode)

    # -- direct-first fast path -------------------------------------------
    # Try a plain (proxy-free) fetch first; only engage the proxy pool when
    # the target blocks or the content does not verify. Disable with
    # --no-direct / $PROXYFETCH_NO_DIRECT for always-proxy behavior.
    direct_first: bool = True

    # -- output ---------------------------------------------------------
    out_dir: Path = field(default_factory=lambda: Path(_env("OUT", "out")))
    save: bool = True
    csv_delimiter: str = ";"

    # -- proxy supply ---------------------------------------------------
    fresh: bool = False                # ignore cached winners
    state_dir: Path = field(default_factory=default_state_dir)
    pool_ttl_s: int = 3 * 3600         # winner cache TTL
    harvest_samples: tuple[int, ...] = (350, 550)
    refresh_sample: int = 300
    stage1_workers: int = 100
    stage2_workers: int = 25
    supply_timeout_s: float = 25.0     # stage-2 (target) probe timeout
    stage1_timeout_s: float = 9.0      # liveness probe timeout

    # -- probe engine -----------------------------------------------------
    # Default engine is aiohttp (~2.5x faster than threads, see
    # asynchttp.py). Persistent via `proxyfetch config set engine ...`;
    # CLI --engine / $PROXYFETCH_ENGINE override for a single run.
    engine: str = "aiohttp"           # aiohttp | threads
    concurrency: int = 300            # parallel probe cap

    # -- collect --------------------------------------------------------
    fetch_timeout_s: float = 40.0      # per page fetch through a proxy
    full_read_bytes: int = 2_500_000
    verify_read_bytes: int = 20_000    # stage-2 probe reads only 20 KB (speed)
    max_proxy_fails: int = 2           # strikes before a proxy is benched

    # -- browser escalation ----------------------------------------------
    use_browser: bool = True
    browser_engine: str = "auto"       # auto | lightpanda | cloakbrowser
    lightpanda_bin: str | None = None  # explicit binary path (else autodetect)
    headed: bool = False
    watchdog_s: int = 110              # hard kill per browser attempt
    browser_escalation_proxies: int = 3
    locale: str | None = None          # recipe provides defaults when None
    timezone: str | None = None

    # -- budget / behavior ------------------------------------------------
    budget_s: int = field(default_factory=lambda: _env_int("BUDGET", 420))
    json_mode: bool = False            # agent mode: single JSON payload on stdout
    quiet: bool = False
    no_color: bool = False
    json_logs: bool = False            # NDJSON logs on stderr
    log_file: str | None = None
    debug: bool = False

    # ------------------------------------------------------------------ #
    def validated(self) -> "Config":
        """Fail fast on nonsensical values with actionable messages."""
        if not self.url:
            raise errors.ConfigError(
                "no target URL given",
                hint='pass a URL: proxyfetch "https://example.com/page"')
        if self.pages < 1:
            raise errors.ConfigError(f"--pages must be >= 1 (got {self.pages})")
        if self.budget_s < 30:
            raise errors.ConfigError(
                f"--budget must be >= 30s (got {self.budget_s}s); the supply "
                "stage alone often needs 60-120s on a cold cache")
        if self.engine not in ("aiohttp", "threads"):
            raise errors.ConfigError(
                f"engine must be 'aiohttp' or 'threads' (got {self.engine!r})",
                hint="proxyfetch config set engine aiohttp")
        if self.browser_engine not in ("auto", "lightpanda", "cloakbrowser"):
            raise errors.ConfigError(
                f"browser_engine must be auto|lightpanda|cloakbrowser "
                f"(got {self.browser_engine!r})")
        if self.concurrency < 1:
            raise errors.ConfigError(
                f"--concurrency must be >= 1 (got {self.concurrency})")
        if self.page_template and "{n}" not in self.page_template:
            raise errors.ConfigError(
                f"--page-template must contain '{{n}}' (got {self.page_template!r})",
                hint='e.g. "https://x.com/list/page-{n}.html"')
        if sum(bool(x) for x in (self.css_selector, self.json_key,
                                 self.table_index is not None)) > 1:
            raise errors.ConfigError(
                "--css, --json-key and --table are mutually exclusive",
                hint="pick one extraction mode per run")
        return self

    def resolved(self) -> "Config":
        """Post-parse normalization (URL scheme, paths)."""
        from .net import normalize_url
        self.url = normalize_url(self.url)
        self.out_dir = Path(self.out_dir).expanduser()
        self.state_dir = Path(self.state_dir).expanduser()
        return self

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe view of the interesting fields (for run payloads)."""
        return {
            "url": self.url,
            "pages": self.pages,
            "recipe": self.recipe,
            "budget_s": self.budget_s,
            "fresh": self.fresh,
            "engine": self.engine,
            "concurrency": self.concurrency,
            "direct_first": self.direct_first,
            "use_browser": self.use_browser,
            "browser_engine": self.browser_engine,
            "headed": self.headed,
            "state_dir": str(self.state_dir),
            "out_dir": str(self.out_dir),
        }
