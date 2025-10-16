# src/foldergen/core/gen_syntax.py
from __future__ import annotations
import re
from datetime import date, timedelta

_GEN_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")


class GeneratorSyntaxError(ValueError):
    def __init__(self, message: str, fragment: str | None = None):
        if fragment:
            super().__init__(f"{message}  [at: {{ {{ {fragment} }} }} ]")
        else:
            super().__init__(message)


def _parse_kv(s: str) -> dict:
    out = {}
    for part in [p.strip() for p in s.split(";") if p.strip()]:
        if "=" not in part:
            raise GeneratorSyntaxError("Bad generator parameter (missing '=')", s)
        k, v = part.split("=", 1)
        k = k.strip().lower()
        v = v.strip().strip("'\"")
        out[k] = v
    return out


def _range_int_count(start: int, stop: int, step: int) -> int:
    if step == 0:
        raise GeneratorSyntaxError("int step cannot be 0", f"int: start={start}; stop={stop}; step=0")
    if (step > 0 and start > stop) or (step < 0 and start < stop):
        return 0
    return (abs(stop - start) // abs(step)) + 1


def _range_alpha_count(a: int, b: int, step: int) -> int:
    if step == 0:
        raise GeneratorSyntaxError("alpha step cannot be 0", "alpha: step=0")
    if (step > 0 and a > b) or (step < 0 and a < b):
        return 0
    return (abs(b - a) // abs(step)) + 1


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    mdays = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(d.day, mdays[m - 1])
    return date(y, m, day)


def _range_date_count(start: date, stop: date, step_spec: str) -> int:
    if not step_spec:
        raise GeneratorSyntaxError("date step is required, e.g. 1m/7d/1y", "date: step=")
    unit = step_spec[-1].lower()
    try:
        n = int(step_spec[:-1])
    except Exception:
        raise GeneratorSyntaxError(f"invalid date step: {step_spec}", f"date: step={step_spec}")
    if n == 0:
        raise GeneratorSyntaxError("date step cannot be 0", f"date: step={step_spec}")
    # 估算：逐步推进计数，避免生成实际列表
    cur = start
    count = 0

    def leq(a, b):
        return a <= b

    def geq(a, b):
        return a >= b

    cmp = leq if n > 0 else geq
    while cmp(cur, stop):
        count += 1
        if unit == "d":
            cur = cur + timedelta(days=n)
        elif unit == "m":
            cur = _add_months(cur, n)
        elif unit == "y":
            cur = _add_months(cur, n * 12)
        else:
            raise GeneratorSyntaxError(f"unknown date step unit: {unit}", f"date: step={step_spec}")
        if count > 1_000_000:  # 防御性上限，避免异常模板导致死循环
            break
    return count


def _expand_one(expr: str) -> list[str]:
    if ":" not in expr:
        raise GeneratorSyntaxError("Bad generator (missing type prefix like int/alpha/date)", expr)
    t, rest = expr.split(":", 1)
    typ = t.strip().lower()
    kv = _parse_kv(rest)

    if typ == "int":
        try:
            start = int(kv.get("start"))
            stop = int(kv.get("stop"))
        except Exception:
            raise GeneratorSyntaxError("int requires numeric start/stop", expr)
        step = int(kv.get("step", "1"))
        pad = kv.get("pad")
        pad_n = int(pad) if pad is not None else None
        # 预检
        _ = _range_int_count(start, stop, step)
        # 实际生成
        cur = start
        cond = (lambda x: x <= stop) if step > 0 else (lambda x: x >= stop)
        out = []
        while cond(cur):
            s = str(cur)
            if pad_n is not None:
                s = s.zfill(int(pad_n))
            out.append(s)
            cur += step
        return out

    elif typ == "alpha":
        start = kv.get("start");
        stop = kv.get("stop")
        if not start or not stop or len(start) != 1 or len(stop) != 1:
            raise GeneratorSyntaxError("alpha requires single-char start/stop", expr)
        a = ord(start);
        b = ord(stop)
        step = int(kv.get("step", "1"))
        _ = _range_alpha_count(a, b, step)
        rng = range(a, b + (1 if step > 0 else -1), step)
        return [chr(c) for c in rng]

    elif typ == "date":
        s = kv.get("start");
        e = kv.get("stop")
        if not s or not e:
            raise GeneratorSyntaxError("date requires start/stop", expr)
        y1, m1, d1 = [int(x) for x in s.split("-")]
        y2, m2, d2 = [int(x) for x in e.split("-")]
        step = kv.get("step", None)
        fmt = kv.get("fmt", "%Y%m%d")
        # 预检只算数量
        _ = _range_date_count(date(y1, m1, d1), date(y2, m2, d2), step)
        # 实际生成
        cur = date(y1, m1, d1);
        stop = date(y2, m2, d2)
        unit = step[-1].lower();
        n = int(step[:-1])
        out = []
        cmp = (lambda a, b: a <= b) if n > 0 else (lambda a, b: a >= b)
        while cmp(cur, stop):
            out.append(cur.strftime(fmt))
            if unit == "d":
                cur = cur + timedelta(days=n)
            elif unit == "m":
                cur = _add_months(cur, n)
            else:
                cur = _add_months(cur, n * 12)
        return out

    elif typ == "enum":
        items_str = kv.get("items")
        if not items_str:
            raise GeneratorSyntaxError("enum requires items parameter", expr)
        sep = kv.get("sep", ",")
        pad = kv.get("pad", "true").lower() != "false"
        raw_items = items_str.split(sep)
        if pad:
            raw_items = [x.strip() for x in raw_items]
        return [x for x in raw_items if x]


    else:
        raise GeneratorSyntaxError(f"Unknown generator type: {typ}", expr)


def expand_generators(s: str) -> list[str]:
    tokens = list(_GEN_PATTERN.finditer(s))
    if not tokens:
        return [s]
    parts = []
    last = 0
    gens = []
    for m in tokens:
        if m.start() > last:
            parts.append(s[last:m.start()])
        gens.append(m.group(1).strip())
        parts.append(None)
        last = m.end()
    if last < len(s):
        parts.append(s[last:])

    out = [""]
    gen_idx = 0
    for p in parts:
        if p is None:
            try:
                exp_list = _expand_one(gens[gen_idx])
            except GeneratorSyntaxError as e:
                raise
            gen_idx += 1
            out = [prefix + x for prefix in out for x in exp_list]
        else:
            out = [prefix + p for prefix in out]
    return out


def estimate_generators_count(s: str) -> int:
    """
    估算字符串 s 中所有 {{...}} 生成器展开的总组合数（笛卡尔积），不产生实际列表。
    无生成器则返回 1。
    """
    tokens = list(_GEN_PATTERN.finditer(s))
    if not tokens:
        return 1
    total = 1
    for m in tokens:
        expr = m.group(1).strip()
        if ":" not in expr:
            raise GeneratorSyntaxError("Bad generator (missing type)", expr)
        typ, rest = expr.split(":", 1)
        kv = _parse_kv(rest)
        if typ.strip().lower() == "int":
            start = int(kv.get("start"));
            stop = int(kv.get("stop"))
            step = int(kv.get("step", "1"))
            total *= _range_int_count(start, stop, step)
        elif typ.strip().lower() == "alpha":
            s1 = kv.get("start");
            s2 = kv.get("stop")
            if not s1 or not s2 or len(s1) != 1 or len(s2) != 1:
                raise GeneratorSyntaxError("alpha requires single-char start/stop", expr)
            step = int(kv.get("step", "1"))
            total *= _range_alpha_count(ord(s1), ord(s2), step)
        elif typ.strip().lower() == "date":
            s0 = kv.get("start");
            s1 = kv.get("stop");
            step = kv.get("step", None)
            if not s0 or not s1 or not step:
                raise GeneratorSyntaxError("date requires start/stop/step", expr)
            y1, m1, d1 = [int(x) for x in s0.split("-")]
            y2, m2, d2 = [int(x) for x in s1.split("-")]
            total *= _range_date_count(date(y1, m1, d1), date(y2, m2, d2), step)

        elif typ.strip().lower() == "enum":
            items_str = kv.get("items")
            if not items_str:
                raise GeneratorSyntaxError("enum requires items parameter", expr)
            sep = kv.get("sep", ",")
            count = len([x for x in items_str.split(sep) if x.strip()])
            total *= max(1, count)

        else:
            raise GeneratorSyntaxError(f"Unknown generator type: {typ}", expr)
        if total > 1_000_000:
            break
    return total
