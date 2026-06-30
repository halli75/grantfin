"""360Giving (UK) funder intelligence.

The 360Giving API (api.threesixtygiving.org/api/v1) has no keyword-search endpoint —
only a paginated organisation list and per-org grants. So funder discovery here is
necessarily a client-side NAME match over the org list, capped to a few pages to
respect the 2 req/s rate limit. This is a deliberately limited, UK-only, name-based
source (documented as such); it will not do cause-based discovery.

`filter_orgs` is pure and unit-tested against a fixture.
"""

from __future__ import annotations

import httpx

from ..models import Funder

BASE = "https://api.threesixtygiving.org/api/v1"
ORG_LIST = f"{BASE}/org/"
ORG_PAGE_URL = "https://grantnav.threesixtygiving.org/org/{org_id}"

DEFAULT_MAX_PAGES = 3
PAGE_SIZE = 1000


def normalize_org(org: dict) -> Funder:
    org_id = str(org.get("org_id") or "").strip()
    return Funder(
        id=org_id,
        source="360giving",
        name=(org.get("name") or "").strip(),
        location="United Kingdom",
        focus="",
        url=ORG_PAGE_URL.format(org_id=org_id) if org_id else "",
    )


def filter_orgs(orgs: list[dict], keyword: str) -> list[Funder]:
    """Keep orgs whose name contains the keyword (case-insensitive)."""
    kw = (keyword or "").lower().strip()
    out = []
    for o in orgs:
        name = (o.get("name") or "").strip()
        if not name:
            continue
        if not kw or kw in name.lower():
            out.append(normalize_org(o))
    return out


class ThreeSixtyGivingSource:
    name = "360giving"

    def __init__(self, *, timeout: float = 30.0, max_pages: int = DEFAULT_MAX_PAGES,
                 client: httpx.Client | None = None, logger=None):
        self._timeout = timeout
        self._max_pages = max_pages
        self._client = client
        self._log = logger or (lambda m: None)

    def _get(self, url: str, params: dict | None = None) -> dict:
        if self._client is not None:
            resp = self._client.get(url, params=params)
        else:
            resp = httpx.get(url, params=params, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def find(self, keyword: str, *, location: str = "", rows: int = 25) -> list[Funder]:
        results: list[Funder] = []
        url = ORG_LIST
        params = {"limit": PAGE_SIZE}
        pages = 0
        while url and pages < self._max_pages and len(results) < rows:
            data = self._get(url, params=params)
            results.extend(filter_orgs(data.get("results") or [], keyword))
            url = data.get("next")        # next is a full URL; params already embedded
            params = None
            pages += 1
        if url and len(results) < rows:
            self._log(
                f"360giving: stopped after {pages} pages (rate-limit cap); "
                "more UK orgs may match but were not scanned."
            )
        return results[:rows]
