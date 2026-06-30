"""Clean, end-user-facing CSV export.

The person running Grant Scout is a nonprofit grant-seeker, not a developer.
This module turns opportunity rows into a tidy spreadsheet they open in Excel or
Google Sheets — one row per grant, only decision-relevant columns, deadline-sorted,
no internal IDs or raw API noise.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from .format import format_award_range, truncate

# Column order is the contract with the user. Keep it stable and readable.
COLUMNS = [
    "Grant Title",
    "Funder",
    "Source",
    "Match",
    "Why It Matches",
    "Award Amount",
    "Deadline",
    "Eligibility",
    "Status",
    "Link",
    "Notes",
]

# Far-future sentinel so blank deadlines sort to the bottom, not the top.
_NO_DEADLINE = "9999-12-31"


def _row_from(opp: dict) -> dict:
    """Map a normalised opportunity dict to the user-facing column set."""
    award = opp.get("award_amount") or format_award_range(
        opp.get("award_floor"), opp.get("award_ceiling")
    )
    return {
        "Grant Title": opp.get("title", ""),
        "Funder": opp.get("funder", ""),
        "Source": opp.get("source", ""),
        "Match": opp.get("match", ""),
        "Why It Matches": truncate(opp.get("why", ""), 200),
        "Award Amount": award,
        "Deadline": opp.get("close_date", ""),
        "Eligibility": truncate(opp.get("eligibility", ""), 240),
        "Status": opp.get("status", ""),
        "Link": opp.get("url", ""),
        "Notes": opp.get("notes", ""),
    }


def _deadline_key(row: dict) -> str:
    return row.get("Deadline") or _NO_DEADLINE


def default_path() -> Path:
    """grants_YYYY-MM-DD.csv in the current working directory."""
    return Path(f"grants_{date.today().isoformat()}.csv")


def write_grants_csv(opportunities: list[dict], path: str | Path | None = None) -> Path:
    """Write opportunities to a clean, deadline-sorted CSV. Returns the path written.

    Accepts a list of normalised opportunity dicts (from Opportunity.to_dict(),
    optionally with agent-supplied `match`/`why`/`notes`). UTF-8 with BOM so Excel
    renders accented characters correctly.
    """
    out = Path(path) if path else default_path()
    rows = [_row_from(o) for o in opportunities]
    rows.sort(key=_deadline_key)

    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return out


# --- Funder-intelligence CSV (separate from opportunities, kept clean) ---

FUNDER_COLUMNS = [
    "Funder",
    "Focus",
    "Location",
    "Recent Grants",
    "Source",
    "EIN / ID",
    "Link",
    "Notes",
]


def _funder_row_from(f: dict) -> dict:
    return {
        "Funder": f.get("name", ""),
        "Focus": f.get("focus", ""),
        "Location": f.get("location", ""),
        "Recent Grants": f.get("recent_grants", ""),
        "Source": f.get("source", ""),
        "EIN / ID": f.get("id", ""),
        "Link": f.get("url", ""),
        "Notes": f.get("notes", ""),
    }


def default_funders_path() -> Path:
    return Path(f"funders_{date.today().isoformat()}.csv")


def write_funders_csv(funders: list[dict], path: str | Path | None = None) -> Path:
    """Write funder/grantmaker prospects to a clean CSV (name-sorted). Returns the path."""
    out = Path(path) if path else default_funders_path()
    rows = [_funder_row_from(f) for f in funders]
    rows.sort(key=lambda r: r["Funder"].lower())

    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FUNDER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return out
