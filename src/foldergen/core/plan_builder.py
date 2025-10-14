# src/foldergen/core/plan_builder.py
import os
from typing import Any, Dict, List
from .models import TemplateNode, BuildPlan, BuildPlanItem, Context
from .parser import render_string
from .gen_syntax import expand_generators, estimate_generators_count, GeneratorSyntaxError

def _to_node(d: Dict[str, Any]) -> TemplateNode:
    return TemplateNode(
        name=d.get("name",""),
        dirs=[_to_node(x) for x in d.get("dirs",[]) or []],
        files=list(d.get("files",[]) or [])
    )

def build_plan(template: Dict[str, Any], base_dir: str, context: Context, *, max_expand: int = 50_000) -> BuildPlan:
    roots: List[TemplateNode] = [_to_node(x) for x in template.get("dirs",[]) or []]
    plan = BuildPlan()

    def guard_count(name: str, files: List[str]):
        # 估算当前节点 name 与每个文件名生成器的组合（粗略上界）
        count_name = estimate_generators_count(name) if name else 1
        count_files = 1
        for f in files or []:
            count_files *= max(1, estimate_generators_count(f))
            if count_name * count_files > max_expand:
                break
        total = count_name * count_files
        if total > max_expand:
            raise GeneratorSyntaxError(
                f"Expansion too large: estimated {total} > limit {max_expand}",
                f"name='{name}', files={files}"
            )

    def walk(node: TemplateNode, cur: str):
        guard_count(node.name, node.files)  # 规模守门
        name_variants = expand_generators(node.name) if node.name else [""]
        for nv in name_variants:
            dirname = render_string(nv, context) if nv else ""
            cur_path = os.path.join(cur, dirname) if dirname else cur
            if dirname:
                plan.items.append(BuildPlanItem(type="dir", path=cur_path))
            for f in node.files:
                for fv in expand_generators(f):
                    fname = render_string(fv, context)
                    plan.items.append(BuildPlanItem(type="file", path=os.path.join(cur_path, fname)))
            for child in node.dirs:
                walk(child, cur_path)

    for r in roots:
        walk(r, base_dir)
    return plan
