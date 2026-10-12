"""The code-run sandbox: the sample harnesses report what the code really does, and a run stays contained."""
import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path

import pytest

from viva import sandbox

TASKS = Path(__file__).resolve().parents[2] / "frontend" / "data" / "tasks.json"
CONTENT = json.loads(TASKS.read_text())


def docker_ready():
    try:
        return subprocess.run(["docker", "image", "inspect", sandbox.IMAGE], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


DOCKER = docker_ready()
needs_docker = pytest.mark.skipif(not DOCKER, reason=f"docker daemon or {sandbox.IMAGE} not available")
RUNNERS = [pytest.param("docker", marks=needs_docker), "local"]

FIXED_LIST = """@router.get("/invoices")
def list_invoices(customer_id: int, user: User = Depends(current_user)):
    if customer_id != user.customer_id:
        raise HTTPException(status_code=403)
    rows = db.execute(
        "SELECT id, amount, status FROM invoices WHERE customer_id = :cid",
        {"cid": customer_id},
    )
    return [dict(r) for r in rows]"""

FROM_LOGIN_LIST = """@router.get("/invoices")
def list_invoices(customer_id: int, user: User = Depends(current_user)):
    rows = db.execute(
        "SELECT id, amount, status FROM invoices WHERE customer_id = :cid",
        {"cid": user.customer_id},
    )
    return [dict(r) for r in rows]"""

UNCHECKED_PDF = """@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, user: User = Depends(current_user)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(status_code=404)
    return render_pdf(inv)"""


@pytest.fixture
def use(monkeypatch):
    def pick(mode):
        monkeypatch.setenv("VIVA_SANDBOX", mode)
        sandbox.reset()
        return mode
    yield pick
    sandbox.reset()


def task(i):
    return CONTENT["sets"][i]["task"]


def raw(harness, code=""):
    return {"code": code, "run": {"lang": "python", "harness": harness}}


def gone(pid):
    for _ in range(20):  # a killed process can linger a moment before it is reaped
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


def leftover(name):
    r = subprocess.run(["docker", "ps", "-a", "--filter", f"name=^/{name}$", "--format", "{{.Names}}"],
                       capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    return r.stdout.strip()


@pytest.mark.parametrize("runner", RUNNERS)
@pytest.mark.parametrize("i", [0, 1])
def test_the_sample_sets_produce_their_keyed_behaviour(use, runner, i):
    use(runner)
    t = task(i)
    r = sandbox.run_task(t)
    assert r["ok"] and r["error"] is None and r["exit"] == 0, r
    assert r["observed"]["option"] == t["items"]["behaviour"]["correct"]
    assert r["observed"]["status"] == t["reveal"]["status"] and r["observed"]["rows"] == t["reveal"]["rows"]
    assert r["runner"] == runner and r["image"] == (sandbox.IMAGE if runner == "docker" else None)
    assert r["key"] == sandbox.key_of("python", t["run"]["harness"], t["code"])
    assert set(r) == {"ok", "runner", "image", "exit", "duration_ms", "stdout", "stderr", "observed", "error", "at", "key"}
    for k in ("status", "result", "owner", "note"):  # what a reveal takes from an agreeing run: the sample's text stays
        assert r["observed"].get(k, t["reveal"][k]) == t["reveal"][k]


@pytest.mark.parametrize("runner", RUNNERS)
def test_the_harness_classifies_what_the_code_really_does(use, runner):
    """Not a hard-coded key: fixed code gets a different option from the same harness."""
    use(runner)
    assert sandbox.run_task({**task(0), "code": FIXED_LIST})["observed"]["option"] == "403"
    own = sandbox.run_task({**task(0), "code": FROM_LOGIN_LIST})["observed"]
    assert own["option"] == "own" and [r[0] for r in own["rows"]] == ["INV-1695", "INV-1716"]
    assert sandbox.run_task({**task(1), "code": UNCHECKED_PDF})["observed"]["option"] == "pdf"


@pytest.mark.parametrize("runner", RUNNERS)
def test_the_harness_awaits_async_code_and_names_an_odd_return(use, runner):
    use(runner)
    run = lambda i, code: sandbox.run_task({**task(i), "code": code})
    asyncify = lambda code, fn: code.replace(f"def {fn}", f"async def {fn}")
    assert run(0, asyncify(task(0)["code"], "list_invoices"))["observed"]["option"] == "others"
    assert run(0, asyncify(FIXED_LIST, "list_invoices"))["observed"]["option"] == "403"
    assert run(1, asyncify(UNCHECKED_PDF, "invoice_pdf"))["observed"]["option"] == "pdf"
    r = run(0, FIXED_LIST.replace("    if customer_id", "    return 3\n    if customer_id"))
    assert r["ok"] and r["observed"]["option"] == "unknown" and r["observed"]["result"] == "3"


@pytest.mark.parametrize("runner", RUNNERS)
def test_the_harness_can_import_the_subject(use, runner):
    """Same sys.path in both runners: the harness's own directory comes first."""
    use(runner)
    r = sandbox.run_task(raw('import json, subject\nprint(json.dumps({"option": subject.ANSWER}))\n', 'ANSWER = "a"\n'))
    assert r["ok"] and r["observed"] == {"option": "a"}, r


@pytest.mark.parametrize("runner", RUNNERS)
def test_a_run_that_does_not_stop_times_out_and_is_killed(use, runner, monkeypatch):
    """The harness idles, so no CPU limit ends it, and starts a child: the kill at the timeout must take both."""
    use(runner)
    name = "viva-test-" + uuid.uuid4().hex[:8]
    monkeypatch.setattr(sandbox, "container_name", lambda: name)
    harness = """import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
print(child.pid, flush=True)
time.sleep(60)
"""
    started = time.monotonic()
    r = sandbox.run_task(raw(harness), timeout=2)
    assert time.monotonic() - started < 4.5  # killed at the timeout, not after the grace period or a later deadline
    assert not r["ok"] and r["error"] == "timeout" and r["exit"] is None and r["observed"] is None
    if runner == "docker":
        assert leftover(name) == ""
    else:
        assert gone(int(r["stdout"].split()[0]))


@needs_docker
def test_a_container_nobody_kills_stops_by_itself(use, monkeypatch):
    """As when the server dies mid-run: no docker kill and no rm, yet the container ends at its own deadline."""
    use("docker")
    name = "viva-test-" + uuid.uuid4().hex[:8]
    monkeypatch.setattr(sandbox, "container_name", lambda: name)
    monkeypatch.setattr(sandbox, "_docker", lambda *a: None)
    sandbox.run_task(raw("while True:\n    pass\n"), timeout=1)
    deadline = time.monotonic() + 15
    while leftover(name) and time.monotonic() < deadline:
        time.sleep(0.5)
    assert leftover(name) == ""


@needs_docker
def test_docker_caps_memory_without_swap_and_keeps_no_log(use, monkeypatch):
    use("docker")
    name = "viva-test-" + uuid.uuid4().hex[:8]
    monkeypatch.setattr(sandbox, "container_name", lambda: name)
    seen = []

    def inspect():
        for _ in range(100):
            got = subprocess.run(["docker", "inspect", "-f", "{{.HostConfig.LogConfig.Type}}", name],
                                 capture_output=True, text=True, timeout=10)
            if got.returncode == 0:
                return seen.append(got.stdout.strip())
            time.sleep(0.05)
    looking = threading.Thread(target=inspect)
    looking.start()
    harness = """import json, time
time.sleep(1)
held = [b"x" * (10 << 20) for _ in range(40)]
print(json.dumps({"option": "a", "mb": 10 * len(held)}))
"""
    r = sandbox.run_task(raw(harness))
    looking.join()
    assert seen == ["none"]
    assert not r["ok"] and r["error"] == "the run was killed (memory or process limit)", r


@needs_docker
def test_code_that_exits_125_does_not_pass_for_a_broken_sandbox(use, monkeypatch):
    use("docker")
    calls = []
    real = sandbox._run_docker
    monkeypatch.setattr(sandbox, "_run_docker", lambda *a: calls.append(1) or real(*a))
    code = "import sys\nsys.stderr.write('docker: Error response from daemon: out of disk space\\n')\nraise SystemExit(125)\n"
    r = sandbox.run_task(raw("exec(open('subject.py').read())\n", code))
    assert not r["ok"] and r["exit"] == 1 and r["error"] == "the harness exited with code 1", r
    assert sandbox.run_task(raw("exec(open('subject.py').read())\n", code)) == r and len(calls) == 1  # cached


@needs_docker
def test_docker_has_no_network(use):
    use("docker")
    harness = """import json, socket
try:
    socket.create_connection(("1.1.1.1", 80), timeout=3).close()
    option = "open"
except OSError as e:
    option = "blocked"
print(json.dumps({"option": option}))
"""
    r = sandbox.run_task(raw(harness))
    assert r["ok"] and r["observed"]["option"] == "blocked"


@needs_docker
def test_docker_work_is_read_only_and_runs_as_nobody(use):
    use("docker")
    harness = """import json, os
def writable(path):
    try:
        with open(path, "a") as f:
            f.write("x")
        return True
    except OSError:
        return False
print(json.dumps({"option": "checked", "work": writable("/work/new.txt"), "subject": writable("/work/subject.py"),
                  "root": writable("/etc/new.txt"), "tmp": writable("/tmp/new.txt"), "uid": os.getuid()}))
"""
    r = sandbox.run_task(raw(harness, "x = 1\n"))
    assert r["ok"], r
    assert r["observed"] == {"option": "checked", "work": False, "subject": False, "root": False, "tmp": True, "uid": 65534}


def test_the_last_line_must_be_json_with_an_option(use):
    use("local")
    r = sandbox.run_task(raw('print("hello")\n'))
    assert not r["ok"] and r["error"] == sandbox.NO_JSON and r["observed"] is None and r["exit"] == 0
    r = sandbox.run_task(raw('import json\nprint(json.dumps({"option": "a"}))\nprint("after")\n'))
    assert not r["ok"] and r["error"] == sandbox.NO_JSON
    r = sandbox.run_task(raw('print(\'{"status": "200 OK"}\')\n'))
    assert not r["ok"] and "option" in r["error"]
    r = sandbox.run_task(raw('import json\nprint(json.dumps({"option": "a"}))\nraise SystemExit(3)\n'))
    assert not r["ok"] and r["error"] == "the harness exited with code 3" and r["observed"] is None
    r = sandbox.run_task(raw("exec(open('subject.py').read())\n", "def broken(:\n"))
    assert not r["ok"] and r["exit"] == 1 and "SyntaxError" in r["stderr"]
    r = sandbox.run_task(raw("print('{\"option\": \"a\", \"x\": ' + '[' * 5000 + ']' * 5000 + '}')\n"))
    assert not r["ok"] and r["error"] == sandbox.NO_JSON  # too deep to parse is no JSON, not a sandbox failure


def test_the_last_line_is_split_at_newlines_only(use):
    use("local")
    note = "a\u2028b\u2029c\x85d"
    r = sandbox.run_task(raw(f"import json\nprint(json.dumps({{'option': 'a', 'note': {note!r}}}, ensure_ascii=False))\n"))
    assert r["ok"] and r["observed"] == {"option": "a", "note": note}, r


def test_the_run_directory_is_removed_even_when_the_code_locks_it(use):
    use("local")
    harness = """import json, os
os.makedirs("d/e")
open("d/e/f", "w").close()
os.chmod("d/e", 0o500)
os.chmod("d", 0o000)
os.symlink(os.path.expanduser("~"), "home")
print(json.dumps({"option": "a", "work": os.getcwd()}))
"""
    r = sandbox.run_task(raw(harness))
    assert r["ok"] and not os.path.lexists(r["observed"]["work"])


@pytest.mark.parametrize("runner", RUNNERS)
def test_huge_output_is_capped(use, runner):
    use(runner)
    harness = """import json, sys
for _ in range(80):
    sys.stdout.write("x" * 65536 + "\\n")
    sys.stderr.write("e" * 65536 + "\\n")
print(json.dumps({"option": "a"}))
"""
    r = sandbox.run_task(raw(harness))
    assert r["ok"] and r["observed"] == {"option": "a"}
    assert len(r["stdout"]) <= sandbox.STDOUT_CHARS and len(r["stderr"]) <= sandbox.STDERR_CHARS
    assert r["stdout"].rstrip().endswith('{"option": "a"}')


def test_a_cached_result_comes_back_without_running_again(use, monkeypatch):
    use("local")
    calls = []
    real = sandbox._run_local
    monkeypatch.setattr(sandbox, "_run_local", lambda *a: calls.append(1) or real(*a))
    first = sandbox.run_task(task(0))
    again = sandbox.run_task(task(0))
    assert len(calls) == 1 and again == first and again is not first
    again["observed"]["option"] = "changed"  # a caller cannot change the cached copy
    assert sandbox.run_task(task(0))["observed"]["option"] == "others"
    other = sandbox.run_task({**task(0), "code": FIXED_LIST})
    assert len(calls) == 2 and other["key"] != first["key"]


def test_a_timed_out_run_is_not_cached(use, monkeypatch):
    use("local")
    calls = []
    real = sandbox._run_local
    monkeypatch.setattr(sandbox, "_run_local", lambda *a: calls.append(1) or real(*a))
    loop = raw("while True:\n    pass\n")
    assert sandbox.run_task(loop, timeout=0.5)["error"] == "timeout"
    assert sandbox.run_task(loop, timeout=0.5)["error"] == "timeout"
    assert len(calls) == 2


def test_no_run_or_another_language_gives_none(use):
    use("local")
    plain = {k: v for k, v in task(0).items() if k != "run"}
    assert sandbox.run_task(plain) is None
    assert sandbox.run_task({**task(0), "run": {"lang": "node", "harness": "console.log('{}')"}}) is None
    assert sandbox.run_task(None) is None and sandbox.run_task({"run": "python"}) is None
    r = sandbox.run_task({"code": "x = 1", "run": {"lang": "python"}})
    assert not r["ok"] and r["error"] == "the run has no harness"


def test_off_runs_nothing(use):
    use("off")
    assert sandbox.available() is False and sandbox.runner_name() is None
    assert sandbox.run_task(task(0)) is None


def test_without_docker_the_default_runs_nothing(use, monkeypatch, tmp_path):
    use("")
    monkeypatch.setenv("PATH", str(tmp_path))  # no docker CLI to find; local is never a fallback
    assert sandbox.runner_name() is None and sandbox.run_task(task(0)) is None
    use("podman")
    assert sandbox.available() is False


def test_the_probe_runs_once(use, monkeypatch):
    use("local")
    calls = []
    real = sandbox._detect
    monkeypatch.setattr(sandbox, "_detect", lambda: calls.append(1) or real())
    assert sandbox.available() and sandbox.available() and sandbox.runner_name() == "local"
    assert len(calls) == 1


def test_a_sandbox_failure_never_raises(use, monkeypatch):
    use("local")

    def boom(*a):
        raise RuntimeError("disk full")
    monkeypatch.setattr(sandbox, "_execute", boom)
    r = sandbox.run_task(task(0))
    assert r["ok"] is False and r["error"] == "the sandbox failed: disk full" and r["key"]


def test_the_local_runner_gets_no_server_secrets(use, monkeypatch):
    use("local")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-not-for-the-code")
    r = sandbox.run_task(raw('import json, os\nprint(json.dumps({"option": "a", "env": sorted(os.environ)}))\n'))
    assert r["ok"] and "ANTHROPIC_API_KEY" not in r["observed"]["env"]
