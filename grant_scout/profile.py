"""Public org profile loader.

IMPORTANT (security boundary): this profile holds ONLY public / contextable
fields — mission, programs, geography, focus areas, budget band, 501(c) status,
EIN. It is safe to pass to the LLM. Secrets (bank, SSN, portal credentials) live
in a separate vault introduced in Increment 5 and never load here.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEFAULT_PROFILE_PATH = Path("org_profile.toml")

# Anything here would be a secret and must never live in the public profile.
_FORBIDDEN_KEYS = {
    "bank", "bank_account", "routing", "routing_number", "ssn", "ein_pin",
    "password", "credential", "credentials", "api_key", "secret", "token",
}


@dataclass
class OrgProfile:
    name: str = ""
    ein: str = ""                       # public per IRS 990 disclosure
    mission: str = ""
    programs: list[str] = field(default_factory=list)
    focus_areas: list[str] = field(default_factory=list)
    geography: list[str] = field(default_factory=list)   # e.g. ["US", "California"]
    org_type: str = ""                  # e.g. "501(c)(3)"
    budget_band: str = ""               # e.g. "$1M-$5M"
    populations_served: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)    # default search terms

    def to_dict(self) -> dict:
        return asdict(self)


def load_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> OrgProfile:
    """Load and validate the public org profile from TOML.

    Raises FileNotFoundError if missing and ValueError if a secret-looking key
    is present (defence-in-depth against secrets leaking into LLM context).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"No org profile at {p}. Copy org_profile.example.toml to {p} and fill it in."
        )
    raw = tomllib.loads(p.read_text(encoding="utf-8"))

    leaked = _FORBIDDEN_KEYS & {k.lower() for k in raw}
    if leaked:
        raise ValueError(
            f"Secret-looking keys are not allowed in the public profile: {sorted(leaked)}. "
            "Secrets belong in the vault (Increment 5), never here."
        )

    known = {f for f in OrgProfile.__dataclass_fields__}
    filtered = {k: v for k, v in raw.items() if k in known}
    return OrgProfile(**filtered)
