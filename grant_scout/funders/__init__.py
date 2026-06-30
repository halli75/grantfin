"""Funder-intelligence sources — historical grants / org data for prospecting.

Distinct from `sources/` (apply-able opportunities). Output goes to the separate
funders CSV, never the opportunities CSV.
"""

from .base import FunderSource
from .propublica import ProPublicaSource
from .three_sixty_giving import ThreeSixtyGivingSource

__all__ = ["FunderSource", "ProPublicaSource", "ThreeSixtyGivingSource"]
