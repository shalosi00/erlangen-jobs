"""Leveled, timestamped, crash-capturing logging for the whole pipeline.

Zero new dependencies: built on stdlib ``logging``.

Design (the "spot bugs easily" contract):
* **File channel**  ``logs/pipeline_run_<ts>.log`` at DEBUG level, always --
  every run leaves a complete forensic record: per-source tracebacks,
  proxy rotations, filter decisions, timings.
* **Console channel** stderr at INFO (DEBUG with ``-v``, WARNING with
  ``--quiet``) -- errors are visible by default, detail is opt-in.
* **Format** ``<HH:MM:SS.mmm> <LEVEL> [<thread>] <module>: <message>`` --
  millisecond timestamps and the *thread* name, because parallel fetches
  interleave and the thread tells you which source a line belongs to.
* **Crashes never vanish**: ``install_excepthooks()`` routes unhandled
  exceptions (main thread AND worker threads) into the log with FULL
  tracebacks before the process dies.
* ``logging.captureWarnings(True)`` so ``warnings.warn`` records are kept.

Usage:
    from pipeline import logutil

    log, log_path = logutil.setup(verbose=args.verbose, quiet=args.quiet)
    mod_log = logutil.get("kimeta")     # module-level logger
    mod_log.debug("probe via %s", proxy)
    mod_log.error("pool empty -- run refresh", exc_info=True)
"""
from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime
from pathlib import Path

ROOT_NAME = "pipeline"
_FMT = "%(asctime)s.%(msecs)03d %(levelname)-7s [%(threadName)s] %(name)s: %(message)s"
_DATEFMT = "%H:%M:%S"

_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING,
           "error": logging.ERROR}


def get(name: str) -> logging.Logger:
    """Module logger under the pipeline namespace (attached to setup()'s handlers)."""
    return logging.getLogger(f"{ROOT_NAME}.{name}")


def _log_dir() -> Path:
    # repo root (pipeline/ lives one level below) -- clone-safe, no hardcoded paths
    return Path(__file__).resolve().parent.parent / "logs"


def setup(*, verbose: bool = False, quiet: bool = False,
          log_dir: Path | str | None = None, ts: str | None = None
          ) -> tuple[logging.Logger, str]:
    """Configure the pipeline logger; returns (logger, log_file_path).

    Safe to call once per process (extra calls only add a fresh file handler --
    tests and repeated CLI invocations reuse the same root logger).
    """
    root = logging.getLogger(ROOT_NAME)
    root.setLevel(logging.DEBUG)          # handlers decide what is visible

    # A previous ensure_console()/setup() in this process (tests, repeated
    # invocations) may have attached console handlers -- stacking them would
    # print every record twice, so swap them out. FileHandlers are per-run
    # and stay (each setup() owns its own).
    for h in list(root.handlers):
        if isinstance(h, logging.FileHandler):
            continue
        root.removeHandler(h)

    dir_path = Path(log_dir) if log_dir else _log_dir()
    stamp = ts or datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = dir_path / f"pipeline_run_{stamp}.log"

    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        fh.setLevel(logging.DEBUG)        # the file keeps EVERYTHING
        fh.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        root.addHandler(fh)
    except OSError as e:
        # A broken log dir must not kill the run; console still works.
        root.addHandler(logging.NullHandler())
        _console_fallback = logging.getLogger(ROOT_NAME)
        _console_fallback.warning("cannot create log file %s (%s: %s) -- "
                                  "console-only logging",
                                  log_path, type(e).__name__, e)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if verbose
                     else logging.WARNING if quiet
                     else logging.INFO)
    console.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
    root.addHandler(console)

    logging.captureWarnings(True)
    install_excepthooks()
    root.debug("logging initialized (verbose=%s quiet=%s file=%s)",
               verbose, quiet, log_path)
    return root, str(log_path)


def ensure_console() -> logging.Logger:
    """Attach a stderr INFO handler when no handler exists yet.

    For subcommands (``history``, ``digest``) that run without ``setup()``:
    their module loggers still print errors instead of the stdlib
    "No handlers could be found" void.
    """
    root = logging.getLogger(ROOT_NAME)
    if not any(h for h in root.handlers if not isinstance(h, logging.NullHandler)):
        root.setLevel(logging.DEBUG)
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        root.addHandler(console)
    return root


def install_excepthooks() -> None:
    """Unhandled crashes (main + worker threads) land in the log, then die loudly.

    Idempotent: installing twice keeps a single hook (the first wins).
    """
    if getattr(sys, "_erl_log_excepthook", False):
        return
    sys._erl_log_excepthook = True  # type: ignore[attr-defined]

    log = logging.getLogger(f"{ROOT_NAME}.crash")
    prev_hook = sys.excepthook

    def _main_hook(exc_type, exc, tb):
        # full traceback FIRST (log file + console), then the original behavior
        log.error("UNHANDLED EXCEPTION -- process dying: %s: %s",
                  exc_type.__name__, exc, exc_info=(exc_type, exc, tb))
        if prev_hook is not sys.__excepthook__:
            prev_hook(exc_type, exc, tb)
        else:
            sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _main_hook

    def _thread_hook(args):
        log.error("UNHANDLED EXCEPTION in thread %r -- %s.%s: %s",
                   args.thread.name if args.thread else "?",
                   getattr(args.exc_type, "__module__", "?"),
                   getattr(args.exc_type, "__name__", "?"),
                   args.exc_value,
                   exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = _thread_hook
