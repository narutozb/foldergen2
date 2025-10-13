import os
from typing import Iterable
from .models import BuildPlan, BuildPlanItem

def apply_plan(plan: BuildPlan, simulate: bool = False) -> None:
    for item in plan.items:
        if item.type == "dir":
            if not simulate:
                os.makedirs(item.path, exist_ok=True)
            print(f"[dir ] {item.path}")
        elif item.type == "file":
            if not simulate:
                os.makedirs(os.path.dirname(item.path), exist_ok=True)
                if not os.path.exists(item.path):
                    with open(item.path, "w", encoding="utf-8") as fw:
                        fw.write("")  # 空文件
            print(f"[file] {item.path}")
