"""Shared deterministic rules extracted from IntentFlow V0.1."""
import fnmatch
import math
import operator
import re

def matches(path: str, pattern: str) -> bool:
    path = path.replace("\\", "/")
    pattern = pattern.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    while pattern.startswith("./"):
        pattern = pattern[2:]
    if pattern.endswith("/**"):
        return path == pattern[:-3] or path.startswith(pattern[:-2])
    return fnmatch.fnmatchcase(path, pattern)

def target_passed(targets, evidence):
    failures = []
    if not targets:
        return False, ["No field targets declared"]
    ops = {"==": operator.eq, "!=": operator.ne, "<=": operator.le,
           ">=": operator.ge, "<": operator.lt, ">": operator.gt}
    for target in targets:
        match = re.fullmatch(r"\s*([A-Za-z_]\w*)\s*(==|!=|<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)\s*", str(target))
        if not match:
            failures.append(f"unsupported target expression: {target}")
            continue
        key, op, expected = match.groups()
        actual = evidence.get(key)
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
            failures.append(f"{key}: missing or nonnumeric evidence")
        elif not ops[op](actual, float(expected)):
            failures.append(f"{key}: expected {op} {expected}, got {actual}")
    return not failures, failures
