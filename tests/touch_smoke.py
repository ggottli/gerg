from __future__ import annotations
import json
from gerg.agent import Plan

def test_plan_from_obj_minimal():
    obj = {"explanation": "ok", "commands": ["echo hi"], "require_confirmation": True}
    p = Plan.from_obj(obj)
    assert p.explanation == "ok"
    assert p.commands == ["echo hi"]
    assert p.require_confirmation is True

def test_plan_from_obj_validation_errors():
    bad_objs = [
        {"explanation": 123, "commands": [], "require_confirmation": True},        # explanation not str
        {"explanation": "x", "commands": "echo hi", "require_confirmation": True}, # commands not list
        {"explanation": "x", "commands": [1, 2], "require_confirmation": True},    # commands not list[str]
        {"explanation": "x", "commands": [], "require_confirmation": "yes"},       # require_confirmation not bool
    ]
    for obj in bad_objs:
        try:
            Plan.from_obj(obj)
            assert False, f"Expected validation to fail for: {obj}"
        except Exception:
            pass

