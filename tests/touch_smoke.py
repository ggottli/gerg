# =============================
# tests/test_smoke.py
# =============================
from __future__ import annotations
import json
from gerg.agent import Plan


def test_plan_parse():
raw = '{"explanation":"ok","commands":["echo hi"],"require_confirmation":true}'
p = Plan.from_json(raw)
assert p.commands == ["echo hi"]
