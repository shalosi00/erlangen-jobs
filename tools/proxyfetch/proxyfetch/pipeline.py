"""Pipeline orchestrator: the whole show in one ``run()`` call.

Phase A SUPPLY   cached winners -> harvest -> 2-stage verify (+ self-heal)
Phase B COLLECT  per-request rotation across the live pool, browser
                 escalation for stubborn pages, one automatic re-harvest
Phase C PROOF    best-effort stealth-browser render via the best proxy
Phase D OUTPUT   JSON + CSV artifacts and a console table

Guarantees:
* SIGINT-safe: partial results are returned/saved, exit code 130.
* Budget-guarded: every network attempt checks the wall-clock deadline.
* Never leaves the winner cache corrupted (atomic writes in the pool).
"""
from __future__ import annotations

import json
import signal
import time
import urllib.error
from dataclasses import dataclass, field

from . import __version__, browser, output, recipes, supply
from .config import Config
from .errors import NoProxiesError, NoResultsError
from .logutil import Logger
from .net import host_of, page_url
from .pool import ProxyPool


@dataclass
class _Interrupt:
    """Tiny SIGINT latch shared across the run."""
    raised: bool = False

    def handler(self, signum, frame) -> None:
        self.raised = True


@dataclass
class RunResult:
    payload: dict
    items: list[dict] = field(default_factory=list)


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in name.lower()).strip("-")


def _run_name(cfg: Config) -> str:
    if cfg.name:
        return _slug(cfg.name)
    try:
        host = host_of(cfg.url)
    except ValueError:
        host = "target"
    return _slug(host.removeprefix("www."))


def run(cfg: Config, logger: Logger | None = None) -> dict:
    """Execute the full pipeline and return the machine payload.

    Raises ProxyFetchError subclasses for expected failures; the CLI maps
    them to exit codes. Library users may catch and inspect ``payload``.
    """
    cfg.validated().resolved()
    logger = logger or Logger(quiet=cfg.quiet, colors=not cfg.no_color,
                              json_lines=cfg.json_logs, log_file=cfg.log_file)
    t0 = time.time()
    deadline = t0 + cfg.budget_s
    interrupt = _Interrupt()
    prev_handler = None
    try:
        prev_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, interrupt.handler)
    except (ValueError, OSError):
        pass  # e.g. non-main thread

    try:
        return _run(cfg, logger, t0, deadline, interrupt)
    finally:
        if prev_handler is not None:
            try:
                signal.signal(signal.SIGINT, prev_handler)
            except (ValueError, OSError):
                pass


# ------------------------------------------------------------------ internals
def _direct_probe(cfg: Config, recipe, logger: Logger,
                  challenge_seen: dict | None = None) -> list[tuple[str, float]]:
    """One plain (proxy-free) fetch of page 1 before any proxy work.

    Returns [("direct", latency)] when the target answers AND the recipe
    verifies AND at least one item parses -- proxies are unnecessary.
    [] when blocked/unreachable/JS-walled; the proxy pool takes over and
    can self-heal back to proxies even if direct dies mid-run. Bot-challenge
    answers (AWS WAF, DataDome, ...) are sniffed from error bodies too and
    reported into ``challenge_seen`` so the run can fail with an honest
    explanation instead of a timeout spin.
    """
    from .net import http_get, page_url
    t0 = time.time()
    try:
        html = http_get(page_url(cfg.url, 1, cfg.page_template),
                        timeout=min(cfg.fetch_timeout_s, 20.0),
                        proxy=None, read_limit=cfg.full_read_bytes)
    except urllib.error.HTTPError as e:  # 4xx/5xx: sniff the error body
        try:
            body = e.read(cfg.full_read_bytes).decode("utf-8", "ignore")
        except Exception:
            body = ""
        kind = recipes.challenge_kind(body)
        if kind:
            if challenge_seen is not None:
                challenge_seen[kind] = challenge_seen.get(kind, 0) + 1
            logger.warn(f"direct fetch answered HTTP {e.code} with a "
                        f"bot-challenge page ({kind}) -- target is bot-protected")
        else:
            logger.info(f"direct fetch blocked/failed (HTTP {e.code}) "
                        "-- engaging proxy pool")
        return []
    except Exception as e:
        logger.info(f"direct fetch blocked/failed ({type(e).__name__}) "
                    "-- engaging proxy pool")
        return []
    if not (recipe.verify(html) and recipe.parse(html, cfg.url)):
        kind = recipes.challenge_kind(html)
        if kind:
            if challenge_seen is not None:
                challenge_seen[kind] = challenge_seen.get(kind, 0) + 1
            logger.warn(f"direct fetch answered with a bot-challenge page "
                        f"({kind}) -- this target is bot-protected")
        else:
            logger.info("direct fetch yielded no usable content -- "
                        "engaging proxy pool")
        return []
    return [("direct", round(time.time() - t0, 2))]


