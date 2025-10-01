from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
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
    '    Plan: {"explanation":"List PDFs in Downloads","commands":["find ~/Downloads -maxdepth 1 -type f -iname \'*.pdf\'"],"require_confirmation":false}\n'
    "  - Goal: 'get me to the home directory'\n"
    '    Plan: {"explanation":"Show home path","commands":["pwd"],"require_confirmation":false}\n'
)

# ===== RAG + thinking mode =====

THINK_SYSTEM_PROMPT = (
    "You are GERG in THINK mode (reason-act-observe). "
    "Decide the next single shell command to move toward the user's goal. "
    "Return STRICT JSON with keys: "
    "'explanation' (short string), "
    "'command' (string; a single shell command), "
    "'done' (boolean), "
    "'require_confirmation' (boolean). "
    "Rules:\n"
    "1) Prefer a single, safe, non-interactive command that measurably advances the goal.\n"
    "2) Use absolute paths or '~' instead of relying on prior 'cd'.\n"
    "3) If verification is needed, emit a read-only command (e.g., ls/grep/test/curl -I) and set done=false.\n"
    "4) Only set done=true when the goal is satisfied or nothing more is needed.\n"
    "5) No markdown, no extra keys."
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

        explanation = obj.get("explanation", "")
        if not isinstance(explanation, str):
            raise ValueError("Plan.explanation must be a string")

        commands = obj.get("commands", [])
        if not isinstance(commands, list) or not all(
            isinstance(c, str) for c in commands
        ):
            raise ValueError("Plan.commands must be a list of strings")

        require_confirmation = obj.get("require_confirmation", True)
        if not isinstance(require_confirmation, bool):
            raise ValueError("Plan.require_confirmation must be a boolean")

        return Plan(
            explanation=explanation,
            commands=list(commands),
            require_confirmation=bool(require_confirmation),
        )


@dataclass
class NextAction:
    explanation: str
    command: str
    done: bool
    require_confirmation: bool

    @staticmethod
    def from_obj(obj: Dict[str, Any]) -> "NextAction":
        if not isinstance(obj, dict):
            raise ValueError("NextAction JSON is not an object")

        explanation = obj.get("explanation", "")
        if not isinstance(explanation, str):
            raise ValueError("NextAction.explanation must be a string")

        command = obj.get("command", "")
        if not isinstance(command, str):
            raise ValueError("NextAction.command must be a string")

        done = obj.get("done", False)
        if not isinstance(done, bool):
            raise ValueError("NextAction.done must be a boolean")

        require_confirmation = obj.get("require_confirmation", True)
        if not isinstance(require_confirmation, bool):
            raise ValueError("NextAction.require_confirmation must be a boolean")

        return NextAction(
            explanation=explanation,
            command=command.strip(),
            done=done,
            require_confirmation=require_confirmation,
        )


def _strip_code_fences(s: str) -> str:
    t = s.strip()
    if t.startswith("```"):
        t = t.lstrip("`")
        if "\n" in t:
            t = t.split("\n", 1)[1]
        t = t.rstrip("`").strip()
    return t


def _post_ollama(
    base_url: str, payload: Dict[str, Any], timeout: int
) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/api/chat"
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def request_plan(
    base_url: str,
    model: str,
    user_goal: str,
    temperature: float = 0.2,
    timeout: int = 120,
) -> Plan:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_goal},
        ],
        "format": "json",  # ask for valid JSON
        "stream": False,
        "options": {"temperature": temperature},
    }
    data = _post_ollama(base_url, payload, timeout)

    content = ""
    if isinstance(data, dict):
        msg = data.get("message") or {}
        if isinstance(msg, dict):
            content = msg.get("content", "") or ""
        if not content and "content" in data:
            content = str(data["content"])

    if not content:
        raise ValueError("Ollama response missing message content")

    content = _strip_code_fences(content)
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse plan JSON: {e}\nRaw content:\n{content}"
        ) from e

    return Plan.from_obj(obj)


def request_next_action(
    base_url: str,
    model: str,
    user_goal: str,
    conversation: List[Dict[str, str]],
    rag_context: Optional[str] = None,
    temperature: float = 0.2,
    timeout: int = 120,
) -> NextAction:
    """
    Ask for the next single action. `conversation` should be a list of messages like:
      [{"role":"user","content": "<goal>"}, {"role":"assistant","content":"<prev command/explanation>"}, {"role":"user","content":"OBSERVATION: <stdout/stderr>"} ...]
    Optionally include `rag_context` (short text) to help reasoning.
    """
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": THINK_SYSTEM_PROMPT}
    ]
    if rag_context:
        messages.append(
            {
                "role": "system",
                "content": f"RAG CONTEXT (read-only):\n{rag_context[:20000]}",
            }
        )
    messages.extend(conversation)

    payload = {
        "model": model,
        "messages": messages,
        "format": "json",
        "stream": False,
        "options": {"temperature": temperature},
    }

    data = _post_ollama(base_url, payload, timeout)

    content = ""
    if isinstance(data, dict):
        msg = data.get("message") or {}
        if isinstance(msg, dict):
            content = msg.get("content", "") or ""
        if not content and "content" in data:
            content = str(data["content"])

    if not content:
        raise ValueError("Ollama response missing message content")

    content = _strip_code_fences(content)
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse next-action JSON: {e}\nRaw content:\n{content}"
        ) from e

    return NextAction.from_obj(obj)
