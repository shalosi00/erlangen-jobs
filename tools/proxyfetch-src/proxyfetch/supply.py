"""Supply stage: harvest public proxy lists and verify them against the target.

Two-stage funnel keeps the cold start fast:
  stage 1 -- liveness probe (example.com, marker-checked)
  stage 2 -- target-specific probe (recipe.verify on a 20 KB read)
Winner cache is re-verified first so warm starts skip harvesting entirely.

Probing runs on the configured engine (cfg.engine): aiohttp at high
concurrency by default (~2.5x faster than thread pools in back-to-back
benchmarks), with a transparent fallback to a stdlib thread pool when
aiohttp is unavailable or errors out. Engine semantics are identical --
only speed and dependencies differ.
"""
from __future__ import annotations

import concurrent.futures as cf
import random
import time
from dataclasses import dataclass
from typing import Callable

from . import asynchttp, net
from .config import Config
from .logutil import Logger
from .net import http_get, is_public_ipport
from .pool import ProxyPool

SOURCES = [
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
]

Verifier = Callable[[str], bool]


@dataclass
class ProbeSpec:
    """What a valid response looks like: GET url -> verifier(body) must hold.

    One spec describes a whole batch of probes, which lets the async engine
    fan out without a per-proxy callable.
    """
    url: str
    verifier: Verifier
    timeout: float
    read_limit: int


EXAMPLE_URL = "https://example.com/"


def stage1_spec(cfg: Config) -> ProbeSpec:
    """Stage-1 liveness probe definition."""
    return ProbeSpec(EXAMPLE_URL, lambda body: "Example Domain" in body,
                     cfg.stage1_timeout_s, 2000)


# ------------------------------------------------------------------ harvest
def harvest(logger: Logger, *, timeout: float = 20.0) -> list[str]:
    """Fetch all source lists in parallel; return deduped public candidates."""
    cands: set[str] = set()
    with cf.ThreadPoolExecutor(max_workers=len(SOURCES)) as ex:
        futs = {ex.submit(http_get, s, timeout=timeout, read_limit=5_000_000): s
                for s in SOURCES}
        for fut in cf.as_completed(futs, timeout=timeout + 30):
            src = futs[fut]
            tag = src.split("/")[4]
            try:
                found = {c for c in net.IPPORT_RE.findall(fut.result())
                         if is_public_ipport(c)}
                cands |= found
                logger.info(f"harvest {tag:<14} +{len(found)}")
            except Exception:
                logger.info(f"harvest {tag:<14} (source unreachable, skipped)")
    return sorted(cands)


# ------------------------------------------------------------------ probes
def _probe_threads(spec: ProbeSpec) -> Callable[[str], float | None]:
    """Wrap a spec into the per-proxy callable used by the thread pool."""
    def probe(proxy: str) -> float | None:
        t0 = time.time()
        try:
            body = http_get(spec.url, timeout=spec.timeout, proxy=proxy,
                            read_limit=spec.read_limit)
        except Exception:
            return None
        return round(time.time() - t0, 2) if spec.verifier(body) else None
    return probe


def run_check(cands: list[str], probe: Callable[[str], float | None],
              workers: int, logger: Logger, label: str
              ) -> list[tuple[str, float]]:
    """Run a probe across candidates concurrently, keeping order pairing."""
    out: list[tuple[str, float]] = []
    if not cands:
        return out
    with cf.ThreadPoolExecutor(max_workers=min(workers, max(1, len(cands)))) as ex:
        for cand, res in zip(cands, ex.map(probe, cands)):
            if res is not None:
                out.append((cand, res))
    logger.info(f"{label}: {len(out)}/{len(cands)} passed")
    return out


