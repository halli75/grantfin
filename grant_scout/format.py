"""Pure formatting helpers for human-readable, end-user-facing output.

Kept dependency-free and side-effect-free so they are trivial to unit test.
"""

from __future__ import annotations

import re
from datetime import date, datetime

# Grants.gov hands us dates in a few shapes. Normalise everything to ISO
# (YYYY-MM-DD) so the CSV sorts correctly and reads the same everywhere.
_DATE_FORMATS = (
    "%m/%d/%Y",            # 09/01/2026  (search2 oppHits)
    "%b %d, %Y %I:%M:%S %p %Z",  # Sep 01, 2026 12:00:00 AM EDT (detail responseDate)
    "%b %d, %Y",          # Sep 01, 2026
    "%Y-%m-%d",           # already ISO
)


def parse_date(value: str | None) -> date | None:
    """Best-effort parse of the date strings Grants.gov returns. None if blank/unknown."""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    # Strip a trailing timezone abbrev the platform's strptime can't read (e.g. EDT).
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # Last resort: pull a leading "Mon DD, YYYY" or "MM/DD/YYYY" out of a longer string.
    m = re.match(r"([A-Za-z]{3} \d{1,2}, \d{4})", text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%b %d, %Y").date()
        except ValueError:
            pass
    return None


def iso_date(value: str | None) -> str:
    """Human-readable ISO date string, or '' when unknown."""
    d = parse_date(value)
    return d.isoformat() if d else ""


def epoch_ms_to_iso(value) -> str:
    """Convert epoch milliseconds (int or numeric str) to an ISO date. '' if invalid."""
    if value in (None, "", 0):
        return ""
    try:
        ms = int(value)
    except (ValueError, TypeError):
        return ""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def next_upcoming_iso(epoch_ms_list, today_iso: str | None = None) -> str:
    """Given a list of epoch-ms deadlines, return the soonest one still in the future
    as ISO (falls back to the latest date if all are past). '' if none."""
    if not epoch_ms_list:
        return ""
    dates = sorted(d for d in (epoch_ms_to_iso(v) for v in epoch_ms_list) if d)
    if not dates:
        return ""
    if today_iso is None:
        today_iso = date.today().isoformat()
    future = [d for d in dates if d >= today_iso]
    return future[0] if future else dates[-1]


def format_money(amount) -> str:
    """Format an integer/str dollar amount as $1,234,567. '' for missing/zero-less input."""
    if amount in (None, "", 0, "0"):
        return ""
    try:
        n = int(float(str(amount).replace(",", "").replace("$", "").strip()))
    except (ValueError, TypeError):
        return ""
    return f"${n:,}"


def format_award_range(floor, ceiling) -> str:
    """Combine award floor/ceiling into one readable cell.

    $100,000–$3,500,000 when both present; a single value when only one is;
    '' when neither is known.
    """
    lo = format_money(floor)
    hi = format_money(ceiling)
    if lo and hi:
        return lo if lo == hi else f"{lo}–{hi}"
    return lo or hi or ""


def truncate(text: str | None, limit: int = 280) -> str:
    """Collapse whitespace and cap length so eligibility text stays CSV-friendly."""
    if not text:
        return ""
    flat = re.sub(r"\s+", " ", str(text)).strip()
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"
