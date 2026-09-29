"""Facilitator-only commands. No participant data or allocation API is exposed."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import random
import secrets
import statistics

from .store import connect, initialize
from .tasks import TASKS, public_task, required_run


def init_study(path, *, n=12, seed=None, practice_seconds=360, assessment_seconds=240, delay_seconds=86400, synthetic=False):
    if n < 4 or n % 4:
        raise ValueError("Use a multiple of 4 participants to balance both arm and task form.")
    if min(practice_seconds, assessment_seconds, delay_seconds) < 1:
        raise ValueError("Durations must be positive.")
    if not synthetic and delay_seconds < 86400:
        raise ValueError("Human retention studies require at least 24 hours. Use --synthetic only for software QA.")
    seed = seed if seed is not None else secrets.randbits(64)
    rng = random.Random(seed)
    schedule = []
    for _ in range(n // 4):
        block = [{"group": g, "form": f} for g in "AB" for f in "ab"]
        rng.shuffle(block)
        schedule.extend(block)
    settings = dict(protocol="viva-pilot-v1", n=n, seed=seed, practice_seconds=practice_seconds,
                    assessment_seconds=assessment_seconds, delay_seconds=delay_seconds,
                    synthetic=synthetic, allocation_hash=sha256(json.dumps(schedule, sort_keys=True).encode()).hexdigest())
    code = secrets.token_urlsafe(9)
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO studies(code,settings,allocation) VALUES (?,?,?)", (code, json.dumps(settings), json.dumps(schedule)))
    return code


def load_study(path, code):
    with connect(path) as db:
        row = db.execute("SELECT * FROM studies WHERE code=?", (code,)).fetchone()
        if not row:
            raise ValueError("Unknown study")
        settings = json.loads(row["settings"])
        settings["allocated_count"] = row["next_slot"]
        sessions = [json.loads(x["state"]) for x in db.execute("SELECT state FROM sessions")]
        sessions = [s for s in sessions if s["study"] == code and s["mode"] == "study"]
        sessions.sort(key=lambda s: s["created"])
        ids = {s["id"] for s in sessions}
        attempts = [dict(x) for x in db.execute("SELECT * FROM attempts ORDER BY id") if x["session_id"] in ids]
        for a in attempts:
            a["answer"] = json.loads(a["answer"])
            a["result"] = json.loads(a["result"])
    return settings, sessions, attempts


def export_blind(path, code, directory):
    settings, sessions, attempts = load_study(path, code)
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    pseudonyms = {s["id"]: f"P{i+1:03}" for i, s in enumerate(sessions)}
    rows, key = [], []
    for a in attempts:
        if a["stage"] == "practice":
            continue
        t = TASKS[a["task_id"]]
        rid = "R" + sha256(f"{code}:{a['id']}".encode()).hexdigest()[:12]
        rows.append(dict(review_id=rid, task_id=t["id"], code=public_task(t)["code"],
                         contract="\n".join(public_task(t)["requirements"]),
                         prediction=a["answer"].get("prediction", ""), verdict=a["answer"].get("verdict", ""),
                         evidence=a["answer"].get("evidence", ""), rationale=a["answer"].get("rationale", ""),
                         reasoning_score="", assessor="", review_seconds=""))
        key.append(dict(review_id=rid, participant=pseudonyms[a["session_id"]], attempt_id=a["id"]))
    random.Random(settings["seed"] + 1).shuffle(rows)
    fields = ["review_id", "task_id", "code", "contract", "prediction", "verdict", "evidence", "rationale", "reasoning_score", "assessor", "review_seconds"]
    with (out / "blind-review.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (out / "facilitator-key.json").write_text(json.dumps(key, indent=2))
    return len(rows)


def summarize(path, code, review_csv=None):
    settings, sessions, attempts = load_study(path, code)
    with connect(path) as db:
        timing_events = [dict(x) for x in db.execute("SELECT session_id,payload FROM events WHERE kind='practice_window_ended'")]
    reviews = {}
    known = {"R" + sha256(f"{code}:{a['id']}".encode()).hexdigest()[:12] for a in attempts if a["stage"] != "practice"}
    if review_csv:
        with open(review_csv, newline="") as f:
            for row in csv.DictReader(f):
                if not row["reasoning_score"]:
                    continue
                rid = row["review_id"]
                if rid not in known or rid in reviews:
                    raise ValueError("Unknown or duplicate review_id")
                score, seconds = int(row["reasoning_score"]), float(row["review_seconds"])
                if score not in (0, 1, 2) or not row["assessor"].strip() or not (0 <= seconds < 86400):
                    raise ValueError("Human score must be 0–2, with an assessor and valid review_seconds")
                reviews[rid] = (score, seconds)
    rows = []
    for i, s in enumerate(sessions):
        aa = [a for a in attempts if a["session_id"] == s["id"]]
        by_stage = {a["stage"]: a for a in aa if a["stage"] != "practice"}
        def score(stages):
            return sum(by_stage[x]["result"]["objective_score"] for x in stages) if all(x in by_stage for x in stages) else None
        rr = [reviews["R" + sha256(f"{code}:{a['id']}".encode()).hexdigest()[:12]] for a in aa
              if "R" + sha256(f"{code}:{a['id']}".encode()).hexdigest()[:12] in reviews]
        rows.append(dict(participant=f"P{i+1:03}", group=s["group"], form=s["form"], stage=s["stage"],
                         baseline_out_of_3=score(["baseline"]), transfer_out_of_6=score(["transfer1", "transfer2"]),
                         delayed_out_of_6=score(["delayed1", "delayed2"]),
                         immediate_total_seconds=s["immediate_completed"]-s["created"] if s["immediate_completed"] else None,
                         assessment_wall_seconds=sum(a["wall_seconds"] for a in aa if a["stage"] != "practice"),
                         attempts=len(aa), timed_out=sum(bool(a["answer"].get("timed_out")) for a in aa),
                         external_ai_on_assessment=any(a["answer"].get("external_ai_used") for a in aa if a["stage"] != "practice"),
                         self_reported_interruption_seconds=sum(a["answer"].get("interruption_seconds", 0) for a in aa),
                         human_reviews=len(rr), human_review_seconds=sum(x[1] for x in rr)))
        rows[-1]["practice_overrun_seconds"] = sum(max(0, json.loads(e["payload"]).get("late_seconds", 0)) for e in timing_events if e["session_id"] == s["id"])
        baseline, transfer = rows[-1]["baseline_out_of_3"], rows[-1]["transfer_out_of_6"]
        rows[-1]["normalized_transfer_change"] = transfer/6-baseline/3 if baseline is not None and transfer is not None else None
        immediate_ratings = [reviews.get("R" + sha256(f"{code}:{a['id']}".encode()).hexdigest()[:12])
                             for a in aa if a["stage"] in ("baseline", "transfer1", "transfer2")]
        rows[-1]["immediate_combined_person_seconds"] = (
            rows[-1]["immediate_total_seconds"] + sum(r[1] for r in immediate_ratings)
            if rows[-1]["immediate_total_seconds"] is not None and len(immediate_ratings) == 3 and all(immediate_ratings) else None)
    groups = {}
    for group in "AB":
        members = [r for r in rows if r["group"] == group]
        def summary(key):
            values = [r[key] for r in members if r[key] is not None]
            return {"n": len(values), "median": statistics.median(values) if values else None,
                    "mean": statistics.mean(values) if values else None, "values": values}
        groups[group] = {"enrolled": len(members), "baseline": summary("baseline_out_of_3"),
                         "transfer": summary("transfer_out_of_6"), "retention": summary("delayed_out_of_6"),
                         "normalized_transfer_change": summary("normalized_transfer_change"),
                         "total_wall_seconds": summary("immediate_total_seconds"),
                         "combined_person_seconds": summary("immediate_combined_person_seconds")}
    human_rows = []
    for a in attempts:
        rid = "R" + sha256(f"{code}:{a['id']}".encode()).hexdigest()[:12]
        if rid in reviews:
            s = next(s for s in sessions if s["id"] == a["session_id"])
            human_rows.append(dict(group=s["group"], stage=a["stage"], reasoning_score=reviews[rid][0], review_seconds=reviews[rid][1]))
    return dict(protocol=settings["protocol"], evidence_type="SYNTHETIC SOFTWARE QA — NO LEARNING CLAIMS" if settings["synthetic"] else "HUMAN PILOT — EXPLORATORY",
                settings=settings, enrolled=len(sessions), withdrawn_count=settings["allocated_count"]-len(sessions),
                groups=groups, participants=rows, human_ratings=human_rows,
                human_review_status="not_collected" if not reviews else "partial_or_complete_see_counts",
                interpretation="No causal or retention claim from empty, synthetic, immediate-only, unblinded, or incomplete data. Examine baseline/form balance, exclusions, missingness and per-person scores. Timing is wall-clock; interruptions are retained and separately reported.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/viva.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-study")
    init.add_argument("--participants", type=int, default=12)
    init.add_argument("--seed", type=int)
    init.add_argument("--practice-seconds", type=int, default=360)
    init.add_argument("--assessment-seconds", type=int, default=240)
    init.add_argument("--delay-seconds", type=int, default=86400)
    init.add_argument("--synthetic", action="store_true")
    export = sub.add_parser("export-blind")
    export.add_argument("code")
    export.add_argument("--out", default="data/review")
    report = sub.add_parser("report")
    report.add_argument("code")
    report.add_argument("--reviews")
    args = parser.parse_args()
    if args.command == "init-study":
        print(init_study(args.db, n=args.participants, seed=args.seed, practice_seconds=args.practice_seconds,
                         assessment_seconds=args.assessment_seconds, delay_seconds=args.delay_seconds, synthetic=args.synthetic))
    elif args.command == "export-blind":
        print(json.dumps({"exported": export_blind(args.db, args.code, args.out), "out": args.out}))
    else:
        print(json.dumps(summarize(args.db, args.code, args.reviews), indent=2))


if __name__ == "__main__":
    main()
