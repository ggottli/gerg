from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Backport for <3.11


DEFAULTS = {
    "model": "phi3:latest",
    "ollama_base_url": "http://127.0.0.1:11434",
    "confirm_by_default": True,
    "history_dir": str(Path.home() / ".local" / "share" / "gerg"),
}

# Only include an explicit file path if GERG_CONFIG is set and points to a file
env_cfg = os.environ.get("GERG_CONFIG")
CONFIG_PATHS = []
if env_cfg:
    p = Path(env_cfg).expanduser()
    if p.is_file():
        CONFIG_PATHS.append(p)

# Standard user config path
CONFIG_PATHS.append(Path.home() / ".config" / "gerg" / "config.toml")


@dataclass
class Settings:
    model: str
    ollama_base_url: str
    confirm_by_default: bool
    history_dir: str


def load_settings() -> Settings:
    data = DEFAULTS.copy()

    for path in CONFIG_PATHS:
        try:
            if path.is_file():
                with open(path, "rb") as f:
                    data.update(tomllib.load(f))
        except Exception:
            # Ignore malformed configs; keep defaults/env overrides
            pass

    # Environment overrides
    model = os.environ.get("GERG_MODEL")
    if model:
        data["model"] = model

    base = os.environ.get("GERG_OLLAMA_BASE_URL")
    if base:
        data["ollama_base_url"] = base

    confirm = os.environ.get("GERG_CONFIRM")
    if confirm is not None:
        data["confirm_by_default"] = confirm.lower() in {"1", "true", "yes"}

    hist = os.environ.get("GERG_HISTORY_DIR")
    if hist:
        data["history_dir"] = hist

    Path(data["history_dir"]).expanduser().mkdir(parents=True, exist_ok=True)
    return Settings(**data)
