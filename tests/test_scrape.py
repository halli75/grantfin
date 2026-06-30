"""Scrape tests: robots guard, text extraction, blocked-fetch, + one live fetch."""

from __future__ import annotations

import httpx
import pytest

from grant_scout.scrape import (
    USER_AGENT,
    domain_of,
    extract_text,
    fetch_page,
    robots_allows,
)

_ROBOTS = """
User-agent: *
Disallow: /private/
Allow: /
"""


def _robots_fetcher(_url):
    return _ROBOTS


def test_robots_allows_allowed_path():
    assert robots_allows("https://x.org/grants/", fetcher=_robots_fetcher) is True


def test_robots_blocks_disallowed_path():
    assert robots_allows("https://x.org/private/secret", fetcher=_robots_fetcher) is False


def test_robots_missing_defaults_allow():
    assert robots_allows("https://x.org/anything", fetcher=lambda u: None) is True


def test_robots_bad_url():
    assert robots_allows("not-a-url", fetcher=_robots_fetcher) is False


def test_extract_text_drops_noise_and_caps():
    html = """
    <html><head><style>.x{color:red}</style></head>
    <body><nav>HOME ABOUT</nav>
    <h1>Community Grant</h1>
    <p>We fund literacy programs. Deadline September 1.</p>
    <script>tracker()</script><footer>copyright</footer></body></html>
    """
    text = extract_text(html)
    assert "Community Grant" in text
    assert "literacy programs" in text
    assert "tracker" not in text      # script dropped
    assert "HOME ABOUT" not in text   # nav dropped
    assert "copyright" not in text    # footer dropped


def test_extract_text_cap():
    html = "<p>" + ("word " * 10000) + "</p>"
    out = extract_text(html, cap=100)
    assert len(out) <= 100 + len(" …[truncated]")
    assert out.endswith("[truncated]")


def test_fetch_page_blocked_does_not_fetch_body(monkeypatch):
    # robots disallows -> blocked, and httpx.get must never be called for the body
    monkeypatch.setattr("grant_scout.scrape.robots_allows", lambda *a, **k: False)
    def _boom(*a, **k):
        raise AssertionError("body fetch attempted despite robots block")
    monkeypatch.setattr(httpx, "get", _boom)
    res = fetch_page("https://x.org/private/x")
    assert res["blocked"] is True and res["text"] == ""


def test_fetch_page_uses_clean_text(monkeypatch, tmp_path):
    monkeypatch.setattr("grant_scout.scrape.robots_allows", lambda *a, **k: True)

    class _Resp:
        status_code = 200
        url = "https://x.org/grants"
        text = "<body><h1>Grant X</h1><script>no()</script></body>"

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp())
    res = fetch_page("https://x.org/grants", cache_dir=tmp_path)
    assert res["blocked"] is False
    assert "Grant X" in res["text"] and "no()" not in res["text"]


def test_domain_of():
    assert domain_of("https://www.ford.org/grants/") == "www.ford.org"


@pytest.mark.live
def test_fetch_live_real_page():
    # example.com is stable, public, robots-permissive.
    res = fetch_page("https://example.com/")
    assert res["blocked"] is False
    assert res["status"] == 200
    assert "example" in res["text"].lower()
