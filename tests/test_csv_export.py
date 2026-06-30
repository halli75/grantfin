import csv
from pathlib import Path

from grant_scout.csv_export import COLUMNS, write_grants_csv


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_csv_columns_and_formatting(tmp_path):
    opps = [
        {
            "title": "Rural Literacy Grant", "funder": "NSF", "source": "grants.gov",
            "status": "posted", "close_date": "2026-09-01",
            "award_floor": "100000", "award_ceiling": "3500000",
            "eligibility": "Nonprofits only", "url": "https://x/1",
            "match": "High", "why": "Direct fit for rural literacy programs.",
        },
    ]
    out = write_grants_csv(opps, tmp_path / "g.csv")
    rows = _read(out)
    assert list(rows[0].keys()) == COLUMNS
    r = rows[0]
    assert r["Grant Title"] == "Rural Literacy Grant"
    assert r["Award Amount"] == "$100,000–$3,500,000"
    assert r["Match"] == "High"
    assert r["Deadline"] == "2026-09-01"
    assert r["Link"] == "https://x/1"


def test_csv_sorts_by_deadline_blanks_last(tmp_path):
    opps = [
        {"title": "C", "close_date": ""},
        {"title": "A", "close_date": "2026-01-01"},
        {"title": "B", "close_date": "2026-06-01"},
    ]
    out = write_grants_csv(opps, tmp_path / "g.csv")
    titles = [r["Grant Title"] for r in _read(out)]
    assert titles == ["A", "B", "C"]


def test_csv_prefers_explicit_award_amount(tmp_path):
    opps = [{"title": "X", "award_amount": "$1,000,000", "award_floor": "5"}]
    out = write_grants_csv(opps, tmp_path / "g.csv")
    assert _read(out)[0]["Award Amount"] == "$1,000,000"
