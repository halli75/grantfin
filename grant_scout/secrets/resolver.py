"""The resolver — the ONLY component that reads secret values from the vault.

Enforces the three guards before handing a value to the injection layer:
  1. ref must exist in the registry,
  2. the target domain must be on that ref's allow-list,
  3. the declared form field_type must match the ref's type.
Any violation raises — never silently returns a value.
"""

from __future__ import annotations

import re

from .registry import Registry
from .vault import Vault

_PLACEHOLDER = re.compile(r"^\{\{\s*([\w.\-]+)\s*\}\}$")


def is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER.match(value or ""))


def extract_ref(value: str) -> str | None:
    m = _PLACEHOLDER.match(value or "")
    return m.group(1) if m else None


def mask(value: str | None) -> str:
    """Masked representation safe to show Claude/logs. Never reveals the value.

    ASCII-only so it can't trip console/file encodings on any platform.
    """
    if not value:
        return ""
    return "********"


class ResolverError(Exception):
    pass


class Resolver:
    def __init__(self, vault: Vault, registry: Registry):
        self._vault = vault
        self._registry = registry

    def resolve(self, placeholder: str, domain: str, field_type: str = "") -> str:
        """Return the real secret value for a `{{ref}}` placeholder, or raise.

        domain: the host the value will be entered on (allow-list check).
        field_type: the form field's type as Claude classified it (must match ref type).
        """
        ref = extract_ref(placeholder)
        if not ref:
            raise ResolverError(f"Not a placeholder: {placeholder!r}")
        pol = self._registry.policy(ref)
        if pol is None:
            raise ResolverError(f"Unknown secret ref: {ref!r}")
        if not self._registry.domain_allowed(ref, domain):
            raise ResolverError(
                f"Secret {ref!r} is not allowed on domain {domain!r} "
                f"(allowed: {pol.allowed_domains})"
            )
        if field_type and field_type != pol.type:
            raise ResolverError(
                f"Field-type mismatch for {ref!r}: target field is {field_type!r} "
                f"but secret is {pol.type!r}"
            )
        value = self._vault.get(ref)
        if value is None:
            raise ResolverError(
                f"No value stored for {ref!r}. Set it with: grant-scout vault set {ref}"
            )
        return value
