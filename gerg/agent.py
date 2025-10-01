from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Dict, List
import requests


AGENT_SYSTEM_PROMPT = (
    "You are GERG, a cautious shell-planning assistant for macOS/Linux shells. "
    "You receive a user goal and MUST return STRICT JSON with keys: "
    "'explanation' (short string), 'commands' (array of shell strings), "
    "'require_confirmation' (bool). "
    "Rules:\n"
    "1) Prefer ONE self-contained command that accomplishes the task without requiring a prior 'cd'.\n"
    "   Use absolute paths or '~' in the command itself (e.g., 'ls ~/Downloads/*.pdf').\n"
    "2) If multiple steps are truly needed, return a small list, but NEVER return only 'cd'.\n"
    "3) Produce commands that are non-interactive and safe. Avoid destructive ops. No markdown, no extra keys.\n"
    "4) Favor POSIX-compatible utilities when possible.\n"
    "Examples:\n"
    "  - Goal: 'go to my Downloads and list all pdfs'\n"
    "    Plan: {\"explanation\":\"List PDFs in Downloads\",\"commands\":[\"find ~/Downloads -maxdepth 1 -type f -iname '*.pdf'\"],\"require_confirmation\":false}\n"
    "  - Goal: 'get me to the home directory'\n"
    "    Plan: {\"explanation\":\"Show home path\",\"commands\":[\"pwd\"],\"require_confirmation\":false}\n"
)



@dataclass
class Plan:
    explanation: str
    commands: List[str]
    require_confirmation: bool

    @staticmethod
    def from_obj(obj: Dict[str, Any]) -> "Plan":
        if not isinstance(obj, dict):
            raise ValueError("Plan JSON is not an object")

        # Basic validation and coercion
        explanation = obj.get("explanation", "")
        if not isinstance(explanation, str):
            raise ValueError("Plan.explanation must be a string")

        commands = obj.get("commands", [])
        if not isinstance(commands, list) or not all(isinstance(c, str) for c in commands):
            raise ValueError("Plan.commands must be a list of strings")

        require_confirmation = obj.get("require_confirmation", True)
        if not isinstance(require_confirmation, bool):
            raise ValueError("Plan.require_confirmation must be a boolean")

        return Plan(
            explanation=explanation,
            commands=list(commands),
            require_confirmation=bool(require_confirmation),
        )


def _strip_code_fences(s: str) -> str:
    """
    Remove common Markdown code fences if the model added them.
    """
    t = s.strip()
    if t.startswith("```"):
        # Remove opening fence line
        t = t.lstrip("`")
        # If language tag exists, drop first line up to newline
        if "\n" in t:
            t = t.split("\n", 1)[1]
        # Remove closing fences at the end
        t = t.rstrip("`").strip()
    return t


def request_plan(
    base_url: str,
    model: str,
    user_goal: str,
    temperature: float = 0.2,
    timeout: int = 120,
) -> Plan:
    """
    Ask the local Ollama server for a shell plan given a natural-language goal.

    Expects Ollama running at base_url (e.g., http://127.0.0.1:11434) and a pulled model.
    Uses the /api/chat endpoint and requests JSON output.
    """
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_goal},
        ],
        # Ollama: when "format": "json" is set, the model is constrained to valid JSON
        "format": "json",
        "stream": False,
        "options": {"temperature": temperature},
    }

    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    # Expected shape: {"message": {"content": "<json string>"}, ...}
    content = ""
    if isinstance(data, dict):
        msg = data.get("message") or {}
        if isinstance(msg, dict):
            content = msg.get("content", "") or ""
        # Some versions/situations might return 'content' at top-level
        if not content and "content" in data:
            content = str(data["content"])

    if not content:
        raise ValueError("Ollama response missing message content")

    content = _strip_code_fences(content)

    # Parse JSON and validate
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse plan JSON: {e}\nRaw content:\n{content}") from e

    return Plan.from_obj(obj)

