"""Render engines for browser escalation and proof renders.

Engine chain (per attempt, ``engine="auto"``):

  1. **Lightpanda** — a ~35 MB headless browser speaking CDP
     (``proxyfetch.lightpanda``). Servers start on demand, one per
     (proxy, locale, timezone), route their HTTP through ``--http-proxy``
     when a proxy is given, are health-checked before every render and
     restarted when they die. Renders happen over a raw CDP WebSocket;
     cookie-consent walls are auto-accepted and JS dialogs auto-dismissed.
     Always headless — skipped when ``headed=True``.
  2. **CloakBrowser** — optional extra (``pip install "proxyfetch[browser]"``).
     Each attempt runs in a *spawned, watchdog-killed* process so a hung
     browser can never stall the pipeline. Communication happens exclusively
     through proof files, and only plain strings cross the process boundary
     (no pickling of recipes) -- robust in every launch mode.

Failures return ``None`` and never raise; callers fall back or fail
honestly. Proof dicts gain ``"engine"``: ``"lightpanda"`` | ``"cloakbrowser"``.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
from pathlib import Path

from . import lightpanda as _lp
from .logutil import Logger

PROOF_JSON = "_proof.json"
PROOF_HTML = "_proof.html"

ENGINES = ("auto", "lightpanda", "cloakbrowser")


# --------------------------------------------------------------------------
# availability
# --------------------------------------------------------------------------
def cloakbrowser_available() -> bool:
    try:
        import cloakbrowser  # noqa: F401
        return True
    except Exception:
        return False


def lightpanda_available(binary: str | None = None) -> bool:
    return _lp.lightpanda_available(binary)


def engines(binary: str | None = None) -> dict:
    """Which engines can render right now (for logs and payloads)."""
    return {"lightpanda": lightpanda_available(binary),
            "cloakbrowser": cloakbrowser_available()}


def install_hint() -> str:
    return ('no render engine available -- install lightpanda '
            '(one binary from lightpanda.com / GitHub releases; '
            'proxyfetch finds it on $PATH, $LIGHTPANDA_BIN or common paths) '
            'and/or the stealth-browser extra: '
            'pip install "proxyfetch[browser]" (package: cloakbrowser)')


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------
def _resolve_recipe(recipe_name: str, url: str):
    """Recipe for verification; unknown names (css/custom) fall back to
    the generic recipe so a proof is still content-checked."""
    from .recipes import RECIPES, resolve  # imported lazily (spawn-safe)
    try:
        return resolve(recipe_name, url)
    except Exception:
        return RECIPES["generic"]


def _count_articles(html: str, recipe) -> int:
    if not recipe.article_selector:
        return 0
    try:
        from bs4 import BeautifulSoup
        return len(BeautifulSoup(html, "html.parser")
                   .select(recipe.article_selector))
    except Exception:
        return 0


# --------------------------------------------------------------------------
# engine 1: Lightpanda
# --------------------------------------------------------------------------
def lightpanda_attempt(proxy: str | None, url: str, recipe,
                       *, locale: str | None, timezone: str | None,
                       watchdog_s: int, binary: str | None = None,
                       logger: Logger | None = None,
                       quiet_fail: bool = False) -> dict | None:
    """Render ``url`` on a self-healing Lightpanda server (started through
    ``proxy`` when given). Returns a proof dict or None."""
    endpoint = _lp.ensure_server(
        proxy=None if proxy in (None, "", "direct") else proxy,
        locale=locale, timezone=timezone, binary=binary)
    if not endpoint:
        return None
    t0 = time.time()
    out = _lp.render(url, endpoint, timeout_s=min(watchdog_s, 60.0))
    if not out:
        if not quiet_fail:
            (logger.debug if logger else (lambda m: None))(
                f"lightpanda via {proxy or 'direct'}: no render "
                f"({time.time() - t0:.1f}s)")
        return None
    html, title = out["html"], out["title"]
    if not recipe.verify(html):
        if not quiet_fail:
            (logger.debug if logger else (lambda m: None))(
                f"lightpanda via {proxy or 'direct'}: rendered content "
                "failed recipe verification")
        return None
    articles = _count_articles(html, recipe)
    if recipe.min_articles and articles < recipe.min_articles:
        return None
    return {"proxy": proxy or "direct", "title": title, "articles": articles,
            "html": html, "engine": "lightpanda"}


# --------------------------------------------------------------------------
# engine 2: CloakBrowser (unchanged spawn/watchdog logic)
# --------------------------------------------------------------------------
def _worker(proxy: str | None, url: str, recipe_name: str, headed: bool,
            locale: str | None, timezone: str | None, work_dir: str) -> None:
    """Runs in a spawned process; writes proof files on success."""
    browser = None
    try:
        from cloakbrowser import launch
        kwargs: dict = {
            "headless": not headed,
            "humanize": True,
        }
        if proxy:  # None / "direct" = render without a proxy
            kwargs["proxy"] = proxy if "://" in proxy else f"http://{proxy}"
        if locale:
            kwargs["locale"] = locale
        if timezone:
            kwargs["timezone"] = timezone
        browser = launch(**kwargs)
        page = browser.new_page()
        page.goto(url, timeout=60000, wait_until="domcontentloaded")

        recipe = _resolve_recipe(recipe_name, url)
        proof = None
        for _ in range(4):  # 20s window: interstitials / late JS payloads
            page.wait_for_timeout(5000)
            html = page.content()
            articles = len(page.query_selector_all(recipe.article_selector)) \
                if recipe.article_selector else 0
            if recipe.verify(html) and (recipe.min_articles == 0
                                        or articles >= recipe.min_articles):
                proof = {"proxy": proxy or "direct", "title": page.title(),
                         "articles": articles}
                with open(os.path.join(work_dir, PROOF_HTML), "w",
                          encoding="utf-8") as f:
                    f.write(html)
                break
        if proof:
            with open(os.path.join(work_dir, PROOF_JSON), "w",
                      encoding="utf-8") as f:
                json.dump(proof, f)
    except Exception:
        pass
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# public entry point
# --------------------------------------------------------------------------
def browser_attempt(proxy: str, url: str, recipe_name: str, *,
                    headed: bool = False, watchdog_s: int = 110,
                    locale: str | None = None, timezone: str | None = None,
                    work_dir: Path | str, logger: Logger,
                    quiet_fail: bool = False,
                    engine: str = "auto",
                    lightpanda_bin: str | None = None) -> dict | None:
    """Render ``url`` through the engine chain.

    Returns ``{"proxy","title","articles","html","engine"}`` on verified
    success, else None. Never raises -- hangs are hard-killed (watchdog for
    cloakbrowser, bounded socket timeouts for lightpanda).
    """
    if engine not in ENGINES:
        engine = "auto"
    recipe = _resolve_recipe(recipe_name, url)

    # -- engine 1: lightpanda (headless only, never for --headed) ----------
    if engine in ("auto", "lightpanda") and not headed:
        proof = lightpanda_attempt(
            proxy, url, recipe, locale=locale, timezone=timezone,
            watchdog_s=watchdog_s, binary=lightpanda_bin,
            logger=logger, quiet_fail=quiet_fail)
        if proof:
            return proof

    # -- engine 2: cloakbrowser (spawned, watchdog-killed) ------------------
    if engine in ("auto", "cloakbrowser") and cloakbrowser_available():
        work_dir = str(work_dir)
        for f in (PROOF_JSON, PROOF_HTML):
            try:
                os.remove(os.path.join(work_dir, f))
            except OSError:
                pass
        ctx = mp.get_context("spawn")
        proc = ctx.Process(target=_worker, args=(proxy, url, recipe_name,
                                                 headed, locale, timezone,
                                                 work_dir))
        proc.start()
        proc.join(watchdog_s)
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            logger.warn(f"browser via {proxy}: HARD-TIMEOUT after {watchdog_s}s "
                        "(killed)")
            return None
        try:
            with open(os.path.join(work_dir, PROOF_JSON), encoding="utf-8") as f:
                proof = json.load(f)
            with open(os.path.join(work_dir, PROOF_HTML), encoding="utf-8") as f:
                proof["html"] = f.read()
            proof["engine"] = "cloakbrowser"
            return proof
        except Exception:
            if not quiet_fail:
                logger.debug(f"browser via {proxy}: no proof produced")
            return None
    return None


def proof_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
