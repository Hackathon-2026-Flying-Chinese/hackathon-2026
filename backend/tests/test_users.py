"""Sign-in, one person's data, per-concept levels, and checks generated for real pull requests."""
import sqlite3
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from viva import ai
from viva.app import create_app
from viva.store import Store

from test_api import CONTENT, RIGHT, WRONG, lock, run_viva

SHA = "3f9a1c2b7d4e5f60718293a4b5c6d7e8f9012345"


def generated(author="tony", key="money", number=7, sha=SHA):
    pr = {"repo": "acme/shop", "number": number, "title": "Round fees once", "author": author, "branch": "fees", "base": "main",
          "sha": sha, "files": [{"name": "fees.py", "add": 12, "del": 3}], "url": f"https://github.com/acme/shop/pull/{number}"}
    pack = {"source": "generated", "pr": pr, "concept": {"key": key, "name": "Money and rounding"},
            "scoring": {"r": 2, "n": 2, "why": {"r": "Fees are money.", "n": "You changed fees.py before, in a new way."}},
            "sets": CONTENT["sets"]}
    return pr, pack


@pytest.fixture
def server(tmp_path, monkeypatch):
    """One server (one database), any number of signed-in browsers."""
    monkeypatch.setattr(ai, "client", None)
    monkeypatch.setenv("VIVA_STT", "off")

    def browser(login="tony", demo=False, camera=False, **kw):
        c = TestClient(create_app(data_dir=tmp_path / "data", demo=demo, dev_login=True, **kw))
        if login:
            assert c.post("/api/auth/dev", json={"login": login}).status_code == 200
        if demo:
            c.post("/api/demo/settings", json={"camera_required": camera})
        else:  # outside demo mode the camera is required; these tests type their answers
            c.app.state.engine.store.set_setting("camera_required", False)
        return c
    return browser


def test_everything_but_health_needs_a_login(server):
    c = server(login=None)
    assert c.get("/api/health").status_code == 200
    for method, path in [("GET", "/api/me"), ("POST", "/api/check"), ("POST", "/api/sessions"), ("GET", "/api/portfolio"),
                         ("GET", "/api/sessions/x"), ("POST", "/api/sessions/x/leave"), ("POST", "/api/media/m_1/link")]:
        assert c.request(method, path, json={}).json() == {"detail": "Sign in first."}, path
    assert c.get("/index.html").status_code == 200


def test_sign_in_and_out(server):
    c = server()
    me = c.get("/api/me").json()
    assert me["user"]["login"] == "tony" and me["auth"] == {"github": False, "dev": True}
    cookie = c.cookies.get("viva_login")
    assert cookie and len(cookie) > 30
    with sqlite3.connect(c.app.state.engine.store.root / "viva.db") as db:  # only the hash is stored
        assert db.execute("SELECT count(*) FROM logins WHERE token_hash = ?", (cookie,)).fetchone()[0] == 0
    assert c.post("/api/auth/logout").json() == {"signed_out": True}
    c.cookies.set("viva_login", cookie)  # an old cookie no longer works
    assert c.get("/api/me").status_code == 401
    assert c.post("/api/auth/dev", json={"login": "not a login"}).status_code == 422


def test_plain_sign_in_only_in_demo_or_dev(tmp_path):
    c = TestClient(create_app(data_dir=tmp_path, demo=False, dev_login=False))
    assert c.post("/api/auth/dev", json={"login": "tony"}).status_code == 404
    assert c.get("/api/health").json()["auth"] == {"github": False, "dev": False}


def test_one_person_cannot_see_or_touch_anothers_session(server):
    tony, priya = server("tony"), server("priya")
    sid = tony.post("/api/sessions", json={}).json()["id"]
    v = tony.get(f"/api/sessions/{sid}").json()
    assert priya.get(f"/api/sessions/{sid}").status_code == 404
    assert priya.post(f"/api/sessions/{sid}/predict", json={"version": v["version"], **lock(RIGHT[0])}).status_code == 404
    assert priya.post(f"/api/sessions/{sid}/leave").status_code == 404
    assert priya.delete(f"/api/sessions/{sid}").status_code == 404
    assert tony.get(f"/api/sessions/{sid}").status_code == 200

    out = run_viva(tony, sid, 1, RIGHT[0])
    token = tony.app.state.engine.store.session(sid)["reviewer_token"]
    tony.post(f"/api/reviews/{token}/decision", json={"verdict": "correction", "note": "Take the id from the session."})
    assert out["assessment"]["verdict"] == "shown"
    assert tony.get("/api/portfolio").json()["concept"]["level"] == 2
    pf = priya.get("/api/portfolio").json()  # a second person starts from nothing
    assert pf["points"]["total"] == 0 and pf["concept"]["level"] == 1 and pf["points"]["entries"] == []
    assert priya.post("/api/check", json={}).json()["scoring"]["level"] == 1
    assert tony.post("/api/check", json={}).json()["scoring"]["level"] == 2


