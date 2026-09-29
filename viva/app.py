from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import time
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .store import connect, event, initialize, read_state, save
from .tasks import TASKS, artifact_run, grade, public_task

STATIC = Path(__file__).parent / "static"


class Join(BaseModel):
    study_code: str = Field(default="", max_length=100)
    consent: bool = False


class Submission(BaseModel):
    version: int
    prediction: str = Field(default="", max_length=100)
    verdict: Literal["meets", "violates", ""] = ""
    evidence: str = Field(default="", max_length=100)
    rationale: str = Field(default="", max_length=4000)
    confidence: Literal["low", "medium", "high"] = "medium"
    external_ai_used: bool = False
    interruption_seconds: int = Field(default=0, ge=0, le=3600)


class Correction(BaseModel):
    version: int
    reflection: str = Field(min_length=10, max_length=4000)


def task_for(s):
    stage, form = s["stage"], s["form"]
    if s["mode"] == "demo":
        return TASKS[s["demo_task"]] if stage == "demo" else None
    ids = {
        "baseline": f"baseline-{form}", "practice": f"practice-{form}",
        "transfer1": f"transfer-{form}-{'bug' if form == 'a' else 'valid'}", "transfer2": f"transfer-{form}-{'valid' if form == 'a' else 'bug'}",
        "delayed1": f"delayed-{form}-{'valid' if form == 'a' else 'bug'}", "delayed2": f"delayed-{form}-{'bug' if form == 'a' else 'valid'}",
    }
    return TASKS[ids[stage]] if stage in ids else None


def new_state(mode, now):
    return dict(id=secrets.token_urlsafe(24), mode=mode, study=None, group="B", form="a",
                stage="demo" if mode == "demo" else "baseline", demo_task="demo-start",
                version=0, created=now, stage_started=now, task_started=now, gaps={},
                last_result=None, last_task=None, correction=None, reveals=[],
                settings={}, immediate_completed=None, consent=True)


