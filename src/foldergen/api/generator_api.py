from pathlib import Path
from .plan_api import make_plan
from ..core.fs_ops import apply_plan
from ..core.models import BuildPlan

def preview(
    template_path: str | Path,
    base_dir: str | Path,
    vars_path: str | Path,
) -> BuildPlan:
    return make_plan(template_path, base_dir, vars_path)

def simulate(
    template_path: str | Path,
    base_dir: str | Path,
    vars_path: str | Path,
) -> None:
    plan = make_plan(template_path, base_dir, vars_path)
    apply_plan(plan, simulate=True)

def build(
    template_path: str | Path,
    base_dir: str | Path,
    vars_path: str | Path,
) -> None:
    plan = make_plan(template_path, base_dir, vars_path)
    apply_plan(plan, simulate=False)
