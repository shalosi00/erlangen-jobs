"""Offline tests for the Lightpanda engine (proxyfetch.lightpanda) and its
browser.py integration -- no binary, no network: a threaded mock CDP server
speaks just enough of the protocol (HTTP /json/version + a raw WebSocket
with Target/Page/Runtime/handleJavaScriptDialog).

A live smoke test runs only when the lightpanda binary is present
(skipif); CI has no binary, so the mock carries the coverage there.
"""
import json
import os
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from proxyfetch import browser, lightpanda as lp
from proxyfetch.config import Config
from proxyfetch import errors


# --------------------------------------------------------------------------
# mock CDP server
# --------------------------------------------------------------------------
class MockCDP:
    """Just enough CDP to exercise lp.render(): /json/version over HTTP,
    one WebSocket, createTarget/attach/Page.navigate (dialog before load),
    Runtime.evaluate (consent js + the final JSON.stringify, sent in two
    fragmented frames), handleJavaScriptDialog, Target.closeTarget."""

    MOCK_HTML = ("<html><head><title>Mock Title</title></head><body>"
                 "mock content for the offline CDP mock server; padding the "
                 "body past 200 characters so Recipe.verify's minimum-length "
                 "gate is satisfied when the mock is used through browser.py "
                 "(verification requires a realistic page length, and this "
                 "sentence exists to provide exactly that, plus a little more "
                 "harmless filler text to be safe on all code paths.)"
                 "</body></html>")

    def __init__(self, dialog: bool = False):
        self.dialog = dialog
        self.port = None
        self._srv = None
        self._thread = None
        self.seen = {"navigate": [], "evaluate": [], "handle_dialog": [],
                     "close_target": 0, "consent": 0}
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        self._srv = socket.socket()
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(4)
        self.port = self._srv.getsockname()[1]
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self.endpoint

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        try:
            self._srv.close()
        except OSError:
            pass

    def _loop(self):
        while True:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            try:
                self._serve(conn)
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    # -- HTTP + WS dispatch --------------------------------------------------
    def _serve(self, conn):
        conn.settimeout(10)
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = conn.recv(4096)
            if not chunk:
                return
            head += chunk
        if b"websocket" not in head.lower():
            path = head.split(b" ", 2)[1]
            if path == b"/json/version":
                body = json.dumps({
                    "Browser": "MockCDP", "Protocol-Version": "1.3",
                    "webSocketDebuggerUrl": f"ws://127.0.0.1:{self.port}/",
                }).encode()
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: "
                             b"application/json\r\nContent-Length: "
                             + str(len(body)).encode() + b"\r\n\r\n" + body)
            return
        conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\n"
                     b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
                     b"Sec-WebSocket-Accept: k\r\n\r\n")
        self._ws_session(conn)

    # -- framing (client frames are masked; server frames are not) ----------
    @staticmethod
    def _read_frame(conn, buf):
        while len(buf) < 2:
            buf += conn.recv(4096)
        b1, b2 = buf[0], buf[1]
        op, masked, ln = b1 & 0x0F, b2 & 0x80, b2 & 0x7F
        idx = 2
        if ln == 126:
            while len(buf) < idx + 2:
                buf += conn.recv(4096)
            ln = int.from_bytes(buf[idx:idx + 2], "big")
            idx += 2
        elif ln == 127:
            while len(buf) < idx + 8:
                buf += conn.recv(4096)
            ln = int.from_bytes(buf[idx:idx + 8], "big")
            idx += 8
        mask = b""
        if masked:
            while len(buf) < idx + 4:
                buf += conn.recv(4096)
            mask = buf[idx:idx + 4]
            buf = buf[idx + 4:]
        while len(buf) < ln:
            buf += conn.recv(4096)
        payload, buf = buf[:ln], buf[ln:]
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return op, payload, buf

    @staticmethod
    def _send_frame(conn, opcode, payload, fin=True):
        header = bytearray([0x80 | opcode if fin else 0x00 | opcode])
        n = len(payload)
        if n < 126:
            header.append(n)
        elif n < 1 << 16:
            header.append(126)
            header += n.to_bytes(2, "big")
        else:
            header.append(127)
            header += n.to_bytes(8, "big")
        conn.sendall(bytes(header) + payload)

    def _send_json(self, conn, obj, fragment=False):
        data = json.dumps(obj).encode()
        if fragment and len(data) > 40:
            cut = int(len(data) * 0.6)
            self._send_frame(conn, 0x1, data[:cut], fin=False)
            self._send_frame(conn, 0x0, data[cut:], fin=True)
        else:
            self._send_frame(conn, 0x1, data)

    # -- CDP session -----------------------------------------------------------
    def _ws_session(self, conn):
        buf = b""
        session_id = "S-1"
        while True:
            try:
                op, payload, buf = self._read_frame(conn, buf)
            except Exception:
                return
            if op == 8:
                return
            if op != 1:
                continue
            try:
                msg = json.loads(payload.decode())
            except Exception:
                continue
            method = msg.get("method", "")
            mid = msg.get("id")
            if method == "Target.createTarget":
                self._send_json(conn, {"id": mid, "result": {"targetId": "T-1"}})
            elif method == "Target.attachToTarget":
                self._send_json(conn, {"id": mid, "result": {"sessionId": session_id}})
            elif method in ("Page.enable", "Runtime.enable"):
                self._send_json(conn, {"id": mid, "result": {}})
            elif method == "Page.navigate":
                with self._lock:
                    self.seen["navigate"].append(msg["params"]["url"])
                self._send_json(conn, {"id": mid, "result": {}})
                if self.dialog:
                    self._send_json(conn, {"method": "Page.javascriptDialogOpening",
                                           "params": {"message": "hi"},
                                           "sessionId": session_id})
                else:
                    self._send_json(conn, {"method": "Page.loadEventFired",
                                           "params": {}, "sessionId": session_id})
            elif method == "Page.handleJavaScriptDialog":
                with self._lock:
                    self.seen["handle_dialog"].append(msg.get("params"))
                self._send_json(conn, {"id": mid, "result": {}})
                self._send_json(conn, {"method": "Page.loadEventFired",
                                       "params": {}, "sessionId": session_id})
            elif method == "Target.closeTarget":
                with self._lock:
                    self.seen["close_target"] += 1
                self._send_json(conn, {"id": mid, "result": {"ok": True}})
            elif method == "Runtime.evaluate":
                expr = msg.get("params", {}).get("expression", "")
                if expr.startswith("(()"):
                    with self._lock:
                        self.seen["consent"] += 1
                    self._send_json(conn, {"id": mid,
                                           "result": {"result": {"value": None}}})
                else:  # the final JSON.stringify([title, html])
                    with self._lock:
                        self.seen["evaluate"].append(expr[:40])
                    value = json.dumps(["Mock Title", self.MOCK_HTML])
                    self._send_json(conn, {"id": mid,
                                           "result": {"result": {"value": value}}},
                                    fragment=True)
            else:
                self._send_json(conn, {"id": mid, "result": {}})


