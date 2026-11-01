"""Registry primitives (no submodule imports — avoids circular imports)."""
from __future__ import annotations
from pipeline.core import SourceError

SOURCES: dict = {}          # id -> callable(FetchCtx) -> list[Job]
GEO_SCOPE: dict = {}        # id -> "query" | "country"

def register(source_id: str, geo_scope: str = "country"):
    def deco(fn):
        SOURCES[source_id] = fn
        GEO_SCOPE[source_id] = geo_scope
        return fn
    return deco

def check_http(resp, source_id: str, url: str):
    """Uniform HTTP guard: raise SourceError with pinpoint info on non-200."""
    if resp.status_code != 200:
        kind = "waf" if resp.status_code in (403, 429, 503) or "cloudflare" in resp.headers.get("server", "").lower() else "http"
        snippet = (resp.text or "")[:160].replace("\n", " ")
        raise SourceError(kind, f"HTTP {resp.status_code} from {url}", resp.status_code, url, snippet)
