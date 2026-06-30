"""EU Funding & Tenders (SEDIA) source — open/forthcoming grant calls.

The portal's live search-api ignores structured filters via anonymous access and
its multipart channel 500s, so we use the portal's own canonical bulk export
(`grantsTenders.json`, ~125 MB) that backs the public calls listing. We download
it once (gzip stream), cache to disk for 24h, then filter open/forthcoming calls
by keyword locally. No API key required.

`normalize_call` and `filter_calls` are pure (operate on already-decoded JSON) and
are unit-tested against a small captured fixture — no network.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import httpx

from ..format import epoch_ms_to_iso, next_upcoming_iso, truncate
from ..models import Opportunity

BULK_URL = (
    "https://ec.europa.eu/info/funding-tenders/opportunities/data/"
    "referenceData/grantsTenders.json"
)
TOPIC_URL = (
    "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/"
    "opportunities/topic-details/{id}"
)
# status ids in the export
STATUS_OPEN = 31094502
STATUS_FORTHCOMING = 31094501
_OPEN_STATUSES = {STATUS_OPEN, STATUS_FORTHCOMING}

_CACHE_TTL_SECONDS = 24 * 3600


def normalize_call(call: dict) -> Opportunity:
    """Map one GrantTenderObj entry to an Opportunity."""
    ident = str(call.get("identifier") or "").strip()
    fw = call.get("frameworkProgramme") or {}
    funder = fw.get("description") or "European Commission"
    status = (call.get("status") or {}).get("abbreviation") or ""
    divisions = call.get("programmeDivision") or []
    div_desc = "; ".join(
        d.get("description", "") for d in divisions if d.get("description")
    )
    return Opportunity(
        id=ident,
        source="eu-sedia",
        title=(call.get("title") or call.get("callTitle") or "").strip(),
        funder=truncate(funder, 120),
        status=status,
        open_date=epoch_ms_to_iso(call.get("plannedOpeningDateLong")),
        close_date=next_upcoming_iso(call.get("deadlineDatesLong")),
        eligibility=truncate(div_desc, 240),
        description="",
        url=TOPIC_URL.format(id=ident) if ident else "",
    )


def _matches(call: dict, keyword: str) -> bool:
    if not keyword:
        return True
    kw = keyword.lower()
    haystack = " ".join(
        str(x) for x in (
            call.get("title"), call.get("callTitle"),
            " ".join(call.get("tags") or []),
            " ".join(call.get("keywords") or []),
            (call.get("frameworkProgramme") or {}).get("description", ""),
            "; ".join(
                d.get("description", "") for d in (call.get("programmeDivision") or [])
            ),
        ) if x
    ).lower()
    return kw in haystack


def filter_calls(objs: list[dict], keyword: str, *, open_only: bool = True) -> list[Opportunity]:
    """Filter the bulk call list to open/forthcoming keyword matches → Opportunities."""
    out: list[Opportunity] = []
    for call in objs:
        status_id = (call.get("status") or {}).get("id")
        if open_only and status_id not in _OPEN_STATUSES:
            continue
        if not _matches(call, keyword):
            continue
        out.append(normalize_call(call))
    return out


class EuSediaSource:
    name = "eu-sedia"

    def __init__(self, *, cache_dir: str | Path | None = None, timeout: float = 240.0):
        self.name = "eu-sedia"
        self._timeout = timeout
        self._cache = Path(cache_dir or Path.home() / ".grant_scout_cache") / "eu_grantsTenders.json"
        self._objs: list[dict] | None = None

    def _cache_fresh(self) -> bool:
        return self._cache.exists() and (time.time() - self._cache.stat().st_mtime) < _CACHE_TTL_SECONDS

    def _download(self) -> None:
        self._cache.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream(
            "GET", BULK_URL, timeout=self._timeout,
            headers={"Accept-Encoding": "gzip"}, follow_redirects=True,
        ) as r:
            r.raise_for_status()
            with self._cache.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    def _load(self) -> list[dict]:
        if self._objs is not None:
            return self._objs
        if not self._cache_fresh():
            self._download()
        data = json.load(io.open(self._cache, encoding="utf-8"))
        self._objs = (data.get("fundingData") or {}).get("GrantTenderObj") or []
        return self._objs

    def search(self, keyword: str, *, status: str = "posted", rows: int = 25) -> list[Opportunity]:
        # `status`/`posted` from the common interface maps to open+forthcoming here.
        objs = self._load()
        results = filter_calls(objs, keyword, open_only=True)
        return results[:rows]

    def fetch(self, opportunity_id: str) -> Opportunity | None:
        for call in self._load():
            if str(call.get("identifier")) == str(opportunity_id):
                return normalize_call(call)
        return None
