"""The GitHub App end to end, with the real engine and a fake GitHub: a pull request opens, its check links to the
interview, the author takes it, and the check follows them to the senior's decision."""
import hashlib
import hmac
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import pytest
from fastapi.testclient import TestClient

from viva import ai, github
from viva.app import create_app

from test_api import RIGHT, WRONG, run_viva
from test_users import generated

SECRET = "webhook-secret"
SHA = "3f9a1c2b7d4e5f60718293a4b5c6d7e8f9012345"


class FakeGitHub:
    def __init__(self):
        self.calls, self.runs = [], {}
        self.head, self.diff = SHA, FEES_DIFF  # a push moves the head and can change the diff

    def __call__(self, request):
        path, method = request.url.path, request.method
        self.calls.append((method, path))
        if path == "/app/installations/9/access_tokens":
            return httpx.Response(201, json={"token": "ghs_x", "expires_at": "2099-01-01T00:00:00Z"})
        if path == "/repos/acme/shop/pulls/7" and request.headers["accept"] == github.DIFF:
            return httpx.Response(200, text=self.diff)
        if path == "/repos/acme/shop/pulls/7":
            return httpx.Response(200, json=pull_at(self.head))
        if path == "/repos/acme/shop/pulls/7/files":
            return httpx.Response(200, json=[{"filename": "fees.py", "status": "modified", "additions": 12, "deletions": 3},
                                             {"filename": "tests/test_fees.py", "status": "modified", "additions": 9, "deletions": 0}])
        if path == "/repos/acme/shop/contents/fees.py" and request.url.params.get("ref") == SHA:
            return httpx.Response(200, text="def fee(x):\n    return round(x * 0.029, 2)\n")
        if path == "/repos/acme/shop/commits":
            return httpx.Response(200, json=[{"sha": "old"}])  # tony changed fees.py before
        if path == "/repos/acme/shop/check-runs" and method == "POST":
            rid = 100 + len(self.runs)
            self.runs[rid] = [json.loads(request.content)]
            return httpx.Response(201, json={"id": rid})
        if path.startswith("/repos/acme/shop/check-runs/") and method == "PATCH":
            rid = int(path.rsplit("/", 1)[1])
            self.runs[rid].append(json.loads(request.content))
            return httpx.Response(200, json={"id": rid})
        if path.startswith("/repos/acme/shop/check-runs/") and method == "GET":
            rid = int(path.rsplit("/", 1)[1])
            return httpx.Response(200, json={"id": rid, **self.state(rid)})
        return httpx.Response(404, json={"message": "Not Found"})

    def state(self, rid):
        state = {}
        for p in self.runs[rid]:
            state.update(p)
        return state

    def latest(self):
        """What the pull request shows: the newest run, with every update applied."""
        return self.state(max(self.runs))


FEES_DIFF = "diff --git a/fees.py b/fees.py\n+def fee(x):\n+    return round(x * 0.029, 2)\n"
SAMPLE_DIFF = (Path(__file__).parent / "fixtures" / "sample_pr.diff").read_text()  # the code of the sample pack
SHA2, SHA3 = "4" * 40, "5" * 40


def pull_at(sha):
    return {**PULL, "head": {**PULL["head"], "sha": sha}}


PULL = {"number": 7, "title": "Round fees once", "user": {"login": "tony"}, "html_url": "https://github.com/acme/shop/pull/7",
        "body": "Fees drifted by a cent.", "created_at": "2026-10-01T00:00:00Z", "draft": False,
        "head": {"ref": "fees", "sha": SHA}, "base": {"ref": "main", "repo": {"full_name": "acme/shop"}}}


def sign(body):
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "client", None)
    monkeypatch.setenv("VIVA_STT", "off")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    fake = FakeGitHub()
    gh = github.GitHubApp(github.Config(app_id="1", private_key=pem, webhook_secret=SECRET, api="https://api.github.test",
                                        public_url="https://viva.test"), http=httpx.Client(transport=httpx.MockTransport(fake)))
    seen = {}

    monkeypatch.setattr(github, "PUSH_WAIT", 0)  # a push is read at once

    def generate(pr, diff, novelty):
        seen.update(pr=pr, diff=diff, novelty=novelty, n=seen.get("n", 0) + 1)
        _, pack = generated(sha=pr["sha"])
        return {"status": "ready", "pack": pack, "report": {"model": "fake"}, "scoring": {"s": 4, "band": "light", "r": 2, "n": 1, "g": 2}}
    now = lambda fn, *a: fn(*a)  # run the jobs inline, so the test sees each step
    app = create_app(data_dir=tmp_path, demo=False, dev_login=True, github_app=gh, generate=generate, submit=now, notify=now)

    def browser(login):
        c = TestClient(app)
        c.post("/api/auth/dev", json={"login": login})
        c.app.state.engine.store.set_setting("camera_required", False)
        return c
    return fake, browser, seen


def deliver(c, event, payload, delivery="d1"):
    body = json.dumps(payload).encode()
    return c.post("/api/github/webhook", content=body, headers={"X-GitHub-Event": event, "X-GitHub-Delivery": delivery,
                                                               "X-Hub-Signature-256": sign(body), "Content-Type": "application/json"})


