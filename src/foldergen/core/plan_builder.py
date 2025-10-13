import os
from typing import Any, Dict, List
from .models import TemplateNode, BuildPlan, BuildPlanItem, Context
from .parser import render_string
from .gen_syntax import expand_generators  # ⬅ 新增

def _to_node(d: Dict[str, Any]) -> TemplateNode:
    node = TemplateNode(
        name=d.get("name", ""),
        dirs=[_to_node(x) for x in d.get("dirs", []) or []],
        files=list(d.get("files", []) or []),
    )
    return node

def build_plan(template: Dict[str, Any], base_dir: str, context: Context) -> BuildPlan:
    root_dirs: List[TemplateNode] = [_to_node(x) for x in template.get("dirs", []) or []]
    plan = BuildPlan()

    def walk(node: TemplateNode, cur: str):
        # 1) 对 name 进行生成器展开（{{...}}）
        name_variants = expand_generators(node.name) if node.name else [""]
        for name_variant in name_variants:
            # 2) 对展开后的每个名字，再做 {var|filter} 渲染
            rendered_name = render_string(name_variant, context) if name_variant else ""
            cur_path = os.path.join(cur, rendered_name) if rendered_name else cur

            if rendered_name:
                plan.items.append(BuildPlanItem(type="dir", path=cur_path))

            # 文件同理：每个文件名也允许带生成器
            for f in node.files:
                for f_var in expand_generators(f):
                    rendered_file = render_string(f_var, context)
                    plan.items.append(BuildPlanItem(type="file", path=os.path.join(cur_path, rendered_file)))

            for child in node.dirs:
                walk(child, cur_path)

    for root in root_dirs:
        walk(root, base_dir)

    return plan
