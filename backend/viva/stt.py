"""Speech-to-text on the server: a spoken viva answer becomes the text and the timestamped segments the viva grades.

faster-whisper runs locally, so the recording never leaves the server. The model loads once, on first use or from
warm(), and is shared by every request. Without faster-whisper, with VIVA_STT=off, or when the model cannot load,
available() is False and transcribe() returns None, so the engine keeps its typed answers and its demo stand-ins.

Env: VIVA_STT (off disables), VIVA_WHISPER_MODEL (default base), VIVA_WHISPER_DEVICE (default cpu),
VIVA_STT_LANGUAGE (default en; auto detects the language).
"""
import logging
import math
import os
import threading
import time

try:
    import av
    import numpy as np
    from faster_whisper import WhisperModel
except ImportError:  # the server still runs, without server-side transcripts
    av = np = WhisperModel = None

log = logging.getLogger("viva.stt")

round1 = lambda x: math.floor(x * 10 + 0.5) / 10  # same rounding as the engine's segments

SAMPLE_RATE = 16000  # what Whisper listens at
MAX_SECONDS = 300  # longer than any clip the viva records; the cap when no length is reported
SLACK = 1.0  # how far past the reported length the decoded audio may run before the file is refused

_lock = threading.Lock()
_model = None
_load_error = None  # why the model did not load; set once, so a broken setup is not retried on every upload


def _enabled():
    return WhisperModel is not None and os.environ.get("VIVA_STT", "").strip().lower() not in ("off", "0", "false")


def _size():
    return os.environ.get("VIVA_WHISPER_MODEL") or "base"


def available():
    """faster-whisper is installed, VIVA_STT is not off, and the model has not already failed to load."""
    return _enabled() and _load_error is None


def name():
    return f"faster-whisper {_size()}" if available() else None


def _load():
    size, device = _size(), os.environ.get("VIVA_WHISPER_DEVICE") or "cpu"
    try:  # the cached copy first, so a server without network starts the same way
        return WhisperModel(size, device=device, compute_type="int8", local_files_only=True)
    except FileNotFoundError:  # only a missing model downloads; a bad device or compute type fails with its own message
        log.info("%s is not cached yet: downloading it", size)
        return WhisperModel(size, device=device, compute_type="int8")


def _get_model():
    """The shared model, loaded once behind the lock (two first requests at once still load it once). None if it cannot load."""
    global _model, _load_error
    if _model is not None:
        return _model
    with _lock:
        if _model is None and _load_error is None:
            started = time.monotonic()
            try:
                _model = _load()
                log.info("loaded %s in %.1fs", name(), time.monotonic() - started)
            except Exception as e:
                _load_error = f"{type(e).__name__}: {e}"
                log.warning("could not load the speech model: %s", _load_error)
    return _model


def warm():
    """Loads the model ahead of the first upload (call it from a background thread at startup). True when it is ready."""
    return available() and _get_model() is not None


def _container(head):
    """The demuxer for the containers browsers record into, from the file's first bytes. Left to probe for itself,
    ffmpeg also opens formats that read other files on the server (an ffconcat list, for one)."""
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "matroska"  # webm: Chrome, Firefox
    if head[4:8] == b"ftyp":
        return "mp4"  # Safari
    if head[:4] == b"OggS":
        return "ogg"  # Firefox, audio only
    return None


def _decode(path, limit):
    """The first audio track as 16 kHz mono float32. Decoding stops past limit seconds, so a small file that expands
    into hours of audio costs no more than a clip; such a file raises, since it is not what the browser reported."""
    with open(path, "rb") as f:
        fmt = _container(f.read(8))
    if fmt is None:
        raise ValueError("not a webm, mp4 or ogg recording")
    resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
    chunks, seconds = [], 0.0
    with av.open(str(path), format=fmt, metadata_errors="ignore") as container:
        if not container.streams.audio:
            raise ValueError("no audio track")
        try:
            for frame in container.decode(audio=0):
                seconds += frame.samples / frame.sample_rate
                if seconds > limit:
                    raise ValueError(f"the audio runs past {limit:g}s")
                frame.pts = None  # as faster-whisper does: the resampler need not check timestamps
                chunks += [r.to_ndarray().reshape(-1) for r in resampler.resample(frame)]
        except av.error.InvalidDataError:
            pass  # a damaged tail: keep what decoded before it, as faster-whisper does
        chunks += [r.to_ndarray().reshape(-1) for r in resampler.resample(None)]
    return np.concatenate(chunks) if chunks else np.zeros(0, np.float32)


def transcribe(path, duration=None):
    """The words in one recording (webm/opus from Chrome, mp4/aac from Safari). Never raises.

    duration is the length the browser reported, in seconds; segment times are clamped to it and to the decoded length,
    so a segment never runs past the clip the learner plays back. Audio that runs more than SLACK past it (or past
    MAX_SECONDS) is refused rather than transcribed: the file is not the clip the browser described.

    Returns {"text", "segments": [{"start", "end", "text"}], "language", "model", "duration_ms", "audio_seconds"}, where
    duration_ms is the time the transcription took. A clip that decodes but holds no speech gives text "" and no
    segments ("silent"); None means no transcript at all ("broken" or switched off): unavailable, unreadable file, not a
    webm/mp4/ogg recording, longer than reported, no audio in it, or the model failed. The reason is logged.
    """
    if not available():
        return None
    model = _get_model()
    if model is None:
        return None
    try:
        claimed = float(duration)
    except (TypeError, ValueError):
        claimed = None
    if claimed is not None and not 0 < claimed < math.inf:  # NaN fails the comparison too
        claimed = None
    language = os.environ.get("VIVA_STT_LANGUAGE") or "en"
    file = os.path.basename(str(path))
    started = time.monotonic()
    try:
        audio = _decode(path, min(claimed or MAX_SECONDS, MAX_SECONDS) + SLACK)
        if not audio.size:
            log.warning("no audio in %s", file)
            return None
        raw, info = model.transcribe(audio, language=None if language == "auto" else language, vad_filter=True)
        raw = list(raw)  # segments decode lazily: errors surface here, inside the try
    except Exception as e:
        log.warning("could not transcribe %s: %s: %s", file, type(e).__name__, e)
        return None
    # Whisper can place the last segment end a little past the audio; rounding down keeps the cap inside the clip.
    limit = min(info.duration, claimed) if claimed else info.duration
    cap = math.floor(limit * 10) / 10
    segments = []
    for s in raw:
        text = s.text.strip()
        if text:
            start = min(round1(max(s.start, 0)), cap)
            segments.append({"start": start, "end": max(start, min(round1(s.end), cap)), "text": text})
    took = time.monotonic() - started
    log.info("transcribed %.1fs of audio in %.1fs (%d segments)", info.duration, took, len(segments))
    return {
        "text": " ".join(s["text"] for s in segments),
        "segments": segments,
        "language": info.language,
        "model": name(),
        "duration_ms": round(took * 1000),
        "audio_seconds": round1(info.duration),
    }
