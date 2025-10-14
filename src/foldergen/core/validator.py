# src/foldergen/core/validator.py
import re
from typing import Any, Dict, Set

_GEN_RE = re.compile(r"\{\{[^{}]*\}\}")
_VAR_RE = re.compile(r"(?<!\{)\{([^{}|]+?)(?:\|[^{}]*)?\}(?!\})")

def collect_placeholders(s: str) -> Set[str]:
    if not s:
        return set()
    cleaned = _GEN_RE.sub("", s)
    return {m.group(1).strip() for m in _VAR_RE.finditer(cleaned)}

def validate_template_dict(template: Dict[str, Any]) -> None:
    if "dirs" not in template or not isinstance(template["dirs"], list):
        raise ValueError("Template root must have a 'dirs' list.")

def find_missing_vars(template: Dict[str, Any], context: Dict[str, Any]) -> Set[str]:
    missing: Set[str] = set()
    def walk(node: Dict[str, Any]) -> None:
        name = node.get("name","")
        for var in collect_placeholders(name):
            if var not in context:
                missing.add(var)
        for f in node.get("files",[]) or []:
            for var in collect_placeholders(f):
                if var not in context:
                    missing.add(var)
        for c in node.get("dirs",[]) or []:
            walk(c)
    for root in template.get("dirs",[]) or []:
        walk(root)
    return missing

def find_used_vars(template: Dict[str, Any]) -> Set[str]:
    used: Set[str] = set()
    def walk(node: Dict[str, Any]) -> None:
        used.update(collect_placeholders(node.get("name","")))
        for f in node.get("files",[]) or []:
            used.update(collect_placeholders(f))
        for c in node.get("dirs",[]) or []:
            walk(c)
    for root in template.get("dirs",[]) or []:
        walk(root)
    return used

def find_unused_vars(template: Dict[str, Any], context: Dict[str, Any]) -> Set[str]:
    used = find_used_vars(template)
    return set(context.keys()) - used
