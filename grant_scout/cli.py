"""Command-line entry point.

  grant-scout            -> run the MCP server (same as `python -m grant_scout`)
  grant-scout serve      -> run the MCP server
  grant-scout vault set <ref>   -> store a secret (prompted; never echoed, never via Claude)
  grant-scout vault list        -> list policy refs and whether a value is stored
  grant-scout vault rm <ref>    -> delete a stored secret

Secrets are entered by a HUMAN here via getpass — they never pass through the LLM.
"""

from __future__ import annotations

import getpass
import sys


def _vault_cmd(args: list[str]) -> int:
    from .secrets import Vault
    from .secrets.registry import Registry

    if not args or args[0] in ("-h", "--help"):
        print("usage: grant-scout vault <set|list|rm> [ref]")
        return 0
    sub = args[0]
    vault = Vault()  # KeyringBackend -> OS keychain

    if sub == "set":
        if len(args) < 2:
            print("usage: grant-scout vault set <ref>")
            return 2
        ref = args[1]
        value = getpass.getpass(f"Enter secret value for {ref} (input hidden): ")
        if not value:
            print("Aborted: empty value.")
            return 1
        vault.set(ref, value)
        print(f"Stored {ref} in the OS keychain.")
        return 0

    if sub == "rm":
        if len(args) < 2:
            print("usage: grant-scout vault rm <ref>")
            return 2
        vault.delete(args[1])
        print(f"Removed {args[1]}.")
        return 0

    if sub == "list":
        reg = Registry.load()
        for p in reg.refs():
            has = vault.get(p["ref"]) is not None
            mark = "set" if has else "MISSING"
            print(f"  {p['ref']:30} type={p['type']:14} [{mark}] domains={p['allowed_domains']}")
        return 0

    print(f"Unknown vault command: {sub}")
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "vault":
        return _vault_cmd(argv[1:])
    if not argv or argv[0] == "serve":
        from .server import run
        run()
        return 0
    print(f"Unknown command: {argv[0]}\nusage: grant-scout [serve|vault ...]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
