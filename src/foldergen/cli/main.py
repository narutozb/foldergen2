import json
from typing import List

import click
from pathlib import Path
from ..api import plan_api, generator_api
from ..core.checker import audit_filesystem


@click.group(help="Generate folder structures from template strings.")
def main():
    pass


@main.command(help="Show build plan or export a manifest.")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
@click.option("--relative/--absolute", default=True, show_default=True,
              help="Manifest shows paths relative to --base (or absolute).")
@click.option("--export-manifest", "export_manifest", type=click.Path(dir_okay=False), default=None,
              help="If given, write manifest to this file instead of stdout.")
@click.option("--manifest-format", type=click.Choice(["json", "jsonl"]), default="json", show_default=True,
              help="Manifest file format.")
# ---- 新增：状态注入选项（沿用 check 的参数）----
@click.option("--with-status", is_flag=True,
              help="Include status (existing/missing/conflict/planned) and name issues in manifest.")
@click.option("--warn-unused-vars", is_flag=True, help="Warn if keys in --vars are not used by the template.")
@click.option("--max-expand", type=int, default=50000, show_default=True,
              help="Maximum allowed generator expansion per node.")
@click.option("--portable",
              type=click.Choice(["auto", "windows", "posix", "mac", "all", "none"]),
              default="auto", show_default=True)
@click.option("--max-path-len", default=240, show_default=True, type=int)
@click.option("--follow-symlinks/--no-follow-symlinks", default=False, show_default=True)
def plan(template_path, vars_path, base_dir, relative, export_manifest, manifest_format,
         with_status, portable, max_path_len, follow_symlinks, warn_unused_vars, max_expand, ):
    p = plan_api.make_plan(template_path, base_dir, vars_path, max_expand=max_expand)
    # 未使用变量警告
    if warn_unused_vars:
        from ..api import plan_api as _pa
        template = _pa.load_json(template_path)
        ctx = _pa.load_json(vars_path)
        from ..core.validator import find_unused_vars
        unused = sorted(find_unused_vars(template, ctx))
        if unused:
            click.secho(f"Warning: unused vars: {unused}", fg="yellow")

    status_map = issues_map = None
    if with_status:
        from ..core.checker import audit_filesystem
        rep = audit_filesystem(
            p, base_dir,
            follow_symlinks=follow_symlinks,
            max_path_len=max_path_len,
            portable=portable,
        )
        status_map, issues_map = _build_status_maps(rep)

    manifest = p.to_manifest(base_dir=base_dir, relative=relative,
                             status_map=status_map, issues_map=issues_map)

    if export_manifest:
        out_path = Path(export_manifest)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if manifest_format == "json":
            with open(out_path, "w", encoding="utf-8") as fw:
                json.dump(manifest, fw, ensure_ascii=False, indent=2)
        else:  # jsonl
            with open(out_path, "w", encoding="utf-8") as fw:
                for row in manifest:
                    fw.write(json.dumps(row, ensure_ascii=False) + "\n")
        click.echo(f"Manifest written to: {out_path}")
    else:
        click.echo(json.dumps(manifest, ensure_ascii=False, indent=2))


@main.command(help="Simulate generation (print operations, no writes).")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
@click.option("--quiet", is_flag=True, help="Only print final summary.")
@click.option("--summary", is_flag=True, help="Print summary after listing.")
@click.option("--max-expand", type=int, default=50000, show_default=True)
def simulate(template_path, vars_path, base_dir, quiet, summary, max_expand):
    plan = plan_api.make_plan(template_path, base_dir, vars_path, max_expand=max_expand)
    dirs = [i.path for i in plan.items if i.type == "dir"]
    files = [i.path for i in plan.items if i.type == "file"]
    if not quiet:
        for d in dirs: click.echo(f"[dir ] {d}")
        for f in files: click.echo(f"[file] {f}")
    if summary or quiet:
        click.secho(f"Summary: dirs={len(dirs)}, files={len(files)}", fg="cyan")


@main.command(help="Apply plan and write to filesystem.")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
@click.option("--assume-yes", is_flag=True, help="Do not ask for confirmation.")
@click.option("--max-expand", type=int, default=50000, show_default=True)
def build(template_path, vars_path, base_dir, assume_yes, max_expand):
    plan = plan_api.make_plan(template_path, base_dir, vars_path, max_expand=max_expand)
    if not assume_yes:
        total = len(plan.items)
        click.confirm(f"This will create {total} entries. Continue?", abort=True)
    generator_api.build(template_path, vars_path, base_dir)  # 内部再生成一次也行；如想避免重复可直接 apply_plan(plan)


@main.command(help="Check filesystem against template plan and report issues.")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
@click.option("--follow-symlinks/--no-follow-symlinks", default=False, show_default=True)
@click.option("--max-path-len", default=240, show_default=True, type=int, help="Max path length to warn.")
@click.option("--portable",
              type=click.Choice(["auto", "windows", "posix", "mac", "all", "none"]),
              default="auto", show_default=True,
              help="Name portability rules to apply.")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json", show_default=True)
