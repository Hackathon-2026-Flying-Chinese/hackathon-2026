# Can Viva write a fair check from any pull request? A small eval

October 2026. Twenty real, merged pull requests from seven open-source projects, two rounds of the generator, and a
review of every pack by a separate Claude Opus 5.5 agent briefed to act as a sceptical senior engineer. No person
reviewed the packs, and the model calls were answered by agents, not the API (see Limits).

## In short

- **The answer keys held up.** The judges marked 239 of 240 keys correct, re-running the Python ones. The one wrong key
  (django-oscar#4616, question 3) was in a pack the gate held back, because the blind solver disagreed with it. In 7
  more round-2 sets the judges called the key defensible but contestable, and the TypeScript and Go keys were checked
  by reading only.
- **The code really runs.** Every Python set (29 per round) had a harness that ran in the Docker sandbox and printed
  the keyed answer. The gutted-code check (the same harness against the code with its function bodies removed) ran on
  26 of 29 sets in round 1 and 25 of 29 in round 2, and never caught a harness printing the keyed answer from gutted
  code; in 23 and 19 sets a gutted run printed a different answer.
- **The first gate threw away most of the good packs.** The judges would have shown 9 of the 20 round-1 packs, but
  the gate released only 2: its checks had false positives, and test notes gave answers away.
- **The second round releases most of what is good, and little that is not.** The judges would show 12 of the 20
  round-2 packs. The gate would release 13; the judges would show 12 of those as they are (in 2 of them one set still
  gives its answer away) and found no pack they would show that the gate held back. Most of the change from 2 to 12
  is the gate: under the round-2 code checks (the probe was not run on them), 7 of the 9 good round-1 packs would also
  pass. Whether the packs themselves
  got better (9 to 12 good) cannot be told from one generation per round.
- **Round 2 traded leaks for ambiguity.** Sets that gave an answer away before the predictions lock fell from 16 to 6;
  sets the judges called ambiguous rose from 2 to 8, 7 of them in the third question ("which test backs up your
  answer"). That question needs a redesign.

Recommendation: the generator is promising and the gate is what makes it safe. Before a pilot, run a third round on
the current code (round 2 plus the hold on unsure solvers, below) with the real API, on fresh pull requests, and pilot
if the gate's releases stay as good. Expect about 1 in 13 released packs to be one a reviewer would reject (12 of 13
here; the 95% interval is roughly 67% to 99%). Every pass in Viva already goes to a senior, who is the backstop for
those.

## What was measured, and how

`eval/run.py` runs `taskgen.build_pack()` as the server does when the GitHub App sees a pull request: the diff is parsed
and widened with the changed files' whole text at the head commit, the prompt is built, the answer is checked in code,
each Python harness runs in the sandbox (and again against gutted code), the leak probe and the blind solver answer,
and one repair round follows a failed check. Only the model is swapped: every model call is recorded with its exact
prompt, answered elsewhere, and replayed. The prompts are the production ones byte for byte; the model's conditions
are not (see Limits).

| | |
|---|---|
| Pull requests | 14 for development (`prs.json`) and 6 held out (`holdout.json`), merged, 36 to 395 diff lines, all with tests. Python (django-oscar, saleor, pretix, mealie, zulip), TypeScript (documenso), Go (gitea). Concepts: access control, money and rounding, authentication, input validation, time, empty values, ordering, concurrency |
| Generator, probe, solver | Claude Opus 5.5 (high effort for generation and repair, medium for the probe and the solver, as in production). The calls were answered by agents running that model inside an agent harness, told to read only the recorded request and use no other tool. This was instructed, not enforced, and their context and decoding differ from an API call |
| Gate | The checks in `taskgen.py`. A pack is **ready** (the gate would release it to the PR author) only when every check passes; otherwise it is held as `needs_review` and the GitHub check says Viva will not ask |
| Judges | One Claude Opus 5.5 agent per pack at high effort (`protocol/workflows/judge.js`). It reads the diff, the whole changed files and the pack, verifies each key itself (running Python reproductions), scores grounding, transfer, rubric and fairness, and says whether it would show the pack as it is. All 40 packs were judged with the same brief |
| Round 1 | The generator as first built (`protocol/taskgen_round1.py`, checked to reproduce the round-1 prompts byte for byte). The 14 development packs, plus a baseline run of the same code on the 6 held-out pull requests, made after round 2's changes and used only as a baseline |
| Round 2 | The generator after the changes below, on all 20 |

### Limits

- The model calls were answered by agents, not the API, so every number here may differ with the real API. The API
  path (`ai.ask_model`, streaming, timeouts, failures) was not exercised.
- The generator, the probe, the solver and the judges are all Claude Opus 5.5, so their errors may correlate. The
  judges are not people, and "would show" is a judge's call, not a measured learner outcome.
- Twenty pull requests is a small sample, and six held-out ones is very small. The held-out set was also used to check
  the later rule on unsure solvers, so for that rule it is no longer unseen.
- Each round generated one pack per pull request, so a single pull request can come out better or worse by chance:
  four were good in round 1 and not in round 2, seven the other way round.
- Each pack was judged once. Re-judging the 14 round-1 development packs with a corrected brief moved mean fairness
  from 3.57 to 3.43 and mean transfer from 3.43 to 3.14, and flipped one decision (saleor#19463), so differences in
  the mean scores below are within judge noise.
- Cost and time per pull request were not measured.

## Results

| | Round 1, dev (14) | Round 1, held out (6) | Round 2, dev (14) | Round 2, held out (6) |
|---|---|---|---|---|
| Packs the gate would release (ready) | 3 | 0 | 9 | 4 |
| ... of which the judges would show | 2 | 0 | 8 | 4 |
| Packs the judges would show, held back by the gate | 4 | 3 | 0 | 0 |
| All packs the judges would show | 6 | 3 | 8 | 4 |
| Answer keys correct (judges) | 84/84 | 36/36 | 84/84 | 35/36 |
| Sets with an answer given away before the predictions lock | 10/28 | 6/12 | 5/28 | 1/12 |
| Sets the judges called ambiguous | 1/28 | 1/12 | 6/28 | 2/12 |
| Python sets whose harness ran and printed the keyed answer | 19/19 | 10/10 | 19/19 | 10/10 |
| Mean fairness score, 1 to 5 | 3.43 | 3.50 | 3.64 | 3.67 |
| Mean transfer of the retake, 1 to 5 | 3.14 | 2.50 | 3.36 | 3.00 |

In round 2 the judges agreed with 12 of the gate's 13 releases (8 of 9 on the development pull requests, 4 of 4 held
out). On the six held-out pull requests the round-1 code released none of the 3 packs the judges would show; the
round-2 code released 4, all of which they would show. Six pull requests are too few to show that the generator
itself improved.

## What round 1 taught us

On the 14 development pull requests the judges agreed with every key, so the errors were elsewhere:

1. **Test notes and rules gave answers away** (10 of 28 sets). Notes like "gets INVALID error, stays unconfirmed" or
   "expects 422" are shown before the predictions lock and state the outcome of the behaviour question. The leak check
   only compared the model's own list of leak phrases, so a reworded giveaway passed. Rules that spell out the
   mechanism ("rounded half up to four decimal places") did the same.
2. **The code checks blocked good packs.** 16 of the 27 errors were "test not in the diff", and every one of those
   tests is in the diff: 12 are named after a block's second `@@` (git names the function the block sits in there, and
   the check ignored that line) and 4 are parametrized cases (`test_x[case]`). A retake written as a variant of the
   same function was refused too. The held-out baseline, run later, showed the same pattern (5 of its 13 errors).
