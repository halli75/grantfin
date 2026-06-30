"""Common interface for funder-intelligence sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Funder


class FunderSource(ABC):
    name: str = "base"

    @abstractmethod
    def find(self, keyword: str, *, location: str = "", rows: int = 25) -> list[Funder]:
        """Return funders/grantmakers relevant to `keyword` (a cause/program area)."""
