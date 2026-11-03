"""Registry primitives (no submodule imports — avoids circular imports)."""
from __future__ import annotations

from pipeline import logutil
from pipeline.core import SourceError

log = logutil.get("sources")

SOURCES: dict = {}          # id -> callable(FetchCtx) -> list[Job]
GEO_SCOPE: dict = {}        # id -> "query" | "country"

def register(source_id: str, geo_scope: str = "country"):
    def deco(fn):
        SOURCES[source_id] = fn
        GEO_SCOPE[source_id] = geo_scope
        return fn
    return deco

def check_http(resp, source_id: str, url: str):
    """Uniform HTTP guard: raise SourceError with pinpoint info on non-200.

    Single choke point for HTTP failures across all sources: every non-200
    answer is logged (with the WAF suspicion flag) BEFORE the SourceError
    travels up, so the run log shows the full failure chain per source.
    """
    if resp.status_code != 200:
        waf = resp.status_code in (403, 429, 503) \
            or "cloudflare" in resp.headers.get("server", "").lower()
        kind = "waf" if waf else "http"
        snippet = (resp.text or "")[:160].replace("\n", " ")
        log.warning("[%s] HTTP %s from %s%s — body: %.120s",
                    source_id, resp.status_code, url,
                    " (WAF/bot-page suspected)" if waf else "", snippet)
        raise SourceError(kind, f"HTTP {resp.status_code} from {url}", resp.status_code, url, snippet)
