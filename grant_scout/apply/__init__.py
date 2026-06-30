"""Auto-apply layer: drive agent-browser to fill grant forms, with secrets injected
deterministically (never through the LLM) and a human gate before submit."""

from .browser import AgentBrowser
from .filler import Filler
from .gate import SubmitGate, CONFIRM_TOKEN

__all__ = ["AgentBrowser", "Filler", "SubmitGate", "CONFIRM_TOKEN"]
