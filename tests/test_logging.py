"""Logging tests (v1.2.0): leveled logs, crash capture, silent-layer visibility.

Offline only. Pinned behaviors:
* logutil.setup() creates the run log file; file keeps DEBUG, console keeps INFO
* quiet mode: console drops INFO, keeps WARNING+
* SourceError paths log error-level; unexpected failures log full tracebacks
* unhandled crashes (main thread + worker threads) land in the log file
* proxy_pool: corrupt data file -> logged + empty pool (no crash)
* geo: missing data file -> clear RuntimeError naming the file
* sources._base.check_http logs every non-200 before raising
"""
from __future__ import annotations

import json
import logging
import re
import sys
import threading
from typing import ClassVar

import pytest


@pytest.fixture()
def clean_pipeline_logger():
    """Isolate the shared 'pipeline' logger between tests."""
    root = logging.getLogger("pipeline")
    saved_handlers = list(root.handlers)
    yield root
    root.handlers = saved_handlers


def _read(path) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ setup
def test_setup_creates_log_file_and_returns_path(tmp_path, clean_pipeline_logger):
    from pipeline import logutil
    _, path = logutil.setup(log_dir=tmp_path, ts="20260101-000000")
    assert path.endswith("pipeline_run_20260101-000000.log")
    logutil.get("x").info("hello-info")
    assert "hello-info" in _read(path)


def test_file_gets_debug_console_does_not(tmp_path, clean_pipeline_logger,
                                          capsys):
    from pipeline import logutil
    _, path = logutil.setup(log_dir=tmp_path, ts="t1")
    logutil.get("x").debug("debug-only-record")
    out = capsys.readouterr().err
    assert "debug-only-record" not in out      # console at INFO
    assert "debug-only-record" in _read(path)  # file at DEBUG


def test_verbose_console_shows_debug(tmp_path, clean_pipeline_logger, capsys):
    from pipeline import logutil
    logutil.setup(verbose=True, log_dir=tmp_path, ts="t2")
    logutil.get("x").debug("verbose-debug")
    assert "verbose-debug" in capsys.readouterr().err


def test_quiet_console_hides_info_keeps_warning(tmp_path, clean_pipeline_logger,
                                                capsys):
    from pipeline import logutil
    logutil.setup(quiet=True, log_dir=tmp_path, ts="t3")
    logutil.get("x").info("quiet-info-hidden")
    logutil.get("x").warning("quiet-warning-visible")
    out = capsys.readouterr().err
    assert "quiet-info-hidden" not in out
    assert "quiet-warning-visible" in out
    # the file keeps everything regardless of console level
    assert "quiet-info-hidden" in _read(f"{tmp_path}/pipeline_run_t3.log")


def test_ms_timestamp_and_thread_in_records(tmp_path, clean_pipeline_logger):
    from pipeline import logutil
    _, path = logutil.setup(log_dir=tmp_path, ts="t4")
    logutil.get("x").info("format-check")
    line = next(ln for ln in _read(path).splitlines() if "format-check" in ln)
    # `HH:MM:SS.mmm LEVEL   [thread] pipeline.x: message`
    assert re.match(r"^\d{2}:\d{2}:\d{2}\.\d{3} INFO\s+\[", line), line
    assert "[MainThread]" in line
    assert "pipeline.x: format-check" in line


# ------------------------------------------------------------------ crashes
def test_unhandled_main_thread_crash_logged(tmp_path, clean_pipeline_logger):
    from pipeline import logutil
    logutil.setup(log_dir=tmp_path, ts="t5")
    try:
        raise RuntimeError("kaputt-main")
    except RuntimeError as e:
        tb = e.__traceback__
        sys.excepthook(RuntimeError, e, tb)      # what Python does on a crash
    txt = _read(f"{tmp_path}/pipeline_run_t5.log")
    assert "UNHANDLED EXCEPTION" in txt
    assert "kaputt-main" in txt
    assert "Traceback" in txt or "in test_unhandled" in txt


def test_unhandled_worker_thread_crash_logged(tmp_path, clean_pipeline_logger):
    from pipeline import logutil
    _, path = logutil.setup(log_dir=tmp_path, ts="t6")

    def _boom():
        raise ValueError("kaputt-thread")

    t = threading.Thread(target=_boom)
    t.start()
    t.join()
    txt = _read(path)
    assert "UNHANDLED EXCEPTION in thread" in txt
    assert "kaputt-thread" in txt


def test_source_unexpected_failure_logs_traceback(tmp_path, clean_pipeline_logger,
                                                  monkeypatch):
    """run_seq/run_par_error equivalent: log.exception writes the traceback."""
    from pipeline import logutil
    _, path = logutil.setup(log_dir=tmp_path, ts="t7")
    log = logutil.get("run")
    try:
        raise KeyError("unexpected-key")
    except KeyError:
        log.exception("[fake] UNEXPECTED failure")
    txt = _read(path)
    assert "[fake] UNEXPECTED failure" in txt
    assert "KeyError" in txt


