from __future__ import annotations
import re
from datetime import date, timedelta

_GEN_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")  # 捕获 {{ ... }}

def _parse_kv(s: str) -> dict:
    """
    解析 'k=v; k2=v2' 形式；去空格；支持引号包裹；大小写不敏感的键
    """
    out = {}
    for part in [p.strip() for p in s.split(";") if p.strip()]:
        if "=" not in part:
            raise ValueError(f"Bad generator parameter: {part}")
        k, v = part.split("=", 1)
        k = k.strip().lower()
        v = v.strip().strip("'\"")
        out[k] = v
    return out

def _range_int(start: int, stop: int, step: int = 1, pad: int | None = None):
    if step == 0:
        raise ValueError("int step cannot be 0")
    cur = start
    if step > 0:
        cond = lambda x: x <= stop
    else:
        cond = lambda x: x >= stop
    res = []
    while cond(cur):
        s = str(cur)
        if pad is not None:
            s = s.zfill(int(pad))
        res.append(s)
        cur += step
    return res

def _range_alpha(start: str, stop: str, step: int = 1):
    if len(start) != 1 or len(stop) != 1:
        raise ValueError("alpha start/stop must be single letters")
    a = ord(start)
    b = ord(stop)
    if step == 0:
        raise ValueError("alpha step cannot be 0")
    res = []
    if step > 0:
        rng = range(a, b + 1, step)
    else:
        rng = range(a, b - 1, step)
    for code in rng:
        res.append(chr(code))
    return res

def _add_months(d: date, months: int) -> date:
    # 纯标准库实现的加月
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    # 修正天数（月底问题）
    mdays = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(d.day, mdays[m-1])
    return date(y, m, day)

def _range_date(start: date, stop: date, step_spec: str, fmt: str = "%Y%m%d"):
    """
    step_spec: 'Xd' 天, 'Xm' 月, 'Xy' 年（X为整数，可为负）
    """
    if not step_spec:
        raise ValueError("date step is required (e.g., 1m, 7d, 1y)")
    unit = step_spec[-1].lower()
    try:
        n = int(step_spec[:-1])
    except Exception:
        raise ValueError(f"invalid date step: {step_spec}")
    if n == 0:
        raise ValueError("date step cannot be 0")

    cur = start
    res = []
    def leq(a, b): return a <= b
    def geq(a, b): return a >= b
    cmp = leq if n > 0 else geq

    while cmp(cur, stop):
        res.append(cur.strftime(fmt))
        if unit == "d":
            cur = cur + timedelta(days=n)
        elif unit == "m":
            cur = _add_months(cur, n)
        elif unit == "y":
            cur = _add_months(cur, n * 12)
        else:
            raise ValueError(f"unknown date step unit: {unit}")
    return res

def _expand_one(expr: str) -> list[str]:
    """
    将单个生成器表达式（不含花括号）展开为字符串列表
    形如：'int: start=0; stop=10; step=2; pad=3'
    """
    if ":" not in expr:
        raise ValueError(f"Bad generator: {expr}")
    t, rest = expr.split(":", 1)
    typ = t.strip().lower()
    kv = _parse_kv(rest)

    if typ == "int":
        start = int(kv.get("start"))
        stop  = int(kv.get("stop"))
        step  = int(kv.get("step", "1"))
        pad   = kv.get("pad")
        pad_n = int(pad) if pad is not None else None
        return _range_int(start, stop, step, pad_n)

    elif typ == "alpha":
        start = kv.get("start")
        stop  = kv.get("stop")
        step  = int(kv.get("step", "1"))
        if not start or not stop:
            raise ValueError("alpha requires start/stop")
        if len(start) != 1 or len(stop) != 1:
            raise ValueError("alpha start/stop must be a single char")
        return _range_alpha(start, stop, step)

    elif typ == "date":
        s = kv.get("start"); e = kv.get("stop")
        if not s or not e:
            raise ValueError("date requires start/stop")
        fmt  = kv.get("fmt", "%Y%m%d")
        step = kv.get("step")
        y1, m1, d1 = [int(x) for x in s.split("-")]
        y2, m2, d2 = [int(x) for x in e.split("-")]
        return _range_date(date(y1, m1, d1), date(y2, m2, d2), step, fmt)

    else:
        raise ValueError(f"Unknown generator type: {typ}")

def expand_generators(s: str) -> list[str]:
    """
    对包含 0..N 个 {{...}} 生成器的字符串做**笛卡尔积展开**。
    若不存在生成器，返回 [s]。
    返回的每一项仍可能包含 {var|filter}，由后续变量渲染处理。
    """
    tokens = list(_GEN_PATTERN.finditer(s))
    if not tokens:
        return [s]

    # 分段：常量片段 + 生成器片段
    parts = []
    last = 0
    gens = []
    for m in tokens:
        if m.start() > last:
            parts.append(s[last:m.start()])
        gens.append(m.group(1).strip())  # 不带 {{ }}
        parts.append(None)  # 占位：此处为生成器
        last = m.end()
    if last < len(s):
        parts.append(s[last:])

    # 递归做笛卡尔积
    out = [""]  # 累积字符串
    gen_idx = 0
    for p in parts:
        if p is None:
            exp_list = _expand_one(gens[gen_idx])
            gen_idx += 1
            out = [prefix + x for prefix in out for x in exp_list]
        else:
            out = [prefix + p for prefix in out]
    return out