def test_cross_site_writes_are_refused(server):
    c = server()
    assert c.post("/api/sessions", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/sessions", json={}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert c.post("/api/sessions", json={}, headers={"Origin": "http://testserver"}).status_code == 200


def test_unknown_pull_requests_get_no_sample_outside_demo(server):
    c = server()
    assert c.post("/api/check", json={"pr": {"repo": "acme/shop", "number": 99}}).status_code == 404
    assert c.post("/api/sessions", json={"pr": {"repo": "acme/shop", "number": 99}}).status_code == 404
    sample = CONTENT["pr"]
    assert c.post("/api/check", json={"pr": {"repo": sample["repo"], "number": sample["number"]}}).json()["pack"]["source"] == "sample"
    demo = server(demo=True)
    assert demo.post("/api/check", json={"pr": {"repo": "acme/shop", "number": 99}}).json()["pr"]["repo"] == "acme/shop"


def test_a_generated_check_is_for_its_author_and_has_its_own_level(server):
    tony, priya = server("tony"), server("priya")
    pr, pack = generated()
    pid = tony.app.state.engine.packs.put(pr, "ready", pack)
    link = {"repo": "acme/shop", "number": 7, "sha": SHA[:7]}

    seen = priya.post("/api/check", json={"pr": link}).json()
    assert seen["can_start"] is False and "tony" in seen["reason"]
    assert priya.post("/api/sessions", json={"pr": link}).status_code == 403

    home = tony.post("/api/check", json={"pr": link}).json()
    assert home["can_start"] and home["pack"] == {"status": "ready", "source": "generated", "message": None}
    assert home["scoring"]["concept"] == {"key": "money", "name": "Money and rounding", "level": 1}
    assert home["scoring"]["s"] == 12  # Risk 2 x Novelty 2 x Gap 3
    v = tony.post("/api/sessions", json={"pr": {**link, "title": "a title from the link is ignored"}}).json()
    assert v["pr"]["title"] == "Round fees once" and v["pr"]["sha"] == SHA
    assert tony.app.state.engine.store.session(v["id"])["pack_id"] == pid

    run_viva(tony, v["id"], 1, RIGHT[0])  # pass: money goes to level 2, access control stays at 1
    pf = tony.get("/api/portfolio").json()
    assert [(c["key"], c["level"]) for c in pf["concepts"]] == [("money", 2)]
    assert tony.post("/api/check", json={}).json()["scoring"]["concept"]["level"] == 1
    sid = tony.post("/api/sessions", json={}).json()["id"]
    out = run_viva(tony, sid, 1, WRONG[0], profile="generic")
    tony.post(f"/api/sessions/{sid}/retake", json={"version": out["version"]})
    run_viva(tony, sid, 2, WRONG[1], profile="generic")  # a failed retake lowers access control only
    levels = {c["key"]: c["level"] for c in tony.get("/api/portfolio").json()["concepts"]}
    assert levels == {"money": 2, "access-control": 0}


def test_a_check_that_is_not_ready_says_why(server):
    c = server()
    pr, pack = generated()
    engine = c.app.state.engine
    engine.packs.put(pr, "generating")
    home = c.post("/api/check", json={"pr": {"repo": "acme/shop", "number": 7}}).json()
    assert home["pack"]["status"] == "generating" and home["scoring"] is None and not home["can_start"]
    assert home["pr"]["title"] == "Round fees once"
    assert c.post("/api/sessions", json={"pr": {"repo": "acme/shop", "number": 7}}).status_code == 409
    engine.packs.put(pr, "needs_review", report={"issues": ["the run disagreed"]})
    assert c.post("/api/check", json={"pr": {"repo": "acme/shop", "number": 7}}).json()["pack"]["status"] == "needs_review"
    pid = engine.packs.put(pr, "ready", pack)  # the same head: one row, now ready
    assert engine.packs.find("acme/shop", 7)["id"] == pid
    sid = c.post("/api/sessions", json={"pr": {"repo": "acme/shop", "number": 7}}).json()["id"]
    # Preparing the same head again (a re-run check) leaves the ready pack, and the session on it, alone.
    again = engine.packs.put(pr, "generating")
    assert again != pid and engine.packs.find("acme/shop", 7)["id"] == again
    assert c.get(f"/api/sessions/{sid}").json()["task"]["fn"] == "list_invoices"
    assert c.get("/api/portfolio").status_code == 200
    assert engine.packs.put(pr, "ready", pack) == again


def test_listeners_hear_every_change_and_cannot_break_it(server):
    c = server(demo=True)
    heard = []
    engine = c.app.state.engine
    engine.listeners += [lambda e, s: heard.append((e, s["attempt"])), lambda e, s: 1 / 0]
    sid = c.post("/api/sessions", json={}).json()["id"]
    out = run_viva(c, sid, 1, WRONG[0], profile="generic")
    c.post(f"/api/sessions/{sid}/retake", json={"version": out["version"]})
    run_viva(c, sid, 2, RIGHT[1])
    token = engine.store.session(sid)["reviewer_token"]
    c.post(f"/api/reviews/{token}/decision", json={"verdict": "followup"})
    assert heard == [("finished", 1), ("retake", 2), ("finished", 2), ("decided", 2)]


def test_sign_in_with_github(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "Iv1.abc")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "s3cret")

    def github(request):
        if request.url.path == "/login/oauth/access_token":
            body = parse_qs(request.content.decode())
            ok = body["code"] == ["the-code"] and body["client_secret"] == ["s3cret"]
            return httpx.Response(200, json={"access_token": "gho_x"} if ok else {"error": "bad_verification_code"})
        if request.url.path == "/user" and request.headers["authorization"] == "Bearer gho_x":
            return httpx.Response(200, json={"id": 4242, "login": "tony-l", "name": "Tony L", "avatar_url": "https://a/x.png"})
        return httpx.Response(404)
    c = TestClient(create_app(data_dir=tmp_path, demo=False, dev_login=False,
                              auth_http=httpx.Client(transport=httpx.MockTransport(github))), follow_redirects=False)
    assert c.get("/api/health").json()["auth"] == {"github": True, "dev": False}

    go = c.get("/api/auth/github", params={"next": "/portfolio.html"})
    assert go.status_code == 302
    q = parse_qs(urlsplit(go.headers["location"]).query)
    assert go.headers["location"].startswith("https://github.com/login/oauth/authorize?")
    assert q["client_id"] == ["Iv1.abc"] and q["redirect_uri"] == ["http://testserver/api/auth/github/callback"]
    state = q["state"][0]

    assert c.get("/api/auth/github/callback", params={"code": "the-code", "state": "forged"}).status_code == 400
    back = c.get("/api/auth/github/callback", params={"code": "the-code", "state": state})
    assert back.status_code == 302 and back.headers["location"] == "/portfolio.html"
    assert c.get("/api/me").json()["user"] == {"id": c.get("/api/me").json()["user"]["id"], "login": "tony-l",
                                               "name": "Tony L", "avatar_url": "https://a/x.png"}

    # a renamed GitHub account is the same person; a link that points off the site goes home instead
    go = c.get("/api/auth/github", params={"next": "//evil.example/x"})
    state = parse_qs(urlsplit(go.headers["location"]).query)["state"][0]
    back = c.get("/api/auth/github/callback", params={"code": "the-code", "state": state})
    assert back.headers["location"] == "/"


def test_sessions_from_before_sign_in_are_kept_but_hidden(tmp_path):
    with sqlite3.connect(tmp_path / "viva.db") as db:
        db.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, created REAL NOT NULL, state TEXT NOT NULL)")
        db.execute("INSERT INTO sessions VALUES ('old', 1, '{}')")
    store = Store(tmp_path)
    assert store.session("old") == {} and store.sessions("anyone") == []
