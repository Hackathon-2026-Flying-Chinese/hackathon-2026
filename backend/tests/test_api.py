import json

import pytest
from fastapi.testclient import TestClient

from viva import ai
from viva.app import TASKS, create_app

CONTENT = json.loads(TASKS.read_text())
RIGHT = [p["right"] for p in CONTENT["predictions"]]
WRONG = [p["wrong"] for p in CONTENT["predictions"]]


def lock(p):
    return {"answers": {k: p[k] for k in ("behaviour", "requirement", "evidence")}, "confidence": p["confidence"]}


@pytest.fixture
def make(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "client", None)  # tests never call the model unless they patch it in

    def build(demo=True, camera=False):
        c = TestClient(create_app(data_dir=tmp_path / ("demo" if demo else "prod"), demo=demo))
        if demo:
            c.post("/api/demo/settings", json={"camera_required": camera})
        return c
    return build


def run_viva(c, sid, attempt, prediction, profile="specific"):
    """Lock the predictions, answer every question with the stand-in answers, and finish. Returns the results view."""
    v = c.get(f"/api/sessions/{sid}").json()
    v = c.post(f"/api/sessions/{sid}/predict", json={"version": v["version"], **lock(prediction)}).json()
    res = c.post(f"/api/sessions/{sid}/next", json={"version": v["version"]}).json()
    answers = CONTENT["sets"][attempt - 1]["answers"][profile]
    turn = res
    while True:
        text = answers["probe" if turn["key"].startswith("probe") else turn["key"]]
        res = c.post(f"/api/sessions/{sid}/answer", json={"version": v["version"], "turn": turn["turn"], "text": text, "mode": "text"})
        assert res.status_code == 200, res.text
        res = res.json()
        v = res["view"]
        if res["done"]:
            break
        turn = res
    return c.post(f"/api/sessions/{sid}/finish", json={"version": v["version"]}).json()


def test_health_and_the_answer_key_stays_on_the_server(make):
    c = make()
    assert c.get("/api/health").json() == {"service": "viva", "live": False, "model": None, "demo": True}
    assert c.get("/data/tasks.json").status_code == 404
    assert c.get("/index.html").status_code == 200
    v = c.post("/api/sessions", json={}).json()
    raw = json.dumps(v)
    task = CONTENT["sets"][0]["task"]
    assert '"correct"' not in raw and task["facts"] not in raw and "sim" not in v["task"]
    assert v["task"]["fn"] == "list_invoices" and set(v["task"]["items"]) == {"behaviour", "requirement", "evidence"}


def test_pass_review_and_points(make):
    c = make()
    sid = c.post("/api/sessions", json={"pr": {"number": 214}}).json()["id"]
    # the first attempt reads list_invoices; the right predictions and specific answers pass
    out = run_viva(c, sid, 1, RIGHT[0])
    a = out["assessment"]
    assert (a["verdict"], a["right"], a["met"], a["simulated"]) == ("shown", 3, 3, True)
    assert out["review"] == {"status": "pending"} and out["scoring"]["status"] == "pending"
    assert out["reviewer_link"] is None  # only with ?presenter=1, in demo mode
    link = c.get(f"/api/sessions/{sid}?presenter=1").json()["reviewer_link"]
    token = link.split("#", 1)[1]

    r = c.get(f"/api/reviews/{token}").json()
    assert r["role"] == "senior" and r["assessment"]["verdict"] == "shown"
    assert c.post(f"/api/reviews/{token}/decision", json={"verdict": "correction"}).status_code == 422
    d = c.post(f"/api/reviews/{token}/decision", json={"verdict": "correction", "note": "Take the id from the session."}).json()
    assert d["status"] == "decided"

    v = c.get(f"/api/sessions/{sid}").json()
    assert v["scoring"]["status"] == "earned" and v["scoring"]["points"] == 9
    pf = c.get("/api/portfolio").json()
    assert pf["points"]["total"] == 9 and pf["concept"]["level"] == 2 and pf["concept"]["next"]["s"] == 6
    assert [e["action"] for e in v["access_log"]] == ["open_review"]


def test_first_miss_stays_private_then_retake_reads_new_code(make):
    c = make()
    sid = c.post("/api/sessions", json={}).json()["id"]
    out = run_viva(c, sid, 1, WRONG[0], profile="generic")
    assert out["assessment"]["verdict"] == "not_shown" and out["review"] == {"status": "not_requested"} and out["can_retake"]
    assert c.get("/api/portfolio").json()["concept"]["level"] == 1  # a first failure leaves the level alone

    v = c.post(f"/api/sessions/{sid}/retake", json={"version": out["version"]}).json()
    assert v["attempt"] == 2 and v["task"]["fn"] == "invoice_pdf" and v["predict"] is None
    out = run_viva(c, sid, 2, RIGHT[1])
    assert out["assessment"]["verdict"] == "shown" and out["previous"][0]["verdict"] == "not_shown"
    assert not out["can_retake"]


def test_second_failure_goes_to_a_senior_and_lowers_the_level(make):
    c = make()
    sid = c.post("/api/sessions", json={}).json()["id"]
    out = run_viva(c, sid, 1, WRONG[0], profile="generic")
    c.post(f"/api/sessions/{sid}/retake", json={"version": out["version"]})
    out = run_viva(c, sid, 2, WRONG[1], profile="generic")
    assert out["review"] == {"status": "pending"} and out["scoring"]["concept"]["after"] == 0


