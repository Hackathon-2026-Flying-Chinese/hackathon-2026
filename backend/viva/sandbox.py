"""Real code runs: what a task's code returns comes from running it, not from the task author's word.

A task with a run ({"lang": "python", "harness": "<source>"}) runs in a throwaway sandbox. The task's code is written to
subject.py and the harness to harness.py, in a fresh directory mounted read-only at /work, and `python /work/harness.py`
runs with /work as its working directory. The harness (standard library only) stubs what the code needs, runs the
behaviour question's scenario on synthetic data and prints one JSON object as its last line, at least
{"option": "<behaviour option id>"}. That object is the run's "observed" result.

Runners, chosen by VIVA_SANDBOX:
  docker  the default when the docker CLI and daemon answer and the image is present: no network, a read-only file
          system, capped memory (no swap), CPU and processes, no capabilities, an unprivileged user, no daemon log of
          the output and a wall-clock timeout, with a later deadline inside the container as a backstop.
  local   a plain subprocess with resource limits, only when set explicitly. This is NOT isolation: the code can read
          and reach whatever the server's user can. For development and tests only.
  off     nothing runs.
The harness and the run results are server-only: they never go into a session view. Docker Desktop shares the default
temp directory with its daemon; with another setup, point TMPDIR at a directory the daemon can mount.
"""
import copy
import hashlib
import json
import logging
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid

try:
    import resource
except ImportError:  # not on Windows; the local runner then runs without limits
    resource = None

log = logging.getLogger("viva.sandbox")

IMAGE = "python:3.12-slim"
LANGS = ("python",)
STDOUT_CHARS, STDERR_CHARS = 4000, 2000
TAIL_BYTES = 64 * 1024  # kept of each stream while it runs; older output is dropped as it arrives
NO_JSON = "no JSON on the last line"
DOCKER_FLAGS = [
    "--rm", "--pull", "never", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=16m", "--memory", "256m",
    "--memory-swap", "256m", "--cpus", "1", "--pids-limit", "64", "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges", "--user", "65534:65534",
    "--log-driver", "none",  # the output reaches us through the attached client; the daemon keeps no copy on disk
]
# Inside the container: a deadline of its own, so the container stops even if the server dies mid-run and nothing kills
# it. A harness exit of 125 is passed on as 1, because docker's 125 means docker itself failed before the harness ran.
IN_CONTAINER = 'timeout -s KILL "$1" python /work/harness.py; c=$?; [ "$c" -eq 125 ] && c=1; exit "$c"'
DEADLINE_GRACE = 5  # seconds the container's own deadline allows past the timeout
LOCAL_MEMORY = 512 * 1024 * 1024
LOCAL_FILE_BYTES = 1024 * 1024

_lock = threading.Lock()
_probe = None  # the runner found by the first call: "docker", "local", or "" for none
_results = {}  # (runner, key) -> RunResult


def reset():
    """Forget the runner probe and the cached results (tests change VIVA_SANDBOX between runs)."""
    global _probe
    with _lock:
        _probe = None
        _results.clear()


def _detect():
    mode = os.environ.get("VIVA_SANDBOX", "").strip().lower()
    if mode == "off":
        return None
    if mode == "local":
        log.warning("VIVA_SANDBOX=local: task code runs as a plain subprocess, without isolation. For development only.")
        return "local"
    if mode not in ("", "docker"):
        log.warning("VIVA_SANDBOX=%s is not docker, local or off: no code runs", mode)
        return None
    try:  # one call answers all three: the CLI is there, the daemon answers, the image is present
        r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.info("no docker sandbox: %s", e)
        return None
    if r.returncode != 0:
        log.info("no docker sandbox: %s", (r.stderr or r.stdout).strip()[:200])
        return None
    return "docker"


def runner_name():
    """"docker", "local" or None. Probed once, then cached."""
    global _probe
    with _lock:
        if _probe is None:
            _probe = _detect() or ""
        return _probe or None


