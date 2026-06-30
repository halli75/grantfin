"""Integration test for the scan pipeline tool (stubbed sources, no network)."""

from __future__ import annotations

from pathlib import Path

from grant_scout import server
from grant_scout.models import Opportunity


class _FakeSource:
    name = "fake"

    def __init__(self, opps):
        self._opps = opps

    def search(self, keyword, *, status="posted", rows=25):
        return self._opps


def _opp(oid, title=None):
    return Opportunity(id=oid, source="fake", title=title or f"Grant {oid}",
                       funder="F", close_date="2026-09-01")


def test_scan_twice_dedupes_and_writes_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # auto-CSV lands here
    db = str(tmp_path / "db.sqlite")

    monkeypatch.setattr(server, "_opportunity_sources",
                        lambda: [_FakeSource([_opp("1"), _opp("2")])])
    first = server.scan.fn("literacy", db_path=db)
    assert first["new_count"] == 2
    assert first["pipeline_size"] == 2
    assert Path(first["csv"]).exists()

    # identical second run -> nothing new
    second = server.scan.fn("literacy", db_path=db)
    assert second["new_count"] == 0
    assert second["pipeline_size"] == 2

    # a new id appears -> only that one returns
    monkeypatch.setattr(server, "_opportunity_sources",
                        lambda: [_FakeSource([_opp("2"), _opp("3")])])
    third = server.scan.fn("literacy", db_path=db)
    assert third["new_count"] == 1
    assert third["new"][0]["id"] == "3"


def test_dismiss_drops_from_open_pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = str(tmp_path / "db.sqlite")
    monkeypatch.setattr(server, "_opportunity_sources",
                        lambda: [_FakeSource([_opp("1"), _opp("2")])])
    server.scan.fn("x", db_path=db)
    server.dismiss.fn("fake", "1", db_path=db)
    again = server.scan.fn("x", db_path=db)
    assert again["pipeline_size"] == 1  # dismissed one excluded


def test_set_status_records_assessment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = str(tmp_path / "db.sqlite")
    monkeypatch.setattr(server, "_opportunity_sources",
                        lambda: [_FakeSource([_opp("1")])])
    server.scan.fn("x", db_path=db)
    res = server.set_status.fn("fake", "1", "matched", match="High", why="fits", db_path=db)
    assert res["updated"] is True
    rows = server.list_pipeline.fn(stage="matched", db_path=db)
    assert rows[0]["match"] == "High" and rows[0]["why"] == "fits"
