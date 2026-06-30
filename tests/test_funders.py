"""ProPublica normaliser (fixture) + funders CSV tests, plus one live smoke."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from grant_scout.csv_export import FUNDER_COLUMNS, write_funders_csv
from grant_scout.funders.propublica import ProPublicaSource, normalize_org

FIXTURES = Path(__file__).parent / "fixtures"


def _orgs() -> list[dict]:
    d = json.load(io.open(FIXTURES / "propublica_literacy.json", encoding="utf-8"))
    return d["organizations"]


def test_normalize_org():
    f = normalize_org(_orgs()[0])
    assert f.source == "propublica"
    assert f.id                       # EIN
    assert f.name
    assert f.url.endswith(f.id)
    # NTEE "B01" -> Education focus, location "City, ST"
    assert "Education" in f.focus
    assert "," in f.location


def test_normalize_org_blank_ntee():
    f = normalize_org({"ein": 1, "name": "X", "city": "A", "state": "B"})
    assert f.focus == ""
    assert f.location == "A, B"


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_funders_csv_columns_and_sort(tmp_path):
    funders = [
        {"name": "Zeta Fund", "focus": "Education", "location": "NY", "source": "propublica", "id": "1", "url": "u1"},
        {"name": "Alpha Fund", "focus": "Health", "location": "CA", "source": "propublica", "id": "2", "url": "u2"},
    ]
    out = write_funders_csv(funders, tmp_path / "f.csv")
    rows = _read(out)
    assert list(rows[0].keys()) == FUNDER_COLUMNS
    assert [r["Funder"] for r in rows] == ["Alpha Fund", "Zeta Fund"]  # name-sorted
    assert rows[0]["Focus"] == "Health"


@pytest.mark.live
def test_propublica_live():
    res = ProPublicaSource().find("literacy", rows=3)
    assert len(res) >= 1
    assert all(r.source == "propublica" and r.name for r in res)