@pytest.fixture()
def mock_cdp():
    srv = MockCDP()
    srv.start()
    yield srv
    srv.stop()


# --------------------------------------------------------------------------
# lightpanda module
# --------------------------------------------------------------------------
def test_consent_selectors_sane():
    assert lp.CONSENT_SELECTORS
    for sel in lp.CONSENT_SELECTORS:
        assert sel.startswith(("#", "button")), sel
        assert " " not in sel.strip()


def test_find_binary_override(tmp_path):
    fake = tmp_path / "lightpanda"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    old = os.environ.pop("LIGHTPANDA_BIN", None)
    try:
        assert lp.find_binary(str(fake)) == str(fake)
        assert lp.find_binary(str(tmp_path / "missing")) is None
    finally:
        if old:
            os.environ["LIGHTPANDA_BIN"] = old


def test_render_on_mock(mock_cdp):
    out = lp.render("https://example.com/x", mock_cdp.endpoint)
    assert out and out["title"] == "Mock Title"
    assert "mock content" in out["html"]          # fragmented evaluate reassembled
    assert mock_cdp.seen["navigate"] == ["https://example.com/x"]
    assert mock_cdp.seen["consent"] == 1
    assert mock_cdp.seen["close_target"] == 1


def test_render_dismisses_dialogs(mock_cdp):
    srv = MockCDP(dialog=True)
    srv.start()
    try:
        out = lp.render("https://example.com/", srv.endpoint)
        assert out and out["title"] == "Mock Title"
        assert srv.seen["handle_dialog"] == [{"accept": False}]
    finally:
        srv.stop()


