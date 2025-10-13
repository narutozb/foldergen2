import json
import click
from pathlib import Path
from ..api import plan_api, generator_api
from ..core.checker import audit_filesystem
from ..core.models import BuildPlan
from ..core.validator import find_duplicate_rendered_paths


@click.group(help="Generate folder structures from template strings.")
def main():
    pass


@main.command(help="Show build plan (no filesystem changes).")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
def plan(template_path, vars_path, base_dir):
    plan = plan_api.make_plan(template_path, base_dir, vars_path)
    # click.echo(json.dumps([i.__dict__ for i in plan.items], ensure_ascii=False, indent=2))
    for i in plan.items:
        print(i)


@main.command(help="Simulate generation (print operations, no writes).")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
def simulate(template_path, vars_path, base_dir):
    generator_api.simulate(template_path, base_dir, vars_path)


@main.command(help="Apply plan and write to filesystem.")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
def build(template_path, vars_path, base_dir):
    generator_api.build(template_path, base_dir, vars_path)


@main.command(help="Check filesystem against template plan and report issues.")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
@click.option("--follow-symlinks/--no-follow-symlinks", default=False, show_default=True)
@click.option("--max-path-len", default=240, show_default=True, type=int, help="Max path length to warn.")
@click.option("--portable",
              type=click.Choice(["auto","windows","posix","mac","all","none"]),
              default="auto", show_default=True,
              help="Name portability rules to apply.")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json", show_default=True)
@click.option("--strict", is_flag=True, help="Non-zero exit if any issue found (good for CI).")
def check(template_path, vars_path, base_dir, follow_symlinks, max_path_len, portable, fmt, strict):
    plan = plan_api.make_plan(template_path, base_dir, vars_path)
    dup = find_duplicate_rendered_paths(plan)

    rep = audit_filesystem(
        plan,
        base_dir,
        follow_symlinks=follow_symlinks,
        max_path_len=max_path_len,
        portable=portable,   # ⬅ 传入
    )
    rep.duplicate_planned_paths = dup or rep.duplicate_planned_paths

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


def _print_tree_ascii(tree: dict, *, max_depth: int | None = None, _prefix: str = "", _is_last: bool = True, _level: int = 0):
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

@main.command(help="Print the folder plan as an ASCII tree (no filesystem writes).")
@click.option("--template", "template_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--vars", "vars_path", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--base", "base_dir", required=True, type=click.Path(file_okay=False))
@click.option("--relative/--absolute", default=True, show_default=True, help="Show tree paths relative to --base.")
@click.option("--depth", type=int, default=None, help="Max depth to print (default: unlimited).")
@click.option("--show-files/--no-show-files", default=True, show_default=True, help="Whether to include files in the tree.")
@click.option("--sort", type=click.Choice(["template", "alpha"]), default="template", show_default=True, help="Sort children by template order or alphabetically.")
def tree(template_path, vars_path, base_dir, relative, depth, show_files, sort):
    plan = plan_api.make_plan(template_path, base_dir, vars_path)
    tree_obj = plan.to_tree(base_dir=base_dir, relative=relative, include_files=show_files, sort=sort)
    _print_tree_ascii(tree_obj, max_depth=depth)