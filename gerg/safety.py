# =============================
# gerg/safety.py
# =============================
from __future__ import annotations
import re
from typing import Iterable


# Very conservative denylist (exact or regex)
DENY_PATTERNS = [
    r"\brm\s+-rf\s*/\b",
    r"\brm\s+-rf\s+~/?\b",
    r"\bmkfs(\.|\b)",
    r"\bdd\s+if=",
    r"\b: \(\)\{ :\|:& \};:\b",  # fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bchown\s+-R\s+root\b",
    r"\bchmod\s+0{3,}\b",
    r"\bwget\s+.*\|\s+sh\b",
    r"\bcurl\s+.*\|\s+sh\b",
]


_COMPILED = [re.compile(p, re.IGNORECASE) for p in DENY_PATTERNS]


def is_risky(cmd: str) -> bool:
    return any(r.search(cmd) for r in _COMPILED)
