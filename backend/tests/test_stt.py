"""Server-side speech-to-text: real speech in the formats browsers upload, silence, broken files, and the switch."""
import json
import os
import shutil
import subprocess
import threading
import time

import pytest

from viva import stt

SAID = "The query filters invoices by the customer from the login, so another customer's invoices never come back."


@pytest.fixture(autouse=True)
def default_env(monkeypatch):
    monkeypatch.delenv("VIVA_STT", raising=False)
    monkeypatch.delenv("VIVA_STT_LANGUAGE", raising=False)


def run(*cmd):
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)


def seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         check=True, capture_output=True, text=True, timeout=30).stdout
    return float(json.loads(out)["format"]["duration"])


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    """Synthesised speech encoded like Chrome's MediaRecorder (webm/opus) and Safari's (mp4/aac), plus silence and junk."""
    if not (shutil.which("say") and shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("needs macOS say and ffmpeg")
    d = tmp_path_factory.mktemp("stt")
    voices = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    voice = ["-v", "Samantha"] if "Samantha" in voices else []
    try:
        run("say", *voice, "-o", str(d / "speech.aiff"), SAID)
        run("ffmpeg", "-y", "-i", str(d / "speech.aiff"), "-ac", "1", "-ar", "48000", "-c:a", "libopus", "-b:a", "32k", str(d / "speech.webm"))
        run("ffmpeg", "-y", "-i", str(d / "speech.aiff"), "-ac", "1", "-ar", "48000", "-c:a", "aac", "-b:a", "64k", str(d / "speech.mp4"))
        run("ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "3", "-c:a", "libopus", str(d / "silent.webm"))
        run("ffmpeg", "-y", "-stream_loop", "49", "-i", str(d / "speech.webm"), "-c", "copy", str(d / "long.webm"))  # 5 minutes
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        pytest.skip(f"could not make the test clips: {e}")
    (d / "corrupt.webm").write_bytes(b"\x1aE\xdf\xa3" + os.urandom(3000))  # a webm magic number, then noise
    return d


@pytest.fixture(scope="module")
def ready(clips):
    if not stt.warm():
        pytest.skip("faster-whisper or its model is not available")
    return clips


@pytest.mark.parametrize("name", ["speech.webm", "speech.mp4"])
def test_transcribes_browser_uploads(ready, name):
    length = seconds(ready / name)  # the container's length, as the browser reports it with the upload
    r = stt.transcribe(ready / name, duration=length)
    assert r is not None and abs(r["audio_seconds"] - length) < 0.2
    for word in ("invoices", "customer", "login"):
        assert word in r["text"].lower()
    assert r["language"] == "en" and r["model"] == stt.name() and r["model"].startswith("faster-whisper ")
    assert isinstance(r["duration_ms"], int) and r["duration_ms"] >= 0
    segs = r["segments"]
    assert segs and r["text"] == " ".join(s["text"] for s in segs)
    for i, s in enumerate(segs):
        assert s["text"] == s["text"].strip() and s["text"]
        assert 0 <= s["start"] <= s["end"] <= length
        assert s["start"] == round(s["start"], 1) and s["end"] == round(s["end"], 1)
        if i:
            assert segs[i - 1]["start"] <= s["start"]


def test_segments_never_run_past_the_reported_length(ready):
    claimed = seconds(ready / "speech.webm") - 0.6  # within the slack: the browser's timer and the audio can differ a little
    r = stt.transcribe(ready / "speech.webm", duration=claimed)
    assert r["segments"] and all(s["end"] <= claimed for s in r["segments"])
    assert "back" in r["text"].lower()  # the words after the cap are kept; only their times are clamped


def test_audio_longer_than_reported_is_refused_without_decoding_it_all(ready, monkeypatch, caplog):
    short = seconds(ready / "speech.webm") - 1.5  # past the slack
    started = time.monotonic()
    assert stt.transcribe(ready / "long.webm", duration=5.0) is None  # 5 minutes of speech that claims to be 5 seconds
    assert stt.transcribe(ready / "speech.webm", duration=short) is None
    assert time.monotonic() - started < 2
    monkeypatch.setattr(stt, "MAX_SECONDS", 60)  # with no reported length, the cap still holds
    assert stt.transcribe(ready / "long.webm") is None
    assert sum("the audio runs past" in m for m in caplog.messages) == 3


def test_a_container_that_reads_other_files_is_refused(ready):
    """Uploads are stored without an extension; ffmpeg left to probe would follow an ffconcat list to a sibling file."""
    (ready / "m_list").write_text("ffconcat version 1.0\nfile speech.webm\n")
    assert stt.transcribe(ready / "m_list", duration=5.0) is None


@pytest.mark.parametrize("duration", ["soon", float("nan"), float("inf"), -3.0, 0])
def test_a_reported_length_that_is_not_a_length_is_ignored(ready, duration):
    r = stt.transcribe(ready / "speech.webm", duration=duration)
    assert r is not None and "invoices" in r["text"].lower()


def test_silence_is_an_empty_transcript(ready):
    r = stt.transcribe(ready / "silent.webm")
    assert r is not None and r["text"] == "" and r["segments"] == []


def test_broken_or_missing_files_give_none(ready):
    assert stt.transcribe(ready / "corrupt.webm") is None
    assert stt.transcribe(ready / "missing.webm") is None


# ---------- the switch and the shared model, without loading the real one ----------
@pytest.fixture
def fresh(monkeypatch):
    """No model loaded yet; restored afterwards so the real model stays loaded for the other tests."""
    monkeypatch.setattr(stt, "_model", None)
    monkeypatch.setattr(stt, "_load_error", None)
    if stt.WhisperModel is None:
        monkeypatch.setattr(stt, "WhisperModel", object)
    return monkeypatch


def test_switched_off(fresh, tmp_path):
    fresh.setenv("VIVA_STT", "off")
    fresh.setattr(stt, "_load", lambda: pytest.fail("the model must not load when speech-to-text is off"))
    (tmp_path / "a.webm").write_bytes(b"x")
    assert stt.available() is False and stt.name() is None and stt.warm() is False
    assert stt.transcribe(tmp_path / "a.webm") is None


def test_concurrent_first_calls_load_the_model_once(fresh):
    loads, model = [], object()

    def slow_load():
        loads.append(1)
        time.sleep(0.2)
        return model

    fresh.setattr(stt, "_load", slow_load)
    gate, got = threading.Barrier(4), []

    def first_call():
        gate.wait()
        got.append(stt.warm() and stt._get_model())

    threads = [threading.Thread(target=first_call) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5)
    assert len(loads) == 1 and got == [model] * 4


@pytest.mark.parametrize("error, downloads", [(FileNotFoundError("not cached"), True),
                                             (ValueError("This CTranslate2 package was not compiled with CUDA support"), False)])
def test_only_a_model_that_is_not_cached_is_downloaded(fresh, error, downloads):
    calls = []

    class Model:
        def __init__(self, size, device, compute_type, local_files_only=False):
            calls.append(local_files_only)
            if local_files_only:
                raise error

    fresh.setattr(stt, "WhisperModel", Model)
    assert stt.warm() is downloads
    assert calls == ([True, False] if downloads else [True])  # a bad device never reaches the network
    assert (stt._load_error is None) is downloads


def test_a_model_that_cannot_load_is_not_retried(fresh, tmp_path):
    loads = []

    def broken_load():
        loads.append(1)
        raise RuntimeError("no model files")

    fresh.setattr(stt, "_load", broken_load)
    (tmp_path / "a.webm").write_bytes(b"x")
    assert stt.warm() is False
    assert stt.transcribe(tmp_path / "a.webm") is None and stt.available() is False and stt.name() is None
    assert len(loads) == 1