def check_batch(cands: list[str], spec: ProbeSpec, engine: str,
                concurrency: int, logger: Logger, label: str
                ) -> list[tuple[str, float]]:
    """Probe a batch against one spec with the configured engine.

    aiohttp is the default (fast) engine; any failure or missing install
    degrades transparently to the stdlib thread pool -- same results,
    same pairing, just slower.
    """
    if not cands:
        logger.info(f"{label}: 0/0 passed")
        return []
    if engine == "aiohttp" and asynchttp.available():
        try:
            out = asynchttp.check(cands, spec.url, timeout=spec.timeout,
                                  read_limit=spec.read_limit,
                                  verifier=spec.verifier,
                                  concurrency=concurrency,
                                  progress=logger.info)
            logger.info(f"{label}: {len(out)}/{len(cands)} passed "
                        f"(aiohttp x{concurrency})")
            return out
        except Exception as e:  # engine must never kill the run
            logger.warn(f"aiohttp engine error ({type(e).__name__}: {e}) "
                        "-- falling back to threads")
    elif engine == "aiohttp":
        logger.warn(f"aiohttp not installed -- using thread fallback "
                    f"({asynchttp.install_hint()} for the fast engine)")
    return run_check(cands, _probe_threads(spec), min(100, max(1, concurrency)),
                     logger, label)


# ------------------------------------------------------------------ supply
def supply(pool: ProxyPool, cfg: Config, spec: ProbeSpec, logger: Logger
           ) -> list[tuple[str, float]]:
    """Phase A: return [(proxy, latency)] verified against the target site."""
    winners: list[tuple[str, float]] = []

    cached = pool.cached_for_site(_site(cfg.url), fresh=cfg.fresh)
    if cached:
        logger.info(f"winner cache: re-verifying {len(cached)} cached proxy(ies) ...")
        winners = check_batch(cached, spec, cfg.engine, cfg.concurrency,
                              logger, "cache-reverify")
        if winners:
            return winners
        logger.info("cache stale (all expired) -- harvesting fresh")

    tested: set[str] = set()
    for rnd, sample_n in enumerate(cfg.harvest_samples, 1):
        if winners:
            break
        logger.info(f"round {rnd}: harvesting public proxy lists ...")
        cands = [c for c in harvest(logger) if c not in tested]
        if not cands:
            logger.warn("no candidates harvested (GitHub reachable?)")
            continue
        random.shuffle(cands)
        pick = cands[:sample_n]
        tested |= set(pick)
        alive = check_batch(pick, stage1_spec(cfg), cfg.engine,
                            cfg.concurrency, logger, "stage1-liveness")
        if not alive:
            continue
        alive.sort(key=lambda x: x[1])
        winners = check_batch([p for p, _ in alive[:120]], spec, cfg.engine,
                              cfg.concurrency, logger, "stage2-target")
        if winners:
            pool.record([p for p, _ in winners], site=_site(cfg.url),
                        target=cfg.name or _site(cfg.url), latency=dict(winners))
    return winners


def refresh(pool: ProxyPool, cfg: Config, spec: ProbeSpec, logger: Logger,
            exclude: set[str]) -> list[tuple[str, float]]:
    """Self-healing: harvest a fresh batch when the pool dies mid-run."""
    logger.warn("pool exhausted -- auto re-harvest for fresh proxies ...")
    cands = [c for c in harvest(logger) if c not in exclude]
    if not cands:
        logger.error("re-harvest returned nothing")
        return []
    random.shuffle(cands)
    alive = check_batch(cands[:cfg.refresh_sample], stage1_spec(cfg),
                        cfg.engine, cfg.concurrency, logger, "refresh-stage1")
    if not alive:
        return []
    alive.sort(key=lambda x: x[1])
    fresh = check_batch([p for p, _ in alive[:60]], spec, cfg.engine,
                        cfg.concurrency, logger, "refresh-stage2")
    if fresh:
        pool.record([p for p, _ in fresh], site=_site(cfg.url),
                    target=cfg.name or _site(cfg.url), latency=dict(fresh))
    return fresh


def _site(url: str) -> str:
    try:
        return net.host_of(url)
    except ValueError:
        return "unknown"
