"""Conservative Python import and unconditional-entry-call constraints."""
import ast
from datetime import date
from fnmatch import fnmatchcase

from adapters.git import commit, git, repository
from intentflow_core.behavior import ArchitectureRule, relative_path


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted(node.value)
        return parent + "." + node.attr if parent else ""
    return ""


def inspect_source(source, path, config):
    rule = ArchitectureRule.model_validate(config)
    findings = []
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, RecursionError, ValueError):
        return [{"path": path, "line": 1, "status": "UNKNOWN", "reason": "源码无法静态解析"}]
    aliases = {}
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
            aliases.update({a.asname or a.name.split(".")[0]: a.name if a.asname else a.name.split(".")[0] for a in node.names})
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            names = [module]
            aliases.update({a.asname or a.name: module + "." + a.name for a in node.names})
            if node.level and rule.forbidden_imports:
                findings.append({"path": path, "line": node.lineno, "status": "UNKNOWN",
                                 "reason": "相对导入需结合包结构人工复核"})
        for name in names:
            if any(name == forbidden or name.startswith(forbidden + ".") or fnmatchcase(name, forbidden)
                   for forbidden in rule.forbidden_imports):
                findings.append({"path": path, "line": node.lineno, "status": "VIOLATION",
                                 "reason": "导入了受限模块 " + name})
        if rule.forbidden_imports and isinstance(node, ast.Call) and (
                dotted(node.func) in {"__import__", "eval", "exec", "getattr"}
                or dotted(node.func).startswith("importlib.")):
            findings.append({"path": path, "line": node.lineno, "status": "UNKNOWN",
                             "reason": "动态加载或反射无法可靠判断模块依赖"})
    def call_name(call):
        name = dotted(call.func)
        head, _, tail = name.partition(".")
        return aliases.get(head, head) + (("." + tail) if tail else "")
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and (n.name in rule.entry_functions if rule.entry_functions else not n.name.startswith("_"))]
    if rule.required_calls and not functions:
        findings.append({"path": path, "line": 1, "status": "UNKNOWN", "reason": "未找到约定的入口函数"})
    for func in functions:
        dynamic = any(isinstance(n, ast.Call) and (dotted(n.func) in {"getattr", "eval", "exec", "__import__"}
                      or dotted(n.func).startswith("importlib.")) for n in ast.walk(func))
        # Only unconditional leading calls are accepted as structural evidence.
        # A call buried in `if False:` cannot satisfy a guard requirement.
        leading = set()
        for statement in func.body:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                continue
            value = getattr(statement, "value", None)
            if isinstance(statement, (ast.Expr, ast.Assign, ast.AnnAssign, ast.Return)) and isinstance(value, ast.Call):
                name = call_name(value)
                if name not in rule.required_calls:
                    break
                leading.add(name)
                if isinstance(statement, ast.Return):
                    break
            else:
                break
        all_calls = {call_name(n) for n in ast.walk(func) if isinstance(n, ast.Call)}
        for required in rule.required_calls:
            if required not in leading:
                uncertain = dynamic or required in all_calls
                findings.append({"path": path, "line": func.lineno, "function": func.name,
                    "status": "UNKNOWN" if uncertain else "VIOLATION",
                    "reason": ("需人工复核调用是否覆盖所有入口路径：" if uncertain else "入口缺少约定调用：") + required})
    if rule.exception_until and date.fromisoformat(rule.exception_until) >= date.today():
        for item in findings:
            if item["status"] == "VIOLATION":
                item.update(status="EXEMPT", exception_reason=rule.exception_reason, exception_until=rule.exception_until)
    for item in findings:
        item["business_reason"] = rule.reason
    return findings


def scan(root, ref, rules):
    root, resolved = repository(root), commit(root, ref)
    paths = git(root, "ls-tree", "-r", "--name-only", resolved).splitlines()
    files = [p for p in paths if p.endswith(".py")]
    if len(files) > 200:
        raise ValueError("首版架构扫描最多支持 200 个 Python 文件")
    result = []
    for rule in rules:
        matching = [p for p in files if fnmatchcase(p, rule["content"]["scope"])]
        if not matching:
            result.append({"rule_id": rule["id"], "path": rule["content"]["scope"], "line": 0,
                           "status": "UNKNOWN", "reason": "没有匹配文件，不能判为通过"})
        for path in matching:
            relative_path(path, python=True)
            source = git(root, "show", resolved + ":" + path)
            if len(source) > 1_000_000:
                findings = [{"path": path, "line": 0, "status": "UNKNOWN", "reason": "文件超过静态分析大小限制"}]
            else:
                findings = inspect_source(source, path, rule["content"])
            result.extend({**finding, "rule_id": rule["id"], "rule_revision": rule["revision_id"]} for finding in findings)
    return result


def compare(root, current_ref, previous_ref, rules):
    current = scan(root, current_ref, rules)
    old = scan(root, previous_ref, rules) if previous_ref else None
    def key(item):
        return (item["rule_id"], item["path"], item.get("function", ""), item["reason"])
    prior = {key(item) for item in old or []}
    for item in current:
        item["introduced"] = key(item) not in prior if old is not None else None
    status = "FAIL" if any(f["status"] == "VIOLATION" for f in current) else (
        "UNKNOWN" if not rules or any(f["status"] == "UNKNOWN" for f in current) else "PASS")
    return {"status": status, "findings": current, "previous_findings": old,
            "scope": "受支持的 Python 静态结构检查，不等于证明所有运行路径安全"}
