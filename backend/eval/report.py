"""The numbers behind eval/REPORT.md, from runs/<round>/<slug>/result.json and judge.json, and for a live round
calls.jsonl and live.json (see run.py).

    uv run python eval/report.py            -> runs/metrics.json, and the tables on stdout
"""
import json
import math
import pathlib
import statistics

HERE = pathlib.Path(__file__).resolve().parent
RUNS = HERE / "runs"
ROUNDS = ("round1", "round2", "round3")
PR_LISTS = {"round3": "prs_round3.json"}  # earlier rounds: prs.json (dev) and holdout.json
ITEMS = ("behaviour", "requirement", "evidence")


def refs(rnd):
    if rnd in PR_LISTS:  # set: "core", or "stress" for the pull requests outside the main numbers
        return [{**r, "set": "core" if r["kind"] == "core" else "stress"} for r in json.loads((HERE / PR_LISTS[rnd]).read_text())]
    out = [{**r, "set": "dev"} for r in json.loads((HERE / "prs.json").read_text())]
    out += [{**r, "set": "holdout"} for r in json.loads((HERE / "holdout.json").read_text())]
    return out


def slug(r):
    return f"{r['repo'].replace('/', '__')}__{r['number']}"


def rows(rnd):
    out = []
    for r in refs(rnd):
        d = RUNS / rnd / slug(r)
        if not (d / "result.json").exists():
            continue
        res = json.loads((d / "result.json").read_text())
        judge = json.loads((d / "judge.json").read_text()) if (d / "judge.json").exists() else None
        rep = res.get("report") or {}
        calls = [json.loads(x) for x in (d / "calls.jsonl").read_text().splitlines() if x.strip()] if (d / "calls.jsonl").exists() else []
        live = json.loads((d / "live.json").read_text()) if (d / "live.json").exists() else None
        out.append({"pr": f"{r['repo']}#{r['number']}", "set": r["set"], "kind": r.get("kind"), "why": r["why"],
                    "status": res["status"], "report": rep, "pack": res.get("pack") or {}, "judge": judge,
                    "calls": calls, "live": live, "cost_usd": round(sum(c["cost_usd"] for c in calls), 4)})
    return out


def p90(xs):
    """Nearest rank: the smallest value with at least 90% of the values at or below it."""
    xs = sorted(xs)
    return xs[math.ceil(0.9 * len(xs)) - 1] if xs else None


def spread(xs, digits=4):
    return {"n": len(xs), "median": round(statistics.median(xs), digits), "p90": round(p90(xs), digits),
            "max": round(max(xs), digits), "total": round(sum(xs), digits)} if xs else None


def money_and_time(rs):
    """What the live calls cost (US$ at list prices) and how long each pull request took, from calls.jsonl and live.json."""
    live = [r for r in rs if r["live"]]
    by_kind = {}
    for r in live:
        for c in r["calls"]:
            k = by_kind.setdefault(c["kind"], {"calls": 0, "failed": 0, "cost_usd": 0.0, "seconds": [], "input_tokens": 0, "output_tokens": 0})
            k["calls"] += 1
            k["failed"] += bool(c["error"])
            k["cost_usd"] = round(k["cost_usd"] + c["cost_usd"], 4)
            k["seconds"].append(c["seconds"])
            for u in c["usage"].values():
                k["input_tokens"] += u["input_tokens"]
                k["output_tokens"] += u["output_tokens"]
    for k in by_kind.values():
        k["seconds"] = spread(k["seconds"], 1)
    return {
        "prs": len(live),
        "cost_usd": spread([r["cost_usd"] for r in live]),
        "duration_s": spread([r["live"]["duration_ms"] / 1000 for r in live], 1),
        "calls_per_pr": spread([len(r["calls"]) for r in live], 1),
        "by_kind": by_kind,
        "failed_calls": [{"pr": r["pr"], **{k: c[k] for k in ("kind", "attempt", "seconds", "error")}}
                         for r in live for c in r["calls"] if c["error"]],
        "warnings": sorted({w for r in live for c in r["calls"] for w in c["warnings"]}),
        "models": sorted({m for r in live for c in r["calls"] for m in c["usage"]}),
    }


