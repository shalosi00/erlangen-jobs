"""Offline tests: probe engines (asynchttp), persistent user config
(userconfig), engine resolution and the `proxyfetch config` CLI."""
from __future__ import annotations

import http.server
import json
import socket
import threading

import pytest

from proxyfetch import asynchttp, cli, config, errors, supply, userconfig
from proxyfetch.config import Config
from proxyfetch.logutil import Logger


def _logger() -> Logger:
    return Logger(quiet=True, colors=False)


# ---------------------------------------------------------------- userconfig
def test_userconfig_roundtrip(tmp_path):
    sd = tmp_path / "state"
    assert userconfig.load(sd) == {}
    saved = userconfig.set_value("engine", "threads", sd)
    assert saved == "threads"
    assert userconfig.load(sd) == {"engine": "threads"}
    assert userconfig.path(sd).exists()
    userconfig.set_value("concurrency", "500", sd)
    assert userconfig.load(sd) == {"engine": "threads", "concurrency": 500}
    userconfig.unset_value("engine", sd)
    assert userconfig.load(sd) == {"concurrency": 500}


def test_userconfig_validation(tmp_path):
    sd = tmp_path / "state"
    with pytest.raises(errors.ConfigError):
        userconfig.set_value("engine", "gevent", sd)
    with pytest.raises(errors.ConfigError):
        userconfig.set_value("concurrency", "0", sd)
    with pytest.raises(errors.ConfigError):
        userconfig.set_value("nope", "x", sd)
    with pytest.raises(errors.ConfigError):
        userconfig.unset_value("nope", sd)
    # nothing was written
    assert userconfig.load(sd) == {}


def test_userconfig_corrupt_quarantined(tmp_path):
    p = userconfig.path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    assert userconfig.load(tmp_path) == {}
    assert p.with_suffix(".json.corrupt").exists()
    assert not p.exists()


def test_userconfig_accepts_uppercase_engine(tmp_path):
    assert userconfig.set_value("engine", "AioHttp", tmp_path) == "aiohttp"


# ---------------------------------------------------------------- config
def test_config_engine_defaults():
    cfg = Config()
    assert cfg.engine == "aiohttp"
    assert cfg.concurrency == 300


def test_config_validated_rejects_bad_engine():
    cfg = Config(url="https://example.com", engine="gevent")
    with pytest.raises(errors.ConfigError):
        cfg.validated()


def test_config_validated_rejects_bad_concurrency():
    cfg = Config(url="https://example.com", concurrency=0)
    with pytest.raises(errors.ConfigError):
        cfg.validated()


def test_to_dict_includes_engine():
    d = Config(url="https://example.com").to_dict()
    assert d["engine"] == "aiohttp" and d["concurrency"] == 300


# ---------------------------------------------------------------- resolution
def test_resolve_engine_chain(monkeypatch):
    for var in ("PROXYFETCH_ENGINE", "PROXYFETCH_CONCURRENCY"):
        monkeypatch.delenv(var, raising=False)

    # 1. dataclass default stands when nothing else set
    cfg = Config(url="https://example.com")
    cli.resolve_engine(cfg, None, None, {})
    assert (cfg.engine, cfg.concurrency) == ("aiohttp", 300)

    # 2. saved config wins over default
    cfg = Config(url="https://example.com")
    cli.resolve_engine(cfg, None, None, {"engine": "threads", "concurrency": 64})
    assert (cfg.engine, cfg.concurrency) == ("threads", 64)

    # 3. env wins over saved config
    monkeypatch.setenv("PROXYFETCH_ENGINE", "threads")
    monkeypatch.setenv("PROXYFETCH_CONCURRENCY", "42")
    cfg = Config(url="https://example.com")
    cli.resolve_engine(cfg, None, None, {"engine": "aiohttp"})
    assert (cfg.engine, cfg.concurrency) == ("threads", 42)

    # 4. CLI flag wins over everything
    cfg = Config(url="https://example.com")
    cli.resolve_engine(cfg, "aiohttp", None, {"engine": "threads"})
    assert cfg.engine == "aiohttp"

    # 5. bad env values fail with ConfigError
    monkeypatch.setenv("PROXYFETCH_ENGINE", "gevent")
    with pytest.raises(errors.ConfigError):
        cli.resolve_engine(Config(), None, None, {})
    monkeypatch.setenv("PROXYFETCH_ENGINE", "threads")
    monkeypatch.setenv("PROXYFETCH_CONCURRENCY", "lots")
    with pytest.raises(errors.ConfigError):
        cli.resolve_engine(Config(), None, None, {})


# ---------------------------------------------------------------- asynchttp
@pytest.fixture()
def example_server():
    """Local HTTP server whose body passes the stage-1 verifier."""

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"<html><body>Example Domain</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # silence
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


def test_asynchttp_available():
    assert asynchttp.available() is True


def test_check_empty_input():
    assert asynchttp.check([], "https://example.com", timeout=5,
                           read_limit=100, verifier=lambda b: True) == []


def test_check_direct_against_local_server(example_server):
    """Full async path offline: 'direct' pseudo-proxy hits the local server."""
    out = asynchttp.check(["direct"], example_server, timeout=5,
                          read_limit=1000,
                          verifier=lambda b: "Example Domain" in b,
                          concurrency=10, prescan_min=10**9)
    assert len(out) == 1 and out[0][0] == "direct" and out[0][1] >= 0


