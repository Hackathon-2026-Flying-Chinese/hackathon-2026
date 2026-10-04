"""The GitHub App, offline: a fake GitHub behind httpx.MockTransport and a fake engine on a real Store."""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import threading
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest

from viva import github as gh
from viva.store import Store

SECRET = "hook-secret"
API = "https://api.github.test"
PUBLIC = "https://viva.example"
REPO = "acme/billing"
SHA, SHA2 = "a1" * 20, "b2" * 20
INST = 9
PACK_ID = "p_0123456789ab"
READY = {
    "status": "ready",
    "pack": {"id": PACK_ID, "concept": {"key": "access-control", "name": "Access control: whose data"},
             "scoring": {"r": 3, "n": 3, "why": {"r": "Customer data.", "n": "You have not changed this file before."}}},
    "report": {"checks": "passed"},
    "scoring": {"s": 27, "band": "full", "r": 3, "n": 3, "g": 3},
}


def private_pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


@pytest.fixture(scope="module")
def keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_pem(key), key.public_key()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pull(number=7, sha=SHA, draft=False):
    return {"number": number, "title": "Let customers download invoices", "user": {"login": "mia"}, "draft": draft,
            "head": {"ref": "mia/invoices", "sha": sha}, "base": {"ref": "main", "repo": {"full_name": REPO}},
            "html_url": f"https://github.com/{REPO}/pull/{number}", "body": "Adds a download endpoint. " * 400,
            "created_at": "2026-10-01T10:00:00Z"}


class Clock:
    def __init__(self):
        self.t = time.time()

    def __call__(self):
        return self.t


class FakeGitHub:
    """Just enough of the REST API. Records every request. history maps a path to the author's commits there (a list),
    or to an HTTP status to fail with; fail maps "METHOD /path" to a status."""

    def __init__(self, clock):
        self.clock, self.requests, self.runs, self.next_run, self.tokens = clock, [], {}, 100, 0
        self.head = SHA
        self.diff = "diff --git a/app/invoices.py b/app/invoices.py\n+def list_invoices(user):\n"
        self.files = [{"filename": "app/invoices.py", "additions": 40, "deletions": 2},
                      {"filename": "tests/test_invoices.py", "additions": 30, "deletions": 0}]
        self.history, self.fail = {}, {}
        self.too_large = False  # the diff is one GitHub will not build
        self.push_after_read = None  # a head sha pushed right after the next read of the pull request

    def __call__(self, request):
        self.requests.append(request)
        m, path = request.method, request.url.path
        if f"{m} {path}" in self.fail:
            return httpx.Response(self.fail[f"{m} {path}"], json={"message": "Nope"})
        if m == "POST" and re.fullmatch(r"/app/installations/\d+/access_tokens", path):
            self.tokens += 1
            return httpx.Response(201, json={"token": f"ghs_{self.tokens}", "expires_at": iso(self.clock() + 3600)})
        if m == "POST" and path == f"/repos/{REPO}/check-runs":
            self.next_run += 1
            self.runs[self.next_run] = [json.loads(request.content)]
            return httpx.Response(201, json={"id": self.next_run, **self.runs[self.next_run][0]})
        if m == "PATCH" and (hit := re.fullmatch(rf"/repos/{REPO}/check-runs/(\d+)", path)):
            self.runs[int(hit[1])].append(json.loads(request.content))
            return httpx.Response(200, json={"id": int(hit[1])})
        if m == "GET" and (hit := re.fullmatch(rf"/repos/{REPO}/pulls/(\d+)", path)):
            if request.headers["accept"] == gh.DIFF:
                if self.too_large:
                    return httpx.Response(406, json={"message": "Sorry, the diff exceeded the maximum number of files (300).",
                                                     "errors": [{"resource": "PullRequest", "field": "diff", "code": "too_large"}]})
                return httpx.Response(200, text=self.diff)
            got = httpx.Response(200, json=pull(int(hit[1]), self.head))
            if self.push_after_read:
                self.head, self.push_after_read = self.push_after_read, None
            return got
        if m == "GET" and path == f"/repos/{REPO}/pulls/7/files":
            page = int(request.url.params.get("page", 1))
            return httpx.Response(200, json=self.files[(page - 1) * 100: page * 100])
        if m == "GET" and path == f"/repos/{REPO}/commits":
            h = self.history.get(request.url.params["path"], [])
            return httpx.Response(h, json={"message": "Server Error"}) if isinstance(h, int) else httpx.Response(200, json=h)
        return httpx.Response(404, json={"message": "Not Found"})

    def sent(self, path_end):
        return [q for q in self.requests if q.url.path.endswith(path_end)]


class FakePacks:
    """Like the store, put returns its own id for the row (row1, row2, ...), whatever id the pack carries."""

    def __init__(self):
        self.puts = []

    def put(self, pr, status, pack=None, report=None):
        self.puts.append({"pr": pr, "status": status, "pack": pack, "report": report, "id": f"row{len(self.puts) + 1}"})
        return self.puts[-1]["id"]

    def find(self, repo, number, sha=None):
        hits = [p for p in self.puts if (p["pr"]["repo"], p["pr"]["number"]) == (repo, number) and p["pr"]["sha"].startswith(sha or "")]
        return {"id": hits[-1]["id"], "status": hits[-1]["status"]} if hits else None


