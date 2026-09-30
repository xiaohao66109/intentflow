"""Pinned snapshots and bounded test execution; native mode is NOT a sandbox."""
from __future__ import annotations

import importlib.metadata
import io
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from uuid import uuid4

from adapters.git import commit, git, repository
from intentflow_core.behavior import relative_path
from intentflow_core.versioning import digest


def environment(mode="native"):
    packages = sorted((d.metadata.get("Name", ""), d.version) for d in importlib.metadata.distributions())
    return {"python": sys.version.split()[0], "platform": platform.platform(), "dependencies": digest(packages),
            "mode": mode, "container_image": os.environ.get("INTENTFLOW_EXECUTION_IMAGE", "") if mode == "docker" else ""}


def capabilities():
    # No pull or installation is performed. Formal isolation must be provisioned.
    docker = shutil.which("docker")
    image = os.environ.get("INTENTFLOW_EXECUTION_IMAGE", "")
    ready = False
    if docker and "@sha256:" in image:
        try:
            check = subprocess.run([docker, "image", "inspect", image], capture_output=True, timeout=5)
            ready = check.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"native": {"available": True, "isolated": False, "label": "本机受信项目执行（不是安全沙箱）"},
            "docker": {"available": ready, "isolated": ready, "label": "预配置容器隔离执行",
                       "reason": "" if ready else "未配置已下载、带摘要的 INTENTFLOW_EXECUTION_IMAGE；不会自动安装或拉取"}}


def _bounded_path(path, allowed_root, *, must_exist=False):
    candidate = Path(path).expanduser().resolve(strict=must_exist)
    if allowed_root is not None:
        boundary = Path(allowed_root).expanduser().resolve(strict=True)
        if candidate != boundary and not candidate.is_relative_to(boundary):
            raise ValueError("工作目录或输出路径越出允许范围")
    return candidate


def snapshot(root, ref, destination, *, allowed_destination_root=None):
    root = repository(root)
    destination = _bounded_path(destination, allowed_destination_root)
    if destination.exists():
        raise FileExistsError("快照目标已存在，拒绝覆盖")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.partial-{uuid4().hex}"
    resolved = commit(root, ref)
    # Bound archive size before allocating it. Only tracked files are executed.
    listing = git(root, "ls-tree", "-rl", resolved)
    total = 0
    for row in listing.splitlines():
        meta = row.split("\t", 1)[0].split()
        if len(meta) >= 4 and meta[3].isdigit():
            total += int(meta[3])
    if total > 20_000_000:
        raise ValueError("首版执行器仅支持受管文件总量不超过 20 MB 的小型项目")
    try:
        archive = subprocess.run(["git", "archive", "--format=zip", resolved], cwd=root,
                                 capture_output=True, timeout=30, check=True).stdout
        staging.mkdir()
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for entry in bundle.infolist():
                name = entry.filename.rstrip("/")
                relative_path(name)
                if stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError("执行快照不允许符号链接")
                target = (staging / entry.filename).resolve()
                if not target.is_relative_to(staging.resolve()):
                    raise ValueError("快照路径越界")
            bundle.extractall(staging)
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return resolved


def _command(test, mode):
    path = relative_path(test["content"]["path"], python=True)
    if test["content"].get("framework", "unittest") == "pytest":
        tail = ["-B", "-m", "pytest", "-q", "--", path]
    else:
        parsed = Path(path)
        tail = ["-B", "-m", "unittest", "discover", "-s", parsed.parent.as_posix(), "-p", parsed.name]
    return (["python"] if mode == "docker" else [sys.executable]) + tail