def test_check_verifier_filters(example_server):
    out = asynchttp.check(["direct"], example_server, timeout=5,
                          read_limit=1000, verifier=lambda b: False,
                          concurrency=10, prescan_min=10**9)
    assert out == []


def test_check_inside_running_loop(example_server):
    """Calling check() from async context must not explode (worker thread)."""
    import asyncio

    async def inner():
        return asynchttp.check(["direct"], example_server, timeout=5,
                               read_limit=1000,
                               verifier=lambda b: "Example Domain" in b)
    out = asyncio.run(inner())
    assert len(out) == 1


def test_prescan_local_socket():
    # open, listening port -> reachable
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port_open = srv.getsockname()[1]
    # closed port: grab a free port number, then release it
    tmp = socket.socket()
    tmp.bind(("127.0.0.1", 0))
    port_closed = tmp.getsockname()[1]
    tmp.close()

    found = asynchttp.prescan([f"127.0.0.1:{port_open}",
                               f"127.0.0.1:{port_closed}"], timeout=2)
    assert found == {f"127.0.0.1:{port_open}"}
    srv.close()


# ---------------------------------------------------------------- supply
def _stage1_spec():
    return supply.ProbeSpec("https://example.com/",
                            lambda b: "Example Domain" in b, 9.0, 2000)


def test_check_batch_falls_back_to_threads(monkeypatch):
    """When aiohttp is unavailable the thread path must produce results."""
    monkeypatch.setattr(asynchttp, "available", lambda: False)
    seen = []

    def fake_get(url, *, timeout, proxy, read_limit, headers=None):
        seen.append(proxy)
        return "Example Domain"

    monkeypatch.setattr(supply, "http_get", fake_get)
    out = supply.check_batch(["1.2.3.4:8080", "5.6.7.8:3128"], _stage1_spec(),
                             "aiohttp", 8, _logger(), "test-label")
    assert {p for p, _ in out} == {"1.2.3.4:8080", "5.6.7.8:3128"}
    assert seen  # thread fallback actually probed


def test_check_batch_empty(monkeypatch):
    monkeypatch.setattr(asynchttp, "available", lambda: False)
    out = supply.check_batch([], _stage1_spec(), "threads", 8,
                             _logger(), "empty")
    assert out == []


def test_check_batch_verifier_rejects(monkeypatch):
    monkeypatch.setattr(asynchttp, "available", lambda: False)

    def fake_get(url, **kw):
        return "totally different page"

    monkeypatch.setattr(supply, "http_get", fake_get)
    out = supply.check_batch(["1.2.3.4:8080"], _stage1_spec(), "threads",
                             8, _logger(), "reject")
    assert out == []


def test_stage1_spec_shape():
    cfg = Config()
    spec = supply.stage1_spec(cfg)
    assert spec.url == supply.EXAMPLE_URL
    assert spec.verifier("<html>Example Domain</html>") is True
    assert spec.verifier("<html>nope</html>") is False


# ---------------------------------------------------------------- cli config
def _with_state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("PROXYFETCH_STATE_DIR", str(tmp_path / "state"))


def test_cli_config_set_get_unset(monkeypatch, tmp_path, capsys):
    _with_state_dir(monkeypatch, tmp_path)
    assert cli.main(["config", "set", "engine", "threads"]) == 0
    assert json.loads((tmp_path / "state" / "config.json").read_text()) \
        == {"engine": "threads"}
    capsys.readouterr()  # discard 'saved:' confirmation
    assert cli.main(["config", "get", "engine"]) == 0
    assert capsys.readouterr().out.strip() == "threads"
    assert cli.main(["config", "unset", "engine"]) == 0
    capsys.readouterr()
    assert cli.main(["config", "get", "engine"]) == 0
    assert capsys.readouterr().out.strip() == "aiohttp"  # back to default


def test_cli_config_list_human_and_json(monkeypatch, tmp_path, capsys):
    _with_state_dir(monkeypatch, tmp_path)
    cli.main(["config", "set", "concurrency", "123"])
    capsys.readouterr()
    assert cli.main(["config", "list"]) == 0
    human = capsys.readouterr().out
    assert "concurrency" in human and "123" in human and "saved" in human
    assert cli.main(["config", "--json", "list"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc == {"concurrency": 123, "engine": "aiohttp"}


def test_cli_config_bad_value_exit_2(monkeypatch, tmp_path):
    _with_state_dir(monkeypatch, tmp_path)
    assert cli.main(["config", "set", "engine", "gevent"]) == 2
    # unknown key is caught by argparse itself (exit code 2, usage error)
    with pytest.raises(SystemExit) as e:
        cli.main(["config", "set", "nope", "1"])
    assert e.value.code == 2


def test_cli_config_unknown_key_is_argparse_exit_2():
    with pytest.raises(SystemExit) as e:
        cli.build_config_parser().parse_args(["set", "bogus", "x"])
    assert e.value.code == 2


def test_cli_parser_has_engine_flags():
    args = cli.build_parser().parse_args(
        ["--engine", "threads", "--concurrency", "50", "https://example.com"])
    assert args.engine == "threads" and args.concurrency == 50