@click.option("--strict", is_flag=True, help="Non-zero exit if any issue found (good for CI).")
@click.option("--filter", "filter_status", default=None, help="Filter statuses in output: e.g. 'missing,conflict'.")
def check(template_path, vars_path, base_dir, follow_symlinks, max_path_len, portable, fmt, strict, filter_status):
    plan = plan_api.make_plan(template_path, base_dir, vars_path)
    rep = audit_filesystem(
        plan,
        base_dir,
        follow_symlinks=follow_symlinks,
        max_path_len=max_path_len,
        portable=portable,  # ⬅ 传入
    )

    # 状态过滤（仅影响 table/json 输出，不改变 rep 内部）
    if filter_status:
        want = {s.strip().lower() for s in filter_status.split(",") if s.strip()}

    if fmt == "json":
        def _ser(obj):
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        click.echo(json.dumps(rep, default=_ser, ensure_ascii=False, indent=2))
    else:
        # 精简表格输出
        def _h(title):
            click.secho(f"\n== {title} ==", bold=True)

        _h("Planned")
        click.echo(f"dirs={len(rep.planned_dirs)}, files={len(rep.planned_files)}")
        if rep.duplicate_planned_paths:
            _h("Duplicate Planned Paths")
            for p in rep.duplicate_planned_paths:
                click.echo(p)
        if rep.outside_base_issues:
            _h("Outside Base Issues")
            for p in rep.outside_base_issues: click.echo(p)
        if rep.name_issues:
            _h("Name Issues")
            for ni in rep.name_issues: click.echo(f"{ni.path}  -> {ni.reason}")
        _h("Missing")
        for p in rep.missing_dirs: click.echo(f"[dir ] {p}")
        for p in rep.missing_files: click.echo(f"[file] {p}")
        _h("Conflicts (type mismatch)")
        for c in rep.conflicts: click.echo(f"{c.path}  expected={c.expected}  found={c.found}")
        _h("Existing (as planned)")
        for p in rep.existing_dirs[:10]: click.echo(f"[dir ] {p}")
        for p in rep.existing_files[:10]: click.echo(f"[file] {p}")
        if len(rep.existing_dirs) > 10 or len(rep.existing_files) > 10:
            click.echo("... (use --format json to see all)")
        _h("Extras on Disk")
        for p in rep.extra_dirs[:10]: click.echo(f"[dir ] {p}")
        for p in rep.extra_files[:10]: click.echo(f"[file] {p}")
        if rep.permission_issues:
            _h("Permission Issues")
            for s in rep.permission_issues: click.echo(s)

    if strict:
        has_problem = any([
            rep.missing_dirs, rep.missing_files,
            rep.conflicts, rep.name_issues, rep.permission_issues,
            rep.outside_base_issues, rep.duplicate_planned_paths
        ])
        raise SystemExit(2 if has_problem else 0)


def _print_tree_ascii(tree: dict, *, max_depth: int | None = None, _prefix: str = "", _is_last: bool = True,
                      _level: int = 0):
    """
    递归打印树为 ASCII。
    目录排在前面（如果传入时已排序）；文件按传入顺序。
    """
    branch = "└─ " if _is_last else "├─ "
    name = tree.get("name", "")
    typ = tree.get("type", "dir")
    label = name if name else "."  # 根用 "."
    if _level == 0:
        click.echo(label)
    else:
        click.echo(f"{_prefix}{branch}{label}")

    if max_depth is not None and _level >= max_depth:
        return

    children = tree.get("children", [])
    for i, child in enumerate(children):
        is_last = (i == len(children) - 1)
        new_prefix = _prefix + ("   " if _is_last else "│  ")
        _print_tree_ascii(child, max_depth=max_depth, _prefix=new_prefix, _is_last=is_last, _level=_level + 1)


@main.command(help="Print or export the folder plan as a tree.")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
@click.option("--relative/--absolute", default=True, show_default=True, help="Show paths relative to --base.")
@click.option("--depth", type=int, default=None, help="Max depth to print (tree mode).")
@click.option("--show-files/--no-show-files", default=True, show_default=True,
              help="Whether to include files in the tree object.")
@click.option("--sort", type=click.Choice(["template", "alpha"]), default="template", show_default=True,
              help="Sort children by template order or alphabetically.")
@click.option("--format", "fmt", type=click.Choice(["tree", "json", "yaml"]), default="tree", show_default=True,
              help="Output format.")
@click.option("--out", "out_path", type=click.Path(dir_okay=False), default=None,
              help="If set, write to file instead of stdout.")
