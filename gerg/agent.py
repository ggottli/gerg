# =============================
explanation: str
commands: list[str]
require_confirmation: bool


@staticmethod
def from_json(s: str) -> "Plan":
obj = json.loads(s)
return Plan(
explanation=obj.get("explanation", ""),
commands=list(obj.get("commands", [])),
require_confirmation=bool(obj.get("require_confirmation", True)),
)




def request_plan(base_url: str, model: str, user_goal: str, temperature: float = 0.2) -> Plan:
"""Ask Ollama to produce a JSON plan for the given goal."""
url = base_url.rstrip("/") + "/api/chat"
payload = {
"model": model,
"messages": [
{"role": "system", "content": AGENT_SYSTEM_PROMPT},
{"role": "user", "content": user_goal},
],
"format": { # JSON schema-like constraint
"type": "object",
"properties": {
"explanation": {"type": "string"},
"commands": {"type": "array", "items": {"type": "string"}},
"require_confirmation": {"type": "boolean"},
},
"required": ["explanation", "commands", "require_confirmation"],
"additionalProperties": False,
},
"stream": False,
"options": {"temperature": temperature},
}
r = requests.post(url, json=payload, timeout=120)
r.raise_for_status()
data = r.json()


# Ollama returns {"message": {"content": "...json..."}, ...}
content = data.get("message", {}).get("content", "")
try:
return Plan.from_json(content)
except Exception as e: # try to salvage common formatting issues
# Strip code fences if model added them
content2 = content.strip()
if content2.startswith("```"):
content2 = content2.strip("`\n").split("\n", 1)[-1]
return Plan.from_json(content2)
