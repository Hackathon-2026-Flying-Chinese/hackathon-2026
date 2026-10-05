"""How stable the live viva is: the follow-up and the rubric assessment, run several times on the same answers.

The cases in viva_cases.json are answers to the two sample tasks of tasks.json, each rubric point labelled by hand. The
calls go through ai._followup and ai._grade, the production path, with the same bodies the engine builds; only the
answers are fixed. The model's raw answer is kept too, so a point the model credited but whose quote failed the check
in code shows up.

    uv run python eval/viva_stability.py        needs ANTHROPIC_API_KEY (and ANTHROPIC_BASE_URL for a relay)
                                                -> runs/viva/<run>/calls.json and summary.json, and a table
VIVA_GRADE_RUNS (default 5), VIVA_FOLLOWUP_RUNS (default 3) and VIVA_WORKERS (default 4) set the size; VIVA_RUN names
the run (default latest); VIVA_CASES picks the case file (default viva_cases.json; viva_cases_hard.json
holds borderline answers).
"""
import collections
import json
import os
import pathlib
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from viva import ai  # noqa: E402

OUT = HERE / "runs" / "viva" / os.environ.get("VIVA_RUN", "latest")
TASKS = json.loads((HERE.parent.parent / "frontend" / "data" / "tasks.json").read_text())
CASES = json.loads((HERE / os.environ.get("VIVA_CASES", "viva_cases.json")).read_text())
GRADE_RUNS = int(os.environ.get("VIVA_GRADE_RUNS", 5))
FOLLOWUP_RUNS = int(os.environ.get("VIVA_FOLLOWUP_RUNS", 3))
WORKERS = int(os.environ.get("VIVA_WORKERS", 4))

raw = threading.local()
_ask = ai.ask_model


def ask_and_keep(*a, **k):
    out = _ask(*a, **k)
    raw.out = out[0]
    return out


ai.ask_model = ask_and_keep  # _followup and _grade look it up at call time


def turns_of(case):
    st = TASKS["sets"][case["set"]]
    asked = [st["questions"]["implementation"]["text"], st["questions"]["rationale"]["text"], st["probes"]["specific"]["text"]]
    return [{"turn": i + 1, "question": asked[i], "answer": a} for i, a in enumerate(case["answers"])]


def bodies(case):
    st = TASKS["sets"][case["set"]]
    t, turns = st["task"], turns_of(case)
    follow = {"file": t["file"], "code": t["code"], "rule": t["rule"], "turns": turns[:2], "leak_terms": t["leak"]}
    grade = {"file": t["file"], "code": t["code"], "rule": t["rule"], "facts": t["facts"],
             "rubric": [{"id": p["id"], "text": p["text"]} for p in st["rubric"]], "turns": turns}
    return follow, grade


def call(kind, case, n):
    follow, grade = bodies(case)
    raw.out = None
    started = time.monotonic()
    try:
        got = ai._followup(follow) if kind == "followup" else ai._grade(grade)
        err = None
    except Exception as e:  # recorded, not raised: a failed call is a result too
        got, err = None, f"{type(e).__name__}: {e}"
    return {"kind": kind, "case": case["id"], "run": n, "seconds": round(time.monotonic() - started, 1),
            "got": got, "raw": raw.out, "error": err}