def _challenge_aware(verifier, seen: dict) -> callable:
    """Wrap a recipe verifier so stage2 counts bot-challenge pages it sees."""
    def check(body: str) -> bool:
        kind = recipes.challenge_kind(body)
        if kind:
            seen[kind] = seen.get(kind, 0) + 1
        return verifier(body)
    return check


def _run(cfg: Config, logger: Logger, t0: float, deadline: float,
         interrupt: _Interrupt) -> dict:
    recipe = recipes.resolve(cfg.recipe, cfg.url, css=cfg.css_selector,
                             fields=cfg.fields, json_key=cfg.json_key,
                             table_index=cfg.table_index, parser=cfg.parser)
    name = _run_name(cfg)
    site = host_of(cfg.url)
    pool = ProxyPool(cfg.state_dir, ttl_s=cfg.pool_ttl_s, max_fails=cfg.max_proxy_fails)
    state_dir = cfg.state_dir
    state_dir.mkdir(parents=True, exist_ok=True)

    logger.stage("SUPPLY", f"target={name} recipe={recipe.name} engine={cfg.engine}")
    if cfg.use_browser:
        avail = browser.engines(cfg.lightpanda_bin)
        if not any(avail.values()):
            logger.warn(browser.install_hint() + " (continuing without escalation)")
        else:
            logger.info("render engines: "
                        + " + ".join(k for k, on in avail.items() if on)
                        + f" (choice={cfg.browser_engine})")

    challenge_seen: dict[str, int] = {}
    spec = supply.ProbeSpec(url=cfg.url, verifier=_challenge_aware(
                                recipe.verify, challenge_seen),
                            timeout=cfg.supply_timeout_s,
                            read_limit=cfg.verify_read_bytes)

    # -- direct-first fast path: unblocked targets skip the proxy pool
    winners = None
    if cfg.direct_first:
        winners = _direct_probe(cfg, recipe, logger, challenge_seen)
    if not winners:
        winners = supply.supply(pool, cfg, spec, logger)
    if interrupt.raised:
        return _payload(cfg, recipe, name, [], t0, _meta(0, pool, False, None), interrupt=True)
    if not winners:
        if challenge_seen:
            kinds = ", ".join(f"{k} x{n}" for k, n in sorted(
                challenge_seen.items(), key=lambda kv: -kv[1]))
            raise NoProxiesError(hint=(
                f"the target is bot-protected: it answered {sum(challenge_seen.values())} "
                f"proxy requests with challenge pages ({kinds}). Free public proxies "
                f"cannot pass WAF interstitials -- use a residential proxy "
                f"(--proxy user:pass@host:port), a cleaner network, or scrape a "
                f"less-protected source."))
        raise NoProxiesError(hint="public proxy lists churn fast -- simply retry, "
                                  "optionally with --fresh; also check outbound internet")
    winners.sort(key=lambda w: w[1])
    live = [p for p, _ in winners]
    mode = "direct" if live == ["direct"] else "proxy"
    if mode == "direct":
        logger.success("direct connection works -- no proxies needed")
    else:
        logger.success(f"proxy pool ready: {len(live)} verified "
                       f"(best: {', '.join(live[:3])})")

    # ------------------------------------------------ Phase B: collect
    logger.stage("COLLECT", f"{cfg.pages} page(s) via {mode}")
    items, meta = _collect(cfg, recipe, pool, live, spec, deadline, interrupt, logger)
    used = sorted(pool.used)

    # ------------------------------------------------ Phase C: proof
    browser_proof = None
    if cfg.use_browser and items and time.time() < deadline and not interrupt.raised:
        logger.stage("PROOF", "stealth-browser render (best-effort)")
        proxy0 = live[0]
        proof = browser.browser_attempt(
            proxy0 if proxy0 != "direct" else None, cfg.url, recipe.name,
            headed=cfg.headed, watchdog_s=cfg.watchdog_s,
            locale=cfg.locale or recipe.locale,
            timezone=cfg.timezone or recipe.timezone, work_dir=state_dir,
            logger=logger, engine=cfg.browser_engine,
            lightpanda_bin=cfg.lightpanda_bin)
        if proof:
            browser_proof = {k: proof[k] for k in ("proxy", "title", "articles", "engine")}
            try:
                (state_dir / "last_success.html").write_text(proof["html"], encoding="utf-8")
            except OSError:
                pass
            logger.success(f"browser proof OK via {proof['proxy']} "
                           f"[{proof['engine']}] "
                           f"| {str(proof['title'])[:60]} | articles={proof['articles']}")
            if proof["proxy"] != "direct":
                pool.record([proof["proxy"]], site=site, target=name, browser_verified=True)
        else:
            logger.info("browser proof skipped/failed (results already collected -- non-fatal)")
    elif cfg.use_browser and not items:
        logger.debug("browser proof skipped: nothing collected")

    # ------------------------------------------------ Phase D: output
    meta = _meta(meta["pages_fetched"], pool, meta["refreshed"], browser_proof)
    meta["engine"] = cfg.engine
    meta["mode"] = "direct" if "direct" in live else "proxy"
    meta["proxies_used"] = used
    payload = _payload(cfg, recipe, name, items, t0, meta,
                       interrupt=interrupt.raised)

    if items:
        pool.record([p for p in used if p != "direct"], site=site, target=name)
        items = sorted(items, key=recipe.sort_key)
        payload["items"] = items
        payload["count"] = len(items)
        if cfg.save:
            files = output.write_outputs(items, payload, cfg.out_dir, name,
                                         recipe, cfg.csv_delimiter)
            payload["files"] = files
            logger.info(f"saved: {files['json']}")
            logger.info(f"       {files['csv']}")
        if not cfg.quiet and not cfg.json_mode:
            output.print_table(items, payload, logger)
    else:
        hint = ("the site may have changed layout, the filters may be too "
                "narrow, or the page is JS-only; try --recipe generic or "
                "more --pages")
        if challenge_seen:
            kinds = ", ".join(f"{k} x{n}" for k, n in sorted(
                challenge_seen.items(), key=lambda kv: -kv[1]))
            hint = ("target is bot-protected: challenge pages were served during "
                    f"the run ({kinds}). Free public proxies cannot pass WAF "
                    "interstitials -- use a residential proxy "
                    "(--proxy user:pass@host:port) or a less-protected source")
        raise NoResultsError(hint=hint)
    payload["ok"] = True
    logger.stage("DONE", f"{payload['count']} item(s) in {time.time() - t0:.0f}s")
    return payload


