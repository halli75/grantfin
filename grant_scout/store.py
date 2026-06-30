"""SQLite pipeline store — persistent, deduped-across-runs opportunity tracking.

ponytail: stdlib sqlite3, one table, no ORM/migrations. Columns are derived from
the Opportunity dataclass so the schema can't drift from the model.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Opportunity

DEFAULT_DB = "grant_scout.db"
STAGES = ("new", "matched", "saved", "dismissed", "applying", "applied")

# table columns = every Opportunity field + pipeline bookkeeping
_OPP_FIELDS = list(Opportunity.__dataclass_fields__)
_EXTRA = ["stage", "first_seen", "last_seen"]
_COLUMNS = _OPP_FIELDS + _EXTRA
_COL_SQL = ", ".join(f'"{c}"' for c in _COLUMNS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cols = ", ".join(f'"{c}" TEXT' for c in _COLUMNS)
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS opportunities ({cols}, "
        f"PRIMARY KEY (source, id))"
    )
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def upsert_new(conn: sqlite3.Connection, opps: list[dict]) -> list[dict]:
    """Insert opportunities not seen before (stage=new); bump last_seen on existing.

    Returns only the rows that were newly inserted — this is the cross-run dedupe.
    """
    now = _now()
    new_rows: list[dict] = []
    for opp in opps:
        source, oid = opp.get("source", ""), str(opp.get("id", ""))
        if not source or not oid:
            continue  # ponytail: skip junk rows, don't raise — a bad source row shouldn't kill a scan
        exists = conn.execute(
            "SELECT 1 FROM opportunities WHERE source=? AND id=?", (source, oid)
        ).fetchone()
        if exists:
            conn.execute(
                "UPDATE opportunities SET last_seen=? WHERE source=? AND id=?",
                (now, source, oid),
            )
            continue
        record = {c: "" for c in _COLUMNS}
        record.update({k: opp.get(k, "") for k in _OPP_FIELDS})
        record["id"] = oid
        record["stage"] = opp.get("stage") or "new"
        record["first_seen"] = now
        record["last_seen"] = now
        placeholders = ", ".join("?" for _ in _COLUMNS)
        conn.execute(
            f"INSERT INTO opportunities ({_COL_SQL}) VALUES ({placeholders})",
            [record[c] for c in _COLUMNS],
        )
        new_rows.append(record)
    conn.commit()
    return new_rows


def list_opportunities(conn: sqlite3.Connection, stage: str | None = None) -> list[dict]:
    if stage:
        cur = conn.execute(
            "SELECT * FROM opportunities WHERE stage=? ORDER BY close_date", (stage,)
        )
    else:
        cur = conn.execute("SELECT * FROM opportunities ORDER BY close_date")
    return [_row_to_dict(r) for r in cur.fetchall()]


def get(conn: sqlite3.Connection, source: str, oid: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM opportunities WHERE source=? AND id=?", (source, str(oid))
    ).fetchone()
    return _row_to_dict(row) if row else None


def set_stage(conn: sqlite3.Connection, source: str, oid: str, stage: str,
              *, match: str | None = None, why: str | None = None,
              notes: str | None = None) -> bool:
    """Update an opportunity's pipeline stage (and optional assessment). False if not found."""
    if stage not in STAGES:
        raise ValueError(f"Unknown stage '{stage}'. Valid: {STAGES}")
    sets = ["stage=?", "last_seen=?"]
    vals: list = [stage, _now()]
    for col, v in (("match", match), ("why", why), ("notes", notes)):
        if v is not None:
            sets.append(f"{col}=?")
            vals.append(v)
    vals += [source, str(oid)]
    cur = conn.execute(
        f"UPDATE opportunities SET {', '.join(sets)} WHERE source=? AND id=?", vals
    )
    conn.commit()
    return cur.rowcount > 0