def test_render_dead_endpoint_returns_none():
    assert lp.render("https://example.com/", "http://127.0.0.1:9") is None


def test_external_endpoint_env(mock_cdp, monkeypatch):
    lp.stop_all()        # isolate: earlier suite tests may own managed servers
    monkeypatch.setenv("LIGHTPANDA_CDP", mock_cdp.endpoint)
    try:
        assert lp.ensure_server() == mock_cdp.endpoint
        assert len(lp._REGISTRY) == 0       # external: never ours to manage
        assert lp.render("https://example.com/", mock_cdp.endpoint)
    finally:
        lp.stop_all()


def test_cdp_off_env(monkeypatch):
    monkeypatch.setenv("LIGHTPANDA_CDP", "off")
    assert lp.ensure_server() is None


# --------------------------------------------------------------------------
# config surface
# --------------------------------------------------------------------------
def test_browser_engine_validation():
    with pytest.raises(errors.ConfigError):
        Config(url="https://x.com", browser_engine="bogus").validated()
    cfg = Config(url="https://x.com", browser_engine="lightpanda").validated()
    assert cfg.browser_engine == "lightpanda"
    assert "browser_engine" in Config(url="https://x.com").to_dict()


# --------------------------------------------------------------------------
# browser.py integration (engine chain, no binary needed)
# --------------------------------------------------------------------------
class _StubLP:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []
    def ensure_server(self, proxy=None, locale=None, timezone=None, binary=None):
        self.calls.append(("ensure", proxy, locale, timezone))
        return None if self.fail else "stub-endpoint"
    def render(self, url, endpoint, **kw):
        self.calls.append(("render", url))
        if self.fail:
            return None
        # >200 bytes: Recipe.verify rejects shorter pages as non-content
        body = "<html><head><title>Stub</title></head><body>" + "plain " * 40 \
               + "</body></html>"
        return {"title": "Stub", "html": body}
    def lightpanda_available(self, binary=None):
        return not self.fail


def test_browser_attempt_lightpanda_engine(monkeypatch, tmp_path):
    stub = _StubLP()
    monkeypatch.setattr(browser, "_lp", stub)
    proof = browser.browser_attempt(
        "direct", "https://example.com/", "generic",
        work_dir=tmp_path, logger=Logger4Test(), engine="lightpanda")
    assert proof and proof["engine"] == "lightpanda"
    assert proof["title"] == "Stub" and "plain" in proof["html"]
    # "direct" must be normalized to None (render without a proxy)
    assert stub.calls[0] == ("ensure", None, None, None)


def test_browser_attempt_lp_fail_no_cloak(monkeypatch, tmp_path):
    stub = _StubLP(fail=True)
    monkeypatch.setattr(browser, "_lp", stub)
    monkeypatch.setattr(browser, "cloakbrowser_available", lambda: False)
    proof = browser.browser_attempt(
        "1.2.3.4:8080", "https://example.com/", "generic",
        work_dir=tmp_path, logger=Logger4Test())
    assert proof is None                    # honest failure, no raise


def test_engines_dict(monkeypatch):
    monkeypatch.setattr(browser, "_lp", _StubLP())
    monkeypatch.setattr(browser, "cloakbrowser_available", lambda: False)
    eng = browser.engines()
    assert set(eng) == {"lightpanda", "cloakbrowser"}
    assert eng == {"lightpanda": True, "cloakbrowser": False}


class Logger4Test:
    """Silent stand-in for logutil.Logger (has debug/warn/info)."""

    def debug(self, msg):
        pass

    warn = info = debug


# --------------------------------------------------------------------------
# live smoke (only when the binary exists -- skipped in CI)
# --------------------------------------------------------------------------
@pytest.mark.skipif(not lp.find_binary(), reason="no lightpanda binary")
def test_live_ensure_server_and_render():
    lp.stop_all()
    ep = lp.ensure_server()
    assert ep
    out = lp.render("https://example.com/", ep)
    assert out and "Example" in out["title"]
    lp.stop_all()
    assert len(lp._REGISTRY) == 0
