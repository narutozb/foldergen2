from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, Set, Tuple, Dict, Literal, Optional
from .models import BuildPlan, AuditReport, ConflictItem, NameIssue

_WIN_ILLEGAL_CHARS = set('<>:"/\\|?*')  # Windows 文件名禁止字符（路径分隔由 os 负责）
_WIN_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

PortableMode = Literal["auto", "windows", "posix", "mac", "all", "none"]


@dataclass(frozen=True)
class NameRules:
    illegal_chars: Set[str]  # 单个“组件名”中不允许出现的字符集合
    reserved_names: Set[str]  # 保留名（大小写不敏感处理与否由大小写敏感策略决定）
    forbid_trailing_space: bool  # 组件名是否禁止以空格结尾（Windows）
    forbid_trailing_dot: bool  # 组件名是否禁止以点结尾（Windows）
    case_insensitive: bool  # 是否按大小写不敏感处理大小写冲突
    note: str = ""  # 可选：规则说明（不参与逻辑）


def _windows_rules() -> NameRules:
    # Windows：非法字符与保留名
    illegal = set('<>:"/\\|?*')  # 单个组件名内部非法（分隔符由路径系统处理）
    # 控制字符 0x00-0x1F 也不允许
    illegal |= {chr(i) for i in range(0, 32)}
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
        # '.' 和 '..' 不是常规保留名，但对应路径特殊含义；下方另行过滤
    }
    return NameRules(
        illegal_chars=illegal,
        reserved_names=reserved,
        forbid_trailing_space=True,
        forbid_trailing_dot=True,
        case_insensitive=True,
        note="Windows portable rules",
    )


def _posix_rules() -> NameRules:
    # POSIX：组件名中唯一非法的是 '/' 与 NUL
    illegal = {"/", "\x00"}
    return NameRules(
        illegal_chars=illegal,
        reserved_names=set(),  # 无固定保留名（'.'/'..' 特殊含义另行过滤）
        forbid_trailing_space=False,
        forbid_trailing_dot=False,
        case_insensitive=False,
        note="POSIX portable rules",
    )


def _mac_rules() -> NameRules:
    # 现代 macOS(APFS) 与 POSIX 基本一致：'/' 与 NUL 不允许
    # （历史 HFS+ 对冒号 ':' 特殊，但现代系统已无此限制）
    return _posix_rules()


def _merge_rules(*rules: NameRules) -> NameRules:
    # “all” 模式：取非法字符的并集、保留名并集、最严格的结尾规则、大小写不敏感只要任一平台不敏感就不敏感
    illegal = set().union(*(r.illegal_chars for r in rules))
    reserved = set().union(*(r.reserved_names for r in rules))
    forbid_space = any(r.forbid_trailing_space for r in rules)
    forbid_dot = any(r.forbid_trailing_dot for r in rules)
    case_ins = any(r.case_insensitive for r in rules)
    return NameRules(
        illegal_chars=illegal,
        reserved_names=reserved,
        forbid_trailing_space=forbid_space,
        forbid_trailing_dot=forbid_dot,
        case_insensitive=case_ins,
        note="Merged portable rules (all)",
    )


def _select_rules(mode: PortableMode) -> Optional[NameRules]:
    """
    根据 portable 模式返回对应规则；返回 None 表示关闭名称检查。
    """
    if mode == "none":
        return None
    if mode == "auto":
        return _windows_rules() if os.name == "nt" else _posix_rules()
    if mode == "windows":
        return _windows_rules()
    if mode == "posix":
        return _posix_rules()
    if mode == "mac":
        return _mac_rules()
    if mode == "all":
        return _merge_rules(_windows_rules(), _posix_rules(), _mac_rules())
    raise ValueError(f"Unknown portable mode: {mode}")


def _iter_components_no_drive(path_str: str):
    """
    逐个返回路径组件，但在 Windows 下跳过盘符（如 'D:'）。
    UNC 路径会返回其各自的组件（'\\server\\share\\...' -> 'server','share',...）。
    """
    drive, tail = os.path.splitdrive(path_str)
    parts = Path(tail).parts
    for comp in parts:
        if comp in (os.sep, os.altsep, "", None):
            continue
        yield comp