def _windows_job(process):
    """Best-effort child-lifetime management, not a security boundary."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    class Limits(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                    ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t), ("maximum", ctypes.c_size_t),
                    ("active", wintypes.DWORD), ("affinity", ctypes.c_size_t),
                    ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]
    class Extended(ctypes.Structure):
        _fields_ = [("basic", Limits), ("io", ctypes.c_uint64 * 6),
                    ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                    ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        return None
    info = Extended()
    info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)) or not kernel.AssignProcessToJobObject(handle, int(process._handle)):
        kernel.CloseHandle(handle)
        return None
    return lambda: kernel.CloseHandle(handle)


def bounded_run(argv, cwd, cancel, timeout=30, *, allowed_root=None, output_limit=64_000):
    if (not isinstance(argv, (list, tuple)) or not argv or len(argv) > 256
            or any(not isinstance(value, str) or not value or len(value) > 4096 for value in argv)):
        raise ValueError("执行命令参数无效或过长")
    if not 0 < timeout <= 300:
        raise ValueError("执行超时必须在 0 到 300 秒之间")
    if not 1024 <= output_limit <= 1_000_000:
        raise ValueError("输出上限必须在 1 KB 到 1 MB 之间")
    cwd = _bounded_path(cwd, allowed_root, must_exist=True)
    if not cwd.is_dir():
        raise ValueError("执行工作目录不存在或不是目录")
    env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP", "PATH") if key in os.environ}
    cache_root = Path(env.get("TEMP", tempfile.gettempdir())).resolve() / "intentflow-execution-pycache"
    env.update({"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": str(cache_root),
                "PYTHONNOUSERSITE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen(list(argv), cwd=cwd, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, creationflags=flags, start_new_session=os.name != "nt")
    except (OSError, ValueError):
        return {"execution_status": "START_ERROR", "exit_code": None, "output": "",
                "seconds": 0.0, "pid": None}
    close_job = _windows_job(process)
    output = bytearray()
    overflow = threading.Event()
    def drain():
        while True:
            chunk = process.stdout.read(1024)
            if not chunk:
                return
            output.extend(chunk)
            if len(output) > output_limit:
                del output[:-output_limit]
                overflow.set()
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    started = time.monotonic()
    status = "FINISHED"
    while process.poll() is None:
        if cancel.is_set() or overflow.is_set() or time.monotonic() - started > timeout:
            status = "CANCELLED" if cancel.is_set() else "OUTPUT_LIMIT" if overflow.is_set() else "TIMEOUT"
            if os.name == "nt":
                if close_job:
                    close_job()
                    close_job = None
                else:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=5,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                if process.poll() is None:
                    process.kill()
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
            break
        cancel.wait(0.05)
    process.wait(timeout=5)
    if close_job:
        close_job()
    reader.join(timeout=2)
    process.stdout.close()
    if status == "FINISHED" and overflow.is_set():
        status = "OUTPUT_LIMIT"
    return {"execution_status": status, "exit_code": process.returncode, "pid": process.pid,
            "output": output.decode("utf-8", errors="replace"), "seconds": round(time.monotonic() - started, 3)}


def execute(root, ref, tests, mode, cancel):
    if mode not in {"native", "docker"}:
        raise ValueError("未知执行环境")
    if mode == "docker" and not capabilities()["docker"]["available"]:
        raise ValueError("隔离环境不可用，不能执行或判为通过")
    results = []
    configured_temp = os.environ.get("INTENTFLOW_EXECUTION_TEMP_ROOT")
    temp_root = _bounded_path(configured_temp, None, must_exist=True) if configured_temp else None
    with tempfile.TemporaryDirectory(prefix="intentflow-v2-run-", dir=temp_root) as temp:
        work = Path(temp) / "snapshot"
        code_commit = snapshot(root, ref, work, allowed_destination_root=temp)
        for test in tests:
            if cancel.is_set():
                break
            path = work / relative_path(test["content"]["path"], python=True)
            if not path.is_file():
                results.append({"test_id": test["id"], "verdict": "UNKNOWN", "reason": "登记测试不在当前代码快照中"})
                continue
            argv = _command(test, mode)
            container_name = ""
            if mode == "docker":
                from uuid import uuid4
                container_name = "intentflow-run-" + uuid4().hex
                argv = [shutil.which("docker"), "run", "--pull", "never", "--name", container_name, "--rm", "--network", "none", "--read-only",
                        "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "64",
                        "--memory", "256m", "--cpus", "1", "--user", "65534:65534",
                        "--tmpfs", "/tmp:rw,nosuid,size=32m", "-v", str(work) + ":/workspace:ro",
                        "-w", "/workspace", os.environ["INTENTFLOW_EXECUTION_IMAGE"], *argv]
            try:
                result = bounded_run(argv, work, cancel, allowed_root=temp)
            finally:
                if container_name:
                    # Killing the Docker client alone does not stop its container.
                    subprocess.run([shutil.which("docker"), "rm", "-f", container_name],
                                   capture_output=True, timeout=10)
            # An empty unittest suite exits successfully: it is not evidence.
            no_tests = "Ran 0 tests" in result["output"] or "no tests ran" in result["output"].lower()
            environment_error = "ModuleNotFoundError" in result["output"] or "ImportError" in result["output"]
            verdict = "UNKNOWN" if result["execution_status"] != "FINISHED" or no_tests or environment_error else (
                "PASS" if result["exit_code"] == 0 else "FAIL")
            results.append({"test_id": test["id"], "revision_id": test["revision_id"],
                            "rule_ids": test["content"]["rule_ids"], "verdict": verdict, **result})
    return {"code_commit": code_commit, "results": results, "environment": environment(mode),
            "execution_mode": mode, "isolated": mode == "docker"}
