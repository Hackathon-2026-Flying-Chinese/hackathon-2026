import csv
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from viva.app import create_app
from viva.cli import export_blind, init_study, load_study, summarize
from viva.store import connect, read_state
from viva.tasks import TASKS, artifact_run, grade, public_task, required_run


class Clock:
    def __init__(self): self.value = 1_800_000_000.0
    def __call__(self): return self.value
    def add(self, value): self.value += value


def correct_answer(s):
    t = TASKS[s["task"]["id"]]
    return dict(version=s["version"], prediction=str(artifact_run(t)),
                verdict="meets" if artifact_run(t) == required_run(t) else "violates",
                evidence="same-currency", rationale="The destination precision controls the final rounding; this test covers that currency.")


class OracleTests(unittest.TestCase):
    def test_independent_known_answers(self):
        expected = {"demo-start": ("119928.09", "119928"), "demo-review": ("65.88", "65.877"),
                    "transfer-a-valid": ("36.958", "36.958"), "delayed-b-valid": ("25.576", "25.576")}
        for key, values in expected.items():
            self.assertEqual((str(artifact_run(TASKS[key])), str(required_run(TASKS[key]))), values)

    def test_understands_bug_but_wrong_business_judgment(self):
        r = grade(TASKS["demo-start"], dict(prediction="119928.09", verdict="meets", evidence="usd-only"))
        self.assertEqual(r["dimensions"], {"behavior": 1, "requirement": 0, "evidence": 0})
        self.assertFalse(r["passed"])

    def test_business_answer_is_not_actual_behavior(self):
        r = grade(TASKS["demo-start"], dict(prediction="119928", verdict="violates", evidence="same-currency"))
        self.assertEqual(r["dimensions"], {"behavior": 0, "requirement": 1, "evidence": 1})

    def test_nonfinite_and_invalid_predictions_fail(self):
        for value in ("NaN", "Infinity", "hello", "1e999999999999999999"):
            self.assertEqual(grade(TASKS["demo-start"], {"prediction": value})["dimensions"]["behavior"], 0)

    def test_curated_tasks_have_intended_validity_and_no_answer_payload(self):
        for t in TASKS.values():
            self.assertEqual(artifact_run(t) == required_run(t), t["correct"])
            for key in ("correct", "actual_output", "required_output", "truth"):
                self.assertNotIn(key, public_task(t))


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "pilot.sqlite3")
        self.clock = Clock()
        self.client = TestClient(create_app(self.db, self.clock))

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def post(self, s, route, body):
        r = self.client.post(f"/api/sessions/{s['id']}/{route}", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def study(self):
        return init_study(self.db, n=4, seed=42, practice_seconds=10, assessment_seconds=60, delay_seconds=100, synthetic=True)

    def join(self, code):
        self.clock.add(1)
        response = self.client.post("/api/join", json={"study_code": code, "consent": True})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_gap_requires_correction_and_new_task_and_persists(self):
        s = self.client.post("/api/demo").json()
        old = dict(s)
        s = self.post(s, "submit", correct_answer(s) | {"verdict": "meets"})
        self.assertEqual(s["gaps"][0]["status"], "open")
        replay = self.client.post(f"/api/sessions/{s['id']}/submit", json=correct_answer(old))
        self.assertEqual(replay.status_code, 409)
        s = self.post(s, "correct", {"version": s["version"], "reflection": "Round the final payout using destination currency precision."})
        self.assertEqual(s["gaps"][0]["status"], "awaiting_transfer")
        self.assertNotEqual(s["task"]["id"], old["task"]["id"])
        s = self.post(s, "submit", correct_answer(s))
        self.assertEqual(s["gaps"][0]["status"], "closed")
        with TestClient(create_app(self.db, self.clock)) as fresh:
            persisted = fresh.get(f"/api/sessions/{s['id']}").json()
        self.assertEqual(persisted["gaps"], s["gaps"])

    def test_failed_transfer_reopens_gap(self):
        s = self.client.post("/api/demo").json()
        s = self.post(s, "submit", correct_answer(s) | {"evidence": "http-ok"})
        s = self.post(s, "correct", {"version": s["version"], "reflection": "Destination precision must drive final rounding."})
        s = self.post(s, "submit", correct_answer(s) | {"evidence": "usd-only"})
        self.assertEqual(s["gaps"][0]["status"], "open")

    def test_consent_and_allocation_balance(self):
        code = self.study()
        self.assertEqual(self.client.post("/api/join", json={"study_code": code}).status_code, 422)
        for _ in range(4):
            s = self.join(code)
            self.assertNotIn("group", s)
        settings, sessions, _ = load_study(self.db, code)
        self.assertEqual(sorted((s["group"], s["form"]) for s in sessions), [("A", "a"), ("A", "b"), ("B", "a"), ("B", "b")])
        self.assertEqual(self.client.post("/api/join", json={"study_code": code, "consent": True}).status_code, 409)

    def test_full_pilot_feedback_blinding_deadline_retention_and_export(self):
        code = self.study()
        self.client.post("/api/demo")  # Must never enter study denominator.
        for _ in range(4):
            s = self.join(code)
            s = self.post(s, "submit", correct_answer(s))
            self.assertEqual(s["stage"], "practice")
            if s["interaction"] == "self_review":
                self.assertEqual(self.client.post(f"/api/sessions/{s['id']}/run").status_code, 200)
                early = self.client.post(f"/api/sessions/{s['id']}/submit", json={"version": s["version"], "rationale": "Ordinary self review using the same reference."})
                self.assertEqual(early.status_code, 409)
                self.clock.add(10)
                self.assertEqual(self.client.post(f"/api/sessions/{s['id']}/run").status_code, 403)
                s = self.post(s, "submit", {"version": s["version"], "rationale": "Destination currency precision checked against the spec."})
            else:
                s = self.post(s, "submit", correct_answer(s))
                self.assertIsNotNone(s["last_result"])
                self.clock.add(10)
                s = self.post(s, "finish-practice", {"version": s["version"], "reflection": "Check destination precision in new tasks."})
            for stage in ("transfer1", "transfer2"):
                self.assertEqual(s["stage"], stage)
                self.assertIsNone(s["last_result"])
                self.assertEqual(self.client.post(f"/api/sessions/{s['id']}/run").status_code, 403)
                self.clock.add(5)
                s = self.post(s, "submit", correct_answer(s))
            self.assertEqual(s["stage"], "waiting")
            self.assertEqual(self.client.get(f"/api/sessions/{s['id']}").json()["stage"], "waiting")
            self.clock.add(100)
            s = self.client.get(f"/api/sessions/{s['id']}").json()
            for stage in ("delayed1", "delayed2"):
                self.assertEqual(s["stage"], stage)
                s = self.post(s, "submit", correct_answer(s))
            self.assertEqual(s["stage"], "complete")
        report = summarize(self.db, code)
        self.assertEqual(report["enrolled"], 4)
        self.assertIn("SYNTHETIC", report["evidence_type"])
        self.assertEqual(report["groups"]["A"]["transfer"]["mean"], 6)
        self.assertEqual(report["groups"]["B"]["transfer"]["mean"], 6)
        out = Path(self.temp.name) / "review"
        self.assertEqual(export_blind(self.db, code, out), 20)
        with (out / "blind-review.csv").open() as f:
            rows = list(csv.DictReader(f))
        self.assertNotIn("group", rows[0])
        self.assertNotIn("objective_score", rows[0])
        self.assertEqual(report["human_review_status"], "not_collected")

    def test_server_times_out_answers_and_no_feedback_leak(self):
        s = self.join(self.study())
        answer = correct_answer(s)
        self.clock.add(60)
        s = self.post(s, "submit", answer)
        with connect(self.db) as db:
            row = db.execute("SELECT result,answer FROM attempts").fetchone()
        self.assertEqual(json.loads(row["result"])["objective_score"], 0)
        self.assertTrue(json.loads(row["answer"])["timed_out"])
        self.assertIsNone(s["last_result"])

    def test_empty_report_has_no_fabricated_effect(self):
        code = self.study()
        report = summarize(self.db, code)
        self.assertEqual(report["enrolled"], 0)
        self.assertIsNone(report["groups"]["A"]["transfer"]["mean"])

    def test_blind_scores_import_and_withdrawal_count(self):
        code = self.study()
        s = self.join(code)
        self.post(s, "submit", correct_answer(s))
        out = Path(self.temp.name) / "reviews"
        export_blind(self.db, code, out)
        path = out / "blind-review.csv"
        with path.open() as f:
            reader = csv.DictReader(f)
            fields, rows = reader.fieldnames, list(reader)
        rows[0].update(reasoning_score="2", assessor="Mentor-X", review_seconds="25")
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        report = summarize(self.db, code, path)
        self.assertEqual(report["human_ratings"][0]["reasoning_score"], 2)
        self.assertEqual(report["participants"][0]["human_review_seconds"], 25)
        self.assertIsNone(report["participants"][0]["immediate_combined_person_seconds"])
        self.client.delete(f"/api/sessions/{s['id']}")
        report = summarize(self.db, code)
        self.assertEqual((report["enrolled"], report["withdrawn_count"]), (0, 1))

    def test_reload_cannot_extend_practice(self):
        s = self.join(self.study())
        s = self.post(s, "submit", correct_answer(s))
        self.clock.add(11)
        s = self.client.get(f"/api/sessions/{s['id']}").json()
        self.assertEqual(s["stage"], "transfer1")

    def test_withdraw_removes_answers(self):
        s = self.client.post("/api/demo").json()
        s = self.post(s, "submit", correct_answer(s))
        self.assertEqual(self.client.delete(f"/api/sessions/{s['id']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/sessions/{s['id']}").status_code, 404)
        with connect(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM attempts").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
