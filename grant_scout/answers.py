"""Non-secret reusable answers library (org narratives, standard responses).

ponytail: a flat TOML the human maintains; loaded into a dict. These are PUBLIC
answers (mission statements, program descriptions) safe for Claude to reuse across
applications — never secrets.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

DEFAULT_ANSWERS = "answers.toml"


def load_answers(path: str | Path = DEFAULT_ANSWERS) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return tomllib.loads(p.read_text(encoding="utf-8"))
