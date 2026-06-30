"""Execute a fill-plan against the browser. Public fields filled directly; secret
fields resolved (guarded) and injected via stdin. Returns a MASKED report — Claude
never sees a secret value back."""

from __future__ import annotations

from ..secrets.resolver import Resolver, ResolverError, is_placeholder, mask
from .browser import AgentBrowser


class Filler:
    def __init__(self, browser: AgentBrowser, resolver: Resolver):
        self._browser = browser
        self._resolver = resolver

    def fill(self, plan: list[dict], domain: str) -> list[dict]:
        """plan items: {ref, value, field_type?}. `value` is a literal (public) or
        `{{secret.ref}}`. Returns per-field status with NO secret values."""
        report = []
        for item in plan:
            ref = item.get("ref", "")
            value = item.get("value", "")
            field_type = item.get("field_type", "")
            if is_placeholder(value):
                try:
                    secret = self._resolver.resolve(value, domain, field_type)
                except ResolverError as e:
                    report.append({"ref": ref, "kind": "secret", "status": "blocked",
                                   "reason": str(e)})
                    continue
                self._browser.inject_secret(ref, secret)
                report.append({"ref": ref, "kind": "secret", "status": "filled",
                               "value": mask(secret)})
            else:
                self._browser.fill_public(ref, value)
                report.append({"ref": ref, "kind": "public", "status": "filled",
                               "value": value})
        return report
