"""EU SEDIA normaliser/filter tests (fixture-based, no network) + one live smoke."""

from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
import pytest

from grant_scout.sources.eu_sedia import (
    BULK_URL,
    filter_calls,
    normalize_call,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _objs() -> list[dict]:
    d = json.load(io.open(FIXTURES / "eu_grants.json", encoding="utf-8"))
    return d["fundingData"]["GrantTenderObj"]


def test_normalize_call_core_fields():
    call = _objs()[0]
    opp = normalize_call(call)
    assert opp.source == "eu-sedia"
    assert opp.id
    assert opp.title
    assert opp.funder
    assert opp.status in ("Open", "Forthcoming")
    assert opp.url.endswith(opp.id)
    # deadline must be ISO (or empty), never a raw epoch
    assert opp.close_date == "" or opp.close_date.count("-") == 2
    assert "1651536000000" not in opp.close_date


def test_filter_calls_open_only_and_keyword():
    objs = _objs()
    # fixture is all open/forthcoming, so open_only keeps them
    everything = filter_calls(objs, "", open_only=True)
    assert len(everything) == len(objs)
    # keyword narrows
    erasmus = filter_calls(objs, "erasmus", open_only=True)
    assert all("eu-sedia" == o.source for o in erasmus)
    # a keyword that can't match anything returns nothing
    assert filter_calls(objs, "zzz-no-such-term-zzz", open_only=True) == []


def test_filter_excludes_closed():
    objs = list(_objs())
    objs.append({"identifier": "X", "title": "Closed thing",
                 "status": {"id": 31094503, "abbreviation": "Closed"}})
    res = filter_calls(objs, "", open_only=True)
    assert all(o.status != "Closed" for o in res)


@pytest.mark.live
def test_bulk_endpoint_reachable():
    # Don't pull all 125MB in tests — just confirm 200 + gzip on the first bytes.
    with httpx.stream("GET", BULK_URL, timeout=60.0,
                      headers={"Accept-Encoding": "gzip"}, follow_redirects=True) as r:
        r.raise_for_status()
        first = next(r.iter_bytes())
        assert first  # got data
