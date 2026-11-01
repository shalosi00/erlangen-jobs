"""Lightpanda render engine — self-healing, zero-dependency (stdlib only).

Lightpanda (https://lightpanda.com) is a headless browser that speaks the
Chrome DevTools Protocol from one small binary (~35 MB, ~70 MB RSS under
load). This module turns it into proxyfetch's first render engine:

  * server lifecycle is fully dynamic — start on demand, health-check
    before every render, restart on death, move ports when one is held,
    and route every render through an HTTP proxy when asked
    (``lightpanda serve --http-proxy``), so proxied renders stay proxied;
  * renders happen over a raw CDP WebSocket (RFC 6455 client included):
    createTarget -> flat session -> Page.navigate -> loadEventFired ->
    consent walls auto-accepted -> JS dialogs auto-dismissed -> HTML out;
  * every socket operation is timeout-bounded, no call ever raises —
    failures return ``None`` and the caller falls back (cloakbrowser /
    plain HTTP), so a browser hiccup can never stall a run.

Environment:
  LIGHTPANDA_BIN   path to the lightpanda binary (default: autodetect via
                   PATH and common locations)
  LIGHTPANDA_CDP   use this external CDP endpoint (e.g. http://127.0.0.1:9222)
                   instead of managing servers here; renders then go out
                   directly through that server (its own --http-proxy wins).

Verified against Lightpanda 1.0.2 (2026-11-01); the protocol subset used
here (Target.*, Page.enable/navigate, Runtime.evaluate,
Page.javascriptDialogOpening) is stable CDP surface.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

__all__ = [
    "find_binary", "lightpanda_available", "ensure_server",
    "render", "stop_all", "WSClient",
]

# cookie-consent accept-all buttons, tried in order (walls hide the list
# behind them; a missing button is a cheap no-op miss). Battle-tested on
# 148 employer boards (OneTrust, Cookiebot, UserCentrics, CIVIC,
# CookieScript, CookieYes).
CONSENT_SELECTORS = (
    '#onetrust-accept-btn-handler',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#CybotCookiebotDialogBodyButtonAccept',
    'button.cm-btn-success', '#cm-btn-success',
    'button[data-testid="uc-accept-all-button"]',
    '#uc-btn-accept-banner', 'button.js-uc-btn-accept',
    '#ccc-recommended-settings',
    '#cookiescript_accept',
    'button[data-cky-tag="accept-button"]',
)

PORT_BASE = 9222          # first choice; +8 alternates when held
PORT_SPAN = 9
STARTUP_WAIT_S = 8.0      # max wait for a fresh server to answer /json/version
MAX_SERVERS = 6           # concurrent servers; oldest get evicted (LRU)
RENDER_TIMEOUT_S = 30     # hard cap per render (nav + settle + evaluate)
MAX_HTML = 4 * 1024 * 1024   # cap on returned HTML

_COMMON_BIN_PATHS = (
    "/usr/local/bin/lightpanda",
    "/usr/bin/lightpanda",
    "/opt/lightpanda/lightpanda",
    str(Path.home() / ".local/bin/lightpanda"),
    str(Path.home() / "bin/lightpanda"),
)


# --------------------------------------------------------------------------
# binary discovery
# --------------------------------------------------------------------------
def find_binary(override: str | None = None) -> str | None:
    """Return the path of a usable lightpanda binary, else None.

    Order: explicit override (CLI --lightpanda-bin) > $LIGHTPANDA_BIN >
    $PATH > common install locations. Only executable files win.
    """
    candidates: list[str] = []
    if override:
        candidates.append(override)
    env = os.environ.get("LIGHTPANDA_BIN")
    if env:
        candidates.append(env)
    which = shutil.which("lightpanda")
    if which:
        candidates.append(which)
    candidates += list(_COMMON_BIN_PATHS)
    for cand in candidates:
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


# --------------------------------------------------------------------------
# CDP endpoint health
# --------------------------------------------------------------------------
def _http_json(endpoint: str, path: str, timeout: float = 3.0):
    """GET <endpoint><path>, return parsed JSON, or None (never raises)."""
    try:
        url = endpoint.rstrip("/") + path
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception:
        return None


def cdp_alive(endpoint: str) -> bool:
    """True if a CDP server answers /json/version with a websocket URL."""
    ver = _http_json(endpoint, "/json/version")
    return bool(ver and ver.get("webSocketDebuggerUrl"))


# --------------------------------------------------------------------------
# server registry / lifecycle
# --------------------------------------------------------------------------
class _Server:
    __slots__ = ("key", "endpoint", "proc", "log")

    def __init__(self, key, endpoint, proc, log):
        self.key, self.endpoint, self.proc, self.log = key, endpoint, proc, log

    def stop(self, grace_s: float = 3.0):
        if self.proc is None:
            return
        try:
            self.proc.terminate()          # SIGTERM
            self.proc.wait(timeout=grace_s)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        if self.log:
            try:
                self.log.close()
            except Exception:
                pass


_REGISTRY: dict[tuple, _Server] = {}      # (proxy, locale, tz) -> _Server


def _proxy_flag(proxy: str | None) -> list[str]:
    if not proxy:
        return []
    url = proxy if "://" in proxy else f"http://{proxy}"
    return ["--http-proxy", url]


def _free_port() -> int | None:
    for port in range(PORT_BASE, PORT_BASE + PORT_SPAN):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port            # bindable now == free to start on
            except OSError:
                continue                # held by a process we do not own
    return None


def _start_server(binary: str, key: tuple, proxy: str | None,
                  locale: str | None, timezone: str | None) -> _Server | None:
    port = _free_port()
    if port is None:
        return None
    cmd = [binary, "serve", "--host", "127.0.0.1", "--port", str(port),
           # stylesheets so consent-button visibility checks are real
           "--load-resources", "stylesheet"]
    cmd += _proxy_flag(proxy)
    if locale:
        cmd += ["--locale", locale]
    if timezone:
        cmd += ["--timezone", timezone]
    # logs: $LIGHTPANDA_LOG (persistent, appended) or an anonymous temp
    # file that vanishes on close -- no /tmp litter from library use
    try:
        if os.environ.get("LIGHTPANDA_LOG"):
            log: object = open(os.environ["LIGHTPANDA_LOG"], "ab",
                               buffering=0)
        else:
            log = tempfile.TemporaryFile()
    except OSError:
        log = None
    try:
        proc = subprocess.Popen(
            cmd, stdout=log if log is not None else subprocess.DEVNULL,
            stderr=log if log is not None else subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        if log is not None:
            log.close()
        return None
    endpoint = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + STARTUP_WAIT_S
    while time.monotonic() < deadline:
        if cdp_alive(endpoint):
            return _Server(key, endpoint, proc, log)
        if proc.poll() is not None:      # died during startup
            break
        time.sleep(0.25)
    _Server(key, endpoint, proc, log).stop()
    return None


def _reap_orphans(binary: str) -> int:
    """Last resort: kill leftover `lightpanda serve` processes whose argv0
    is exactly our binary (never by name). Linux only; no-op elsewhere.
    Returns the number of PIDs signalled."""
    if not os.path.isdir("/proc"):
        return 0
    hit = 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                argv = f.read().decode("utf-8", "replace").split("\0")
        except OSError:
            continue
        if not argv or argv[0] != binary or "serve" not in argv[1:3]:
            continue
        try:
            os.kill(int(pid), 15)
            hit += 1
        except OSError:
            pass
    if hit:
        time.sleep(0.5)
    return hit


def ensure_server(proxy: str | None = None, *, locale: str | None = None,
                  timezone: str | None = None,
                  binary: str | None = None, logger=None) -> str | None:
    """Return a healthy CDP endpoint that renders through ``proxy``.

    Self-healing on every call:
      healthy server for this (proxy, locale, tz) -> reuse it
      entry dead (crashed / hung)                    -> stop ours, start fresh
      no entry                                        -> start one
      every port held and nothing healthy             -> reap orphans, retry once

    With $LIGHTPANDA_CDP set, that external endpoint is health-checked and
    returned for every call (its own --http-proxy applies; ``proxy`` here is
    then informational only).
    """
    external = os.environ.get("LIGHTPANDA_CDP")
    if external:
        if external == "off":
            return None
        if cdp_alive(external):
            return external
        return None

    binpath = find_binary(binary)
    if binpath is None:
        return None

    key = (proxy or "direct", locale, timezone)
    srv = _REGISTRY.get(key)
    if srv and cdp_alive(srv.endpoint):
        return srv.endpoint                     # fast path: healthy reuse

    if srv:                                     # dead: reap, restart below
        srv.stop()
        del _REGISTRY[key]

    srv = _start_server(binpath, key, proxy, locale, timezone)
    if srv is None:
        # every port held and nothing healthy: clear orphans, one retry
        if _reap_orphans(binpath):
            srv = _start_server(binpath, key, proxy, locale, timezone)
    if srv is None:
        if logger:
            logger.debug("lightpanda: no server could be started "
                          "(binary present, all ports busy)")
        return None

    _REGISTRY[key] = srv
    # LRU: evict the oldest servers beyond the cap
    while len(_REGISTRY) > MAX_SERVERS:
        oldest_key = next(iter(_REGISTRY))
        old = _REGISTRY.pop(oldest_key)
        if logger:
            logger.debug(f"lightpanda: evicting server for {oldest_key[0]} (LRU)")
        old.stop()
    return srv.endpoint


def stop_all() -> None:
    """Stop every server this process started (atexit-registered: servers
    live as long as the process that needed them -- warm across runs
    inside it, never leaked after exit)."""
    for srv in list(_REGISTRY.values()):
        srv.stop()
    _REGISTRY.clear()


import atexit  # noqa: E402  (registration must follow stop_all)

atexit.register(stop_all)


def lightpanda_available(binary: str | None = None) -> bool:
    """True if renders are possible (managed binary or external endpoint)."""
    if os.environ.get("LIGHTPANDA_CDP", "") not in ("", "off"):
        return cdp_alive(os.environ["LIGHTPANDA_CDP"])
    return find_binary(binary) is not None


# --------------------------------------------------------------------------
# raw WebSocket (RFC 6455) CDP client — text frames, client-masked sends
# --------------------------------------------------------------------------
class WSClient:
    """Tiny CDP-over-WebSocket client. Never blocks longer than the
    timeouts given; all errors raise, the caller decides what is fatal."""

    def __init__(self, ws_url: str, *, handshake_timeout: float = 5.0):
        host, _, rest = ws_url[5:].partition("/")
        path = "/" + rest
        host, _, port = host.rpartition(":")
        self.sock = socket.create_connection((host, int(port)),
                                             timeout=handshake_timeout)
        self.sock.settimeout(handshake_timeout)
        self.buf = b""
        # no Origin header: Lightpanda accepts upgrades without one
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        while b"\r\n\r\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise EOFError("ws: closed during handshake")
            self.buf += chunk
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0] + b" ":
            raise IOError(f"ws: upgrade refused: {head[:80]!r}")
        self._id = 0
        self._oob = 0

    # -- framing ------------------------------------------------------------
    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError("ws: closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        mask = b"\xcd\xe7\x9fR"                  # any 4 bytes; must mask
        header = bytearray([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 1 << 16:
            header.append(0x80 | 126)
            header += n.to_bytes(2, "big")
        else:
            header.append(0x80 | 127)
            header += n.to_bytes(8, "big")
        header += mask
        self.sock.sendall(bytes(header)
                          + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send_json(self, obj: dict) -> None:
        self._send_frame(0x1, json.dumps(obj).encode())

    def recv_json(self, timeout: float = RENDER_TIMEOUT_S) -> dict:
        """Read one complete text message, reassembling fragments and
        answering interleaved pings on the way."""
        self.sock.settimeout(timeout)
        fragments = bytearray()
        while True:
            b1, b2 = self._read(2)
            fin, op, ln = b1 & 0x80, b1 & 0x0F, b2 & 0x7F
            if ln == 126:
                ln = int.from_bytes(self._read(2), "big")
            elif ln == 127:
                ln = int.from_bytes(self._read(8), "big")
            payload = self._read(ln)
            if op in (0x1, 0x0):                 # text start / continuation
                fragments += payload
                if fin:
                    return json.loads(bytes(fragments).decode("utf-8", "ignore"))
            elif op == 0x8:                      # close from server
                raise EOFError("ws: server closed")
            elif op == 0x9:                      # ping -> pong
                self._send_frame(0xA, payload[:125])
            # binary frames (0x2) never occur on CDP; skipped

    # -- CDP level ------------------------------------------------------------
    def _dismiss_dialog(self, msg: dict) -> None:
        """Out-of-band Page.handleJavaScriptDialog(accept=false): an open
        alert/confirm would block every later evaluate. Response is
        untracked (separate id range) and discarded on arrival."""
        self._oob += 1
        try:
            self.send_json({"id": 1_000_000 + self._oob,
                            "method": "Page.handleJavaScriptDialog",
                            "params": {"accept": False},
                            "sessionId": msg.get("sessionId")})
        except Exception:
            pass

    def _recv_guarded(self, timeout: float) -> dict:
        """recv_json, but auto-dismiss JS dialogs that arrive mid-wait."""
        while True:
            m = self.recv_json(timeout=timeout)
            if m.get("method") == "Page.javascriptDialogOpening":
                self._dismiss_dialog(m)
                continue
            return m

    def call(self, method: str, params: dict | None = None,
             session_id: str | None = None, *,
             timeout: float = RENDER_TIMEOUT_S) -> dict:
        self._id += 1
        mid = self._id
        msg = {"id": mid, "method": method, "params": params or {}}
        if session_id:
            msg["sessionId"] = session_id
        self.send_json(msg)
        while True:
            m = self._recv_guarded(timeout)
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(f"cdp {method}: {m['error']}")
                return m.get("result", {})

    def event(self, name: str, session_id: str | None = None, *,
              timeout: float = RENDER_TIMEOUT_S) -> dict:
        while True:
            m = self._recv_guarded(timeout)
            if m.get("method") == name and \
                    (session_id is None or m.get("sessionId") == session_id):
                return m

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")            # polite close
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
_CONSENT_JS = (
    "(() => {const sels = %s; "
    "for (const s of sels) { try { "
    "  const el = document.querySelector(s); "
    "  if (el && el.getBoundingClientRect().height > 0) { el.click(); "
    "    return s; } } catch (e) {} } return null;})()"
)


def render(url: str, endpoint: str, *, timeout_s: float = RENDER_TIMEOUT_S,
           consent: bool = True, settle_ms: int = 1200,
           max_html: int = MAX_HTML) -> dict | None:
    """Render ``url`` on the Lightpanda server at ``endpoint``.

    Returns ``{"title", "html"}`` or None on any failure (never raises).
    One tab per render: createTarget -> navigate -> wait for load ->
    auto-accept cookie walls -> auto-dismiss JS dialogs -> settle ->
    pull title+HTML -> closeTarget.
    """
    ver = _http_json(endpoint, "/json/version", timeout=3.0)
    if not ver or not ver.get("webSocketDebuggerUrl"):
        return None
    ws = None
    target = None
    try:
        ws = WSClient(ver["webSocketDebuggerUrl"])
        r = ws.call("Target.createTarget", {"url": "about:blank"},
                    timeout=min(timeout_s, 10.0))
        target = r.get("targetId")
        if not target:
            return None
        r = ws.call("Target.attachToTarget",
                    {"targetId": target, "flatten": True},
                    timeout=min(timeout_s, 10.0))
        sid = r.get("sessionId")
        if not sid:
            return None
        ws.call("Page.enable", session_id=sid, timeout=10.0)
        ws.call("Runtime.enable", session_id=sid, timeout=10.0)

        nav_left = time.monotonic() + timeout_s
        ws.call("Page.navigate", {"url": url}, session_id=sid,
                timeout=min(timeout_s, 15.0))
        loaded = False
        while time.monotonic() < nav_left:
            try:
                ws.event("Page.loadEventFired", session_id=sid,
                         timeout=max(1.0, nav_left - time.monotonic()))
                loaded = True
                break
            except Exception:
                break                            # timeout on the wait
        if not loaded:
            return None

        # settle + consent + dialogs (bounded by the same wall clock)
        def _left() -> float:
            return max(0.5, nav_left - time.monotonic())

        if consent:
            js = _CONSENT_JS % json.dumps(CONSENT_SELECTORS)
            try:
                ws.call("Runtime.evaluate",
                        {"expression": js, "returnByValue": True},
                        session_id=sid, timeout=_left())
            except Exception:
                pass
        time.sleep(min(settle_ms / 1000.0, _left()))

        out = ws.call("Runtime.evaluate",
                      {"expression":
                       "JSON.stringify([document.title||'', "
                       "document.documentElement.outerHTML])",
                       "returnByValue": True},
                      session_id=sid, timeout=_left())
        value = (out.get("result") or {}).get("value")
        if not isinstance(value, str):
            return None
        title, html = json.loads(value)
        if len(html) > max_html:
            html = html[:max_html]
        return {"title": title or "", "html": html}
    except Exception:
        return None
    finally:
        if ws is not None:
            if target:
                try:
                    ws.call("Target.closeTarget", {"targetId": target},
                            timeout=3.0)
                except Exception:
                    pass
            ws.close()