def _norm(p: str) -> str:
    # 统一规范化路径比较（大小写在 Windows 不敏感）
    p = os.path.normpath(p)
    if os.name == "nt":
        p = os.path.normcase(p)
    return p


def _is_inside_base(base: Path, candidate: Path) -> bool:
    try:
        return base.resolve(strict=False) in candidate.resolve(strict=False).parents or base.resolve(
            strict=False) == candidate.resolve(strict=False)
    except Exception:
        # 某些无权限路径 resolve 可能失败，退化判断
        return str(candidate).startswith(str(base))


def _gather_planned_sets(plan: BuildPlan) -> Tuple[Set[str], Set[str], Dict[str, int]]:
    planned_dirs, planned_files = set(), set()
    counts: Dict[str, int] = {}
    for item in plan.items:
        p = _norm(item.path)
        counts[p] = counts.get(p, 0) + 1
        if item.type == "dir":
            planned_dirs.add(p)
        elif item.type == "file":
            planned_files.add(p)
    return planned_dirs, planned_files, counts


def _walk_actual(base_dir: str, follow_symlinks: bool) -> Tuple[Set[str], Set[str]]:
    actual_dirs, actual_files = set(), set()
    for root, dirs, files in os.walk(base_dir, followlinks=follow_symlinks):
        # 当前 root 也算目录
        actual_dirs.add(_norm(root))
        for d in dirs:
            actual_dirs.add(_norm(os.path.join(root, d)))
        for f in files:
            actual_files.add(_norm(os.path.join(root, f)))
    return actual_dirs, actual_files


def _illegal_name_reasons_with_rules(name: str, rules: NameRules) -> Tuple[bool, str]:
    bad = []

    # '.' 和 '..'（路径语义保留）
    if name in (".", ".."):
        bad.append("reserved path segment: '.' or '..'")

    # 组件名中的非法字符
    illegal_in_name = set(ch for ch in name if ch in rules.illegal_chars)
    if illegal_in_name:
        bad.append(f"illegal characters: {''.join(sorted(illegal_in_name))}")

    # Windows 风格的尾随限制
    if rules.forbid_trailing_space and name.endswith(" "):
        bad.append("trailing space")
    if rules.forbid_trailing_dot and name.endswith("."):
        bad.append("trailing dot")

    # 保留名（Windows）
    if rules.reserved_names:
        probe = name.upper() if rules.case_insensitive else name
        if probe.split(".")[0] in rules.reserved_names:
            bad.append(f"reserved name: {probe.split('.')[0]}")

    # NUL（已在非法字符集合中覆盖；此处可选重复提示）
    if "\x00" in name:
        bad.append("null character")

    ok = len(bad) == 0
    return ok, "; ".join(bad)


def _check_name_issues(paths: Iterable[str], rules: Optional[NameRules]) -> Iterable[NameIssue]:
    if rules is None:
        return []  # portable=none：不做名称检查
    issues = []
    for p in paths:
        for comp in _iter_components_no_drive(p):
            ok, reason = _illegal_name_reasons_with_rules(comp, rules)
            if not ok:
                issues.append(NameIssue(path=p, reason=reason))
    return issues


def _check_path_length(paths: Iterable[str], max_len: int) -> Iterable[NameIssue]:
    for p in paths:
        if len(p) > max_len:
            yield NameIssue(path=p, reason=f"path too long (> {max_len})")


# 大小写冲突（按规则决定是否检查）
def _case_collisions(paths: Iterable[str], rules: Optional[NameRules]) -> Iterable[NameIssue]:
    # 仅当选择的可移植性规则要求“大小写不敏感”时（如 Windows / all / auto 且在 Windows）才做检查
    if not rules or not rules.case_insensitive:
        return []
    seen: Dict[str, str] = {}
    issues = []
    for p in paths:
        key = os.path.normcase(p)  # 以大小写不敏感视角做键
        if key in seen and seen[key] != p:
            issues.append(NameIssue(path=p, reason=f"case-collision with {seen[key]}"))
        else:
            seen[key] = p
    return issues


