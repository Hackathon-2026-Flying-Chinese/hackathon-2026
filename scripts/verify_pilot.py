"""Reproducible software QA with a controlled clock, never human learning evidence."""
import json
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
from viva.app import create_app
from viva.cli import export_blind, init_study, summarize
from viva.tasks import TASKS, artifact_run, required_run


def main():
    now = [1_800_000_000.0]
    out = Path("output/qa")
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        db = str(Path(directory) / "synthetic.sqlite3")
        code = init_study(db, n=4, seed=7, practice_seconds=6, assessment_seconds=60, delay_seconds=100, synthetic=True)
        with TestClient(create_app(db, lambda: now[0])) as client:
            for i in range(4):
                now[0] += 1
                response = client.post("/api/join", json={"study_code": code, "consent": True})
                response.raise_for_status()
                s = response.json()
                while s["stage"] != "complete":
                    url = f"/api/sessions/{s['id']}"
                    if s["stage"] == "waiting":
                        now[0] += 100
                        response = client.get(url)
                    elif s["stage"] == "practice":
                        if s["interaction"] == "self_review":
                            client.post(url + "/run").raise_for_status()
                            now[0] += 6
                            response = client.post(url + "/submit", json={"version": s["version"], "rationale": "Synthetic QA: normal review note."})
                        else:
                            t = TASKS[s["task"]["id"]]
                            response = client.post(url + "/submit", json=answer(s, t))
                            response.raise_for_status()
                            s = response.json()
                            now[0] += 6
                            response = client.post(url + "/finish-practice", json={"version": s["version"], "reflection": "Synthetic QA reflection: check currency precision."})
                    else:
                        t = TASKS[s["task"]["id"]]
                        body = answer(s, t)
                        # Exercise a mix of known scores, not a fabricated intervention effect.
                        if i % 2 == 0 and s["stage"] == "baseline":
                            body["evidence"] = "usd-only"
                        now[0] += 3
                        response = client.post(url + "/submit", json=body)
                    response.raise_for_status()
                    s = response.json()
            report = summarize(db, code)
            export_blind(db, code, out)
            assert report["enrolled"] == 4
            assert all(report["groups"][g]["retention"]["n"] == 2 for g in "AB")
            (out / "synthetic-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"status": "passed", "synthetic_sessions": 4, "blind_assessment_rows": 20,
                      "human_participants": 0, "evidence": str(out / "synthetic-report.json")}))


def answer(s, t):
    return dict(version=s["version"], prediction=str(artifact_run(t)),
                verdict="meets" if artifact_run(t) == required_run(t) else "violates",
                evidence="same-currency", rationale="Synthetic QA: destination-specific tests support the stated contract.")


if __name__ == "__main__":
    main()
