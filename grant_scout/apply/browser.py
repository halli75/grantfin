"""Thin subprocess wrapper over the agent-browser CLI (Vercel Labs, Apache-2.0).

Secret-safe rule: public values may go as argv (`fill @e "v"`); secret values go
ONLY through stdin via `eval --stdin` — they never appear in argv, shell history,
or logs. `inject_secret` builds the JS in-process and pipes it; the secret is the
`input=` to subprocess, never an argument.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time

BIN = "agent-browser"


def _resolve_bin() -> str:
    # On Windows the global npm bin is agent-browser.cmd; shutil.which finds the
    # right shim. Fall back to the bare name (e.g. when mocked).
    return shutil.which(BIN) or BIN


def build_inject_js(secret_value: str) -> str:
    """JS that sets the focused element's value to `secret_value` and fires events.

    The secret is embedded as a JSON literal; this whole string is piped via stdin.
    """
    lit = json.dumps(secret_value)
    return (
        "(() => { const el = document.activeElement; if (!el) return 'no-active'; "
        f"el.value = {lit}; "
        "el.dispatchEvent(new Event('input', {bubbles:true})); "
        "el.dispatchEvent(new Event('change', {bubbles:true})); "
        "return (el.id || el.name || 'field') + ':set'; })()"
    )


class AgentBrowser:
    def __init__(self, *, session: str | None = None, timeout: float = 30.0, runner=None):
        self._session = session
        self._timeout = timeout
        self._proc = None  # the detached `open` process that holds the daemon
        # runner is injectable for tests: (args:list[str], input:bytes|None) -> (returncode, stdout, stderr)
        self._runner = runner or self._subprocess_runner

    def _subprocess_runner(self, args, input_bytes):
        proc = subprocess.run(
            [_resolve_bin(), *args],
            input=input_bytes,
            capture_output=True,
            timeout=self._timeout,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")

    def _args(self, *parts: str) -> list[str]:
        base = ["--session", self._session] if self._session else []
        return base + list(parts)

    def _run(self, *parts: str, stdin: bytes | None = None) -> str:
        rc, out, err = self._runner(self._args(*parts), stdin)
        if rc != 0:
            raise RuntimeError(f"agent-browser {parts[0]} failed: {err.strip() or out.strip()}")
        return out

    # --- navigation / inspection ---
    def open(self, url: str, *, ready_tries: int = 45) -> str:
        """Open a page. agent-browser's `open` stays attached as the session daemon,
        so we launch it DETACHED and poll readiness instead of blocking on it.

        Mocked runs (injected runner) skip the detached path and just issue `open`.
        """
        if self._runner is not self._subprocess_runner:
            return self._run("open", url)
        args = [_resolve_bin()] + self._args("open", url)
        self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(ready_tries):
            try:
                if "complete" in self.eval("document.readyState").lower():
                    return "ready"
            except Exception:
                pass
            time.sleep(2)
        raise RuntimeError("page did not become ready in time")

    def close(self) -> None:
        try:
            self._run("close")
        except Exception:
            pass
        if self._proc is not None:
            self._proc.terminate()
            self._proc = None

    def snapshot(self) -> str:
        return self._run("snapshot", "-i")

    def eval(self, js: str) -> str:
        return self._run("eval", js)

    def screenshot(self, path: str) -> str:
        return self._run("screenshot", path)

    def click(self, ref: str) -> str:
        return self._run("click", ref)

    # --- form input ---
    def fill_public(self, ref: str, value: str) -> str:
        """Fill a NON-secret field. Value may appear in argv — only for public data."""
        return self._run("fill", ref, value)

    def inject_secret(self, ref: str, secret_value: str) -> str:
        """Inject a SECRET into a field: focus by ref, set value via JS piped through
        stdin. The secret is never an argv argument."""
        self.click(ref)  # focus the field (ref is non-secret)
        js = build_inject_js(secret_value)
        return self._run("eval", "--stdin", stdin=js.encode("utf-8"))