class Generate:
    def __init__(self):
        self.calls, self.out = [], READY

    def __call__(self, pr, diff, novelty):
        self.calls.append((pr, diff, novelty))
        if isinstance(self.out, Exception):
            raise self.out
        return self.out


def inline(fn, *a):  # the job runs inline
    fn(*a)


def make_world(tmp_path, pem, submit=inline, **config):
    clock = Clock()
    fake = FakeGitHub(clock)
    cfg = gh.Config(**{"app_id": "42", "private_key": pem, "webhook_secret": SECRET, "api": API, "public_url": PUBLIC, **config})
    app = gh.GitHubApp(cfg, http=httpx.Client(transport=httpx.MockTransport(fake)), clock=clock)
    engine = SimpleNamespace(packs=FakePacks(), listeners=[], store=Store(tmp_path), demo=False)
    with engine.store.tx():  # the author of the pull request, signed in (a login matches whatever its case)
        engine.store.conn.execute("INSERT INTO users (id, login, created) VALUES ('u_mia', 'Mia', 0)")
    gen = Generate()
    fast = FastAPI()
    fast.include_router(gh.make_router(engine, app, gen, submit=submit))
    return SimpleNamespace(fake=fake, app=app, engine=engine, gen=gen, clock=clock, client=TestClient(fast),
                           checks=gh.CheckStore(engine.store))


@pytest.fixture
def world(tmp_path, keys):
    return make_world(tmp_path, keys[0])


def sign(body, secret=SECRET):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def send(world, event, data, delivery=None, signature=None):
    body = json.dumps(data).encode()
    headers = {"X-GitHub-Event": event, "X-GitHub-Delivery": delivery or uuid4().hex, "Content-Type": "application/json",
               "X-Hub-Signature-256": sign(body) if signature is None else signature}
    if signature == "":
        del headers["X-Hub-Signature-256"]
    return world.client.post("/api/github/webhook", content=body, headers=headers)


def pr_event(action, sha=SHA, draft=False):
    return {"action": action, "installation": {"id": INST}, "repository": {"full_name": REPO}, "pull_request": pull(7, sha, draft)}


def query(url):
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


# ---------- signatures and plumbing ----------
def test_verify_signature():
    body = b'{"zen": "Keep it logically awesome."}'
    good = sign(body, "s")
    assert gh.verify_signature("s", body, good)
    assert not gh.verify_signature("s", body + b" ", good)
    assert not gh.verify_signature("other", body, good)
    assert not gh.verify_signature("s", body, None)
    assert not gh.verify_signature("s", body, good[len("sha256="):])
    assert not gh.verify_signature("s", body, "sha1=" + good[len("sha256="):])
    assert not gh.verify_signature("", body, good)
    assert not gh.verify_signature("s", body, "sha256=café")


def test_webhook_refuses_missing_and_bad_signatures_and_answers_ping(world):
    assert send(world, "ping", {"zen": "hi"}, signature="").status_code == 401
    assert send(world, "ping", {"zen": "hi"}, signature="sha256=" + "0" * 64).status_code == 401
    assert send(world, "ping", {"zen": "hi"}, signature=sign(b"{}", "wrong")).status_code == 401
    r = send(world, "ping", {"zen": "hi", "hook_id": 1})
    assert r.status_code == 200 and r.json() == {"pong": True}


def test_webhook_body_is_capped_before_the_signature_is_checked(world, monkeypatch):
    monkeypatch.setattr(gh, "MAX_HOOK", 100)
    body = json.dumps({"zen": "x" * 200}).encode()
    headers = {"X-GitHub-Event": "ping", "X-Hub-Signature-256": sign(body)}
    assert world.client.post("/api/github/webhook", content=body, headers=headers).status_code == 413
    # without a length (chunked), it is cut off while it is read
    chunks = iter([body[:60], body[60:120], body[120:]])
    assert world.client.post("/api/github/webhook", content=chunks, headers=headers).status_code == 413
    assert send(world, "ping", {"zen": "hi"}).json() == {"pong": True}


def test_unconfigured_app_is_503(tmp_path, keys):
    w = make_world(tmp_path, keys[0], webhook_secret="")
    r = send(w, "ping", {"zen": "hi"})
    assert r.status_code == 503 and not w.fake.requests
    fast = FastAPI()
    fast.include_router(gh.make_router(SimpleNamespace(store=Store(tmp_path / "none")), None, Generate()))
    assert TestClient(fast).post("/api/github/webhook", content=b"{}").status_code == 503


def test_other_events_are_acknowledged_or_ignored(world):
    r = send(world, "installation", {"action": "created", "installation": {"id": INST, "account": {"login": "acme"}}})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert send(world, "installation_repositories", {"action": "added", "installation": {"id": INST}}).status_code == 200
    r = send(world, "issues", {"action": "opened", "installation": {"id": INST}})
    assert r.status_code == 202 and r.json() == {"ignored": "issues"}
    r = send(world, "pull_request", pr_event("closed"))
    assert r.status_code == 202 and r.json() == {"ignored": "pull_request.closed"}
    assert not world.fake.runs


