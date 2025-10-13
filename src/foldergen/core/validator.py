import re

from typing import Any, Dict, Set, List

from foldergen.core.models import BuildPlan

# 新增：正则——去掉生成器 {{ ... }}；只匹配单花括号变量 { ... }（且不被双花包围）
# 说明：
# - (?<!\{)\{  保证左侧不是另一个 { ，避免匹配到 {{ 的第一个 {
# - ([^{}|]+?)  捕获变量名本体（遇到 | 之前截断，忽略过滤器）
# - (?:\|[^{}]*)?  允许后面跟过滤器但不捕获
# - \}(?!\})  右侧不是另一个 } ，避免落在 }} 的左半边
_GEN_RE = re.compile(r"\{\{[^{}]*\}\}")  # 非贪婪足够应付我们的生成器语法
_VAR_RE = re.compile(r"(?<!\{)\{([^{}|]+?)(?:\|[^{}]*)?\}(?!\})")


def collect_placeholders(s: str) -> Set[str]:
    if not s:
        return set()
    # 先删除所有 {{...}} 生成器片段
    cleaned = _GEN_RE.sub("", s)
    # 再在剩余文本里提取 {var}（包含如 {var|pad(3)} 这种，最终取到 var）
    return {m.group(1).strip() for m in _VAR_RE.finditer(cleaned)}

def validate_template_dict(template: Dict[str, Any]) -> None:
    if "dirs" not in template or not isinstance(template["dirs"], list):
        raise ValueError("Template root must have a 'dirs' list.")

def find_missing_vars(template: Dict[str, Any], context: Dict[str, Any]) -> Set[str]:
    missing: Set[str] = set()

    def walk(node: Dict[str, Any]) -> None:
        name = node.get("name", "")
        for var in collect_placeholders(name):
            if var not in context:
                missing.add(var)
        for f in (node.get("files", []) or []):
            for var in collect_placeholders(f):
                if var not in context:
                    missing.add(var)
        for child in (node.get("dirs", []) or []):
            walk(child)

    for root in template.get("dirs", []):
        walk(root)
    return missing


def find_duplicate_rendered_paths(plan: BuildPlan) -> List[str]:
    counts: Dict[str, int] = {}
    for it in plan.items:
        counts[it.path] = counts.get(it.path, 0) + 1
    return sorted([p for p, c in counts.items() if c > 1])
