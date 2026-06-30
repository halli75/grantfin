"""Deduplicate opportunities merged from multiple sources."""

from __future__ import annotations

import re


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def dedupe_opportunities(opps: list[dict]) -> list[dict]:
    """Drop duplicates, keeping first seen.

    Two-level key: exact `(source, id)`, then a cross-source `(title, funder)`
    normalized key so the same grant surfaced by two sources collapses to one row.
    """
    seen_ids: set[tuple] = set()
    seen_titles: set[tuple] = set()
    out: list[dict] = []
    for o in opps:
        id_key = (o.get("source", ""), str(o.get("id", "")))
        title_key = (_norm(o.get("title", "")), _norm(o.get("funder", "")))
        if id_key in seen_ids:
            continue
        if title_key[0] and title_key in seen_titles:
            continue
        seen_ids.add(id_key)
        if title_key[0]:
            seen_titles.add(title_key)
        out.append(o)
    return out