def test_a_pull_request_check_from_open_to_passed(world):
    fake, browser, seen = world
    tony = browser("tony")
    assert tony.get("/api/health").json()["github_app"] is True

    r = deliver(tony, "pull_request", {"action": "opened", "installation": {"id": 9}, "pull_request": PULL,
                                       "repository": {"full_name": "acme/shop"}})
    assert r.status_code == 202, r.text
    assert seen["novelty"] == (1, "You changed this file before.") and "round(x * 0.029, 2)" in seen["diff"]
    assert seen["pr"]["contents"] == {"fees.py": "def fee(x):\n    return round(x * 0.029, 2)\n"}  # whole, at the sha
    stored = tony.app.state.engine.packs.find("acme/shop", 7)["pack"]["pr"]
    assert "contents" not in stored and "body" not in stored
    check = fake.latest()
    assert check["name"] == "Viva" and check["head_sha"] == SHA
    assert check["status"] == "completed" and check["conclusion"] == "action_required"
    assert check["details_url"].startswith("https://viva.test/index.html?") and "repo=acme%2Fshop" in check["details_url"]

    link = {"repo": "acme/shop", "number": 7, "sha": SHA}
    assert browser("priya").post("/api/sessions", json={"pr": link}).status_code == 403  # not the author
    sid = tony.post("/api/sessions", json={"pr": link}).json()["id"]
    out = run_viva(tony, sid, 1, WRONG[0], profile="generic")
    assert out["assessment"]["verdict"] == "not_shown"
    assert fake.latest()["conclusion"] == "action_required"  # a second attempt is available

    tony.post(f"/api/sessions/{sid}/retake", json={"version": out["version"]})
    run_viva(tony, sid, 2, RIGHT[1])
    waiting = fake.latest()
    assert waiting["status"] == "in_progress" and "senior" in waiting["output"]["title"].lower()

    token = tony.app.state.engine.store.session(sid)["reviewer_token"]
    tony.post(f"/api/reviews/{token}/decision", json={"verdict": "correction", "note": "Round once, at the end."})
    done = fake.latest()
    assert done["status"] == "completed" and done["conclusion"] == "success"
    assert "Round once, at the end." in json.dumps(done["output"])


def test_the_webhook_refuses_unsigned_deliveries(world):
    _, browser, _ = world
    c = browser("tony")
    body = b'{"zen": "x"}'
    assert c.post("/api/github/webhook", content=body, headers={"X-GitHub-Event": "ping"}).status_code == 401
    assert c.post("/api/github/webhook", content=body, headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sign(b"other")}).status_code == 401
    assert deliver(c, "ping", {"zen": "x"}).json() == {"pong": True}


def test_a_push_carries_the_check_over_until_it_changes_the_checked_code(world):
    fake, browser, seen = world
    fake.diff = SAMPLE_DIFF  # the generated pack asks about list_invoices and invoice_pdf, which this diff adds
    tony = browser("tony")
    event = lambda action, sha: {"action": action, "installation": {"id": 9}, "pull_request": pull_at(sha),
                                 "repository": {"full_name": "acme/shop"}}
    assert deliver(tony, "pull_request", event("opened", SHA)).status_code == 202 and seen["n"] == 1
    sid = tony.post("/api/sessions", json={"pr": {"repo": "acme/shop", "number": 7, "sha": SHA}}).json()["id"]
    out = run_viva(tony, sid, 1, WRONG[0], profile="generic")  # a first miss: a second attempt is available

    # a push that leaves both functions and the tests alone: the check carries over, where Tony got to, with no model call
    fake.head = SHA2
    assert deliver(tony, "pull_request", event("synchronize", SHA2), delivery="d2").status_code == 202
    assert seen["n"] == 1
    now = fake.latest()
    assert now["head_sha"] == SHA2 and now["conclusion"] == "action_required"
    assert now["output"]["title"] == "A second attempt is available" and "Carried over from 3f9a1c2" in now["output"]["summary"]
    # a link to the new commit opens the same check
    got = tony.post("/api/check", json={"pr": {"repo": "acme/shop", "number": 7, "sha": SHA2}}).json()
    assert got["pack"]["status"] == "ready" and got["pr"]["sha"] == SHA

    # the interview goes on, and moves the new commit's check
    tony.post(f"/api/sessions/{sid}/retake", json={"version": out["version"]})
    run_viva(tony, sid, 2, RIGHT[1])
    waiting = fake.latest()
    assert waiting["head_sha"] == SHA2 and waiting["status"] == "in_progress" and "senior" in waiting["output"]["title"].lower()

    # a push that changes list_invoices: a new check, from a new pack
    fake.head, fake.diff = SHA3, SAMPLE_DIFF.replace("WHERE customer_id = :cid", "WHERE customer_id = :cid AND NOT deleted")
    assert deliver(tony, "pull_request", event("synchronize", SHA3), delivery="d3").status_code == 202
    assert seen["n"] == 2 and seen["pr"]["sha"] == SHA3
    fresh = fake.latest()
    assert fresh["head_sha"] == SHA3 and fresh["output"]["title"] == "Explain this change before it merges"
    assert "Carried over" not in fresh["output"]["summary"]


def test_a_re_run_prepares_a_new_check_even_when_the_code_did_not_change(world):
    fake, browser, seen = world
    fake.diff = SAMPLE_DIFF
    tony = browser("tony")
    deliver(tony, "pull_request", {"action": "opened", "installation": {"id": 9}, "pull_request": PULL,
                                   "repository": {"full_name": "acme/shop"}})
    rid = max(fake.runs)
    deliver(tony, "check_run", {"action": "rerequested", "installation": {"id": 9}, "repository": {"full_name": "acme/shop"},
                                "check_run": {"id": rid, "name": "Viva", "head_sha": SHA, "pull_requests": [{"number": 7}]}},
            delivery="d2")
    assert seen["n"] == 2 and "Carried over" not in fake.latest()["output"]["summary"]
