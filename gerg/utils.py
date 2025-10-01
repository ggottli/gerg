# =============================
# gerg/utils.py
# =============================
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict


def write_history_line(base_dir: Path, record: Dict[str, Any]) -> None:
    path = base_dir / ".gerg_history.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