def available():
    return runner_name() is not None


def key_of(lang, harness, code):
    return hashlib.sha256("\0".join((lang, harness, code)).encode()).hexdigest()


def container_name():
    return "viva-run-" + uuid.uuid4().hex[:12]


def run_task(task, timeout=10):
    """Run the task's harness against its code. None when the task has no run (or not in Python) or no runner is
    available; otherwise a RunResult, also when the run failed (ok False, error set). Never raises."""
    runner = key = None
    try:
        spec = task.get("run") if isinstance(task, dict) else None
        if not isinstance(spec, dict) or spec.get("lang") not in LANGS:
            return None
        runner = runner_name()
        if runner is None:
            return None
        harness, code = spec.get("harness"), task.get("code")
        harness, code = harness if isinstance(harness, str) else "", code if isinstance(code, str) else ""
        key = key_of(spec["lang"], harness, code)
        if not harness:
            return _result(runner, key, error="the run has no harness")
        with _lock:
            hit = _results.get((runner, key))
        if hit:
            return copy.deepcopy(hit)
        res, keep = _execute(runner, harness, code, float(timeout))
        res["key"] = key
        if keep:
            with _lock:
                _results[(runner, key)] = copy.deepcopy(res)
        return res
    except Exception as e:  # a failed run must never take the request down with it
        log.exception("sandbox run failed")
        return _result(runner, key, error=f"the sandbox failed: {e}")


def _result(runner, key, exit_code=None, ms=0, stdout="", stderr="", observed=None, error=None):
    return {"ok": error is None and observed is not None, "runner": runner, "image": IMAGE if runner == "docker" else None,
            "exit": exit_code, "duration_ms": ms, "stdout": stdout[-STDOUT_CHARS:], "stderr": stderr[-STDERR_CHARS:],
            "observed": observed, "error": error, "at": time.time(), "key": key}


