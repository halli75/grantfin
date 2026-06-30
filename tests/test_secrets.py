"""SECURITY-FIRST tests for the secret core: vault, registry, resolver guards."""

from __future__ import annotations

import pytest

from grant_scout.secrets import InMemoryBackend, Registry, Resolver, Vault, mask
from grant_scout.secrets.registry import SecretPolicy
from grant_scout.secrets.resolver import ResolverError, extract_ref, is_placeholder


def _registry() -> Registry:
    return Registry({
        "org.ein": SecretPolicy("org.ein", "ein", ["grants.gov", "*.grants.gov"]),
        "org.bank_account": SecretPolicy("org.bank_account", "bank_account", ["grants.gov"]),
        "org.ssn": SecretPolicy("org.ssn", "ssn", ["grants.gov"]),
    })


def _resolver(values: dict) -> Resolver:
    vault = Vault(InMemoryBackend())
    for k, v in values.items():
        vault.set(k, v)
    return Resolver(vault, _registry())


def test_placeholder_helpers():
    assert is_placeholder("{{org.ein}}")
    assert is_placeholder("{{ org.ein }}")
    assert not is_placeholder("org.ein")
    assert extract_ref("{{org.bank_account}}") == "org.bank_account"
    assert extract_ref("plain") is None


def test_resolve_happy_path():
    r = _resolver({"org.ein": "12-3456789"})
    assert r.resolve("{{org.ein}}", "grants.gov", "ein") == "12-3456789"
    # wildcard domain match
    assert r.resolve("{{org.ein}}", "apply.grants.gov", "ein") == "12-3456789"


def test_resolve_refuses_off_allowlist_domain():
    r = _resolver({"org.bank_account": "000123"})
    with pytest.raises(ResolverError):
        r.resolve("{{org.bank_account}}", "evil.com", "bank_account")


def test_resolve_refuses_field_type_mismatch():
    # SSN value must not go into a field Claude classified as "email"
    r = _resolver({"org.ssn": "111-22-3333"})
    with pytest.raises(ResolverError):
        r.resolve("{{org.ssn}}", "grants.gov", "email")


def test_resolve_unknown_ref_raises():
    r = _resolver({})
    with pytest.raises(ResolverError):
        r.resolve("{{org.unknown}}", "grants.gov", "")


def test_resolve_missing_value_raises():
    r = _resolver({})  # registry knows org.ein but no value stored
    with pytest.raises(ResolverError):
        r.resolve("{{org.ein}}", "grants.gov", "ein")


def test_mask_never_reveals():
    assert "12-3456789" not in mask("12-3456789")
    assert mask("") == ""


def test_registry_refs_have_no_values():
    reg = _registry()
    blob = str(reg.refs())
    # the public view exposes refs/types/domains but obviously no secret values
    assert "org.ein" in blob and "ein" in blob
    assert "12-3456789" not in blob


def test_vault_inmemory_roundtrip():
    v = Vault(InMemoryBackend())
    v.set("k", "s3cret")
    assert v.get("k") == "s3cret"
    v.delete("k")
    assert v.get("k") is None
