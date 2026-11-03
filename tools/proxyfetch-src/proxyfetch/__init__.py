"""proxyfetch -- self-healing free-proxy fetcher.

Library quick start::

    from proxyfetch import Config, run

    payload = run(Config(url="https://www.autoscout24.de/lst/dacia/jogger",
                         pages=3))
    print(payload["count"], payload["files"])

See AGENTS.md for the machine contract and README.md for the full manual.
"""
from __future__ import annotations

__version__ = "0.4.1"

from .config import Config
from .errors import (
                     EXIT_ERROR,
                     EXIT_INTERRUPTED,
                     EXIT_NO_PROXIES,
                     EXIT_NO_RESULTS,
                     EXIT_OK,
                     EXIT_USAGE,
                     ProxyFetchError,
)
from .logutil import Logger
from .pipeline import run

__all__ = [
                     "EXIT_ERROR",
                     "EXIT_INTERRUPTED",
                     "EXIT_NO_PROXIES",
                     "EXIT_NO_RESULTS",
                     "EXIT_OK",
                     "EXIT_USAGE",
                     "Config",
                     "Logger",
                     "ProxyFetchError",
                     "__version__",
                     "run",
]