# ---------- pull request events ----------
def test_opened_creates_a_preparing_check_then_a_ready_one(world):
    r = send(world, "pull_request", pr_event("opened"))
    assert r.status_code == 202 and r.json()["queued"]
    run_id = r.json()["check_run_id"]
    first, last = world.fake.runs[run_id][0], world.fake.runs[run_id][-1]
    assert (first["name"], first["status"], first["head_sha"]) == ("Viva", "in_progress", SHA)
    assert first["output"]["title"] == "Preparing questions from your diff"
    assert first["details_url"].startswith(PUBLIC + "/index.html?")
    assert query(first["details_url"]) == {"repo": REPO, "pr": "7", "sha": SHA, "title": "Let customers download invoices",
                                           "author": "mia", "branch": "mia/invoices"}

    # the job: pull, diff, files, history, then generate
    pr, diff, novelty = world.gen.calls[0]
    assert diff == world.fake.diff
    assert novelty == (3, "You have not changed this file before.")  # the test file is not looked up
    assert [q.url.params["path"] for q in world.fake.sent("/commits")] == ["app/invoices.py"]
    assert {k: pr[k] for k in ("repo", "number", "title", "author", "branch", "base", "sha", "url")} == {
        "repo": REPO, "number": 7, "title": "Let customers download invoices", "author": "mia", "branch": "mia/invoices",
        "base": "main", "sha": SHA, "url": f"https://github.com/{REPO}/pull/7"}
    assert pr["files"] == [{"name": "app/invoices.py", "add": 40, "del": 2}, {"name": "tests/test_invoices.py", "add": 30, "del": 0}]
    assert len(pr["body"]) == gh.MAX_BODY and "diff_truncated" not in pr
    assert [p["status"] for p in world.engine.packs.puts] == ["generating", "ready"]
    assert world.engine.packs.puts[1]["pack"]["id"] == PACK_ID

    assert (last["status"], last["conclusion"], last["external_id"]) == ("completed", "action_required", "row2")  # the store's id
    assert last["output"]["title"] == "Explain this change before it merges" and "head_sha" not in last
    summary = last["output"]["summary"]
    assert "Access control: whose data" in summary and "Risk 3 × Novelty 3 × Gap 3 = 27 points (Full check)." in summary
    assert "Novelty: You have not changed this file before." in last["output"]["text"]
    row = world.checks.latest(REPO, 7, SHA[:12])  # a session keeps a short sha
    assert (row["state"], row["check_run_id"], row["pack_id"], row["installation_id"]) == ("ready", run_id, "row2", INST)

    # every call carries the API version and the agent; the diff is asked for as a diff
    (d,) = [q for q in world.fake.requests if q.headers["accept"] == gh.DIFF]
    assert d.headers["x-github-api-version"] == "2022-11-28" and d.headers["user-agent"] == "viva"
    assert d.headers["authorization"] == "Bearer ghs_1" and world.fake.tokens == 1


def test_drafts_wait_until_ready_for_review(world):
    for action in ("opened", "synchronize"):
        r = send(world, "pull_request", pr_event(action, draft=True))
        assert r.status_code == 200 and r.json() == {"skipped": "draft"}
    assert not world.fake.runs and not world.gen.calls
    r = send(world, "pull_request", pr_event("ready_for_review"))
    assert r.status_code == 202 and len(world.fake.runs) == 1 and len(world.gen.calls) == 1


def test_a_new_commit_gets_its_own_check(world):
    a = send(world, "pull_request", pr_event("opened")).json()["check_run_id"]
    world.fake.head = SHA2
    b = send(world, "pull_request", pr_event("synchronize", sha=SHA2)).json()["check_run_id"]
    assert a != b and world.fake.runs[b][0]["head_sha"] == SHA2 and query(world.fake.runs[b][0]["details_url"])["sha"] == SHA2
    assert world.checks.latest(REPO, 7)["check_run_id"] == b
    assert world.checks.latest(REPO, 7, SHA)["check_run_id"] == a
    assert world.gen.calls[1][0]["sha"] == SHA2


def test_a_commit_that_is_no_longer_the_head_is_skipped(world):
    world.fake.head = SHA2  # by the time the job runs, the pull request moved on
    run_id = send(world, "pull_request", pr_event("opened")).json()["check_run_id"]
    last = world.fake.runs[run_id][-1]
    assert (last["conclusion"], last["output"]["title"]) == ("neutral", "No viva for this change")
    assert last["output"]["summary"] == gh.SUPERSEDED and not world.gen.calls
    # recorded, so the check's link no longer says the questions are being written
    assert [p["status"] for p in world.engine.packs.puts] == ["generating", "skipped"]
    assert world.engine.packs.puts[-1]["report"] == {"reason": gh.SUPERSEDED} and last["external_id"] == "row2"
    assert world.checks.latest(REPO, 7, SHA)["state"] == "superseded"

    # SHA is the head again (a force-push back), so it is prepared afresh; but a push lands while its diff is read,
    # so that diff is the newer commit's and is not used
    world.fake.head, world.fake.push_after_read = SHA, SHA2
    again = send(world, "pull_request", pr_event("synchronize")).json()["check_run_id"]
    assert again != run_id and world.fake.runs[again][-1]["output"]["summary"] == gh.SUPERSEDED and not world.gen.calls
    world.fake.head = SHA
    last = world.fake.runs[send(world, "pull_request", pr_event("synchronize")).json()["check_run_id"]][-1]
    assert last["conclusion"] == "action_required" and world.gen.calls[0][0]["sha"] == SHA


