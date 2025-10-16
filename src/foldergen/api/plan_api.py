from __future__ import annotations

import os
import json
from typing import Any, Dict
from pathlib import Path
from ..core.validator import validate_template_dict, find_missing_vars
from ..core.plan_builder import build_plan
from ..core.models import BuildPlan


def load_json(path: str | Path) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"--vars should be a file, got: {path}")

    with open(path, "r", encoding="utf-8") as fr:
        return json.load(fr)


def make_plan(template_path: str | Path, base_dir: str | Path, vars_path: str | Path, *,
              max_expand: int = 50_000) -> BuildPlan:
    template = load_json(template_path)
    context: Dict[str, Any] = load_json(vars_path)
    validate_template_dict(template)
    missing = find_missing_vars(template, context)
    if missing:
        raise KeyError(f"Missing variables in context: {sorted(missing)}")
    return build_plan(template, str(base_dir), context, max_expand=max_expand)
