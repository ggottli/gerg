from __future__ import annotations
import re

# Conservative denylist of dangerous shell patterns (exact/regex).
# Intentionally narrow and readable; expand as needed.
DENY_PATTERNS = [
    r"\brm\s+-rf\s*/\b",                 # nuke root
    r"\brm\s+-rf\s+~/?\b",               # nuke home
    r"\bmkfs(\.|/|\b)",                  # make filesystem
    r"\bdd\s+if=",                       # raw disk writes
    r"\b: \(\)\{ :\|:& \};:\b",          # classic fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bchown\s+-R\s+root\b",
    r"\bchmod\s+0{3,}\b",
    r"\bwget\s+.*\|\s*sh\b",             # curl | sh / wget | sh
    r"\bcurl\s+.*\|\s*sh\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in DENY_PATTERNS]


def is_risky(cmd: str) -> bool:
    """
    Returns True if the command string matches a denylisted pattern.
    Use this as a hard block unless the user passes --allow-unsafe.
    """
    return any(rx.search(cmd) for rx in _COMPILED)

