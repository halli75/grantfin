from grant_scout import store


def _opp(source="grants.gov", oid="1", title="A", **kw):
    d = {"source": source, "id": oid, "title": title, "funder": "X", "close_date": "2026-09-01"}
    d.update(kw)
    return d


def test_upsert_new_returns_only_new(tmp_path):
    conn = store.connect(tmp_path / "db.sqlite")
    first = store.upsert_new(conn, [_opp(oid="1"), _opp(oid="2")])
    assert {r["id"] for r in first} == {"1", "2"}
    assert all(r["stage"] == "new" for r in first)
    # cross-run dedupe: identical second run inserts nothing
    second = store.upsert_new(conn, [_opp(oid="1"), _opp(oid="2")])
    assert second == []
    # only a genuinely new id comes back
    third = store.upsert_new(conn, [_opp(oid="2"), _opp(oid="3")])
    assert {r["id"] for r in third} == {"3"}


def test_upsert_skips_junk_rows(tmp_path):
    conn = store.connect(tmp_path / "db.sqlite")
    new = store.upsert_new(conn, [{"title": "no id or source"}, _opp(oid="9")])
    assert {r["id"] for r in new} == {"9"}


def test_set_stage_and_assessment_persist(tmp_path):
    conn = store.connect(tmp_path / "db.sqlite")
    store.upsert_new(conn, [_opp(oid="1")])
    ok = store.set_stage(conn, "grants.gov", "1", "matched", match="High", why="fits")
    assert ok
    row = store.get(conn, "grants.gov", "1")
    assert row["stage"] == "matched" and row["match"] == "High" and row["why"] == "fits"
    # unknown id -> False, no crash
    assert store.set_stage(conn, "grants.gov", "999", "saved") is False


def test_invalid_stage_rejected(tmp_path):
    conn = store.connect(tmp_path / "db.sqlite")
    store.upsert_new(conn, [_opp(oid="1")])
    try:
        store.set_stage(conn, "grants.gov", "1", "bogus")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_list_filters_by_stage(tmp_path):
    conn = store.connect(tmp_path / "db.sqlite")
    store.upsert_new(conn, [_opp(oid="1"), _opp(oid="2")])
    store.set_stage(conn, "grants.gov", "1", "dismissed")
    assert len(store.list_opportunities(conn)) == 2
    assert len(store.list_opportunities(conn, stage="dismissed")) == 1
    assert len(store.list_opportunities(conn, stage="new")) == 1


def test_persistence_across_reopen(tmp_path):
    p = tmp_path / "db.sqlite"
    conn = store.connect(p)
    store.upsert_new(conn, [_opp(oid="1")])
    store.set_stage(conn, "grants.gov", "1", "saved")
    conn.close()
    # reopen the file -> rows survive (simulates server restart)
    conn2 = store.connect(p)
    row = store.get(conn2, "grants.gov", "1")
    assert row is not None and row["stage"] == "saved"
