"""Unit tests for the Grants.gov normalisers (fixture-based, no network)
plus one live smoke test marked @pytest.mark.live."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from grant_scout.sources.grants_gov import (
    GrantsGovSource,
    normalize_detail,
    normalize_hit,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_normalize_hit_maps_core_fields():
    data = _load("search2_education.json")["data"]
    hits = data["oppHits"]
    opp = normalize_hit(hits[0])
    assert opp.source == "grants.gov"
    assert opp.id  # non-empty
    assert opp.title
    assert opp.funder
    assert opp.status == "posted"
    # openDate "06/24/2021" -> ISO
    if hits[0].get("openDate"):
        assert opp.open_date.count("-") == 2
    assert opp.url.endswith(opp.id)


def test_normalize_hit_handles_blank_close_date():
    # A hit with an empty closeDate must not crash and must yield "".
    opp = normalize_hit({"id": "1", "title": "T", "agency": "A", "oppStatus": "posted",
                         "openDate": "01/02/2020", "closeDate": "", "cfdaList": []})
    assert opp.close_date == ""
    assert opp.open_date == "2020-01-02"


def test_normalize_detail_extracts_award_and_eligibility():
    data = _load("fetch_334326.json")["data"]
    opp = normalize_detail(data)
    assert opp.id == "334326"
    assert opp.title
    # funder must be the clean agency name, never the contact person, never multi-line
    assert opp.funder == "U.S. National Science Foundation"
    assert "\n" not in opp.funder
    assert opp.award_floor == "100000"
    assert opp.award_ceiling == "3500000"
    assert "2026-09-01" == opp.close_date           # responseDate "Sep 01, 2026 ..."
    assert opp.eligibility                            # non-empty applicantEligibilityDesc
    assert opp.cfda                                   # "47.076"


@pytest.mark.live
def test_search_live():
    src = GrantsGovSource()
    results = src.search("education", rows=3)
    assert len(results) >= 1
    assert all(r.source == "grants.gov" for r in results)
    assert all(r.title for r in results)


@pytest.mark.live
def test_fetch_live():
    src = GrantsGovSource()
    detail = src.fetch("334326")
    assert detail is not None
    assert detail.id == "334326"
