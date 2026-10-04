"""The numbers behind eval/REPORT.md, from runs/<round>/<slug>/result.json and judge.json.

    uv run python eval/report.py            -> runs/metrics.json, and the tables on stdout
"""
import json
import pathlib
import statistics

HERE = pathlib.Path(__file__).resolve().parent
RUNS = HERE / "runs"


def refs():
    out = [{**r, "set": "dev"} for r in json.loads((HERE / "prs.json").read_text())]
    out += [{**r, "set": "holdout"} for r in json.loads((HERE / "holdout.json").read_text())]
    return out


def slug(r):
    return f"{r['repo'].replace('/', '__')}__{r['number']}"


def rows(rnd):
    out = []
    for r in refs():
        d = RUNS / rnd / slug(r)
        if not (d / "result.json").exists():
            continue
        res = json.loads((d / "result.json").read_text())
        judge = json.loads((d / "judge.json").read_text()) if (d / "judge.json").exists() else None
        rep = res.get("report") or {}
        out.append({"pr": f"{r['repo']}#{r['number']}", "set": r["set"], "status": res["status"], "report": rep,
                    "pack": res.get("pack") or {}, "judge": judge})
    return out


def metrics(rs):
    judged = [r for r in rs if r["judge"]]
    keys = [k for r in judged for s in r["judge"]["sets"]
            for k in (s["behaviour_key_correct"], s["requirement_key_correct"], s["evidence_key_correct"])]
    ready = [r for r in rs if r["status"] == "ready"]
    tp = sum(r["status"] == "ready" and r["judge"]["would_ship"] for r in judged)
    fp = sum(r["status"] == "ready" and not r["judge"]["would_ship"] for r in judged)
    fn = sum(r["status"] != "ready" and r["judge"]["would_ship"] for r in judged)
    tn = sum(r["status"] != "ready" and not r["judge"]["would_ship"] for r in judged)
    sets = [s for r in judged for s in r["judge"]["sets"]]
    runs = [x for r in rs for x in r["report"].get("runs", []) if x.get("needed")]
    mean = lambda k: round(statistics.mean(r["judge"][k] for r in judged), 2) if judged else None
    repairs = [r["report"]["repair"] for r in rs if r["report"].get("repair")]
    probes = [p for r in rs for p in r["report"].get("probe") or []]
    return {
        "prs": len(rs), "ready": len(ready), "judged": len(judged),
        "keys_correct": sum(keys), "keys_total": len(keys),
        "would_ship": sum(r["judge"]["would_ship"] for r in judged),
        "gate": {"ready_and_ship": tp, "ready_not_ship": fp, "held_but_ship": fn, "held_not_ship": tn,
                 "precision": round(tp / (tp + fp), 2) if tp + fp else None},
        "leaky_sets": sum(s["leak"] for s in sets), "ambiguous_sets": sum(s["ambiguous"] for s in sets), "sets": len(sets),
        "mean": {k: mean(k) for k in ("grounding", "transfer", "rubric_quality", "fair_and_useful")},
        "question_quality": round(statistics.mean(s["question_quality"] for s in sets), 2) if sets else None,
        "python_runs": {"needed": len(runs), "ok_and_agree": sum(bool((x.get("result") or {}).get("ok")) and bool(x.get("agree")) for x in runs),
                        "ignores_code": sum(bool(x.get("ignores_code")) for x in runs)},
        "repair": {"tried": len(repairs), "fixed": sum(bool(x.get("fixed")) for x in repairs)},
        "probe": {"calls": len(probes), "gave_away": sum(bool(p.get("gives_away")) for p in probes)},
        "reasons": sorted({i["code"] for r in rs for i in r["report"].get("issues", []) if i["severity"] == "error"}),
    }


def main():
    out = {}
    for rnd in ("round1", "round2"):
        rs = rows(rnd)
        out[rnd] = {part: metrics([r for r in rs if r["set"] == part]) for part in ("dev", "holdout")}
        out[rnd]["per_pr"] = [{"pr": r["pr"], "set": r["set"], "status": r["status"],
                               "concept": (r["pack"].get("concept") or {}).get("key"),
                               "would_ship": r["judge"]["would_ship"] if r["judge"] else None,
                               "gate_call": r["judge"]["gate_call"] if r["judge"] else None,
                               "fair": r["judge"]["fair_and_useful"] if r["judge"] else None,
                               "keys": [f"{int(s['behaviour_key_correct'])}{int(s['requirement_key_correct'])}{int(s['evidence_key_correct'])}"
                                        for s in r["judge"]["sets"]] if r["judge"] else None,
                               "leaks": [s["leak"] for s in r["judge"]["sets"]] if r["judge"] else None,
                               "reasons": r["report"].get("reasons", [])} for r in rs]
    (RUNS / "metrics.json").write_text(json.dumps(out, indent=1))
    for rnd in ("round1", "round2"):
        for part in ("dev", "holdout"):
            m = out[rnd][part]
            print(f"{rnd} {part:8} prs {m['prs']:2} ready {m['ready']:2} | judged {m['judged']:2} keys {m['keys_correct']}/{m['keys_total']} "
                  f"ship {m['would_ship']} | gate tp {m['gate']['ready_and_ship']} fp {m['gate']['ready_not_ship']} "
                  f"fn {m['gate']['held_but_ship']} tn {m['gate']['held_not_ship']} prec {m['gate']['precision']} | "
                  f"leaky {m['leaky_sets']}/{m['sets']} amb {m['ambiguous_sets']} | fair {m['mean']['fair_and_useful']} "
                  f"grd {m['mean']['grounding']} trn {m['mean']['transfer']} qq {m['question_quality']} | "
                  f"py {m['python_runs']} repair {m['repair']} probe {m['probe']}")


if __name__ == "__main__":
    main()