def audit_filesystem(
        plan: BuildPlan,
        base_dir: str,
        *,
        follow_symlinks: bool = False,
        max_path_len: int = 240,
        portable: PortableMode = "auto",
) -> AuditReport:
    base = Path(base_dir)
    rep = AuditReport(base_dir=str(base_dir))

    planned_dirs, planned_files, counts = _gather_planned_sets(plan)
    rep.planned_dirs = sorted(planned_dirs)
    rep.planned_files = sorted(planned_files)

    rep.duplicate_planned_paths = sorted(p for p, c in counts.items() if c > 1)

    # 目录逃逸检查
    for p in list(planned_dirs) + list(planned_files):
        cand = Path(p)
        if not _is_inside_base(base, cand):
            rep.outside_base_issues.append(p)

    # 可移植性规则选择
    rules = _select_rules(portable)

    # 名称/长度/大小写冲突（按规则）
    rep.name_issues.extend(_check_name_issues(planned_dirs | planned_files, rules))
    rep.name_issues.extend(_check_path_length(planned_dirs | planned_files, max_path_len))
    rep.name_issues.extend(_case_collisions(planned_dirs | planned_files, rules))

    # 实际磁盘扫描
    if not base.exists():
        rep.permission_issues.append(f"base dir not found: {base}")
        # 仍然继续做“缺失”分类
        actual_dirs, actual_files = set(), set()
    else:
        try:
            actual_dirs, actual_files = _walk_actual(str(base), follow_symlinks=follow_symlinks)
        except PermissionError as e:
            rep.permission_issues.append(f"walk permission error: {e}")
            actual_dirs, actual_files = set(), set()

    # 计划 → 实际：缺失 / 已存在 / 类型冲突
    for d in planned_dirs:
        if d in actual_dirs:
            rep.existing_dirs.append(d)
        elif d in actual_files:
            rep.conflicts.append(ConflictItem(path=d, expected="dir", found="file"))
        else:
            rep.missing_dirs.append(d)

    for f in planned_files:
        if f in actual_files:
            rep.existing_files.append(f)
        elif f in actual_dirs:
            rep.conflicts.append(ConflictItem(path=f, expected="file", found="dir"))
        else:
            rep.missing_files.append(f)

    # 实际 → 计划：多余项
    all_planned = planned_dirs | planned_files
    rep.extra_dirs = sorted(x for x in actual_dirs if x not in all_planned)
    rep.extra_files = sorted(x for x in actual_files if x not in all_planned)

    # 权限快速检查：尝试对缺失项的父目录做可写性探测（轻量，非强制）
    for p in rep.missing_dirs + rep.missing_files:
        parent = Path(p).parent
        try:
            if parent.exists() and not os.access(parent, os.W_OK):
                rep.permission_issues.append(f"no write permission to parent: {parent}")
        except Exception:
            # 忽略无法判断的情况
            pass

    # 排序整理
    rep.missing_dirs.sort()
    rep.missing_files.sort()
    rep.existing_dirs.sort()
    rep.existing_files.sort()
    rep.extra_dirs.sort()
    rep.extra_files.sort()
    rep.conflicts.sort(key=lambda c: c.path)
    rep.permission_issues = sorted(set(rep.permission_issues))
    rep.outside_base_issues = sorted(set(rep.outside_base_issues))
    # name_issues 可能有重复
    seen = set()
    uniq = []
    for ni in rep.name_issues:
        key = (ni.path, ni.reason)
        if key not in seen:
            seen.add(key)
            uniq.append(ni)
    rep.name_issues = uniq

    # 计算多余项时，排除 base 自身
    base_norm = _norm(str(base))
    all_planned = planned_dirs | planned_files
    rep.extra_dirs = sorted(x for x in actual_dirs if x not in all_planned and x != base_norm)
    rep.extra_files = sorted(x for x in actual_files if x not in all_planned)

    return rep
