"""A small eval of task generation on real pull requests, through the production code path.

taskgen.build_pack() runs exactly as on the server: the diff is parsed and widened with the files' whole text at the
head commit, the prompt is built, the answer is checked in code, each Python harness runs in the sandbox (and again
against gutted code), the leak probe and the blind solver answer, and one repair round follows a failed check. Only the
model is swapped: every model call is recorded with its exact prompt, answered elsewhere (the API, or an agent given
the same request and nothing else), and replayed. A run that meets a call with no answer yet stops and lists it.

    uv run python eval/run.py fetch                    PRs in prs.json and holdout.json -> cache/<slug>/
    EVAL_ROUND=round2 uv run python eval/run.py step   run every PR as far as the answers go
                                                       -> runs/<round>/<slug>/pending.json (calls to answer) or result.json
    EVAL_ROUND=round2 uv run python eval/run.py pending     the pending calls, as workflow args
    EVAL_ROUND=round2 uv run python eval/run.py save <out>  answers from a workflow result -> answers.json
    EVAL_ROUND=round2 uv run python eval/run.py summary     -> runs/<round>/summary.json, and a table
EVAL_TASKGEN=<path to an older taskgen.py> runs that version instead (a baseline on the same PRs); EVAL_SET=dev or
holdout limits the PRs.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from viva import ai  # noqa: E402

CACHE = HERE / "cache"
RUNS = HERE / "runs" / os.environ.get("EVAL_ROUND", "round1")


def load_taskgen():
    path = os.environ.get("EVAL_TASKGEN")
    if not path:
        from viva import taskgen
        return taskgen
    spec = importlib.util.spec_from_file_location("viva.taskgen_baseline", path)  # in the package, for its relative imports
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tg = load_taskgen()


class Stop(Exception):
    pass


def refs():
    out = [{**r, "set": "dev"} for r in json.loads((HERE / "prs.json").read_text())]
    if (HERE / "holdout.json").exists():
        out += [{**r, "set": "holdout"} for r in json.loads((HERE / "holdout.json").read_text())]
    only = os.environ.get("EVAL_SET")
    return [r for r in out if not only or r["set"] == only]


def slug(ref):
    return f"{ref['repo'].replace('/', '__')}__{ref['number']}"


def load(ref):
    d = CACHE / slug(ref)
    return json.loads((d / "pr.json").read_text()), (d / "diff.patch").read_text()


def fetch():
    token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip() or None
    for ref in refs():
        d = CACHE / slug(ref)
        if (d / "pr.json").exists():
            continue
        pr, diff = tg.fetch_pr(ref["repo"], ref["number"], token=token)
        d.mkdir(parents=True, exist_ok=True)
        (d / "pr.json").write_text(json.dumps(pr, indent=1))
        (d / "diff.patch").write_text(diff)
        print(slug(ref), f"{len(diff.splitlines())} diff lines, whole files: {', '.join(pr['contents']) or 'none'}")


class Replay:
    """The model, from recorded answers. A missing generation or repair stops the run; a missing solve or probe gets a
    stand-in so the run can list the other calls it can already make. A solve or probe prompt depends only on the pack,
    so each is recorded; a repair after a stand-in is not, since what it would fix depends on the real answers."""

    def __init__(self, answers):
        self.answers, self.pending, self.stood_in = answers, [], False

    def __call__(self, system, user, schema, effort, **opts):
        kind = ("repair" if "<failed_checks>" in user else "gen") if schema is not tg.SOLVE_SCHEMA else (
            "probe" if system is getattr(tg, "PROBE_SYSTEM", None) else "solve")
        cid = hashlib.sha1(f"{kind}\0{system}\0{user}".encode()).hexdigest()[:16]
        if cid in self.answers:
            return self.answers[cid], f"agent:{kind}"
        if not self.stood_in or kind in ("probe", "solve"):
            self.pending.append({"id": cid, "kind": kind, "system": system, "user": user, "schema": schema, "effort": effort})
        if kind in ("gen", "repair"):
            raise Stop()
        self.stood_in = True
        return {"behaviour": "", "requirement": "", "evidence": "", "confidence": "low", "why": "stand-in"}, "stand-in"


def step():
    for ref in refs():
        d = RUNS / slug(ref)
        d.mkdir(parents=True, exist_ok=True)
        answers = json.loads((d / "answers.json").read_text()) if (d / "answers.json").exists() else {}
        pr, diff = load(ref)
        replay = Replay(answers)
        try:
            out = tg.build_pack(pr, diff, call_model=replay)
        except Stop:
            out = None
        (d / "pending.json").unlink(missing_ok=True)
        if replay.pending:
            (d / "pending.json").write_text(json.dumps(replay.pending, indent=1))
            print(f"{slug(ref):45} pending {', '.join(p['kind'] for p in replay.pending)}")
        else:
            (d / "result.json").write_text(json.dumps(out, indent=1, default=str))
            print(f"{slug(ref):45} {out['status']:13} {out['reason'] or ''}"[:220])


def pending():
    items = []
    for ref in refs():
        f = RUNS / slug(ref) / "pending.json"
        if f.exists():
            items += [{"slug": slug(ref), "id": p["id"], "kind": p["kind"]} for p in json.loads(f.read_text())]
    print(json.dumps(items))


def save(path):
    data = json.loads(pathlib.Path(path).read_text())
    found = data.get("result", data) if isinstance(data, dict) else data
    by = {}
    for item in found or []:
        if item and item.get("answer") is not None and item.get("round", RUNS.name) == RUNS.name:
            by.setdefault(item["slug"], {})[item["id"]] = item["answer"]
    for s, got in by.items():
        f = RUNS / s / "answers.json"
        answers = json.loads(f.read_text()) if f.exists() else {}
        answers.update(got)
        f.write_text(json.dumps(answers, indent=1, ensure_ascii=False))
        print(s, f"{len(got)} answer(s)")


def summary():
    rows = []
    for ref in refs():
        f = RUNS / slug(ref) / "result.json"
        if not f.exists():
            continue
        out = json.loads(f.read_text())
        rep, pack = out["report"], out.get("pack") or {}
        rows.append({
            "pr": f"{ref['repo']}#{ref['number']}", "slug": slug(ref), "set": ref["set"], "why": ref["why"], "status": out["status"],
            "concept": (pack.get("concept") or {}).get("key"), "risk": (pack.get("scoring") or {}).get("r"),
            "origins": [s["task"].get("origin") for s in pack.get("sets") or []],
            "errors": sorted({i["code"] for i in rep.get("issues", []) if i["severity"] == "error"}),
            "runs": [{"set": r["set"], "needed": r.get("needed"), "ok": (r.get("result") or {}).get("ok"), "agree": r.get("agree"),
                      "ignores_code": r.get("ignores_code")} for r in rep.get("runs", [])],
            "probe": [{"set": p["set"], "gives_away": p.get("gives_away")} for p in rep.get("probe") or []],
            "repair": {k: (rep.get("repair") or {}).get(k) for k in ("failed", "fixed", "error")} if rep.get("repair") else None,
            "solve": [{"set": s["set"], "agree": s.get("agree"), "mismatch": s.get("mismatch")} for s in rep.get("solve") or []],
            "reasons": rep.get("reasons", []),
        })
    (RUNS / "summary.json").write_text(json.dumps(rows, indent=1))
    for r in rows:
        runs = " ".join(f"s{x['set']}:{'-' if x['ok'] is None else 'ok' if x['ok'] and x['agree'] else 'X'}" for x in r["runs"])
        solve = " ".join(f"s{x['set']}:{'ok' if x['agree'] else 'X'}" for x in r["solve"])
        rp = "" if not r["repair"] else f" repair:{'fixed' if r['repair']['fixed'] else 'no'}"
        print(f"{r['set'][:3]} {r['pr']:32} {r['status']:13} run[{runs}] solve[{solve}]{rp} {','.join(r['errors'])}")
    for part in ("dev", "holdout"):
        sub = [r for r in rows if r["set"] == part]
        if sub:
            print(f"{part}: {len(sub)} PRs: " + ", ".join(f"{k} {sum(r['status'] == k for r in sub)}"
                                                         for k in ("ready", "needs_review", "failed", "skipped")))


if __name__ == "__main__":
    ai.client = None  # never the API from here: the answers come from files
    {"fetch": fetch, "step": step, "pending": pending, "save": save, "summary": summary}[sys.argv[1]](*sys.argv[2:])
