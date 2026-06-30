"""Normalised grant opportunity — the common shape every source maps into."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Opportunity:
    """A single grant opportunity, normalised across all sources.

    `match` and `why` are intentionally left blank by the data layer — they are
    filled by Claude Code (the agent loop) when it reasons over the org profile.
    """

    id: str
    source: str               # e.g. "grants.gov"
    title: str
    funder: str               # agency / foundation name
    status: str = ""          # posted / forecasted / closed ...
    open_date: str = ""       # ISO
    close_date: str = ""      # ISO (the deadline)
    award_floor: str = ""     # raw, formatted at export time
    award_ceiling: str = ""
    est_funding: str = ""
    eligibility: str = ""
    description: str = ""
    cfda: str = ""
    url: str = ""
    # Agent-supplied, optional:
    match: str = ""           # High / Medium / Low
    why: str = ""             # one-sentence rationale
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    # (Funder is defined below — kept in this module so all normalised shapes live together.)

    def enriched_with(self, detail: "Opportunity") -> "Opportunity":
        """Return a copy where blank fields are filled from `detail`.

        Used to combine a lightweight search hit (which has the clean status) with
        a fetched detail record (which has award amounts and eligibility) without
        either clobbering the other's good values.
        """
        merged = self.to_dict()
        for key, value in detail.to_dict().items():
            if value and not merged.get(key):
                merged[key] = value
        return Opportunity(**merged)


@dataclass
class Funder:
    """A grantmaker / foundation to prospect — distinct from an apply-able Opportunity.

    Produced by funder-intelligence sources (ProPublica 990, 360Giving). Exported to
    a SEPARATE funders CSV so it never clutters the opportunities list.
    """

    id: str                   # EIN / org id
    source: str               # e.g. "propublica" / "360giving"
    name: str
    location: str = ""        # "City, ST" or country
    focus: str = ""           # human-readable cause/category
    recent_grants: str = ""   # optional: recent giving summary
    url: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
