"""Viva server: the interview API, signed recording links, and the front end in ../frontend.

Run (from backend/):
  uv run uvicorn viva.app:app --port 8792
Environment:
  ANTHROPIC_API_KEY   the live viva (follow-up and rubric assessment); without it the viva runs simulated, labelled so
  VIVA_MODEL          the model for the viva (claude-sonnet-5-5 by default)
  VIVA_DATA           where the database and the recordings live (backend/data by default)
  VIVA_DEMO=1         presenter controls: stand-in answers, the reviewer link on the learner page, settings and reset
"""
import json
import logging
import os
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import ai
from .engine import Engine, Fail, fail
from .store import Store

HERE = Path(__file__).resolve().parent
FRONTEND = HERE.parent.parent / "frontend"
TASKS = FRONTEND / "data" / "tasks.json"
MAX_UPLOAD = 100 * 1024 * 1024  # a 180-second clip is well under this

logging.basicConfig(level=logging.INFO, format="[viva] %(message)s")


def create_app(data_dir=None, demo=None, content=None):
    demo = os.environ.get("VIVA_DEMO") == "1" if demo is None else demo
    store = Store(data_dir or os.environ.get("VIVA_DATA") or HERE.parent / "data")
    engine = Engine(store, content or json.loads(TASKS.read_text()), demo=demo)
    app = FastAPI(title="Viva", docs_url=None, redoc_url=None)
    app.state.engine = engine

    @app.exception_handler(Fail)
    async def failed(_, e: Fail):
        return JSONResponse({"detail": e.detail}, status_code=e.status)

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        else:  # the pages always revalidate, so a deploy never pairs old scripts with a new API
            response.headers["Cache-Control"] = "no-cache"
        return response

    def need_demo():
        if not demo:
            fail(404, "Not found")

    @app.get("/api/health")
    def health():
        return {"service": "viva", **ai.status(), "demo": demo}

    @app.post("/api/check")
    def check(body: dict = Body(default={})):
        return engine.check(body.get("pr"))

    @app.post("/api/sessions")
    def start(body: dict = Body(default={})):
        return engine.start(body.get("pr"))

    @app.get("/api/sessions/{sid}")
    def session(sid: str, presenter: bool = False):
        return engine.session(sid, presenter)

    @app.post("/api/sessions/{sid}/predict")
    def predict(sid: str, body: dict = Body(default={}), presenter: bool = False):
        return engine.predict(sid, body, presenter)

    @app.post("/api/sessions/{sid}/next")
    def interview_next(sid: str, body: dict = Body(default={}), presenter: bool = False):
        return engine.interview_next(sid, body, presenter)

    @app.post("/api/sessions/{sid}/answer")
    def interview_answer(sid: str, body: dict = Body(default={}), presenter: bool = False):
        return engine.interview_answer(sid, body, presenter)

    @app.post("/api/sessions/{sid}/finish")
    def interview_finish(sid: str, body: dict = Body(default={}), presenter: bool = False):
        return engine.interview_finish(sid, body, presenter)

    @app.post("/api/sessions/{sid}/retake")
    def retake(sid: str, body: dict = Body(default={}), presenter: bool = False):
        return engine.retake(sid, body, presenter)

    @app.post("/api/sessions/{sid}/leave")
    def leave(sid: str):
        return engine.leave(sid)

    @app.delete("/api/sessions/{sid}")
    def remove(sid: str):
        return engine.remove(sid)

    @app.post("/api/sessions/{sid}/media")
    def media_upload(sid: str, blob: UploadFile = File(...), turn: int = Form(...), duration: float = Form(...),
                     kind: str = Form("video"), mode: str = Form("text")):
        def write(path):
            size = 0
            with open(path, "wb") as out:
                while chunk := blob.file.read(1 << 20):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        fail(413, "This recording is too large.")
                    out.write(chunk)
            return size
        mime = (blob.content_type or "application/octet-stream").split(";")[0]
        return engine.media_upload(sid, turn, kind if kind in ("video", "audio") else "video", duration, mode, mime, write)

    @app.delete("/api/sessions/{sid}/media/{mid}")
    def media_discard(sid: str, mid: str):
        return engine.media_discard(sid, mid)

    @app.post("/api/media/{mid}/link")
    def media_link(mid: str, body: dict = Body(default={})):
        return engine.media_link(mid, token=body.get("token"), sid=body.get("sid"))

    @app.get("/api/media/{mid}")
    def media_open(mid: str, exp: int, a: str, sig: str):
        path, mime = engine.media_open(mid, exp, a, sig)
        return FileResponse(path, media_type=mime, headers={"Cache-Control": "private, no-store"})

    @app.get("/api/reviews/{token}")
    def review(token: str, silent: bool = False):
        return engine.review(token, silent)

    @app.post("/api/reviews/{token}/decision")
    def decide(token: str, body: dict = Body(default={})):
        return engine.decide(token, body)

    @app.get("/api/portfolio")
    def portfolio():
        return engine.portfolio()

    @app.get("/api/demo")
    def demo_info():
        need_demo()
        return engine.demo_info()

    @app.post("/api/demo/settings")
    def demo_settings(body: dict = Body(default={})):
        need_demo()
        return engine.set_settings(body)

    @app.post("/api/demo/reset")
    def demo_reset():
        need_demo()
        return engine.reset()

    # The answer key stays on the server: the front end gets the question side of a task in the session view.
    @app.get("/data/{rest:path}")
    def hidden(rest: str):
        fail(404, "Not found")

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def unknown(rest: str):
        fail(404, "Not found")

    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
    return app


app = create_app()