def test_a_diff_github_will_not_build_is_skipped_plainly(world):
    world.fake.too_large = True
    with pytest.raises(gh.TooLarge):
        world.app.pr_diff(INST, REPO, 7)
    run_id = send(world, "pull_request", pr_event("opened")).json()["check_run_id"]
    last = world.fake.runs[run_id][-1]
    assert (last["status"], last["conclusion"], last["output"]["title"]) == ("completed", "neutral", "No viva for this change")
    assert last["output"]["summary"] == gh.TOO_LARGE and "Re-run" not in last["output"]["summary"]
    assert not world.gen.calls and [p["status"] for p in world.engine.packs.puts] == ["generating", "skipped"]
    assert world.checks.latest(REPO, 7)["state"] == "skipped"
    # a reopened pull request does not ask GitHub again
    n = len(world.fake.requests)
    assert send(world, "pull_request", pr_event("reopened")).json()["unchanged"] == "skipped" and len(world.fake.requests) == n

    world.fake.too_large = False  # any other refusal is still an error
    world.fake.fail[f"GET /repos/{REPO}/pulls/7"] = 406
    with pytest.raises(gh.GitHubError) as e:
        world.app.pr_diff(INST, REPO, 7)
    assert not isinstance(e.value, gh.TooLarge)


def test_a_reopened_pull_request_keeps_its_check(world):
    send(world, "pull_request", pr_event("opened"))
    on = gh.listener(world.engine, world.app)
    on("finished", session("shown", {"status": "pending"}))
    on("decided", session("shown", {"status": "decided", "verdict": "correction", "note": ""}))
    passed = world.checks.latest(REPO, 7)
    assert passed["state"] == "passed"
    runs, requests = len(world.fake.runs), len(world.fake.requests)
    send(world, "pull_request", pr_event("closed"))
    for action in ("reopened", "ready_for_review", "synchronize"):  # the same head: its passed check is still on it
        r = send(world, "pull_request", pr_event(action))
        assert r.status_code == 200 and r.json() == {"unchanged": "passed", "check_run_id": passed["check_run_id"]}
    assert (len(world.fake.runs), len(world.fake.requests), len(world.gen.calls)) == (runs, requests, 1)
    assert world.checks.latest(REPO, 7)["check_run_id"] == passed["check_run_id"]


def test_a_duplicate_delivery_is_ignored(world):
    assert send(world, "pull_request", pr_event("opened"), delivery="d-1").status_code == 202
    r = send(world, "pull_request", pr_event("opened"), delivery="d-1")
    assert r.status_code == 200 and r.json() == {"duplicate": True}
    assert len(world.fake.runs) == 1 and len(world.gen.calls) == 1


def test_a_github_failure_can_be_redelivered(world):
    world.fake.fail[f"POST /repos/{REPO}/check-runs"] = 500
    r = send(world, "pull_request", pr_event("opened"), delivery="d-2")
    assert r.status_code == 502 and "Nope" in r.json()["detail"]
    del world.fake.fail[f"POST /repos/{REPO}/check-runs"]
    assert send(world, "pull_request", pr_event("opened"), delivery="d-2").status_code == 202


def test_a_check_is_never_left_spinning(world):
    def broken(*a, **k):
        raise RuntimeError("database is locked")
    world.engine.packs.put = broken
    r = send(world, "pull_request", pr_event("opened"))
    assert r.status_code == 500
    (runs,) = world.fake.runs.values()
    assert (runs[0]["status"], runs[-1]["conclusion"]) == ("in_progress", "neutral") and not world.gen.calls


def test_a_failing_generator_ends_in_a_neutral_check_and_the_server_keeps_serving(world):
    world.gen.out = RuntimeError("the model is down")
    r = send(world, "pull_request", pr_event("opened"))
    assert r.status_code == 202
    last = world.fake.runs[r.json()["check_run_id"]][-1]
    assert (last["status"], last["conclusion"]) == ("completed", "neutral")
    assert last["output"]["title"] == "Viva could not prepare questions"
    assert world.engine.packs.puts[-1]["status"] == "failed" and world.checks.latest(REPO, 7)["state"] == "failed"
    assert send(world, "ping", {"zen": "still here"}).json() == {"pong": True}

    world.gen.out = {"status": "maybe"}  # an outcome the check cannot show is a failure too
    r = send(world, "pull_request", pr_event("reopened"))
    assert world.fake.runs[r.json()["check_run_id"]][-1]["output"]["title"] == "Viva could not prepare questions"


