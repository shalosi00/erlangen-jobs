"""Stealth-browser escalation (optional CloakBrowser extra).

Each attempt runs in a *spawned, watchdog-killed* process so a hung browser
can never stall the pipeline. Communication happens exclusively through
proof files, and only plain strings cross the process boundary (no pickling
of recipes) -- that keeps this module robust in every launch mode
(`python -m`, installed console script, frozen builds).
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
from pathlib import Path

from .logutil import Logger

PROOF_JSON = "_proof.json"
PROOF_HTML = "_proof.html"


def cloakbrowser_available() -> bool:
    try:
        import cloakbrowser  # noqa: F401
        return True
    except Exception:
        return False


def install_hint() -> str:
    return ('stealth browser unavailable -- install the extra: '
            'pip install "proxyfetch[browser]" (package: cloakbrowser)')


def _worker(proxy: str | None, url: str, recipe_name: str, headed: bool,
            locale: str | None, timezone: str | None, work_dir: str) -> None:
    """Runs in a spawned process; writes proof files on success."""
    from .recipes import RECIPES, resolve  # imported lazily inside the child

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

        try:
            recipe = resolve(recipe_name, url)
        except Exception:
            recipe = RECIPES["generic"]  # custom/css recipes: generic proof
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


def browser_attempt(proxy: str, url: str, recipe_name: str, *,
                    headed: bool = False, watchdog_s: int = 110,
                    locale: str | None = None, timezone: str | None = None,
                    work_dir: Path | str, logger: Logger,
                    quiet_fail: bool = False) -> dict | None:
    """Render ``url`` through CloakBrowser via ``proxy``.

    Returns ``{"proxy","title","articles","html"}`` on verified success,
    else None. Never raises -- hangs are hard-killed by the watchdog.
    """
    work_dir = str(work_dir)
    for f in (PROOF_JSON, PROOF_HTML):
        try:
            os.remove(os.path.join(work_dir, f))
        except OSError:
            pass

    ctx = mp.get_context("spawn")
    proc = ctx.Process(target=_worker, args=(proxy, url, recipe_name, headed,
                                             locale, timezone, work_dir))
    proc.start()
    proc.join(watchdog_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        logger.warn(f"browser via {proxy}: HARD-TIMEOUT after {watchdog_s}s (killed)")
        return None
    try:
        with open(os.path.join(work_dir, PROOF_JSON), encoding="utf-8") as f:
            proof = json.load(f)
        with open(os.path.join(work_dir, PROOF_HTML), encoding="utf-8") as f:
            proof["html"] = f.read()
        return proof
    except Exception:
        if not quiet_fail:
            logger.debug(f"browser via {proxy}: no proof produced")
        return None


def proof_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