def create_app(db_path=None, clock=time.time):
    path = db_path or os.environ.get("VIVA_DB", "data/viva.sqlite3")
    initialize(path)
    app = FastAPI(title="Viva learning pilot", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @contextmanager
    def transaction(sid=None):
        db = connect(path)
        try:
            db.execute("BEGIN IMMEDIATE")
            state = read_state(db, sid) if sid else None
            if sid and not state:
                raise HTTPException(404, "Session not found")
            yield db, state
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def view(s, now):
        t = task_for(s)
        assessment = s["mode"] == "study" and s["stage"] != "practice"
        budget = s["settings"].get("practice_seconds", 360) if s["stage"] == "practice" else s["settings"].get("assessment_seconds", 240)
        # Before delayed assessment ends, neither arm can inspect scored test answers.
        public = {k: s[k] for k in ("id", "mode", "stage", "version", "created", "stage_started", "immediate_completed")}
        public.update(task=public_task(t) if t else None,
                      interaction="self_review" if s["stage"] == "practice" and s["group"] == "A" else "structured",
                      assessment=assessment, elapsed=max(0, now-s["stage_started"]), budget_seconds=budget,
                      practice_ready=s["stage"] != "practice" or now-s["stage_started"] >= budget,
                      delayed_due=(s["immediate_completed"] + s["settings"].get("delay_seconds", 86400)) if s["immediate_completed"] else None,
                      gaps=list(s["gaps"].values()) if s["mode"] == "demo" else [],
                      last_result=s["last_result"] if s["mode"] == "demo" or s["stage"] == "practice" else None,
                      correction=s["correction"] if s["mode"] == "demo" else None)
        return public

    def check_version(s, version):
        if s["version"] != version:
            raise HTTPException(409, "This task has already changed. Reload to continue; nothing was overwritten.")

    def advance(s, stage, now):
        s.update(stage=stage, stage_started=now, task_started=now, version=s["version"]+1, last_result=None)

    def record(db, s, answer, now):
        t = task_for(s)
        result = grade(t, answer)
        db.execute("INSERT INTO attempts(session_id,stage,task_id,answer,result,started,submitted,wall_seconds) VALUES (?,?,?,?,?,?,?,?)",
                   (s["id"], s["stage"], t["id"], json.dumps(answer), json.dumps(result), s["task_started"], now, max(0, now-s["task_started"])))
        s["last_task"] = t["id"]
        event(db, s["id"], "submitted", now, {"stage": s["stage"], "task": t["id"]})
        return result

    @app.get("/")
    def home():
        return FileResponse(STATIC / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "contract": "fx-contract-v1"}

    @app.post("/api/demo")
    def demo():
        now = clock()
        with transaction() as (db, _):
            s = new_state("demo", now)
            save(db, s)
            event(db, s["id"], "demo_started", now)
        return view(s, now)

    @app.post("/api/join")
    def join(body: Join):
        if not body.consent:
            raise HTTPException(422, "Consent is required. Do not enter names, private code, or personal information.")
        now = clock()
        with transaction() as (db, _):
            row = db.execute("SELECT * FROM studies WHERE code=?", (body.study_code.strip(),)).fetchone()
            if not row:
                raise HTTPException(404, "Study code not found. Ask your facilitator.")
            allocation = json.loads(row["allocation"])
            slot = row["next_slot"]
            if slot >= len(allocation):
                raise HTTPException(409, "This study has no remaining places.")
            s = new_state("study", now)
            s.update(study=row["code"], settings=json.loads(row["settings"]), **allocation[slot])
            db.execute("UPDATE studies SET next_slot=next_slot+1 WHERE code=?", (row["code"],))
            save(db, s)
            event(db, s["id"], "consented_and_allocated", now)
        return view(s, now)

    @app.get("/api/sessions/{sid}")
    def session(sid: str):
        now = clock()
        with transaction(sid) as (db, s):
            if s["mode"] == "study" and s["stage"] == "practice" and now-s["stage_started"] >= s["settings"]["practice_seconds"]:
                event(db, sid, "practice_window_ended", now, {"late_seconds": now-s["stage_started"]-s["settings"]["practice_seconds"], "unsubmitted_note": True})
                advance(s, "transfer1", now)
                save(db, s)
            if s["stage"] == "waiting" and now >= s["immediate_completed"] + s["settings"]["delay_seconds"]:
                advance(s, "delayed1", now)
                event(db, sid, "delayed_started", now)
                save(db, s)
            return view(s, now)

    @app.post("/api/sessions/{sid}/submit")
    def submit(sid: str, body: Submission):
        now = clock()
        with transaction(sid) as (db, s):
            check_version(s, body.version)
            t = task_for(s)
            if not t:
                raise HTTPException(409, "No active question")
            answer = body.model_dump(exclude={"version"})
            assessment = s["mode"] == "study" and s["stage"] != "practice"
            timed_out = assessment and now-s["stage_started"] >= s["settings"]["assessment_seconds"]
            practice_expired = s["stage"] == "practice" and now-s["stage_started"] >= s["settings"]["practice_seconds"]
            if practice_expired and s["group"] == "B":
                event(db, sid, "practice_window_ended", now, {"late_seconds": now-s["stage_started"]-s["settings"]["practice_seconds"]})
                advance(s, "transfer1", now)
                save(db, s)
                return view(s, now)
            if timed_out:
                # Both groups get the same deadline; late answers cannot improve score.
                answer.update(prediction="", verdict="", evidence="", rationale="[time limit expired]", timed_out=True)
            elif not (s["stage"] == "practice" and s["group"] == "A"):
                if not answer["prediction"].strip() or not answer["verdict"] or answer["evidence"] not in {e["id"] for e in public_task(t)["evidence"]}:
                    raise HTTPException(422, "Complete the prediction, contract verdict, and evidence choice.")
                if len(answer["rationale"].strip()) < 10:
                    raise HTTPException(422, "Add a short explanation (at least 10 characters).")
            if s["stage"] == "practice" and s["group"] == "A" and not practice_expired and len(answer["rationale"].strip()) < 10:
                raise HTTPException(422, "Write a short self-review note.")
            if s["stage"] == "practice" and s["group"] == "A" and now-s["stage_started"] < s["settings"]["practice_seconds"]:
                raise HTTPException(409, "Use the full allocated practice window. You may review the material and use AI.")
            result = record(db, s, answer, now)
            if practice_expired:
                event(db, sid, "practice_window_ended", now, {"late_seconds": now-s["stage_started"]-s["settings"]["practice_seconds"]})
            if s["mode"] == "demo":
                gap = s["gaps"].get(t["concept"])
                if not result["passed"]:
                    s["gaps"][t["concept"]] = dict(concept=t["concept"], status="open", origin=t["id"],
                        origin_hash=t["artifact_hash"], opened=now, due=now, correction=None, closed=None)
                elif gap and gap["status"] != "closed" and gap["correction"] and t["artifact_hash"] != gap["origin_hash"] and now >= gap["due"]:
                    gap.update(status="closed", closed=now, transfer_task=t["id"], transfer_hash=t["artifact_hash"], evidence="immediate_transfer_only")
                s.update(last_result=result, stage="feedback", version=s["version"]+1)
            elif s["stage"] == "practice" and s["group"] == "B":
                s.update(last_result=result, version=s["version"]+1, task_started=now)
            else:
                next_stage = {"baseline": "practice", "practice": "transfer1", "transfer1": "transfer2",
                              "transfer2": "waiting", "delayed1": "delayed2", "delayed2": "complete"}[s["stage"]]
                if next_stage == "waiting":
                    s["immediate_completed"] = now
                    event(db, sid, "immediate_completed", now)
                advance(s, next_stage, now)
            save(db, s)
            return view(s, now)

    @app.post("/api/sessions/{sid}/finish-practice")
    def finish_practice(sid: str, body: Correction):
        now = clock()
        with transaction(sid) as (db, s):
            check_version(s, body.version)
            if s["mode"] != "study" or s["stage"] != "practice" or s["group"] != "B":
                raise HTTPException(409, "No structured practice session is active.")
            if now-s["stage_started"] < s["settings"]["practice_seconds"]:
                raise HTTPException(409, "Use the full practice window before proceeding.")
            event(db, sid, "practice_reflection", now, {"text": body.reflection})
            event(db, sid, "practice_window_ended", now, {"late_seconds": now-s["stage_started"]-s["settings"]["practice_seconds"]})
            advance(s, "transfer1", now)
            save(db, s)
            return view(s, now)

    @app.post("/api/sessions/{sid}/run")
    def run(sid: str):
        now = clock()
        with transaction(sid) as (db, s):
            if s["stage"] != "practice" or s["group"] != "A":
                raise HTTPException(403, "Run is available only during ordinary self-review practice.")
            if now-s["stage_started"] >= s["settings"]["practice_seconds"]:
                raise HTTPException(403, "The practice window has ended. Continue to the transfer assessment.")
            result = grade(task_for(s), {})
            event(db, sid, "reference_viewed", now)
            return {k: result[k] for k in ("actual_output", "required_output", "feedback")}

    @app.post("/api/sessions/{sid}/correct")
    def correct(sid: str, body: Correction):
        now = clock()
        with transaction(sid) as (db, s):
            check_version(s, body.version)
            if s["mode"] != "demo" or s["stage"] != "feedback":
                raise HTTPException(409, "No demo feedback to review")
            gap = s["gaps"].get(TASKS[s["last_task"]]["concept"])
            if gap and gap["status"] != "closed":
                gap.update(status="awaiting_transfer", correction=body.reflection)
            s["correction"] = body.reflection
            next_id = {"demo-start": "demo-review", "demo-review": "demo-review-2"}.get(s["last_task"])
            event(db, sid, "reflection_saved", now, {"text": body.reflection, "source": "learner_reflection_not_senior_review"})
            if next_id:
                s["demo_task"] = next_id
                advance(s, "demo", now)
            else:
                advance(s, "complete", now)
            save(db, s)
            return view(s, now)

    @app.delete("/api/sessions/{sid}")
    def withdraw(sid: str):
        with transaction(sid) as (db, s):
            db.execute("DELETE FROM events WHERE session_id=?", (sid,))
            db.execute("DELETE FROM attempts WHERE session_id=?", (sid,))
            db.execute("DELETE FROM sessions WHERE id=?", (sid,))
        return {"deleted": True}

    return app


app = create_app()