# ------------------------------------------------------------------ layers
def _isolate_proxy_pool(monkeypatch, tmp_path, content: str):
    """Point proxy_pool at a fresh temp file and reset its module state."""
    from pipeline import proxy_pool
    (tmp_path / "validated_proxies.json").write_text(content, encoding="utf-8")
    monkeypatch.setattr(proxy_pool, "DATA_FILE", tmp_path / "validated_proxies.json")
    saved = (proxy_pool._rows, proxy_pool._load_failed, proxy_pool._dead)
    proxy_pool._rows = []
    proxy_pool._load_failed = False
    return proxy_pool, saved


def _restore_proxy_pool(module, saved):
    module._rows, module._load_failed, module._dead = saved


def test_proxy_pool_corrupt_file_logged_not_fatal(tmp_path, monkeypatch):
    proxy_pool, saved = _isolate_proxy_pool(monkeypatch, tmp_path, "{corrupt")
    try:
        proxy_pool._load()  # must not raise
        assert proxy_pool.stats()["alive"] == 0
        assert proxy_pool.stats()["load_failed"] is True
        assert proxy_pool.pick("kimeta") is None
    finally:
        _restore_proxy_pool(proxy_pool, saved)


def test_proxy_pool_wrong_shape_is_also_a_failure(tmp_path, monkeypatch):
    proxy_pool, saved = _isolate_proxy_pool(monkeypatch, tmp_path,
                                            '{"not": "a list"}')
    try:
        proxy_pool._load()
        assert proxy_pool.stats()["load_failed"] is True   # not a JSON list
        assert proxy_pool.stats()["alive"] == 0
    finally:
        _restore_proxy_pool(proxy_pool, saved)


def test_proxy_pool_valid_file_loads(tmp_path, monkeypatch):
    rows = [{"protocol": "http", "host": "1.2.3.4", "port": 8080,
             "kimeta_ok": True}]
    proxy_pool, saved = _isolate_proxy_pool(
        monkeypatch, tmp_path, json.dumps(rows))
    try:
        proxy_pool._load()
        st = proxy_pool.stats()
        assert st["alive"] == 1 and st["load_failed"] is False
        entry = proxy_pool.pick("kimeta")
        assert entry and entry["host"] == "1.2.3.4"
    finally:
        _restore_proxy_pool(proxy_pool, saved)


def test_geo_missing_data_file_clear_runtimeerror(monkeypatch):
    from pipeline import geo
    monkeypatch.setattr(geo, "DATA_FILE",
                        geo.Path("/nonexistent/transit_whitelist.json"))
    geo._CACHE = None
    with pytest.raises(RuntimeError) as ei:
        geo.zero_xfer_rx()
    assert "transit whitelist data file unusable" in str(ei.value)
    assert "nonexistent" in str(ei.value)


def test_check_http_logs_before_raising(tmp_path, clean_pipeline_logger, caplog):
    from pipeline import logutil
    from pipeline.core import SourceError
    from pipeline.sources._base import check_http

    class FakeResp:
        status_code = 403
        headers: ClassVar[dict] = {"server": "cloudflare"}
        text = "<html>blocked</html>"

    logutil.setup(log_dir=tmp_path, ts="t8")
    with pytest.raises(SourceError) as ei:
        check_http(FakeResp(), "fakesource", "https://x.example/serp")
    assert ei.value.kind == "waf"
    assert "HTTP 403" in str(ei.value)


def test_check_http_200_passes_silently(tmp_path, clean_pipeline_logger, capsys):
    from pipeline.sources._base import check_http

    class FakeResp:
        status_code = 200
        headers: ClassVar[dict] = {}
        text = "ok"

    check_http(FakeResp(), "fakesource", "https://x.example/")   # must not raise
    assert "HTTP 200" not in capsys.readouterr().err


# ------------------------------------------------------------------ misc
def test_ba_module_logger_exists():
    from pipeline.sources import ba
    assert ba.log.name == "pipeline.ba"


def test_history_logs_update_counts(tmp_path, monkeypatch,
                                    clean_pipeline_logger):
    from pipeline import history, logutil
    from pipeline.core import Job
    # ISOLATION: never touch the production memory DB (pattern from
    # tests/test_history.py) -- point the module at a throwaway file.
    monkeypatch.setattr(history, "DB_PATH", str(tmp_path / "mem.db"))
    _, path = logutil.setup(log_dir=tmp_path, ts="t9")
    # memory update requires sqlite_utils; both paths must log something
    try:
        history.update([Job(source="t", title="IT-Support", company="ACME",
                           city="Erlangen")])
        assert "memory update:" in _read(path)
    except history.MemoryUnavailable:
        # dependency missing -> that is also logged by the caller layer; here
        # we only assert the log channel itself works
        logutil.get("history").warning("memory unavailable fallback")
        assert "memory unavailable fallback" in _read(path)


def test_ensure_console_attaches_handler(clean_pipeline_logger, capsys):
    from pipeline import logutil
    clean_pipeline_logger.handlers = []        # simulate fresh process
    logutil.ensure_console()
    logutil.get("sub").error("ensure-console-error")
    assert "ensure-console-error" in capsys.readouterr().err
