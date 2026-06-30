"""Secret value storage. Values live in the OS keychain, never on disk in plaintext.

ponytail: thin wrapper over `keyring`; a dict backend for tests. No 1Password/age —
deferred. The vault is written ONLY by the human CLI (`grant-scout vault set`), never
by an MCP tool, so values never pass through Claude even at setup time.
"""

from __future__ import annotations

from typing import Protocol

SERVICE = "grant-scout"


class VaultBackend(Protocol):
    def get(self, ref: str) -> str | None: ...
    def set(self, ref: str, value: str) -> None: ...
    def delete(self, ref: str) -> None: ...


class InMemoryBackend:
    """Test/ephemeral backend. Never used for real secrets."""

    def __init__(self) -> None:
        self._d: dict[str, str] = {}

    def get(self, ref: str) -> str | None:
        return self._d.get(ref)

    def set(self, ref: str, value: str) -> None:
        self._d[ref] = value

    def delete(self, ref: str) -> None:
        self._d.pop(ref, None)


class KeyringBackend:
    """Real backend: OS keychain via `keyring` (Win Credential Manager / macOS / libsecret)."""

    def __init__(self, service: str = SERVICE) -> None:
        import keyring  # imported lazily so tests don't need a keychain
        self._keyring = keyring
        self._service = service

    def get(self, ref: str) -> str | None:
        return self._keyring.get_password(self._service, ref)

    def set(self, ref: str, value: str) -> None:
        self._keyring.set_password(self._service, ref, value)

    def delete(self, ref: str) -> None:
        try:
            self._keyring.delete_password(self._service, ref)
        except Exception:
            pass


class Vault:
    def __init__(self, backend: VaultBackend | None = None) -> None:
        self._backend = backend or KeyringBackend()

    def get(self, ref: str) -> str | None:
        return self._backend.get(ref)

    def set(self, ref: str, value: str) -> None:
        if not ref or value is None:
            raise ValueError("ref and value are required")
        self._backend.set(ref, value)

    def delete(self, ref: str) -> None:
        self._backend.delete(ref)