@pytest.mark.parametrize("out,state,title", [
    ({"status": "needs_review", "pack": {"id": "p_aaaaaaaaaaaa"}, "report": {"failed": "blind solve"}}, "not_verified",
     "No questions for this change"),
    ({"status": "skipped", "pack": None, "report": {"reason": "Only documentation changed."}}, "skipped", "No viva for this change"),
])
def test_unverified_and_skipped_packs_end_in_neutral_checks(world, out, state, title):
    world.gen.out = out
    run_id = send(world, "pull_request", pr_event("opened")).json()["check_run_id"]
    last = world.fake.runs[run_id][-1]
    assert (last["status"], last["conclusion"], last["output"]["title"]) == ("completed", "neutral", title)
    assert world.checks.latest(REPO, 7)["state"] == state
    assert world.engine.packs.puts[-1]["status"] == out["status"]
    if state == "not_verified":
        assert "could not verify its questions" in last["output"]["summary"] and last["external_id"] == "row2"
    else:
        assert last["output"]["summary"] == "Only documentation changed."


def test_rerun_requested_runs_the_job_again(world):
    first = send(world, "pull_request", pr_event("opened")).json()["check_run_id"]
    data = {"action": "rerequested", "installation": {"id": INST}, "repository": {"full_name": REPO},
            "check_run": {"id": first, "name": "Viva", "head_sha": SHA, "pull_requests": [{"number": 7}]}}
    r = send(world, "check_run", data)
    assert r.status_code == 202 and r.json()["check_run_id"] != first and len(world.gen.calls) == 2
    assert world.checks.latest(REPO, 7)["state"] == "ready"
    data["check_run"]["pull_requests"] = []  # a pull request from a fork: our own row says which one
    assert send(world, "check_run", data).status_code == 202 and len(world.gen.calls) == 3
    data["check_run"]["name"] = "CI"
    r = send(world, "check_run", data)
    assert r.json() == {"ignored": "check_run.rerequested"} and len(world.gen.calls) == 3
    r = send(world, "check_run", {**data, "action": "completed", "check_run": {**data["check_run"], "name": "Viva"}})
    assert r.json() == {"ignored": "check_run.completed"}


# ---------- the engine's events ----------
def session(verdict="shown", review=None, attempt=1, repo=REPO, sha=SHA[:12], user_id="u_mia", pack_id="p_taken"):
    return {"id": "s1", "user_id": user_id, "pack_id": pack_id,
            "pr": {"repo": repo, "number": 7, "sha": sha, "title": "Let customers download invoices", "author": "mia",
                   "branch": "mia/invoices"}, "attempt": attempt, "assessment": {"verdict": verdict}, "review": review}


def test_listener_pass_then_correction(world):
    ready_run = send(world, "pull_request", pr_event("opened")).json()["check_run_id"]
    on = gh.listener(world.engine, world.app)
    on("finished", session("shown", {"status": "pending"}))
    row = world.checks.latest(REPO, 7, SHA)
    assert row["state"] == "waiting_review" and row["check_run_id"] != ready_run  # the ready run was completed: a new one
    p = world.fake.runs[row["check_run_id"]][0]
    assert (p["status"], p["head_sha"], p["external_id"]) == ("in_progress", SHA, "p_taken")  # the pack the session took
    assert p["output"]["title"] == "Waiting for a senior review" and query(p["details_url"])["sha"] == SHA

    on("decided", session("shown", {"status": "decided", "verdict": "correction", "note": "Take the id from the session."}))
    assert world.checks.latest(REPO, 7)["check_run_id"] == row["check_run_id"]  # an open run is patched
    last = world.fake.runs[row["check_run_id"]][-1]
    assert (last["status"], last["conclusion"]) == ("completed", "success") and "head_sha" not in last
    assert "Take the id from the session." in last["output"]["summary"]
    assert world.checks.latest(REPO, 7)["state"] == "passed"


def test_listener_retake_then_followup(world):
    send(world, "pull_request", pr_event("opened"))
    on = gh.listener(world.engine, world.app)
    on("finished", session("not_shown", {"status": "not_requested"}))
    retake_row = world.checks.latest(REPO, 7)
    p = world.fake.runs[retake_row["check_run_id"]][0]
    assert retake_row["state"] == "retake"
    assert (p["status"], p["conclusion"], p["output"]["title"]) == ("completed", "action_required", "A second attempt is available")

    n = len(world.fake.requests)
    on("retake", session("not_shown", None, attempt=2))  # the second attempt began: the retake check stays
    assert len(world.fake.requests) == n and world.checks.latest(REPO, 7)["check_run_id"] == retake_row["check_run_id"]

    on("finished", session("gaps", {"status": "pending"}, attempt=2))  # a failed last attempt goes to a senior
    wait = world.checks.latest(REPO, 7)
    assert wait["state"] == "waiting_review" and wait["check_run_id"] != retake_row["check_run_id"]
    assert world.fake.runs[wait["check_run_id"]][0]["output"]["summary"].startswith("Both attempts are done.")

    on("decided", session("gaps", {"status": "decided", "verdict": "followup", "note": "Let's pair on the query."}, attempt=2))
    last = world.fake.runs[wait["check_run_id"]][-1]
    assert (last["conclusion"], last["output"]["title"]) == ("action_required", "A senior asked for a short follow-up conversation")
    assert "Let's pair on the query." in last["output"]["summary"] and world.checks.latest(REPO, 7)["state"] == "followup"


