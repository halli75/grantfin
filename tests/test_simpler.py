from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from grant_scout.sources.simpler import (
    SimplerSource,
    is_enabled,
    normalize_opportunity,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalize_opportunity():
    data = json.load(io.open(FIXTURES / "simpler_search.json", encoding="utf-8"))
    op = normalize_opportunity(data["data"][0])
    assert op.source == "simpler.grants.gov"
    assert op.id == "abc-123"
    assert op.title == "Rural Literacy Innovation Grants"
    assert op.funder == "Department of Education"
    assert op.status == "posted"
    assert op.open_date == "2026-05-01"
    assert op.close_date == "2026-09-15"
    assert op.award_floor == "50000"
    assert op.award_ceiling == "500000"
    assert op.eligibility.startswith("Nonprofit")
    assert op.url.endswith("abc-123")


def test_search_without_key_raises(monkeypatch):
    monkeypatch.delenv("SIMPLER_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        SimplerSource(api_key="").search("literacy")


def test_is_enabled_reflects_env(monkeypatch):
    monkeypatch.delenv("SIMPLER_API_KEY", raising=False)
    assert is_enabled() is False
    monkeypatch.setenv("SIMPLER_API_KEY", "x")
    assert is_enabled() is True


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("SIMPLER_API_KEY"), reason="no SIMPLER_API_KEY set")
def test_simpler_live():
    res = SimplerSource().search("education", rows=3)
    assert all(o.source == "simpler.grants.gov" for o in res)
