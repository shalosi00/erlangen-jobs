"""Stdlib-only HTTP helpers (direct and via proxy).

Design notes:
* TLS verification is relaxed -- we traverse untrusted public proxies whose
  CONNECT MITM behavior is unpredictable; confidentiality is NOT a goal here,
  reachability is. Never send credentials through this client.
* Reads are capped (``read_limit``) so slow/huge pages cannot stall a run.
"""
from __future__ import annotations

import re
import ssl
import urllib.parse
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

SSLCTX = ssl.create_default_context()
SSLCTX.check_hostname = False
SSLCTX.verify_mode = ssl.CERT_NONE

# IP:port pairs hidden inside arbitrary proxy-list text formats.
IPPORT_RE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}")

# RFC1918 / link-local / loopback targets can never be public proxies.
_PRIVATE_PREFIXES = ("0.", "10.", "127.", "192.168.", "172.16.", "169.254.",
                     "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
                     "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
                     "172.27.", "172.28.", "172.29.", "172.30.", "172.31.")


def host_of(url: str) -> str:
    """Hostname of a URL (raises ValueError on unparsable input)."""
    host = urllib.parse.urlparse(url).netloc.split("@")[-1].split(":")[0]
    if not host:
        raise ValueError(f"cannot parse host from URL: {url!r}")
    return host.lower()


def normalize_url(url: str) -> str:
    """Add https:// when the scheme is missing; reject other junk early."""
    url = (url or "").strip()
    if not url:
        raise ValueError("empty URL")
    if "://" not in url:
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"cannot parse netloc from URL: {url!r}")
    return url


def is_public_ipport(candidate: str) -> bool:
    return bool(IPPORT_RE.fullmatch(candidate)) and not candidate.startswith(_PRIVATE_PREFIXES)


def http_get(
    url: str,
    *,
    timeout: float,
    proxy: str | None = None,
    read_limit: int = 2_500_000,
    headers: dict | None = None,
) -> str:
    """GET ``url`` and return decoded body (up to ``read_limit`` bytes).

    ``proxy`` is ``host:port`` (http proxy used for both schemes) or None.
    Raises on network errors -- callers decide how to mark the proxy.
    """
    handlers: list = []
    if proxy:
        px = proxy if "://" in proxy else f"http://{proxy}"
        handlers.append(urllib.request.ProxyHandler({"http": px, "https": px}))
    handlers.append(urllib.request.HTTPSHandler(context=SSLCTX))
    opener = urllib.request.build_opener(*handlers)

    req = urllib.request.Request(url, headers=headers or DEFAULT_HEADERS)
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read(read_limit)
    return raw.decode("utf-8", "ignore")


def page_url(base_url: str, page: int, template: str | None = None) -> str:
    """URL of ``page`` (1-based).

    * with ``template`` (must contain ``{n}``; ``{url}`` optional): the
      template drives every page -- e.g.
      ``https://x.com/list/page-{n}.html`` for path-style pagination.
    * otherwise: ``&page=N`` / ``?page=N`` is appended for page > 1, the
      convention used by AutoScout24 and most search UIs.
    """
    if template:
        if "{n}" not in template:
            raise ValueError("page template must contain '{n}'")
        return template.replace("{url}", base_url).replace("{n}", str(page))
    if page <= 1:
        return base_url
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}page={page}"