def _collect(cfg: Config, recipe, pool: ProxyPool, live: list[str],
             spec, deadline: float, interrupt: _Interrupt, logger: Logger):
    """Rotation engine: urllib per-request rotation -> browser escalation ->
    single self-heal re-harvest. Returns (items, meta)."""
    from . import browser as browser_mod
    from .net import http_get

    dead: set[str] = set()
    results: list[dict] = []
    seen: set = set()
    refreshed = False
    got_pages = 0
    min_items = max(recipe.min_items, 1)

    page = 1
    while page <= cfg.pages:
        if interrupt.raised or time.time() >= deadline:
            logger.warn("budget/interrupt reached -- returning what we have")
            break
        url = page_url(cfg.url, page, cfg.page_template)
        page_items: list[dict] | None = None

        # -- rotation across the live pool ("direct" = no proxy)
        for p in live:
            if interrupt.raised or time.time() >= deadline:
                break
            if p in dead or pool.is_dead(p):
                continue
            try:
                html = http_get(url, timeout=cfg.fetch_timeout_s,
                                proxy=None if p == "direct" else p,
                                read_limit=cfg.full_read_bytes)
            except Exception as e:
                logger.debug(f"page {page} via {p}: {type(e).__name__}")
                pool.mark(p, False)
                if pool.is_dead(p):
                    dead.add(p)
                    logger.info(f"rotation: benching {p} (repeated failures)")
                continue
            parsed = recipe.parse(html, url)
            if recipe.verify(html) and len(parsed) >= min_items:
                page_items = parsed
                pool.mark(p, True)
                logger.success(f"page {page}: {len(parsed)} item(s) via {p}")
                break
            logger.debug(f"page {page} via {p}: no usable payload")
            pool.mark(p, False)

        # -- browser escalation if urllib failed on this page
        if page_items is None and cfg.use_browser and (
                browser_mod.cloakbrowser_available()
                or browser_mod.lightpanda_available(cfg.lightpanda_bin)):
            for p in [x for x in live if x not in dead and not pool.is_dead(x)][:cfg.browser_escalation_proxies]:
                if interrupt.raised or time.time() >= deadline:
                    break
                proof = browser_mod.browser_attempt(
                    p if p != "direct" else None,
                    url, recipe.name, headed=False, watchdog_s=cfg.watchdog_s,
                    locale=cfg.locale or recipe.locale,
                    timezone=cfg.timezone or recipe.timezone,
                    work_dir=cfg.state_dir, logger=logger, quiet_fail=True,
                    engine=cfg.browser_engine,
                    lightpanda_bin=cfg.lightpanda_bin)
                if proof:
                    parsed = recipe.parse(proof["html"], url)
                    if len(parsed) >= min_items:
                        page_items = parsed
                        pool.mark(p, True)
                        logger.success(f"page {page}: {len(parsed)} item(s) "
                                       f"via BROWSER {p} [{proof['engine']}]")
                        break
                pool.mark(p, False)

        # -- last resort: one automatic pool refresh, then retry this page
        if page_items is None and not refreshed and time.time() < deadline and not interrupt.raised:
            refreshed = True
            fresh = supply.refresh(pool, cfg, spec, logger, exclude=dead | set(live))
            if fresh:
                live += [p for p, _ in fresh if p not in live]
                for p, _ in fresh:
                    dead.discard(p)
                page -= 1  # retry the same page with the fresh pool
                continue

        if page_items is not None:
            got_pages += 1
            for it in page_items:
                key = it.get("id") or it.get("url") or json.dumps(it, sort_keys=True)
                if key and key in seen:
                    continue
                seen.add(key)
                results.append(it)
            page += 1
        else:
            logger.warn(f"page {page}: all paths exhausted -- stopping here")
            break

    return results, {"pages_fetched": got_pages, "refreshed": refreshed}


def _meta(pages_fetched: int, pool: ProxyPool, refreshed: bool,
          browser_proof: dict | None) -> dict:
    return {
        "pages_fetched": pages_fetched,
        "proxies_used": [],
        "pool_refreshed": refreshed,
        "browser_proof": browser_proof,
        "pool_stats": pool.stats(),
    }


def _payload(cfg: Config, recipe, name: str, items: list[dict], t0: float,
             meta: dict, *, interrupt: bool) -> dict:
    return {
        "schema": "proxyfetch.result/v1",
        "tool": "proxyfetch",
        "version": __version__,
        "ok": False,  # flipped to True on success
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t0)) + "Z",
        "duration_s": round(time.time() - t0, 1),
        "target": {"name": name, "url": cfg.url, "recipe": recipe.name},
        "count": len(items),
        "items": items,
        "meta": meta,
        "files": None,
        "interrupted": interrupt,
        "error": None,
    }
