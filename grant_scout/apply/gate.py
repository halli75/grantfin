"""Human-in-the-loop submit gate.

Grant submissions are irreversible and often legally attested, so submit is NEVER
automatic. The agent must `preview` (screenshot for the human), and only a human
who has reviewed it supplies the exact confirm token. (First-use-on-a-new-domain is
already gated upstream: a domain not in the secret's allow-list is refused by the
resolver — the human must add it to vault_policy.toml.)
"""

from __future__ import annotations

from .browser import AgentBrowser

# The human types this verbatim after reviewing the preview. Claude must not invent it.
CONFIRM_TOKEN = "I-REVIEWED-AND-APPROVE-SUBMIT"


class SubmitGate:
    def __init__(self, browser: AgentBrowser):
        self._browser = browser

    def preview(self, path: str = "apply_preview.png") -> dict:
        """Screenshot the filled form for the human to review before submit."""
        self._browser.screenshot(path)
        return {"preview": path,
                "next": f"A human must review it, then call submit with confirm_token='{CONFIRM_TOKEN}'."}

    def submit(self, submit_ref: str, confirm_token: str) -> dict:
        if confirm_token != CONFIRM_TOKEN:
            return {"submitted": False,
                    "reason": "Blocked: submit requires explicit human approval. "
                              f"A human must review the preview and pass confirm_token='{CONFIRM_TOKEN}'."}
        self._browser.click(submit_ref)
        return {"submitted": True}