def criteria(rs, m, mt):
    """Section 1 of the round-3 plan, each bar set before the run: (what, value, bar, met). met is None when not measured."""
    judged = [r for r in rs if r["judge"]]
    released = m["gate"]["ready_and_ship"] + m["gate"]["ready_not_ship"]
    held_ship = sum(r["status"] == "needs_review" and r["judge"]["would_ship"] for r in judged)
    q3 = (m["ambiguous_by_item"] or {}).get("evidence")
    cost, dur = mt["cost_usd"], mt["duration_s"]
    failed = sum(r["status"] == "failed" for r in rs)

    def row(what, value, bar, met):
        return {"what": what, "value": value, "bar": bar, "met": met}
    return [
        row("released packs a judge would show", f"{m['gate']['ready_and_ship']}/{released}" if released else "none released",
            ">= 85%", m["gate"]["ready_and_ship"] / released >= 0.85 if released else None),
        row("held packs (needs_review) a judge would show", held_ship if judged else None, "<= 2", held_ship <= 2 if judged else None),
        row("answer keys a judge found correct", f"{m['keys_correct']}/{m['keys_total']}" if m["keys_total"] else None,
            ">= 98%", m["keys_correct"] / m["keys_total"] >= 0.98 if m["keys_total"] else None),
        row("sets a judge called ambiguous in question 3", q3, "<= 2", q3 <= 2 if q3 is not None else None),
        row("US$ per pull request, median (P90)", f"{cost['median']:.2f} ({cost['p90']:.2f})" if cost else None,
            "median <= 0.60", cost["median"] <= 0.60 if cost else None),
        row("seconds per pull request, P90 (median)", f"{dur['p90']:.0f} ({dur['median']:.0f})" if dur else None,
            "P90 <= 600", dur["p90"] <= 600 if dur else None),
        row("pull requests whose generation failed", failed, "<= 1", failed <= 1),
    ]


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
        "ambiguous_by_item": {k: sum(k in s["ambiguous_item"] for s in sets) for k in ITEMS}
        if sets and all("ambiguous_item" in s for s in sets) else None,
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
    for rnd in ROUNDS:
        if rnd in PR_LISTS and not (HERE / PR_LISTS[rnd]).exists():
            continue
        rs = rows(rnd)
        parts = list(dict.fromkeys(r["set"] for r in refs(rnd)))
        out[rnd] = {part: metrics([r for r in rs if r["set"] == part]) for part in parts}
        if any(r["live"] for r in rs):
            for part in parts:
                out[rnd][part]["money_and_time"] = money_and_time([r for r in rs if r["set"] == part])
            core = [r for r in rs if r["set"] == "core"]
            out[rnd]["criteria"] = criteria(core, out[rnd]["core"], out[rnd]["core"]["money_and_time"])
        out[rnd]["per_pr"] = [{"pr": r["pr"], "set": r["set"], "kind": r["kind"], "status": r["status"],
                               "cost_usd": r["cost_usd"] if r["live"] else None,
                               "seconds": round(r["live"]["duration_ms"] / 1000, 1) if r["live"] else None,
                               "calls": len(r["calls"]),
                               "ambiguous_item": [s.get("ambiguous_item") for s in r["judge"]["sets"]] if r["judge"] else None,
                               "concept": (r["pack"].get("concept") or {}).get("key"),
                               "would_ship": r["judge"]["would_ship"] if r["judge"] else None,
                               "gate_call": r["judge"]["gate_call"] if r["judge"] else None,
                               "fair": r["judge"]["fair_and_useful"] if r["judge"] else None,
                               "keys": [f"{int(s['behaviour_key_correct'])}{int(s['requirement_key_correct'])}{int(s['evidence_key_correct'])}"
                                        for s in r["judge"]["sets"]] if r["judge"] else None,
                               "leaks": [s["leak"] for s in r["judge"]["sets"]] if r["judge"] else None,
                               "reasons": r["report"].get("reasons", [])} for r in rs]
    (RUNS / "metrics.json").write_text(json.dumps(out, indent=1))
    for rnd in out:
        for part in (k for k in out[rnd] if k not in ("per_pr", "criteria")):
            m = out[rnd][part]
            print(f"{rnd} {part:8} prs {m['prs']:2} ready {m['ready']:2} | judged {m['judged']:2} keys {m['keys_correct']}/{m['keys_total']} "
                  f"ship {m['would_ship']} | gate tp {m['gate']['ready_and_ship']} fp {m['gate']['ready_not_ship']} "
                  f"fn {m['gate']['held_but_ship']} tn {m['gate']['held_not_ship']} prec {m['gate']['precision']} | "
                  f"leaky {m['leaky_sets']}/{m['sets']} amb {m['ambiguous_sets']} | fair {m['mean']['fair_and_useful']} "
                  f"grd {m['mean']['grounding']} trn {m['mean']['transfer']} qq {m['question_quality']} | "
                  f"py {m['python_runs']} repair {m['repair']} probe {m['probe']}"
                  + (f" | amb by item {m['ambiguous_by_item']}" if m["ambiguous_by_item"] else ""))
            mt = m.get("money_and_time")
            if mt and mt["prs"]:
                print(f"  live: {mt['prs']} PRs, US$ {mt['cost_usd']}, seconds {mt['duration_s']}, calls/PR {mt['calls_per_pr']}")
                for kind, k in mt["by_kind"].items():
                    print(f"    {kind:7} calls {k['calls']:3} failed {k['failed']} US$ {k['cost_usd']:.2f} "
                          f"in {k['input_tokens']} out {k['output_tokens']} seconds {k['seconds']}")
                for f in mt["failed_calls"]:
                    print(f"    failed call: {f}")
                for w in mt["warnings"]:
                    print(f"    warning: {w}")
        for c in out[rnd].get("criteria", []):
            print(f"  {'MET    ' if c['met'] else 'not met' if c['met'] is False else 'n/a    '} {c['what']}: {c['value']} (bar {c['bar']})")
        if rnd in PR_LISTS:
            for r in out[rnd]["per_pr"]:
                print(f"  {r['set']:6} {r['pr']:38} {r['status']:13} US$ {r['cost_usd']} s {r['seconds']} calls {r['calls']} "
                      f"ship {r['would_ship']} amb {r['ambiguous_item']}")


if __name__ == "__main__":
    main()
