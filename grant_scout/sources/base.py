"""Common interface every grant source implements.

Increment 1 ships only Grants.gov; the interface exists now so Increment 2
(Simpler, ProPublica, 360Giving, EU SEDIA) slots in without touching the server.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Opportunity


class GrantSource(ABC):
    #: short, stable identifier shown in the CSV "Source" column
    name: str = "base"

    @abstractmethod
    def search(self, keyword: str, *, status: str = "posted", rows: int = 25) -> list[Opportunity]:
        """Return lightweight opportunities matching `keyword`."""

    @abstractmethod
    def fetch(self, opportunity_id: str) -> Opportunity | None:
        """Return a fully-enriched opportunity (award amounts, eligibility, ...)."""
