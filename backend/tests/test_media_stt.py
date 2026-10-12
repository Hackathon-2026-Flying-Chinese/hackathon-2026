"""The real thing through the API: a spoken answer transcribed on the server, and the code run in the sandbox."""
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from viva import ai, sandbox, stt
from viva.app import create_app

from test_api import RIGHT, lock

SAID = "List invoices takes the customer id from the query string, so the caller chooses it."


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    if not (shutil.which("say") and shutil.which("ffmpeg")) or not stt.available():
        pytest.skip("needs macOS say, ffmpeg and faster-whisper")
    d = tmp_path_factory.mktemp("clip")
    subprocess.run(["say", "-o", str(d / "a.aiff"), SAID], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(d / "a.aiff"), "-c:a", "libopus", str(d / "a.webm")], check=True)
    return (d / "a.webm").read_bytes()


@pytest.fixture
def tony(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "client", None)
    if not sandbox.available():  # without docker, the local runner still runs the code for real
        monkeypatch.setenv("VIVA_SANDBOX", "local")
        sandbox.reset()
    c = TestClient(create_app(data_dir=tmp_path, demo=False, dev_login=True))
    c.post("/api/auth/dev", json={"login": "tony"})
    yield c
    sandbox.reset()


def speak(c, sid, turn, clip):
    return c.post(f"/api/sessions/{sid}/media", data={"turn": str(turn), "duration": "6", "kind": "audio", "mode": "voice"},
                  files={"blob": ("answer.webm", clip, "audio/webm;codecs=opus")}).json()


def test_spoken_answers_are_transcribed_and_the_code_really_runs(tony, clip):
    c = tony
    v = c.post("/api/sessions", json={}).json()
    sid = v["id"]
    c.post(f"/api/sessions/{sid}/predict", json={"version": 0, **lock(RIGHT[0])})
    turn = c.post(f"/api/sessions/{sid}/next", json={"version": 0}).json()
    edited = False
    while True:
        up = speak(c, sid, turn["turn"], clip)
        assert up["transcriber"] == stt.name() and up["transcriber"].startswith("faster-whisper")
        words = up["transcript"].lower()
        assert "invoices" in words and "query string" in words and "caller" in words
        assert up["segments"] and all(0 <= s["start"] <= s["end"] <= 6 for s in up["segments"])
        text = up["transcript"] if turn["turn"] == 1 else up["transcript"] + " It never checks the login."
        edited = edited or turn["turn"] != 1
        res = c.post(f"/api/sessions/{sid}/answer", json={"version": 0, "turn": turn["turn"], "text": text,
                                                         "media_id": up["media_id"], "mode": "voice"}).json()
        if res["done"]:
            break
        turn = res
    out = c.post(f"/api/sessions/{sid}/finish", json={"version": 0}).json()

    run = out["assessment"]["reveal"]["run"]
    assert run["ok"] and run["agrees"] and run["runner"] in ("docker", "local")
    assert '"option": "others"' in run["stdout"]  # what the code really returned for customer 42 asking for 17

    token = c.app.state.engine.store.session(sid)["reviewer_token"]
    turns = TestClient(c.app).get(f"/api/reviews/{token}").json()["turns"]
    assert turns[0]["transcribed_by"] == stt.name() and turns[0]["edited"] is False
    assert turns[0]["segments"][0]["start"] < 1  # real timings from the recording, not estimated from the words
    assert turns[1]["edited"] is True and edited
