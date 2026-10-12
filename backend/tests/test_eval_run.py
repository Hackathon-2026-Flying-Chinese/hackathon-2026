"""eval/run.py live mode, with a stand-in for ai.ask_model: no network."""
import importlib.util
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from viva import ai
from test_taskgen import FIX, local_sandbox, model  # noqa: F401 (local_sandbox is a fixture)

spec = importlib.util.spec_from_file_location("eval_run", Path(__file__).resolve().parents[1] / "eval" / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

SLUGS = ["acme__shop__1", "acme__shop__2"]


@pytest.fixture
def ev(tmp_path, monkeypatch, local_sandbox):  # noqa: F811
    """Two PRs (both the sample pull request) in a temporary eval folder, run live against a counted fake model that
    reports tokens the way ai.ask_model does."""
    for s in SLUGS:
        (tmp_path / "cache" / s).mkdir(parents=True)
        shutil.copy(FIX / "sample_pr.json", tmp_path / "cache" / s / "pr.json")
        shutil.copy(FIX / "sample_pr.diff", tmp_path / "cache" / s / "diff.patch")
    (tmp_path / "prs_t.json").write_text(json.dumps([{"repo": "acme/shop", "number": n, "kind": "core", "why": "x"} for n in (1, 2)]))
    monkeypatch.setattr(run, "HERE", tmp_path)
    monkeypatch.setattr(run, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(run, "RUNS", tmp_path / "runs" / "round3")
    monkeypatch.setattr(run, "LIVE", True)
    monkeypatch.setenv("EVAL_PRS", "prs_t.json")
    fake, state = model(), SimpleNamespace(calls=[], fail=[], runs=tmp_path / "runs" / "round3")

    def ask_model(system, user, schema, effort, **kw):
        state.calls.append(kw)
        if state.fail:
            raise ai.ModelUnavailable(state.fail.pop(0))
        got, _ = fake(system, user, schema, effort, **kw)
        ai._count(kw["model"], SimpleNamespace(input_tokens=100_000, output_tokens=10_000), 1.0)
        return got, kw["model"]
    monkeypatch.setattr(ai, "ask_model", ask_model)
    return state


def lines(path):
    return [json.loads(x) for x in path.read_text().splitlines()]


def test_a_call_with_no_answer_goes_to_the_api_and_is_recorded(ev):
    run.step()
    d = ev.runs / SLUGS[0]
    out, logged, answers = json.loads((d / "result.json").read_text()), lines(d / "calls.jsonl"), json.loads((d / "answers.json").read_text())
    assert out["status"] == "ready" and len(answers) == len(logged) == len(ev.calls) // 2 == 5  # gen, 2 probes, 2 solves
    gen = logged[0]
    assert gen["kind"] == "gen" and gen["streamed"] and gen["max_tokens"] == 32000 and gen["model"] == "claude-opus-5-5"
    assert gen["cost_usd"] == pytest.approx(0.6)  # 100k in x $4 + 10k out x $20, per million
    assert "user" not in gen and "system" not in gen
    live = json.loads((d / "live.json").read_text())
    assert live["status"] == "ready" and live["usage"]["claude-opus-5-5"]["calls"] == 5


def test_a_recorded_call_is_not_made_again(ev, monkeypatch):
    run.step()
    made = len(ev.calls)
    for s in SLUGS:
        (ev.runs / s / "result.json").unlink()
    run.step()  # live again: every answer is on file
    assert len(ev.calls) == made
    monkeypatch.setattr(run, "LIVE", False)
    run.step()
    assert len(ev.calls) == made and not list(ev.runs.glob("*/pending.json"))


def test_a_pr_with_a_result_is_not_generated_again(ev, capsys):
    run.step()
    made = len(ev.calls)
    run.step()
    assert len(ev.calls) == made and capsys.readouterr().out.count("done already") == 2


def test_the_run_stops_before_a_pr_that_could_pass_the_budget(ev, monkeypatch):
    monkeypatch.setattr(run, "BUDGET_USD", 5.0)  # one PR costs 5 x 0.6 = 3.0; 3.0 + 3.0 > 5
    with pytest.raises(SystemExit, match="Stopped before acme__shop__2"):
        run.step()
    assert (ev.runs / SLUGS[0] / "result.json").exists() and not (ev.runs / SLUGS[1]).exists()


def test_eval_only_runs_one_pr(ev, monkeypatch):
    monkeypatch.setenv("EVAL_ONLY", SLUGS[1])
    run.step()
    assert [p.name for p in ev.runs.iterdir()] == [SLUGS[1]]


def test_a_transient_failure_is_retried_once_and_a_lasting_one_is_recorded(ev, monkeypatch):
    monkeypatch.setenv("EVAL_ONLY", SLUGS[0])
    ev.fail[:] = ["network error"]
    run.step()
    d = ev.runs / SLUGS[0]
    logged = lines(d / "calls.jsonl")
    assert [(x["attempt"], x["error"]) for x in logged[:2]] == [(1, "network error"), (2, None)]
    assert json.loads((d / "result.json").read_text())["status"] == "ready"

    monkeypatch.setenv("EVAL_ONLY", SLUGS[1])
    ev.fail[:] = ["API error 529: overloaded", "API error 529: overloaded"]
    run.step()
    d = ev.runs / SLUGS[1]
    out = json.loads((d / "result.json").read_text())
    assert out["status"] == "failed" and len(lines(d / "calls.jsonl")) == 2
    made = len(ev.calls)
    (d / "result.json").unlink()
    run.step()  # the recorded failure replays: the PR fails the same way, with no new call
    assert json.loads((d / "result.json").read_text())["status"] == "failed" and len(ev.calls) == made