def test_listener_moves_only_the_authors_own_check(world):
    send(world, "pull_request", pr_event("opened"))
    with world.engine.store.tx():
        world.engine.store.conn.execute("INSERT INTO users (id, login, created) VALUES ('u_mal', 'mallory', 0)")
    on = gh.listener(world.engine, world.app)
    n = len(world.fake.requests)
    decided = {"status": "decided", "verdict": "correction", "note": ""}
    on("decided", session("shown", decided, user_id="u_mal"))  # someone else took the check
    on("decided", session("shown", decided, user_id="u_gone"))
    on("decided", session("shown", decided, user_id=None))
    on("decided", session("shown", decided, pack_id="sample"))
    world.engine.demo = True  # anyone may take any check, and the presenter sees the reviewer link
    on("decided", session("shown", decided))
    assert len(world.fake.requests) == n and world.checks.latest(REPO, 7)["state"] == "ready"
    world.engine.demo = False
    on("decided", session("shown", decided))
    assert world.checks.latest(REPO, 7)["state"] == "passed"


def test_a_decision_while_a_rerun_prepares_gets_its_own_run(tmp_path, keys):
    queued = []
    w = make_world(tmp_path, keys[0], submit=lambda fn, *a: queued.append((fn, a)))

    def drain():
        while queued:
            fn, a = queued.pop(0)
            fn(*a)
    drain()
    first = send(w, "pull_request", pr_event("opened")).json()["check_run_id"]
    drain()
    on = gh.listener(w.engine, w.app)
    on("finished", session("shown", {"status": "pending"}))
    data = {"action": "rerequested", "installation": {"id": INST}, "repository": {"full_name": REPO},
            "check_run": {"id": first, "name": "Viva", "head_sha": SHA, "pull_requests": [{"number": 7}]}}
    rerun = send(w, "check_run", data).json()["check_run_id"]  # queued: still Preparing
    on("decided", session("shown", {"status": "decided", "verdict": "correction", "note": "Fine."}))
    passed = w.checks.latest(REPO, 7)
    assert passed["state"] == "passed" and passed["check_run_id"] != rerun and len(w.fake.runs[rerun]) == 1
    drain()  # the job finishes its own run; the pass stays the newest
    assert w.fake.runs[rerun][-1]["output"]["title"] == "Explain this change before it merges"
    assert w.checks.latest(REPO, 7)["check_run_id"] == passed["check_run_id"]
    assert w.fake.runs[passed["check_run_id"]][-1]["conclusion"] == "success"


def test_a_restart_fails_the_checks_it_left_preparing(tmp_path, keys):
    w = make_world(tmp_path, keys[0], submit=lambda fn, *a: None)  # the job never runs: the server stopped
    run_id = send(w, "pull_request", pr_event("opened")).json()["check_run_id"]
    assert w.checks.latest(REPO, 7)["state"] == "preparing" and w.engine.packs.puts[-1]["status"] == "generating"

    gh.make_router(w.engine, w.app, w.gen, submit=inline)  # the server starts again
    last = w.fake.runs[run_id][-1]
    assert (last["status"], last["conclusion"], last["output"]["title"]) == ("completed", "neutral", "Viva could not prepare questions")
    assert w.checks.latest(REPO, 7)["state"] == "failed" and w.engine.packs.puts[-1]["status"] == "failed" and not w.gen.calls
    n = len(w.fake.requests)
    gh.make_router(w.engine, w.app, w.gen, submit=inline)  # nothing left to fail
    assert len(w.fake.requests) == n
    # a failed check is prepared again by the next event
    assert send(w, "pull_request", pr_event("reopened")).status_code == 202


def test_listener_ignores_sessions_without_a_check_and_never_raises(world):
    on = gh.listener(world.engine, world.app)
    on("finished", session(repo="harbourpay/billing", sha="b7e21f4"))  # the sample
    on("finished", {"id": "x", "pr": None})
    on("unknown", session())
    assert not world.fake.requests

    send(world, "pull_request", pr_event("opened"))
    world.fake.fail[f"POST /repos/{REPO}/check-runs"] = 500
    on("finished", session("shown", {"status": "pending"}))  # GitHub fails: logged, not raised
    assert world.checks.latest(REPO, 7)["state"] == "ready"

    queued = []
    gh.listener(world.engine, world.app, submit=lambda fn, *a: queued.append((fn, a)))("finished", session())
    assert len(queued) == 1 and queued[0][1][0] == "finished"


# ---------- the client ----------
def test_app_jwt_is_rs256_with_the_app_id(world, keys):
    tok = world.app.app_jwt()
    assert jwt.get_unverified_header(tok)["alg"] == "RS256"
    claims = jwt.decode(tok, keys[1], algorithms=["RS256"])
    assert claims["iss"] == "42" and claims["iat"] == int(world.clock.t) - 60 and claims["exp"] == int(world.clock.t) + 540
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(tok, other, algorithms=["RS256"])


