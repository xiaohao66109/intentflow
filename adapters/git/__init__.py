"""Git commit snapshots; no live checkout mutations during verification."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
from intentflow_core.rules import matches

def git(root, *args):
    proc = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=root,
                          capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    if proc.returncode:
        raise ValueError(proc.stderr.strip() or "Git command failed")
    return proc.stdout

def repository(path):
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Repository directory does not exist")
    actual = Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()
    if actual != root:
        raise ValueError("Choose the Git repository root")
    return root

def clone_repository(source, target, branch="", base_commit="HEAD"):
    """Clone a local path or URL without invoking a shell and pin the requested base."""
    destination = Path(target).resolve()
    if destination.exists():
        raise ValueError("Repository destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    args = ["git", "clone", "--no-hardlinks"]
    if branch:
        args += ["--branch", branch]
    args += ["--", str(source), str(destination)]
    proc = subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    if proc.returncode:
        raise ValueError(proc.stderr.strip() or "Unable to clone repository")
    try:
        resolved = commit(destination, base_commit or "HEAD")
        git(destination, "checkout", "--quiet", "--detach", resolved)
        return destination, resolved
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

def commit(root, ref):
    if not ref or ref.startswith("-"):
        raise ValueError("Invalid commit reference")
    return git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()

def context(root):
    root = repository(root)
    names = git(root, "ls-files").splitlines()
    readme = next((p for p in names if p.lower() == "readme.md"), "")
    suffixes = {Path(name).suffix.lower() for name in names}
    language_map = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
                    ".java": "Java", ".go": "Go", ".rs": "Rust", ".cs": "C#", ".rb": "Ruby"}
    languages = sorted({language_map[item] for item in suffixes if item in language_map})
    tests = [name for name in names if name.startswith(("test/", "tests/", "spec/")) or Path(name).name.startswith("test_")]
    return {"files": names[:300], "repository_structure": names[:300],
            "readme": (root / readme).read_text(encoding="utf-8", errors="replace")[:20000] if readme else "",
            "languages": languages, "test_structure": tests[:100],
            "history": git(root, "log", "-8", "--oneline"), "head": commit(root, "HEAD")}

def verify(root, baseline, final, contract):
    root = repository(root)
    baseline, final = commit(root, baseline), commit(root, final)
    git(root, "merge-base", "--is-ancestor", baseline, final)
    # no-renames returns deleted old names AND added new names, so renames cannot bypass scope.
    files = sorted(set(git(root, "diff", "--no-renames", "--name-only", "-z", baseline, final, "--").strip("\0").split("\0")) - {""})
    protected = [p for p in files if any(matches(p, g) for g in contract["protected_scope"])]
    outside = [p for p in files if not any(matches(p, g) for g in contract["allowed_scope"])]
    report = {"baseline_commit": baseline, "final_commit": final, "changed_files": files,
              "diff": git(root, "diff", "--no-ext-diff", "--no-textconv", baseline, final, "--")[:100000],
              "L1": {"status": "REJECT" if protected or outside else "PASS",
                     "protected_violations": protected, "outside_allowed": outside},
              "L2": [], "L3": [], "L4": [], "evidence_matrix": []}
    for pattern in contract["protected_scope"]:
        report["evidence_matrix"].append({"level": "L1", "intent_clause": f"保护范围：{pattern}",
            "evidence": "版本差异中的变更文件", "result": "REJECT" if any(matches(p, pattern) for p in protected) else "PASS"})
    for pattern in contract["allowed_scope"]:
        report["evidence_matrix"].append({"level": "L1", "intent_clause": f"允许范围：{pattern}",
            "evidence": "版本差异中的变更文件", "result": "REJECT" if any(not any(matches(p, g) for g in contract["allowed_scope"]) for p in files) else "PASS"})
    with tempfile.TemporaryDirectory(prefix="intentflow-verify-") as tmp:
        # Clone local immutable commit, ignoring uncommitted working-tree files.
        git(tmp, "clone", "--quiet", "--no-hardlinks", "--", str(root), str(Path(tmp) / "snapshot"))
        snapshot = Path(tmp) / "snapshot"
        git(snapshot, "checkout", "--quiet", "--detach", final)
        commands = [("L2", c, contract.get("protected_behavior", [])[i] if i < len(contract.get("protected_behavior", [])) else "保护行为测试") for i, c in enumerate(contract["preservation_tests"])]
        commands += [("L3", c, contract.get("invariants", [])[i] if i < len(contract.get("invariants", [])) else "不变量") for i, c in enumerate(contract.get("invariant_tests", []))]
        commands += [("L4", c, contract.get("acceptance_criteria", [])[i] if i < len(contract.get("acceptance_criteria", [])) else "验收标准") for i, c in enumerate(contract["acceptance_tests"])]
        for level, command, clause in commands:
            argv = [sys.executable if value == "{python}" else value for value in command]
            try:
                from adapters.execution import bounded_run
                import threading
                execution = bounded_run(argv, snapshot, threading.Event(), timeout=60)
                empty = "Ran 0 tests" in execution["output"] or "no tests ran" in execution["output"].lower()
                result = {"command": command, "exit_code": execution["exit_code"]
                          if execution["execution_status"] == "FINISHED" and not empty else -1,
                          "output": execution["output"][-16000:], "execution_status": execution["execution_status"]}
            except (OSError, subprocess.TimeoutExpired) as exc:
                result = {"command": command, "exit_code": -1, "output": str(exc)}
            report[level].append(result)
            report["evidence_matrix"].append({"level": level, "intent_clause": clause,
                "evidence": " ".join(command), "result": "PASS" if result["exit_code"] == 0 else "REJECT"})
    passed = not protected and not outside and all(r["exit_code"] == 0 for layer in ("L2", "L3", "L4") for r in report[layer])
    report["status"] = "PASS" if passed else "REJECT"
    report["findings"] = (
        (["PROTECTED_SCOPE_VIOLATION"] if protected else [])
        + (["ALLOWED_SCOPE_VIOLATION"] if outside else [])
        + (["PRESERVATION_TEST_FAILURE"] if any(r["exit_code"] for r in report["L2"]) else [])
        + (["INVARIANT_TEST_FAILURE"] if any(r["exit_code"] for r in report["L3"]) else [])
        + (["ACCEPTANCE_TEST_FAILURE"] if any(r["exit_code"] for r in report["L4"]) else [])
    )
    return report