def test_stale_version_and_locked_predictions(make):
    c = make()
    v = c.post("/api/sessions", json={}).json()
    sid = v["id"]
    assert c.post(f"/api/sessions/{sid}/predict", json={"version": 5, **lock(RIGHT[0])}).status_code == 409
    assert c.post(f"/api/sessions/{sid}/next", json={"version": 0}).json()["detail"].startswith("Lock your answers")
    bad = lock(RIGHT[0]) | {"confidence": "maybe"}
    assert c.post(f"/api/sessions/{sid}/predict", json={"version": 0, **bad}).status_code == 422
    assert c.post(f"/api/sessions/{sid}/predict", json={"version": 0, **lock(RIGHT[0])}).status_code == 200
    assert c.post(f"/api/sessions/{sid}/predict", json={"version": 0, **lock(WRONG[0])}).json()["detail"] == "Your answers are already locked."
    assert c.get("/api/sessions/nope").status_code == 404


def test_recordings_need_the_camera_and_a_signed_link(make):
    c = make(camera=True)
    v = c.post("/api/sessions", json={}).json()
    sid = v["id"]
    c.post(f"/api/sessions/{sid}/predict", json={"version": 0, **lock(RIGHT[0])})
    turn = c.post(f"/api/sessions/{sid}/next", json={"version": 0}).json()
    text = CONTENT["sets"][0]["answers"]["specific"]["implementation"]
    assert c.post(f"/api/sessions/{sid}/answer", json={"version": 0, "turn": 1, "text": text}).status_code == 422

    up = c.post(f"/api/sessions/{sid}/media", data={"turn": "1", "duration": "12.34", "kind": "video", "mode": "voice"},
                files={"blob": ("clip.webm", b"fake-webm-bytes", "video/webm;codecs=vp8")}).json()
    assert up["transcriber"] == "simulated" and up["transcript"] == text and up["duration"] == 12.3
    assert c.post(f"/api/sessions/{sid}/answer", json={"version": 0, "turn": turn["turn"], "text": text, "media_id": up["media_id"], "mode": "voice"}).status_code == 200

    assert c.post(f"/api/media/{up['media_id']}/link", json={"sid": "someone-else"}).status_code == 403
    link = c.post(f"/api/media/{up['media_id']}/link", json={"sid": sid}).json()
    got = c.get("/" + link["url"])
    assert got.status_code == 200 and got.content == b"fake-webm-bytes" and got.headers["content-type"] == "video/webm"
    assert c.get("/" + link["url"].replace("sig=", "sig=0")).status_code == 403
    actions = [e["action"] for e in c.get(f"/api/sessions/{sid}").json()["access_log"]]
    assert actions == ["sign", "play"]

    left = c.post(f"/api/sessions/{sid}/leave").json()
    assert left == {"left": True, "media_deleted": 1, "failed": 0}
    assert c.get("/" + link["url"]).status_code == 404


def test_the_model_viva_needs_real_quotes(make, monkeypatch):
    c = make()
    calls = []

    def followup(body):
        calls.append(("followup", body))
        return {"needs_follow_up": True, "question": "What would customer 17 see?", "target": "consequence", "model": "m"}

    def grade(body):
        calls.append(("grade", body))
        return {"points": [{"id": "source", "met": True, "quote": "so the caller chooses it", "turn": 1},
                           {"id": "login", "met": True, "quote": "", "turn": 2},  # no quote, no credit
                           {"id": "harm", "met": False, "quote": "", "turn": 0}], "injection_attempt": False, "model": "m"}
    monkeypatch.setattr(ai, "followup", followup)
    monkeypatch.setattr(ai, "grade", grade)
    sid = c.post("/api/sessions", json={}).json()["id"]
    out = run_viva(c, sid, 1, RIGHT[0])
    fu, gr = calls[0][1], calls[1][1]
    assert "facts" not in fu and "rubric" not in fu and "facts" in gr  # the follow-up never sees the answer key
    q = out["assessment"]["questions"]
    assert q[2]["by"] == "ai" and q[2]["question"] == "What would customer 17 see?"
    v = out["assessment"]["viva"]
    assert v["source"] == "ai" and [p["met"] for p in v["points"]] == [True, False, False]
    assert out["assessment"]["verdict"] == "gaps"  # 3 checks but only 1 rubric point
    assert {"text": "so the caller chooses it", "kind": "quote"} in q[0]["segments"]


def test_without_demo_mode_there_are_no_presenter_controls(make):
    c = make(demo=False)
    assert c.get("/api/demo").status_code == 404 and c.post("/api/demo/reset").status_code == 404
    v = c.post("/api/sessions", json={}).json()
    assert v["camera_required"] is True
    assert c.get(f"/api/sessions/{v['id']}?presenter=1").json()["reviewer_link"] is None
    c.post(f"/api/sessions/{v['id']}/predict", json={"version": 0, **lock(RIGHT[0])})
    c.post(f"/api/sessions/{v['id']}/next", json={"version": 0})
    up = c.post(f"/api/sessions/{v['id']}/media", data={"turn": "1", "duration": "5", "mode": "voice"},
                files={"blob": ("clip.webm", b"x", "video/webm")}).json()
    assert up["transcript"] is None and up["transcriber"] is None  # no stand-in transcripts outside the demo
