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

    # ---------- 新增：返回一个“相对路径版”的 BuildPlan ----------
    def to_relative(self, base_dir: str) -> "BuildPlan":
        base = PurePath(base_dir)
        rel_items: List[BuildPlanItem] = []
        for it in self.items:
            p = PurePath(it.path)
            # 尝试相对化：若不在 base 下则原样返回（也可选择 raise）
            try:
                rel = str(p.relative_to(base))
            except Exception:
                rel = str(p)  # 回退：保留原路径（不会阻塞预览/导出）
            rel_items.append(BuildPlanItem(type=it.type, path=rel))
        return BuildPlan(items=rel_items)

    # ---------- 新增：把计划整理为树结构（用于打印/导出） ----------
    def to_tree(
        self,
        *,
        base_dir: Optional[str] = None,
        relative: bool = True,
        include_files: bool = True,
        sort: Literal["template", "alpha"] = "template",
    ) -> Dict[str, Any]:
        """
        返回一个嵌套 dict 的树：
        { "name": "<root>", "type": "dir", "children": [ ... ] }

        - relative=True 时将以 base_dir 为基准返回相对节点名；
          若 base_dir=None，则根名固定为 "<root>"。
        - include_files=False 时仅构建目录节点树。
        - sort="alpha" 时对子节点按名称字母序排序；"template" 保持插入顺序。
        """
        # 选择路径视图
        plan = self.to_relative(base_dir) if (relative and base_dir) else self

        # 内部树节点结构
        def new_node(name: str, typ: str = "dir") -> Dict[str, Any]:
            return {"name": name, "type": typ, "children": []}

        root_name = "" if (relative and base_dir) else "<root>"
        root = new_node(root_name, "dir")

        # 一个简单的 children 查找缓存，避免 O(n^2)
        def get_child(parent: Dict[str, Any], name: str, typ: str) -> Dict[str, Any]:
            for c in parent["children"]:
                if c["name"] == name and c["type"] == typ:
                    return c
            node = new_node(name, typ)
            parent["children"].append(node)
            return node

        # 先确保所有目录路径都建出来，再加文件（避免顺序问题）
        dir_paths = [PurePath(it.path) for it in plan.items if it.type == "dir"]
        file_paths = [PurePath(it.path) for it in plan.items if it.type == "file"]

        # 目录
        for p in dir_paths:
            parent = root
            for part in p.parts:
                if part in (".", ""):
                    continue
                parent = get_child(parent, part, "dir")

        # 文件
        if include_files:
            for p in file_paths:
                parent = root
                parts = list(p.parts)
                for part in parts[:-1]:
                    if part in (".", ""):
                        continue
                    parent = get_child(parent, part, "dir")
                if parts:
                    get_child(parent, parts[-1], "file")

        # 排序（alpha）
        if sort == "alpha":
            def sort_rec(node: Dict[str, Any]):
                node["children"].sort(key=lambda c: (c["type"] != "dir", c["name"].lower()))
                for c in node["children"]:
                    if c["type"] == "dir":
                        sort_rec(c)
            sort_rec(root)

        return root


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