def _execute(runner, harness, code, timeout):
    """One run in a fresh directory, removed afterwards. Returns (RunResult, whether to cache it): a timeout or a
    sandbox that did not start says nothing about the code, so it is not cached."""
    work = tempfile.mkdtemp(prefix="viva-run-")
    try:
        for name, text in (("subject.py", code), ("harness.py", harness)):
            path = os.path.join(work, name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            os.chmod(path, 0o644)
        os.chmod(work, 0o755)  # the container's user (nobody) reads it through the mount
        started = time.monotonic()
        exit_code, out, err, timed_out, broken = (_run_docker if runner == "docker" else _run_local)(work, timeout)
        ms = int((time.monotonic() - started) * 1000)
    finally:
        _remove(work)
    stdout, stderr = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    observed, error = None, None
    if timed_out:
        error = "timeout"
    elif broken:
        error = "the sandbox did not start: " + (stderr.strip().splitlines() or ["no reason given"])[-1][:200]
    elif exit_code == 137 and runner == "docker":
        error = "the run was killed (memory or process limit)"
    elif exit_code != 0:
        error = f"the harness exited with code {exit_code}"
    else:
        observed, error = _observed(stdout)
    return _result(runner, None, None if timed_out else exit_code, ms, stdout, stderr, observed, error), not (timed_out or broken)


def _remove(work):
    """Remove the run's directory, also when the code took the write bit off a directory it made (local runner)."""
    shutil.rmtree(work, ignore_errors=True)
    if not os.path.lexists(work):
        return
    todo = [work]
    while todo:  # real directories only: a symlink the code left is removed, never followed
        path = todo.pop()
        try:
            os.chmod(path, 0o700)
            with os.scandir(path) as entries:
                todo.extend(e.path for e in entries if e.is_dir(follow_symlinks=False))
        except OSError:
            pass
    shutil.rmtree(work, ignore_errors=True)


def _observed(stdout):
    # print() ends lines with \n only; splitlines() would also split inside a JSON string at U+2028 or U+0085.
    lines = [x for x in stdout.split("\n") if x.strip()]
    try:
        got = json.loads(lines[-1]) if lines else None
    except (ValueError, RecursionError):  # RecursionError: nested too deep to parse
        got = None
    if not isinstance(got, dict):
        return None, NO_JSON
    if not isinstance(got.get("option"), str):
        return None, 'the JSON on the last line has no "option"'
    return got, None


def _tail(pipe, buf):
    try:
        for chunk in iter(lambda: pipe.read1(65536), b""):
            buf += chunk
            if len(buf) > 2 * TAIL_BYTES:
                del buf[:-TAIL_BYTES]
    except (OSError, ValueError):
        pass
    finally:
        pipe.close()


def _spawn(cmd, timeout, on_timeout, cleanup=None, **popen):
    """Run cmd with a wall-clock timeout, keeping only the tail of each stream so a flood of output cannot fill memory.
    Returns (exit code, stdout tail, stderr tail, timed out)."""
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **popen)
    out, err = bytearray(), bytearray()
    readers = [threading.Thread(target=_tail, args=a, daemon=True) for a in ((proc.stdout, out), (proc.stderr, err))]
    for t in readers:
        t.start()
    timed_out = False
    try:
        proc.wait(timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        on_timeout(proc)
    finally:
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        if cleanup:
            cleanup(proc)
    for t in readers:
        t.join(2)
    return proc.returncode, bytes(out[-TAIL_BYTES:]), bytes(err[-TAIL_BYTES:]), timed_out


def _docker(*args):
    try:
        subprocess.run(["docker", *args], capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("docker %s failed: %s", args[0], e)


def _run_docker(work, timeout):
    name = container_name()
    cmd = ["docker", "run", "--name", name, *DOCKER_FLAGS, "-v", f"{work}:/work:ro", "-w", "/work", IMAGE,
           "sh", "-c", IN_CONTAINER, "sh", str(math.ceil(timeout) + DEADLINE_GRACE)]
    try:
        code, out, err, timed_out = _spawn(cmd, timeout, lambda proc: _docker("kill", name))
    except OSError as e:
        return None, b"", str(e).encode(), False, True
    if timed_out:
        _docker("rm", "-f", name)  # also catches a container that was created but never started
    return code, out, err, timed_out, code == 125  # 125: docker itself failed, before the harness ran


def _local_limits(cpu):
    def apply():
        for res, value in ((resource.RLIMIT_CPU, cpu), (resource.RLIMIT_AS, LOCAL_MEMORY),
                           (resource.RLIMIT_FSIZE, LOCAL_FILE_BYTES), (resource.RLIMIT_CORE, 0)):
            try:
                resource.setrlimit(res, (value, value + 1 if res == resource.RLIMIT_CPU else value))
            except (ValueError, OSError):  # macOS refuses an address-space limit; a lower existing limit stays
                pass
    return apply


def _kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_local(work, timeout):
    """Not isolation: a subprocess as the server's user, with CPU, memory, file size and core dump limits, a clean
    environment (no server secrets) and its own process group, killed as a whole on timeout."""
    # -E -s rather than -I, which also leaves the script's directory off sys.path (`import subject` works in docker)
    cmd = [sys.executable, "-E", "-s", "-X", "utf8", os.path.join(work, "harness.py")]
    env = {"PATH": os.defpath, "HOME": work, "TMPDIR": work}
    limits = _local_limits(int(math.ceil(timeout)) + 1) if resource else None
    try:
        # The group is killed after a normal exit too, so nothing the code started outlives the run.
        code, out, err, timed_out = _spawn(cmd, timeout, _kill_group, _kill_group, cwd=work, env=env,
                                           start_new_session=True, preexec_fn=limits)
    except OSError as e:
        return None, b"", str(e).encode(), False, True
    return code, out, err, timed_out, False
