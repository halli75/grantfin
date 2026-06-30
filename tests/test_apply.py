"""Apply-layer tests with a mocked agent-browser runner.

The load-bearing security assertion: a secret value reaches the browser via STDIN
and never appears in the command argv (which would leak to other local processes,
shell history, or logs).
"""

from __future__ import annotations

import pytest

from grant_scout.apply.browser import AgentBrowser, build_inject_js
from grant_scout.apply.filler import Filler
from grant_scout.apply.gate import CONFIRM_TOKEN, SubmitGate
from grant_scout.secrets import InMemoryBackend, Registry, Resolver, Vault
from grant_scout.secrets.registry import SecretPolicy


class _RecordingRunner:
    """Captures every (args, stdin) the browser would have run."""

    def __init__(self):
        self.calls = []

    def __call__(self, args, input_bytes):
        self.calls.append((args, input_bytes))
        return 0, "ok", ""


def _browser():
    rec = _RecordingRunner()
    return AgentBrowser(runner=rec), rec


def _resolver(values):
    vault = Vault(InMemoryBackend())
    for k, v in values.items():
        vault.set(k, v)
    reg = Registry({
        "org.ein": SecretPolicy("org.ein", "ein", ["grants.gov"]),
        "org.bank_account": SecretPolicy("org.bank_account", "bank_account", ["grants.gov"]),
    })
    return Resolver(vault, reg)


SECRET = "SUPER-SECRET-9999"


def test_secret_goes_via_stdin_never_argv():
    br, rec = _browser()
    br.inject_secret("@e5", SECRET)
    # two calls: click (focus) then eval --stdin
    all_args_text = " ".join(" ".join(a) for a, _ in rec.calls)
    assert SECRET not in all_args_text, "secret leaked into argv!"
    # the secret must be present in some stdin payload
    stdins = b"".join(s or b"" for _, s in rec.calls)
    assert SECRET.encode() in stdins
    # and the eval call used --stdin
    assert any("--stdin" in a for a, _ in rec.calls)


def test_build_inject_js_embeds_and_escapes():
    js = build_inject_js('a"b\n')
    assert "activeElement" in js
    assert "\\n" in js or "\\u000a" in js  # newline JSON-escaped, not raw


def test_filler_public_via_argv_secret_via_stdin():
    br, rec = _browser()
    f = Filler(br, _resolver({"org.ein": "12-3456789"}))
    plan = [
        {"ref": "@e3", "value": "Bright Futures", "field_type": "text"},
        {"ref": "@e4", "value": "{{org.ein}}", "field_type": "ein"},
    ]
    report = f.fill(plan, domain="grants.gov")
    assert report[0] == {"ref": "@e3", "kind": "public", "status": "filled", "value": "Bright Futures"}
    assert report[1]["kind"] == "secret" and report[1]["status"] == "filled"
    assert "12-3456789" not in str(report)            # masked in report
    argv_text = " ".join(" ".join(a) for a, _ in rec.calls)
    assert "12-3456789" not in argv_text              # secret never in argv


def test_filler_blocks_off_allowlist_domain():
    br, rec = _browser()
    f = Filler(br, _resolver({"org.bank_account": "000111222"}))
    report = f.fill([{"ref": "@e5", "value": "{{org.bank_account}}", "field_type": "bank_account"}],
                    domain="evil.com")
    assert report[0]["status"] == "blocked"
    # nothing was typed/injected for the blocked field
    assert all("000111222" not in (str(a) + str(s)) for a, s in rec.calls)


def test_submit_gate_blocks_without_token():
    br, rec = _browser()
    gate = SubmitGate(br)
    res = gate.submit("@e2", confirm_token="")
    assert res["submitted"] is False
    assert not rec.calls  # never clicked submit


def test_submit_gate_allows_with_token():
    br, rec = _browser()
    gate = SubmitGate(br)
    res = gate.submit("@e2", confirm_token=CONFIRM_TOKEN)
    assert res["submitted"] is True
    assert any(a[:2] == ["click", "@e2"] or a[0] == "click" for a, _ in rec.calls)
