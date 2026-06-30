"""Simpler.Grants.gov source — modern US federal opportunities API.

Requires a Login.gov-issued API key (X-API-Key). This adapter is ENV-GATED: the
server only registers it when SIMPLER_API_KEY is set, so users without a key see
no errors. Endpoint: POST /v1/opportunities/search.

`normalize_opportunity` is pure and unit-tested against a fixture shaped per the
published OpenAPI schema (no network, no key needed).
"""

from __future__ import annotations

import os

import httpx

from ..format import iso_date, truncate
from ..models import Opportunity

SEARCH_URL = "https://api.simpler.grants.gov/v1/opportunities/search"
DETAIL_URL = "https://simpler.grants.gov/opportunity/{id}"
ENV_KEY = "SIMPLER_API_KEY"


def normalize_opportunity(op: dict) -> Opportunity:
    """Map a Simpler OpportunityV1 record into an Opportunity."""
    opp_id = str(op.get("opportunity_id") or "").strip()
    summary = op.get("summary") or {}
    return Opportunity(
        id=opp_id,
        source="simpler.grants.gov",
        title=(op.get("opportunity_title") or "").strip(),
        funder=(op.get("agency_name") or op.get("agency_code") or "").strip(),
        status=(op.get("opportunity_status") or "").strip(),
        open_date=iso_date(summary.get("post_date")),
        close_date=iso_date(summary.get("close_date")),
        award_floor=str(summary.get("award_floor") or ""),
        award_ceiling=str(summary.get("award_ceiling") or ""),
        est_funding=str(summary.get("estimated_total_program_funding") or ""),
        eligibility=truncate(summary.get("applicant_eligibility_description")),
        description=truncate(summary.get("summary_description"), 600),
        url=DETAIL_URL.format(id=opp_id) if opp_id else "",
    )


def is_enabled() -> bool:
    return bool(os.environ.get(ENV_KEY))


class SimplerSource:
    name = "simpler.grants.gov"

    def __init__(self, *, api_key: str | None = None, timeout: float = 30.0,
                 client: httpx.Client | None = None):
        self._api_key = api_key or os.environ.get(ENV_KEY, "")
        self._timeout = timeout
        self._client = client

    def search(self, keyword: str, *, status: str = "posted", rows: int = 25) -> list[Opportunity]:
        if not self._api_key:
            raise RuntimeError(
                f"Simpler source needs {ENV_KEY}. Get a key at simpler.grants.gov "
                "(log in via Login.gov → Manage API Keys)."
            )
        body = {
            "query": keyword,
            "filters": {"opportunity_status": {"one_of": [status]}},
            "pagination": {
                "page_offset": 1,
                "page_size": rows,
                "sort_order": [{"order_by": "opportunity_id", "sort_direction": "ascending"}],
            },
        }
        headers = {"X-API-Key": self._api_key, "Content-Type": "application/json"}
        if self._client is not None:
            resp = self._client.post(SEARCH_URL, json=body, headers=headers)
        else:
            resp = httpx.post(SEARCH_URL, json=body, headers=headers, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json().get("data") or []
        return [normalize_opportunity(o) for o in data]

    def fetch(self, opportunity_id: str) -> Opportunity | None:
        # Detail endpoint not needed for Increment 2; search records are already rich.
        return None
