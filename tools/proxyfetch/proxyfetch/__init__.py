"""proxyfetch -- self-healing free-proxy fetcher.

Library quick start::

    from proxyfetch import Config, run

    payload = run(Config(url="https://www.autoscout24.de/lst/dacia/jogger",
                         pages=3))
    print(payload["count"], payload["files"])

See AGENTS.md for the machine contract and README.md for the full manual.
"""
from __future__ import annotations

__version__ = "0.3.1"

from .config import Config
from .errors import (EXIT_ERROR, EXIT_INTERRUPTED, EXIT_NO_PROXIES,
                     EXIT_NO_RESULTS, EXIT_OK, EXIT_USAGE, ProxyFetchError)
from .logutil import Logger
from .pipeline import run

__all__ = [
    "Config", "run", "Logger", "ProxyFetchError",
    "EXIT_OK", "EXIT_NO_RESULTS", "EXIT_USAGE", "EXIT_NO_PROXIES",
    "EXIT_ERROR", "EXIT_INTERRUPTED",
    "__version__",
]