3. **Weak discrimination.** Both requirement questions were often an obvious "yes", the "none" option of the evidence
   question explained itself ("None of them has lines that sum to exactly half a cent"), and set 1 sometimes sat on a
   line the pull request only renamed.
4. **Variant retakes looked like the author's code**: a retake written by Viva carried the real file path and
   invented tests, with nothing to say it was not from the pull request.

## What changed in round 2

| Change | Where |
|---|---|
| A test note says what the test sets up, never what it expects; leak phrases are only answer phrases | generation prompt |
| A leak probe: a solver who never sees the code answers question 1 from the rest. Right and sure means the question side gives it away (`answer_without_code`) | `taskgen.leak_probe` |
| One repair round: a failed check or run goes back to the model with the reasons, and the whole pack is checked again | `taskgen.build_pack` |
| Tests named after a block's `@@`, parametrized ids, variant retakes of the same function, and blocks from inside a long function are accepted | `taskgen.validate` |
| A leak phrase in any test note (including the keyed test's, a warning before) blocks the pack. One in the rule or question 1 blocks it unless the phrase also appears in the code shown (new exemption). One in a viva question, asked after the predictions lock, is a warning | `taskgen.validate` |
| The "none" option reads the same in every pack | `taskgen.NONE_TEXT` |
| Changed test files are read whole too, so notes describe what the test really does | `taskgen.wanted_contents`, `github.contents` |
| Prefer one set whose code meets the rule and one that breaks it; set 1 on a line that changes behaviour | generation prompt |

Also changed, but not measured by this eval: a retake written by Viva is labelled on the page ("Written for this
retake", not from the pull request; `engine.task_view`, `js/interview.js`), and the sample check's own note that gave
the retake's answer away ("...: 404.") was reworded (`frontend/data/tasks.json`). The judges' brief described the label,
so round-1 packs were judged as if labelled too.

In round 2 the leak probe flagged 8 first drafts as giving question 1 away. The repair round got 10 of the 11 packs it
was given past the checks that had failed; 6 of those 10 ended as releases the judges would show, 3 were then held by
the blind solver, and 1 was the release the judges rejected.

Found after round 2 and applied in code, but checked only on the recorded round-2 answers: that rejected release
(pretix#6201) had a blind solver that agreed with the key at **low** confidence, saying the visible code did not settle
the answer. Holding back packs with an unsure solver would have removed that release and nothing else here.
`build_pack` now does so. The solver is told to answer "low" whenever it is guessing, so on new pull requests this rule
may hold back more than it did here; the third round should measure it.

## What is still weak

- **The evidence question.** "Which test backs up your answer" mixes "covers this case" with "proves this answer", and
  with setup-only notes the learner has less to go on. In round 2 it caused 7 of the 8 sets the judges called ambiguous
  (the eighth turns on whether a zero-width space counts as blank), 5 of the 7 packs held, and the only wrong key.
  Options: ask "which test would fail if the code returned *X*", show the test's body instead of a note, or drop the
  question for pull requests without a test of the scenario.
- **Rules that hand over the mechanism** (django-oscar#4455) still slip past the probe when it is only fairly sure.
  Lowering the probe's bar to "fairly sure" would also stop packs the judges liked, so this needs a better question,
  not a lower bar.
- **Retakes transfer only moderately** (3.0 to 3.4 of 5): variants often flip one line of set 1's code.
- **Only Python runs.** TypeScript and Go keys rest on the blind solver; a Node and a Go sandbox image would remove
  that dependency.
- **Not tested yet:** the real API with production parameters, cost and time per pull request, very large or
  multi-language pull requests, pull requests without tests, non-English descriptions.

## Per pull request

"Gate" is what the generator decided; "judge" is whether the reviewer would show that round's pack as it is. Each round
generated its own packs, so a row compares two different packs for the same pull request.

| Pull request | Set | Concept (round 2) | Round 1 gate | Round 1 judge | Round 2 gate | Round 2 judge | Round 2 keys |
|---|---|---|---|---|---|---|---|
| django-oscar/django-oscar#4623 | dev | access-control | held | ship | ready | ship | 6/6 |
| django-oscar/django-oscar#4455 | dev | money-rounding | held | no | held | no | 6/6 |
| saleor/saleor#19463 | dev | authentication | held | no | ready | ship | 6/6 |
| saleor/saleor#19662 | dev | empty-values | held | no | ready | ship | 6/6 |
| saleor/saleor#19258 | dev | empty-values | held | ship | ready | ship | 6/6 |
| pretix/pretix#6201 | dev | input-validation | held | no | ready | no | 6/6 |
| pretix/pretix#6532 | dev | time-zones | held | no | ready | ship | 6/6 |
| mealie-recipes/mealie#8295 | dev | input-validation | ready | no | held | no | 6/6 |
| mealie-recipes/mealie#8379 | dev | time-zones | ready | ship | held | no | 6/6 |
| zulip/zulip#40233 | dev | access-control | held | no | ready | ship | 6/6 |
| documenso/documenso#3166 | dev | input-validation | ready | ship | ready | ship | 6/6 |
| documenso/documenso#3153 | dev | other | held | ship | ready | ship | 6/6 |
| go-gitea/gitea#39508 | dev | pagination | held | ship | held | no | 6/6 |
| go-gitea/gitea#39402 | dev | access-control | held | no | held | no | 6/6 |
| saleor/saleor#19527 | held out | access-control | held | ship | ready | ship | 6/6 |
| pretix/pretix#6575 | held out | input-validation | held | no | ready | ship | 6/6 |
| django-oscar/django-oscar#4616 | held out | other | held | ship | held | no | 5/6 |
| saleor/saleor#19821 | held out | concurrency | held | no | ready | ship | 6/6 |
| django-oscar/django-oscar#4594 | held out | concurrency | held | ship | held | no | 6/6 |
| go-gitea/gitea#39521 | held out | access-control | held | no | ready | ship | 6/6 |

End to end, the round-2 pack for django-oscar#4623 was loaded into a server and taken in the browser as its author
(sign-in, predictions, viva with a follow-up, results): the generated harness ran in the Docker sandbox in 233 ms and
printed the keyed answer.

## Reproduce

```bash
cd backend
uv run python eval/run.py fetch                       # PR metadata, diff and whole files into eval/cache (needs gh)
EVAL_ROUND=round3 uv run python eval/run.py step      # runs as far as the recorded answers go; lists the calls to answer
EVAL_ROUND=round3 uv run python eval/run.py pending   # those calls
# answer them (here: protocol/workflows/answer.js, a Claude Code workflow), then:
EVAL_ROUND=round3 uv run python eval/run.py save <workflow result.json>
EVAL_ROUND=round3 uv run python eval/run.py step      # repeat pending, answer, save, step until nothing is pending
EVAL_ROUND=round3 uv run python eval/run.py summary
# judge each runs/round3/<slug>/result.json (protocol/workflows/judge.js) into runs/round3/<slug>/judge.json, then:
uv run python eval/report.py                          # the numbers in this report
# the round-1 baseline on the held-out set:
EVAL_TASKGEN=eval/protocol/taskgen_round1.py EVAL_SET=holdout EVAL_ROUND=round1 uv run python eval/run.py step
```

With `ANTHROPIC_API_KEY` set, `uv run python -m viva.taskgen generate --repo owner/name --pr N` makes the real calls for
one pull request. The cache, the recorded calls and the judgements are in `eval/cache/` and `eval/runs/` (not committed:
they hold other projects' code). `eval/report.py` reads round 1 and round 2; edit its round list for round 3.
