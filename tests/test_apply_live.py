"""LIVE end-to-end auto-apply against a local form using the real agent-browser CLI.

Proves the whole chain: open -> fill public + inject secret -> secret lands in the
field -> secret never appears in the Claude-facing report -> human submit gate.
Marked `browser` (needs Node + Chrome-for-Testing via agent-browser).
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest

from grant_scout.apply import AgentBrowser, Filler, SubmitGate
from grant_scout.apply.gate import CONFIRM_TOKEN
from grant_scout.secrets import InMemoryBackend, Registry, Resolver, Vault
from grant_scout.secrets.registry import SecretPolicy

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_BANK = "ACCT-000-LIVE-SECRET-42"


@pytest.fixture
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://localhost:{port}/apply_form.html"
    httpd.shutdown()


def _resolver():
    vault = Vault(InMemoryBackend())
    vault.set("org.bank_account", SECRET_BANK)
    reg = Registry({
        "org.bank_account": SecretPolicy("org.bank_account", "bank_account", ["localhost"]),
    })
    return Resolver(vault, reg)


@pytest.mark.browser
def test_full_apply_flow(server, tmp_path):
    br = AgentBrowser(session="gs-test", timeout=30.0)
    try:
        _run_flow(br, server, tmp_path)
    finally:
        br.close()


def _run_flow(br, server, tmp_path):
    br.open(server)

    # sanity: domain seen by the resolver path
    host = br.eval("location.hostname").strip().strip('"')
    assert host == "localhost"

    filler = Filler(br, _resolver())
    plan = [
        {"ref": "#org_name", "value": "Bright Futures Coalition", "field_type": "text"},
        {"ref": "#ein", "value": "12-3456789", "field_type": "text"},
        {"ref": "#bank_account", "value": "{{org.bank_account}}", "field_type": "bank_account"},
    ]
    report = filler.fill(plan, domain="localhost")

    # secret is masked in the report Claude would see
    assert SECRET_BANK not in str(report)
    assert any(r["kind"] == "secret" and r["status"] == "filled" for r in report)

    # but the secret actually landed in the field (test reads it directly)
    bank = br.eval("document.getElementById('bank_account').value").strip().strip('"')
    assert bank == SECRET_BANK
    org = br.eval("document.getElementById('org_name').value").strip().strip('"')
    assert org == "Bright Futures Coalition"

    # preview produces a screenshot
    gate = SubmitGate(br)
    prev = gate.preview(str(tmp_path / "preview.png"))
    assert Path(prev["preview"]).exists()

    # submit blocked without token...
    blocked = gate.submit("#submit_btn", confirm_token="")
    assert blocked["submitted"] is False
    assert br.eval("window.__submitted").strip() in ("false", '"false"', "False")

    # ...allowed with the human token
    ok = gate.submit("#submit_btn", confirm_token=CONFIRM_TOKEN)
    assert ok["submitted"] is True
    assert br.eval("window.__submitted").strip() in ("true", '"true"', "True")