def test_installation_token_is_cached_and_refreshed(world, keys):
    world.app.pull(INST, REPO, 7)
    world.app.pull(INST, REPO, 7)
    assert world.fake.tokens == 1
    (tq,) = world.fake.sent("/access_tokens")
    assert tq.url.path == f"/app/installations/{INST}/access_tokens"
    assert jwt.decode(tq.headers["authorization"].split()[1], keys[1], algorithms=["RS256"])["iss"] == "42"
    assert [q.headers["authorization"] for q in world.fake.sent("/pulls/7")] == ["Bearer ghs_1"] * 2

    world.clock.t += 3600 - 30  # within a minute of expiry
    world.app.pull(INST, REPO, 7)
    assert world.fake.tokens == 2 and world.fake.sent("/pulls/7")[-1].headers["authorization"] == "Bearer ghs_2"


def test_a_slow_token_fetch_blocks_no_other_call(world):
    world.app.pull(INST, REPO, 7)  # INST's token is cached
    started, release = threading.Event(), threading.Event()

    def slow(request):
        if request.url.path == "/app/installations/2/access_tokens":
            started.set()
            release.wait(5)
        return world.fake(request)
    world.app.http = httpx.Client(transport=httpx.MockTransport(slow))
    other = threading.Thread(target=world.app.token, args=(2,))
    other.start()
    assert started.wait(5)
    mine = threading.Thread(target=world.app.pull, args=(INST, REPO, 7))
    mine.start()
    mine.join(2)
    blocked = mine.is_alive()
    release.set()
    other.join(5)
    mine.join(5)
    assert not blocked and world.app.cached(2) and world.fake.tokens == 2


def test_errors_carry_the_status_and_message(world):
    world.fake.fail[f"GET /repos/{REPO}/pulls/7"] = 404
    with pytest.raises(gh.GitHubError) as e:
        world.app.pull(INST, REPO, 7)
    assert (e.value.status, e.value.message) == (404, "Nope")
    with pytest.raises(gh.GitHubError):
        world.app.pr_diff(INST, REPO, 7)

    def down(request):
        raise httpx.ConnectError("no route")
    app = gh.GitHubApp(world.app.config, http=httpx.Client(transport=httpx.MockTransport(down)))
    with pytest.raises(gh.GitHubError) as e:
        app.pull(INST, REPO, 7)
    assert e.value.status == 0


def test_diff_is_capped_at_one_megabyte(world):
    world.fake.diff = ("+" + "x" * 99 + "\n") * 11_000
    text, cut = world.app.pr_diff(INST, REPO, 7)
    assert cut and len(text.encode()) <= gh.MAX_DIFF and text.endswith("\n")
    world.fake.diff = "diff --git a/x b/x\n"
    assert world.app.pr_diff(INST, REPO, 7) == ("diff --git a/x b/x\n", False)

    world.fake.diff = ("+" + "x" * 99 + "\n") * 11_000
    run_id = send(world, "pull_request", pr_event("opened")).json()["check_run_id"]
    assert world.gen.calls[-1][0]["diff_truncated"] is True and world.fake.runs[run_id][-1]["conclusion"] == "action_required"


def test_files_are_paginated_up_to_300(world):
    world.fake.files = [{"filename": f"f{i}.py", "additions": 1, "deletions": 0} for i in range(250)]
    assert len(world.app.pr_files(INST, REPO, 7)) == 250 and len(world.fake.sent("/files")) == 3
    world.fake.files = [{"filename": f"f{i}.py", "additions": 1, "deletions": 0} for i in range(350)]
    got = world.app.pr_files(INST, REPO, 7)
    assert len(got) == 300 and got[-1]["filename"] == "f299.py" and len(world.fake.sent("/files")) == 6


def test_novelty(world):
    def nov(*files):
        return world.app.novelty(INST, REPO, "mia", list(files), "2026-10-01T10:00:00Z")

    def f(name, add=10):
        return {"name": name, "add": add, "del": 0}

    # a changed dependency list is new, and needs no lookup
    assert nov(f("app/x.py"), f("pyproject.toml", 1)) == (3, "You changed the dependencies in pyproject.toml.")
    for manifest in ("web/package.json", "requirements-dev.txt", "go.mod", "Cargo.toml", "Gemfile", "pom.xml", "build.gradle.kts",
                     "composer.json"):
        assert nov(f(manifest))[0] == 3
    assert not world.fake.requests

    # a manifest among tests, fixtures or vendored code is not the project's dependency list
    for other in ("tests/fixtures/package.json", "web/node_modules/left-pad/package.json", "vendor/x/go.mod", "testdata/requirements.txt"):
        assert "dependencies" not in nov(f("src/app.py", 40), f(other, 3))[1]
    world.fake.requests.clear()

    # a lock file alone is not a dependency change, and is not looked up
    assert nov(f("package-lock.json", 900), f("src/a.js")) == (3, "You have not changed this file before.")
    assert [q.url.params["path"] for q in world.fake.sent("/commits")] == ["src/a.js"]
    q = world.fake.sent("/commits")[0].url.params
    assert (q["author"], q["until"], q["per_page"]) == ("mia", "2026-10-01T10:00:00Z", "1")

    world.fake.history = {"src/a.js": [{"sha": "x"}]}
    assert nov(f("src/a.js"), f("src/b.js")) == (2, "You changed 1 of these 2 files before.")
    world.fake.history["src/b.js"] = [{"sha": "y"}]
    assert nov(f("src/a.js"), f("src/b.js")) == (1, "You changed these files before.")
    assert nov(f("src/a.js")) == (1, "You changed this file before.")
    assert nov(f("src/c.js"), f("src/d.js")) == (3, "You have not changed these files before.")

    # tests are left out; only the five most-changed paths are looked up
    before = len(world.fake.sent("/commits"))
    nov(*[f(f"src/m{i}.py", add=i + 1) for i in range(8)], f("tests/test_m.py", 500), f("src/thing.test.ts", 400))
    assert [q.url.params["path"] for q in world.fake.sent("/commits")[before:]] == [f"src/m{i}.py" for i in (7, 6, 5, 4, 3)]
    # only tests changed: their history counts
    world.fake.history = {"tests/test_m.py": [{"sha": "z"}]}
    assert nov(f("tests/test_m.py")) == (1, "You changed this file before.")

    # GitHub failing, no author, or nothing to look up
    world.fake.history = {"src/a.js": 500}
    assert nov(f("src/a.js")) == (2, gh.NO_HISTORY)
    assert world.app.novelty(INST, REPO, "", [f("src/a.js")], None) == (2, gh.NO_HISTORY)
    assert nov(f("yarn.lock")) == (2, gh.NO_HISTORY)
    # GitHub file objects work too
    world.fake.history = {}
    assert nov({"filename": "src/e.py", "additions": 3, "deletions": 1}) == (3, "You have not changed this file before.")


