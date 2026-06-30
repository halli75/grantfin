"""Foundation-page fetching for Increment 4.

The server only *fetches* (safely); Claude does the extraction. `fetch_page`
respects robots.txt (the ToS/ethics guard — not optional), returns clean visible
text, and caches politely.
"""

from __future__ import annotations

import hashlib
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "GrantScout/0.1 (+https://github.com/grant-scout/grant-scout)"
_TEXT_CAP = 20_000
_CACHE_TTL = 24 * 3600
_NON_CONTENT_TAGS = ("script", "style", "nav", "footer", "header", "noscript", "form")


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def robots_allows(url: str, user_agent: str = USER_AGENT,
                  fetcher=None) -> bool:
    """Whether `user_agent` may fetch `url` per the site's robots.txt.

    On any failure to read/parse robots.txt, default to allow (standard crawler
    behaviour). `fetcher(robots_url)->str|None` is injectable for testing.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
    if fetcher is None:
        def fetcher(u):
            try:
                r = httpx.get(u, timeout=10.0, headers={"User-Agent": user_agent},
                              follow_redirects=True)
                return r.text if r.status_code == 200 else None
            except Exception:
                return None
    body = fetcher(robots_url)
    if not body:
        return True  # no robots.txt readable -> allowed
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(body.splitlines())
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True


def extract_text(html: str, cap: int = _TEXT_CAP) -> str:
    """Visible text from HTML: drop scripts/nav/etc, collapse whitespace, cap length."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(_NON_CONTENT_TAGS):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = " ".join(text.split())
    if len(text) > cap:
        text = text[:cap].rstrip() + " …[truncated]"
    return text


class _Cache:
    def __init__(self, cache_dir: str | Path | None):
        self.dir = Path(cache_dir or Path.home() / ".grant_scout_cache" / "pages")

    def _path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.dir / f"{h}.txt"

    def get(self, url: str) -> str | None:
        p = self._path(url)
        if p.exists() and (time.time() - p.stat().st_mtime) < _CACHE_TTL:
            return p.read_text(encoding="utf-8")
        return None

    def put(self, url: str, text: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self._path(url).write_text(text, encoding="utf-8")


def fetch_page(url: str, *, timeout: float = 30.0, cache_dir: str | Path | None = None,
               client: httpx.Client | None = None) -> dict:
    """Fetch a public page as clean text, respecting robots.txt.

    Returns {url, final_url, status, text, blocked, reason}. When robots disallows,
    `blocked=True` and the body is NOT fetched.
    """
    if not robots_allows(url):
        return {"url": url, "final_url": url, "status": 0, "text": "",
                "blocked": True, "reason": "Disallowed by robots.txt"}

    cache = _Cache(cache_dir)
    cached = cache.get(url)
    if cached is not None:
        return {"url": url, "final_url": url, "status": 200, "text": cached,
                "blocked": False, "reason": "cache"}

    headers = {"User-Agent": USER_AGENT}
    try:
        if client is not None:
            resp = client.get(url, headers=headers, follow_redirects=True)
        else:
            resp = httpx.get(url, headers=headers, follow_redirects=True, timeout=timeout)
    except Exception as e:
        return {"url": url, "final_url": url, "status": 0, "text": "",
                "blocked": False, "reason": f"fetch error: {e}"}

    text = extract_text(resp.text) if resp.status_code == 200 else ""
    if text:
        cache.put(url, text)
    return {"url": url, "final_url": str(resp.url), "status": resp.status_code,
            "text": text, "blocked": False,
            "reason": "" if resp.status_code == 200 else f"HTTP {resp.status_code}"}