def summarise(calls):
    rows = []
    for case in CASES:
        grades = [c for c in calls if c["case"] == case["id"] and c["kind"] == "grade" and c["got"]]
        follows = [c for c in calls if c["case"] == case["id"] and c["kind"] == "followup" and c["got"]]
        points = {}
        for pid, want in case["gold"].items():
            met = [next(p["met"] for p in g["got"]["points"] if p["id"] == pid) for g in grades]
            raw_met = [next((p["met"] for p in g["raw"]["points"] if p["id"] == pid), False) for g in grades]
            points[pid] = {"gold": want, "met": sum(met), "runs": len(met), "stable": len(set(met)) <= 1,
                           "right": sum(m == want for m in met), "quote_dropped": sum(r and not m for r, m in zip(raw_met, met)),
                           "borderline": pid in case.get("borderline", [])}
        rows.append({
            "case": case["id"], "points": points,
            "scores": [sum(p["met"] for p in g["got"]["points"]) for g in grades],
            "injection": [g["got"]["injection_attempt"] for g in grades], "injection_gold": case.get("injection", False),
            "follow_up": [f["got"]["needs_follow_up"] for f in follows], "follow_up_gold": case["follow_up"],
            "questions": [f["got"].get("question") or f["got"].get("filter_reason") for f in follows if f["got"]["needs_follow_up"]],
            "errors": [c["error"] for c in calls if c["case"] == case["id"] and c["error"]],
        })
    cells = [p for r in rows for p in r["points"].values()]
    clear = [p for p in cells if not p["borderline"]]
    seconds = {k: sorted(c["seconds"] for c in calls if c["kind"] == k and c["got"]) for k in ("grade", "followup")}
    total = {
        "model": next((c["got"]["model"] for c in calls if c["got"]), None),
        "calls": len(calls), "failed": sum(1 for c in calls if c["error"]),
        "point_cells": len(cells), "stable_cells": sum(p["stable"] for p in cells),
        "point_runs": sum(p["runs"] for p in cells), "right_point_runs": sum(p["right"] for p in cells),
        "stable_borderline_cells": [sum(p["stable"] for p in cells if p["borderline"]), sum(p["borderline"] for p in cells)],
        "right_point_runs_clear": [sum(p["right"] for p in clear), sum(p["runs"] for p in clear)],
        "stable_scores": sum(len(set(r["scores"])) <= 1 for r in rows), "cases": len(rows),
        "quote_dropped": sum(p["quote_dropped"] for p in cells),
        "follow_up_filtered": dict(collections.Counter(
            c["got"]["filter_reason"] for c in calls if c["kind"] == "followup" and c["got"] and c["got"].get("filter_reason"))),
        "follow_up_asked": sum(1 for c in calls if c["kind"] == "followup" and c["got"] and c["got"]["needs_follow_up"]),
        "follow_up_stable": sum(len(set(r["follow_up"])) <= 1 for r in rows),
        "follow_up_right": [sum(f == r["follow_up_gold"] for r in rows for f in r["follow_up"]), sum(len(r["follow_up"]) for r in rows)],
        "median_seconds": {k: v[len(v) // 2] if v else None for k, v in seconds.items()},
    }
    return {"total": total, "cases": rows}


def table(s):
    print(f"\n{'case':24} {'points (met/runs, gold)':44} {'scores':16} {'follow-up':10} inj")
    for r in s["cases"]:
        pts = "  ".join(f"{pid}:{p['met']}/{p['runs']}{'Y' if p['gold'] else 'N'}{'' if p['stable'] else '*'}" for pid, p in r["points"].items())
        fu = "".join("Y" if f else "N" for f in r["follow_up"]) + f" ({'Y' if r['follow_up_gold'] else 'N'})"
        print(f"{r['case']:24} {pts:44} {','.join(map(str, r['scores'])):16} {fu:10} {sum(r['injection'])}/{len(r['injection'])}")
        for e in r["errors"]:
            print(f"    error: {e[:160]}")
    print("\n* = the point flipped between runs.  Y/N after a point = the hand label.")
    print(json.dumps(s["total"], indent=1))


def main():
    if ai.client is None:
        sys.exit("no credentials: set ANTHROPIC_API_KEY (and ANTHROPIC_BASE_URL for a relay)")
    jobs = [("grade", c, n) for c in CASES for n in range(GRADE_RUNS)]
    jobs += [("followup", c, n) for c in CASES for n in range(FOLLOWUP_RUNS)]
    print(f"{len(jobs)} calls to {ai.MODEL}, {WORKERS} at a time")
    with ThreadPoolExecutor(WORKERS) as pool:
        calls = list(pool.map(lambda j: call(*j), jobs))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "calls.json").write_text(json.dumps(calls, indent=1, ensure_ascii=False))
    s = summarise(calls)
    (OUT / "summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False))
    table(s)


if __name__ == "__main__":
    main()
