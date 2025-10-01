# =============================
# gerg/config.py
# =============================
from __future__ import annotations
import os
import json
from dataclasses import dataclass
from pathlib import Path


try:
import tomllib # py311+
except Exception: # pragma: no cover
import tomli as tomllib # type: ignore




DEFAULTS = {
"model": "phi3:latest",
"ollama_base_url": "http://127.0.0.1:11434",
"confirm_by_default": True,
"history_dir": str(Path.home() / ".local/share/gerg"),
}


CONFIG_PATHS = [
Path(os.environ.get("GERG_CONFIG", "")),
Path.home() / ".config/gerg/config.toml",
]


@dataclass
class Settings:
model: str
ollama_base_url: str
confirm_by_default: bool
history_dir: str




def load_settings() -> Settings:
data = DEFAULTS.copy()


for p in CONFIG_PATHS:
if p and p.exists():
with open(p, "rb") as f:
data.update(tomllib.load(f))


# env overrides
if os.getenv("GERG_MODEL"):
data["model"] = os.environ["GERG_MODEL"]
if os.getenv("GERG_OLLAMA_BASE_URL"):
data["ollama_base_url"] = os.environ["GERG_OLLAMA_BASE_URL"]
if os.getenv("GERG_CONFIRM"):
data["confirm_by_default"] = os.environ["GERG_CONFIRM"].lower() in {"1", "true", "yes"}
if os.getenv("GERG_HISTORY_DIR"):
data["history_dir"] = os.environ["GERG_HISTORY_DIR"]


Path(data["history_dir"]).expanduser().mkdir(parents=True, exist_ok=True)
return Settings(**data)
