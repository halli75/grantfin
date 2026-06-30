from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from grant_scout.funders.three_sixty_giving import (
    ThreeSixtyGivingSource,
    filter_orgs,
    normalize_org,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _orgs() -> list[dict]:
    d = json.load(io.open(FIXTURES / "threesixty_orgs.json", encoding="utf-8"))
    return d["results"]


def test_normalize_org():
    f = normalize_org(_orgs()[0])
    assert f.source == "360giving"
    assert f.id == "GB-CHC-1111"
    assert f.location == "United Kingdom"
    assert f.url.endswith("GB-CHC-1111")


def test_filter_orgs_by_name():
    res = filter_orgs(_orgs(), "literacy")
    names = sorted(f.name for f in res)
    assert names == ["Childhood Literacy Foundation", "National Literacy Trust"]
    assert all(f.source == "360giving" for f in res)


def test_filter_orgs_empty_keyword_keeps_all():
    assert len(filter_orgs(_orgs(), "")) == 3


@pytest.mark.live
def test_360giving_live():
    # 1 page only, generic keyword likely to match something UK.
    res = ThreeSixtyGivingSource(max_pages=1).find("trust", rows=5)
    assert all(f.source == "360giving" for f in res)
