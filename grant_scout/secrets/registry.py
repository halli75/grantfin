"""Secret policy registry — declares which refs exist, their type, and the domains
each may be used on. Loaded from `vault_policy.toml`. Contains NO secret values.

This is what `list_secret_refs` exposes to Claude so it can build fill-plans by
reference without ever seeing a value.
"""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_POLICY = "vault_policy.toml"


@dataclass
class SecretPolicy:
    ref: str
    type: str
    allowed_domains: list[str]


class Registry:
    def __init__(self, policies: dict[str, SecretPolicy]):
        self._policies = policies

    @classmethod
    def load(cls, path: str | Path = DEFAULT_POLICY) -> "Registry":
        p = Path(path)
        if not p.exists():
            return cls({})
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
        policies = {}
        for ref, spec in raw.items():
            policies[ref] = SecretPolicy(
                ref=ref,
                type=str(spec.get("type", "")),
                allowed_domains=list(spec.get("allowed_domains", [])),
            )
        return cls(policies)

    def refs(self) -> list[dict]:
        """Public view for Claude — refs/types/domains, NO values."""
        return [
            {"ref": p.ref, "type": p.type, "allowed_domains": p.allowed_domains}
            for p in self._policies.values()
        ]

    def policy(self, ref: str) -> SecretPolicy | None:
        return self._policies.get(ref)

    def domain_allowed(self, ref: str, domain: str) -> bool:
        pol = self._policies.get(ref)
        if not pol:
            return False
        domain = (domain or "").lower()
        return any(fnmatch.fnmatch(domain, patt.lower()) for patt in pol.allowed_domains)
