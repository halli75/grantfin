from grant_scout.format import (
    format_award_range,
    format_money,
    iso_date,
    parse_date,
    truncate,
)


def test_parse_date_formats():
    assert parse_date("09/01/2026").isoformat() == "2026-09-01"
    assert parse_date("Sep 01, 2026 12:00:00 AM EDT").isoformat() == "2026-09-01"
    assert parse_date("Sep 01, 2026").isoformat() == "2026-09-01"
    assert parse_date("2026-09-01").isoformat() == "2026-09-01"


def test_parse_date_blank_and_garbage():
    assert parse_date("") is None
    assert parse_date(None) is None
    assert parse_date("not a date") is None


def test_iso_date():
    assert iso_date("09/01/2026") == "2026-09-01"
    assert iso_date("") == ""


def test_format_money():
    assert format_money(100000) == "$100,000"
    assert format_money("3500000") == "$3,500,000"
    assert format_money(0) == ""
    assert format_money(None) == ""
    assert format_money("") == ""


def test_format_award_range():
    assert format_award_range(100000, 3500000) == "$100,000–$3,500,000"
    assert format_award_range(0, 3500000) == "$3,500,000"
    assert format_award_range(50000, 50000) == "$50,000"
    assert format_award_range(None, None) == ""


def test_truncate():
    assert truncate("  a   b  ") == "a b"
    long = "x" * 400
    out = truncate(long, 100)
    assert len(out) == 100 and out.endswith("…")
    assert truncate(None) == ""