# ---------- what the check says ----------
PR = {"repo": REPO, "number": 7, "sha": SHA, "title": "T", "author": "mia", "branch": "b"}


@pytest.mark.parametrize("state,status,conclusion", [
    ("preparing", "in_progress", None), ("ready", "completed", "action_required"), ("skipped", "completed", "neutral"),
    ("not_verified", "completed", "neutral"), ("failed", "completed", "neutral"), ("waiting_review", "in_progress", None),
    ("retake", "completed", "action_required"), ("passed", "completed", "success"), ("followup", "completed", "action_required"),
])
def test_presenters(state, status, conclusion):
    p = gh.PRESENTERS[state](PUBLIC, PR, "p_1")
    assert (p["name"], p["status"], p.get("conclusion"), p["external_id"]) == ("Viva", status, conclusion, "p_1")
    assert p["output"]["title"] and p["output"]["summary"] and p["details_url"].startswith(PUBLIC + "/index.html?")
    assert (state in gh.IN_PROGRESS) == (status == "in_progress")
    bare = gh.PRESENTERS[state]("", PR)
    assert "details_url" not in bare and "external_id" not in bare


def test_ready_summary_without_scoring():
    p = gh.ready(PUBLIC, PR, "p_1", concept="Input validation")
    assert p["output"]["summary"].startswith("This change is about Input validation.") and "points" not in p["output"]["summary"]
    assert gh.points_line({"s": 4, "band": "light"}) == "4 points (Light check)."


# ---------- configuration ----------
def test_config_from_env(tmp_path, keys):
    path = tmp_path / "app.pem"
    path.write_text(keys[0])
    c = gh.Config.from_env({"GITHUB_APP_ID": "42", "GITHUB_APP_PRIVATE_KEY_PATH": str(path), "GITHUB_WEBHOOK_SECRET": "s",
                            "VIVA_PUBLIC_URL": "https://viva.example/"})
    assert c.enabled and c.private_key == keys[0].strip()
    assert (c.api, c.public_url) == ("https://api.github.com", "https://viva.example")
    one_line = keys[0].strip().replace("\n", "\\n")
    c = gh.Config.from_env({"GITHUB_APP_ID": "1", "GITHUB_APP_PRIVATE_KEY": one_line, "GITHUB_WEBHOOK_SECRET": "s",
                            "GITHUB_API": "https://ghe.example/api/v3/"})
    assert c.private_key == keys[0].strip() and c.api == "https://ghe.example/api/v3"
    assert not gh.Config.from_env({}).enabled
    c = gh.Config.from_env({"GITHUB_APP_ID": "1", "GITHUB_APP_PRIVATE_KEY": keys[0], "GITHUB_WEBHOOK_SECRET": "hook-secret-xyz"})
    assert "PRIVATE KEY" not in repr(c) and "hook-secret-xyz" not in repr(c)  # a log line or a traceback never leaks them
    assert not gh.Config.from_env({"GITHUB_APP_ID": "1", "GITHUB_APP_PRIVATE_KEY": "k"}).enabled
    assert not gh.Config.from_env({"GITHUB_APP_ID": "1", "GITHUB_APP_PRIVATE_KEY_PATH": str(tmp_path / "missing"),
                                   "GITHUB_WEBHOOK_SECRET": "s"}).enabled


def test_manifest():
    m = gh.manifest("https://viva.example/")
    assert m["name"] == "Viva" and m["url"] == "https://viva.example"
    assert m["hook_attributes"]["url"] == "https://viva.example/api/github/webhook"
    assert m["callback_urls"] == ["https://viva.example/api/auth/github/callback"]
    assert "redirect_url" not in m  # no page of Viva's would take the one-time code
    assert m["request_oauth_on_install"] is False and m["public"] is False
    assert m["default_permissions"] == {"checks": "write", "pull_requests": "read", "contents": "read", "metadata": "read"}
    assert m["default_events"] == ["pull_request", "check_run"]
