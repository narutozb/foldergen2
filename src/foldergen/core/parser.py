import re
from typing import Any, Callable, Dict

# 简易过滤器注册（如 pad, slug）
_FILTERS: Dict[str, Callable[..., str]] = {}

def register_filter(name: str, fn: Callable[..., str]) -> None:
    _FILTERS[name] = fn

def _filter_pad(value: Any, n: int = 2) -> str:
    s = f"{int(value)}"
    return s.zfill(int(n))

def _filter_slug(value: Any) -> str:
    s = str(value)
    s = s.strip().lower().replace(" ", "_")
    return s

# 注册内置
register_filter("pad", _filter_pad)
register_filter("slug", _filter_slug)

# 模板占位形如 {key|filter(arg)} 或 {key}
_PATTERN = re.compile(r"\{([^{}]+)\}")

def render_string(template: str, context: Dict[str, Any]) -> str:
    """
    渲染单个字符串模板。
    支持：
    - {key}
    - {key|pad(3)}
    - {key|slug}
    多个过滤器串联也可：{key|slug|pad(10)}（会把slug结果再pad）
    """
    def repl(m: re.Match) -> str:
        expr = m.group(1).strip()
        parts = [p.strip() for p in expr.split("|")]
        key = parts[0]
        if key not in context:
            raise KeyError(f"Missing variable: {key}")
        val: Any = context[key]

        # 应用过滤器链
        for p in parts[1:]:
            if "(" in p and p.endswith(")"):
                fname = p[: p.index("(")].strip()
                arg_str = p[p.index("(") + 1 : -1].strip()
                args = []
                if arg_str:
                    # 仅支持逗号分隔的简单参数（数字/字符串）
                    for raw in arg_str.split(","):
                        raw = raw.strip()
                        if raw.isdigit():
                            args.append(int(raw))
                        else:
                            # 去掉可能的引号
                            args.append(raw.strip("'\""))
                fn = _FILTERS.get(fname)
                if not fn:
                    raise ValueError(f"Unknown filter: {fname}")
                val = fn(val, *args)
            else:
                fn = _FILTERS.get(p)
                if not fn:
                    raise ValueError(f"Unknown filter: {p}")
                val = fn(val)

        return str(val)

    return _PATTERN.sub(repl, template)
