"""Grants.gov source — US federal opportunities via the public Search2 API.

No authentication required. Two endpoints:
  - POST /v1/api/search2          -> lightweight opportunity hits
  - POST /v1/api/fetchOpportunity -> full detail (award amounts, eligibility, ...)

The normaliser functions (`normalize_hit`, `normalize_detail`) are pure and take
already-decoded JSON, so they are unit-tested against captured fixtures with no
network access.
"""

from __future__ import annotations

import httpx

from ..format import iso_date, truncate
from ..models import Opportunity

BASE_URL = "https://api.grants.gov/v1/api"
DETAIL_URL_TEMPLATE = "https://www.grants.gov/search-results-detail/{id}"


def normalize_hit(hit: dict) -> Opportunity:
    """Map one search2 `oppHits[]` entry into an Opportunity."""
    opp_id = str(hit.get("id", "")).strip()
    return Opportunity(
        id=opp_id,
        source="grants.gov",
        title=(hit.get("title") or "").strip(),
        funder=(hit.get("agency") or hit.get("agencyCode") or "").strip(),
        status=(hit.get("oppStatus") or "").strip(),
        open_date=iso_date(hit.get("openDate")),
        close_date=iso_date(hit.get("closeDate")),
        cfda=", ".join(hit.get("cfdaList") or []),
        url=DETAIL_URL_TEMPLATE.format(id=opp_id) if opp_id else "",
    )


def normalize_detail(data: dict) -> Opportunity:
    """Map a fetchOpportunity `data` object into a fully-enriched Opportunity."""
    syn = data.get("synopsis") or {}
    opp_id = str(data.get("id", "")).strip()
    cfdas = data.get("cfdas") or []
    cfda_nums = ", ".join(
        str(c.get("cfdaNumber")) for c in cfdas if c.get("cfdaNumber")
    )
    # synopsis.agencyName is unreliable (often holds the contact person). The clean
    # agency name lives in agencyDetails / topAgencyDetails.
    agency = (data.get("agencyDetails") or {}).get("agencyName") \
        or (data.get("topAgencyDetails") or {}).get("agencyName") \
        or data.get("owningAgencyCode") or ""
    return Opportunity(
        id=opp_id,
        source="grants.gov",
        title=(data.get("opportunityTitle") or "").strip(),
        funder=truncate(agency, 120),
        # The detail payload has no clean status flag (docType is "synopsis", not a
        # status). Status comes from the search hit; leave blank here rather than lie.
        status="",
        open_date=iso_date(syn.get("postingDate")),
        close_date=iso_date(syn.get("responseDate")),
        award_floor=str(syn.get("awardFloor") or ""),
        award_ceiling=str(syn.get("awardCeiling") or ""),
        est_funding=str(syn.get("estimatedFunding") or ""),
        eligibility=truncate(syn.get("applicantEligibilityDesc")),
        description=truncate(syn.get("synopsisDesc"), limit=600),
        cfda=cfda_nums,
        url=DETAIL_URL_TEMPLATE.format(id=opp_id) if opp_id else "",
    )


class GrantsGovSource:
    name = "grants.gov"

    def __init__(self, *, timeout: float = 30.0, client: httpx.Client | None = None):
        self._timeout = timeout
        self._client = client

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{BASE_URL}/{endpoint}"
        if self._client is not None:
            resp = self._client.post(url, json=payload)
        else:
            resp = httpx.post(url, json=payload, timeout=self._timeout)
        resp.raise_for_status()
        body = resp.json()
        if body.get("errorcode", 0) != 0:
            raise RuntimeError(f"grants.gov {endpoint} error: {body.get('msg')}")
        return body.get("data", {}) or {}

    def search(self, keyword: str, *, status: str = "posted", rows: int = 25) -> list[Opportunity]:
        data = self._post(
            "search2",
            {"keyword": keyword, "oppStatuses": status, "rows": rows, "startRecord": 0},
        )
        return [normalize_hit(h) for h in (data.get("oppHits") or [])]

    def fetch(self, opportunity_id: str) -> Opportunity | None:
        data = self._post("fetchOpportunity", {"opportunityId": str(opportunity_id)})
        if not data:
            return None
        return normalize_detail(data)
