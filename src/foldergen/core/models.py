from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional
from pathlib import PurePath


@dataclass
class TemplateNode:
    name: str
    dirs: List["TemplateNode"] = field(default_factory=list)
    files: List[str] = field(default_factory=list)


@dataclass
class BuildPlanItem:
    type: str  # "dir" | "file"
    path: str  # 绝对路径（构建用）。如需相对路径，请使用 BuildPlan.to_relative()


@dataclass
class BuildPlan:
    items: List[BuildPlanItem] = field(default_factory=list)

    def to_relative(self, base_dir: str) -> "BuildPlan":
        # 保持不变
        base = PurePath(base_dir)
        rel_items: List[BuildPlanItem] = []
        for it in self.items:
            p = PurePath(it.path)
            try:
                rel = str(p.relative_to(base))
            except Exception:
                rel = str(p)
            rel_items.append(BuildPlanItem(type=it.type, path=rel))
        return BuildPlan(items=rel_items)

    def to_tree(
        self,
        *,
        base_dir: Optional[str] = None,
        relative: bool = True,
        include_files: bool = True,
        sort: Literal["template", "alpha"] = "template",
        # ---- 新增：状态注入 ----
        status_map: Optional[Dict[str, str]] = None,          # 绝对路径 -> status（existing/missing/conflict/planned）
        issues_map: Optional[Dict[str, List[str]]] = None,    # 绝对路径 -> [issue strings]
    ) -> Dict[str, Any]:
        """
        返回嵌套 dict 的树。若提供 status_map / issues_map，则每个节点附带:
        - node["status"] = "existing"|"missing"|"conflict"|"planned"
        - node["issues"] = [...]
        注意：status_map/issue_map 的 key 以“绝对路径”匹配。
        """
        # 选择路径视图
        plan_abs = self                          # 保存绝对视图用于 abs 拼接
        plan = self.to_relative(base_dir) if (relative and base_dir) else self

        def new_node(name: str, typ: str = "dir") -> Dict[str, Any]:
            return {"name": name, "type": typ, "children": []}

        root_name = "" if (relative and base_dir) else "<root>"
        root = new_node(root_name, "dir")

        # 目录 & 文件路径（显示用）
        dir_paths = [PurePath(it.path) for it in plan.items if it.type == "dir"]
        file_paths = [PurePath(it.path) for it in plan.items if it.type == "file"]

        # —— 状态解析：一个小工具，基于构造中的“当前绝对路径”取状态/问题
        import os as _os
        def _norm(p: str) -> str:
            p = _os.path.normpath(p)
            if _os.name == "nt":
                p = _os.path.normcase(p)
            return p

        def attach_status(node: Dict[str, Any], abs_path: Optional[str]):
            if status_map and abs_path:
                node["status"] = status_map.get(_norm(abs_path), "planned")
            if issues_map and abs_path:
                issues = issues_map.get(_norm(abs_path))
                if issues:
                    node["issues"] = issues

        # children 查找缓存
        def get_child(parent: Dict[str, Any], name: str, typ: str) -> Dict[str, Any]:
            for c in parent["children"]:
                if c["name"] == name and c["type"] == typ:
                    return c
            node = new_node(name, typ)
            parent["children"].append(node)
            return node

        # 目录：逐级创建，并注入状态
        for p in dir_paths:
            parent = root
            abs_accum = str(PurePath(base_dir) / p) if (relative and base_dir) else str(p)
            for i, part in enumerate(p.parts):
                if part in (".", ""):
                    continue
                parent = get_child(parent, part, "dir")
                # 逐层更新 abs_accum
                if i == 0:
                    abs_path = str(PurePath(base_dir) / PurePath(part)) if (relative and base_dir) else str(PurePath(part))
                else:
                    abs_path = str(PurePath(base_dir) / PurePath(*p.parts[:i+1])) if (relative and base_dir) else str(PurePath(*p.parts[:i+1]))
                attach_status(parent, abs_path)

        # 文件：挂到对应目录，并注入状态
        if include_files:
            for p in file_paths:
                parent = root
                parts = list(p.parts)
                for i, part in enumerate(parts[:-1]):
                    if part in (".", ""):
                        continue
                    parent = get_child(parent, part, "dir")
                    # 目录中间节点状态我们前面已经设置过，这里无需重复
                if parts:
                    file_node = get_child(parent, parts[-1], "file")
                    abs_path = str(PurePath(base_dir) / p) if (relative and base_dir) else str(p)
                    attach_status(file_node, abs_path)

        # 排序
        if sort == "alpha":
            def sort_rec(node: Dict[str, Any]):
                node["children"].sort(key=lambda c: (c["type"] != "dir", c["name"].lower()))
                for c in node["children"]:
                    if c["type"] == "dir":
                        sort_rec(c)
            sort_rec(root)

        return root

    def to_manifest(
        self,
        *,
        base_dir: Optional[str] = None,
        relative: bool = True,
        # ---- 新增：是否附带状态 ----
        status_map: Optional[Dict[str, str]] = None,
        issues_map: Optional[Dict[str, List[str]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        扁平清单；若提供 status_map / issues_map，则每行附带 status / issues 字段。
        """
        plan = self.to_relative(base_dir) if (relative and base_dir) else self

        import os as _os
        def _norm(p: str) -> str:
            p = _os.path.normpath(p)
            if _os.name == "nt":
                p = _os.path.normcase(p)
            return p

        out = []
        for it in plan.items:
            row = {"type": it.type, "path": it.path}
            if status_map or issues_map:
                # 需要用绝对路径来查映射
                abs_path = str(PurePath(base_dir) / it.path) if (relative and base_dir) else it.path
                key = _norm(abs_path)
                if status_map:
                    row["status"] = status_map.get(key, "planned")
                if issues_map:
                    if key in issues_map and issues_map[key]:
                        row["issues"] = issues_map[key]
            out.append(row)
        return out

Context = Dict[str, Any]


@dataclass
class ConflictItem:
    path: str
    expected: Literal["dir", "file"]
    found: Literal["dir", "file", "missing", "unknown"]


@dataclass
class NameIssue:
    path: str
    reason: str  # e.g. "illegal characters: <>*|", "windows reserved name: CON", "path too long"


@dataclass
class AuditReport:
    base_dir: str
    planned_dirs: List[str] = field(default_factory=list)
    planned_files: List[str] = field(default_factory=list)
    # 结果分类
    missing_dirs: List[str] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
    existing_dirs: List[str] = field(default_factory=list)
    existing_files: List[str] = field(default_factory=list)
    extra_dirs: List[str] = field(default_factory=list)  # 磁盘存在但不在计划里
    extra_files: List[str] = field(default_factory=list)
    conflicts: List[ConflictItem] = field(default_factory=list)  # 目录/文件类型不匹配
    permission_issues: List[str] = field(default_factory=list)  # 无法访问/创建
    name_issues: List[NameIssue] = field(default_factory=list)  # 非法字符/过长/保留名/大小写冲突
    outside_base_issues: List[str] = field(default_factory=list)  # 计划路径逃逸到基准目录之外
    duplicate_planned_paths: List[str] = field(default_factory=list)  # 渲染后重复路径