@click.option("--status", is_flag=True, help="Annotate nodes with check status (existing/missing/conflict/planned).")
@click.option("--portable",
              type=click.Choice(["auto", "windows", "posix", "mac", "all", "none"]),
              default="auto", show_default=True,
              help="Name portability rules (same as `check`).")
@click.option("--max-path-len", default=240, show_default=True, type=int,
              help="Max path length warning (same as `check`).")
@click.option("--follow-symlinks/--no-follow-symlinks", default=False, show_default=True)
def tree(template_path, vars_path, base_dir, relative, depth, show_files, sort, fmt, out_path,
         status, portable, max_path_len, follow_symlinks):
    plan = plan_api.make_plan(template_path, base_dir, vars_path)

    status_map = issues_map = None
    if status:
        # 借用 checker 的审计逻辑
        from ..core.checker import audit_filesystem
        rep = audit_filesystem(
            plan,
            base_dir,
            follow_symlinks=follow_symlinks,
            max_path_len=max_path_len,
            portable=portable,
        )
        status_map, issues_map = _build_status_maps(rep)

    # 生产输出
    if fmt == "tree":
        tree_obj = plan.to_tree(
            base_dir=base_dir, relative=relative, include_files=show_files, sort=sort,
            status_map=status_map, issues_map=issues_map
        )
        text = _render_ascii_tree(tree_obj, max_depth=depth, colorize=status)
    elif fmt == "json":
        obj = plan.to_tree(
            base_dir=base_dir, relative=relative, include_files=show_files, sort=sort,
            status_map=status_map, issues_map=issues_map
        )
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    else:  # yaml
        obj = plan.to_tree(
            base_dir=base_dir, relative=relative, include_files=show_files, sort=sort,
            status_map=status_map, issues_map=issues_map
        )
        try:
            import yaml
            text = yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)
        except Exception:
            text = _fallback_yaml(obj)

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(text, encoding="utf-8")
        click.echo(f"Wrote {fmt} to: {out_path}")
    else:
        click.echo(text)


def _render_ascii_tree(tree: dict, *, max_depth: int | None = None, colorize: bool = False) -> str:
    def color_name(name: str, status: str | None):
        if not colorize or not status:
            return name
        # 颜色：existing=green, missing=red, conflict=yellow, planned=white
        if status == "existing":
            return click.style(name, fg="green")
        if status == "missing":
            return click.style(name, fg="red")
        if status == "conflict":
            return click.style(name, fg="yellow")
        return name  # planned/no-status

    lines: List[str] = []

    def rec(n: dict, prefix: str = "", is_last: bool = True, level: int = 0):
        branch = "└─ " if is_last else "├─ "
        raw_label = n.get("name") or "."
        status = n.get("status")
        label = color_name(raw_label, status)
        suffix = ""
        if colorize and status in ("missing", "conflict"):
            suffix = " " + click.style(f"[{status}]", fg=("red" if status == "missing" else "yellow"))
        if level == 0:
            lines.append(label + suffix)
        else:
            lines.append(f"{prefix}{branch}{label}{suffix}")

        if max_depth is not None and level >= max_depth:
            return
        kids = n.get("children", [])
        for i, c in enumerate(kids):
            last = (i == len(kids) - 1)
            new_prefix = prefix + ("   " if is_last else "│  ")
            rec(c, new_prefix, last, level + 1)

    rec(tree)
    return "\n".join(lines)


def _fallback_yaml(obj, indent=0):
    """
    无 PyYAML 时的简单 YAML-like 文本，仅为“看一眼”用途。
    """
    sp = "  " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{sp}{k}:")
                lines.append(_fallback_yaml(v, indent + 1))
            else:
                lines.append(f"{sp}{k}: {v}")
        return "\n".join(lines)
    elif isinstance(obj, list):
        lines = []
        for it in obj:
            if isinstance(it, (dict, list)):
                lines.append(f"{sp}-")
                lines.append(_fallback_yaml(it, indent + 1))
            else:
                lines.append(f"{sp}- {it}")
        return "\n".join(lines)
    else:
        return f"{sp}{obj}"


def _build_status_maps(rep) -> tuple[dict, dict]:
    import os
    def _norm(p: str) -> str:
        p = os.path.normpath(p)
        if os.name == "nt":
            p = os.path.normcase(p)
        return p

    status = {}

    for p in rep.existing_dirs + rep.existing_files:
        status[_norm(p)] = "existing"
    for p in rep.missing_dirs + rep.missing_files:
        status[_norm(p)] = "missing"
    for c in rep.conflicts:
        status[_norm(c.path)] = "conflict"

    issues = {}
    for ni in rep.name_issues:
        key = _norm(ni.path)
        issues.setdefault(key, []).append(ni.reason)

    # 对未命中的计划项，默认 "planned"
    for p in rep.planned_dirs + rep.planned_files:
        key = _norm(p)
        status.setdefault(key, "planned")

    return status, issues
