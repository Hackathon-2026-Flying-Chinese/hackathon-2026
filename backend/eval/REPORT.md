# Can Viva write a fair check from any pull request? A small eval

October 2026. Twenty real, merged pull requests from seven open-source projects, two rounds of the generator, and a
review of every pack by a separate Claude Opus 5.5 agent briefed to act as a sceptical senior engineer. No person
reviewed the packs, and the model calls were answered by agents, not the API (see Limits). A third round, on the real
API with sixteen fresh pull requests, is reported in [Round 3: the real API](#round-3-the-real-api).

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

## Round 3: the real API

October 2026. Sixteen fresh pull requests through `taskgen.build_pack()` with real model calls, plus four stress cases
kept outside the numbers, judged with the round-2 brief and one added field. The pass bars below were written down
before the run and were not changed afterwards.

### In short

- **The gate released nothing, and was mostly right to.** None of the 16 packs came out ready. The judges would show 3
  of them as they are (round 2: 12 of 20) and agreed with the hold on the other 13.
- **The packs were worse than in round 2 on every judged measure.** Answer keys 90 of 96 correct (round 2: 119 of 120),
  sets that give an answer away before the predictions lock 16 of 32 (6 of 40), ambiguous sets 16 of 32 (8 of 40), mean
  fairness 2.62 of 5 (3.65). This round changed four things at once (the API through a third-party relay, generation at
  medium effort, fresh pull requests, the new question 3), so the drop cannot be put down to one of them.
- **The new question 3 did not cut ambiguity.** Judges called 6 of 32 sets ambiguous in question 3 (bar: at most 2), and
  question 2 is now the most contested (9).
- **Cost and time missed their bars.** US$1.03 per pull request at the median and US$1.66 at P90 (bar: median at most
  US$0.60); 22 minutes at the median and 46 at P90 (bar: P90 at most 10 minutes). Most of the time is the relay's.
- **Real calls found three bugs in the API path**, fixed in `ai.py`: a stream cut partway was not caught, a stream that
  ended without its last event was read as an answer, and a cut-off or declined answer's tokens were not counted.

### The criteria

| | Bar | Round 3 (16 pull requests) | Met |
|---|---|---|---|
| Released packs a judge would show | at least 85% | none released | cannot be measured |
| Held packs a judge would show | at most 2 | 3 | no |
| Answer keys a judge found correct | at least 98% | 90/96 (94%) | no |
| Sets a judge called ambiguous in question 3 | at most 2 | 6 of 32 | no |
| US$ per pull request (list prices), median | at most 0.60 | 1.03 (P90 1.66) | no |
| Time per pull request, P90 | at most 10 minutes | 46 minutes (median 22) | no |
| Pull requests whose generation failed | at most 1 | 0 | yes |

### How this round differs from round 2

| | Round 2 | Round 3 |
|---|---|---|
| Model calls | answered by agents | the Anthropic API through the user's third-party relay, with `ai.ask_model`'s production parameters (streaming, server-side fallback, structured output) |
| Generation and repair effort | high | medium. The relay drops a call that sends nothing for about two minutes, and at high effort generation thinks longer than that before it writes: the first smoke test was cut at 140 s. Production still defaults to high |
| Solver and probe `max_tokens` | 8,000 | 16,000, timeout 300 s: 8,000 cut off 2 of the smoke test's 6 answers mid-thought |
| Pull requests | 14 + 6 | 16, merged August to October 2026: 11 Python, 3 TypeScript, 2 Go; half from the earlier seven repositories, half from netbox, InvenTree, paperless-ngx and authentik. Each slot took the latest merged candidate that met the written criteria (risky behaviour, tests in the pull request, at most 1,500 diff lines) |
| Question 3 | "Which test backs up your answer?" | "Which of these tests tries the case in question 1?", with every listed test an option |
| Judges | `judge.js`, one Opus 5.5 agent per pack at high effort | the same brief, plus `ambiguous_item` per set |

### What held the packs back

The 16 pull requests were held for these reasons (most for several): the leak probe answered question 1 from the
question side alone (12), a blind solver disagreed with a key (11), a harness failed or printed another answer (5),
the retake was too close to set 1 (4), a leak phrase (2), and the pull request text read as an injection (2).

1. **Rules and test names give question 1 away.** In the final packs the leak probe was right and sure on question 1 in
   15 of 32 sets (round 2: 1 of 40), and the judges found 16 of 32 sets leaky. Question 3 now lists every test of the
   set, and real test names often name the scenario and its outcome (`test_patch_without_name_still_updates`,
   `test_webhook_empty_captures`, `test_deactivated_sender_or_creator`). With a rule that states the property, that is
   enough. Retakes written by Viva invent test names that do the same.
2. **Repair stopped working.** 2 of 14 repairs passed the checks (round 2: 10 of 11). Most kept the leak, and a test
   name from the pull request cannot be renamed.
3. **Two false injection flags.** Both paperless-ngx pull requests carry the project's template, whose HTML comments
   give instructions to the contributor; the model flagged them as an attempt to steer the check, which holds the pack
   and skips the repair.

The gate held 3 packs the judges would show: pretix#6498 (the probe answered set 1 from the rule and a test name; the
judge saw the same leak but would still show it), gitea#39399 (a blind solver disagreed on set 1's requirement; the
judge found the key right) and InvenTree#12927 (the probe on set 2, a harness with a syntax error, and a solver
disagreement).

The six wrong keys were all in held packs: django-oscar#4624 set 2, question 3 (the keyed test's order line has no
options, so strictly none of the tests tries the case); documenso#3277 set 2, question 2 (the code shown leaves out the
schema line that decides, and the function meets the stated rule); netbox#23347 set 1, question 2 (non-numeric values
for `__empty` are ignored, not rejected with a 400, which the pull request's own test confirms); netbox#23301 set 2,
questions 2 and 3 (the variant does what the rule says, and a listed test tries exactly the case); paperless-ngx#14189
set 1, question 2 (the lock can expire while a run still holds an account, so the rule is not guaranteed). Three of the
six are question 2.

### Cost and time

Prices are Anthropic's list prices (Opus 5.5: US$4 per million input tokens, US$20 output, US$0.20 cache reads),
applied to the token counts the relay returned. The relay bills its own way: it reserves credit per call from
`max_tokens`, and the account ran out at about US$19 of list-price use, which stopped the last three stress cases. The
user's relay bill is the real figure.

| | Median | P90 | Max | Total (16) |
|---|---|---|---|---|
| US$ per pull request | 1.03 | 1.66 | 2.17 | 17.42 |
| Minutes per pull request | 22 | 46 | 64 | |
| Model calls per pull request | 8 | 10 | 10 | 128 |

Generation (22 calls, US$7.74) and repair (14, US$6.28) are 80% of the cost; the probe (57, US$1.95) and the solver
(35, US$1.45) the rest. Of the 36 generation and repair calls, 10 came back with exactly 31,999 output tokens (the
limit is 32,000) and a complete answer, all 8 whose stop reason was recorded saying `end_turn`; 6 more ended with no
stop reason and the answer cut short. One smoke-test solver reported 15,999 against a 16,000 limit. Either generation at
medium effort often runs into the 32,000-token limit (an answer is about 20,000 characters, some 5,500 tokens, so a
call at the limit thought for about 26,000) and the relay hides the `max_tokens` stop reason, or the relay misreports
the counts. This round cannot tell which.

The times are the relay's more than the model's. It streamed at roughly 30 to 110 tokens a second, generation calls
took a median of 570 s and up to 1,236 s, and a probe that wrote 294 tokens took 308 s. They say little about the API
used directly.

### The API path

What happened on the round's 150 model calls (core, stress and the first smoke test):

| Event | Calls | Handled |
|---|---|---|
| Stream closed partway (`httpx2.RemoteProtocolError`, smoke test, high effort, 140 s) | 1 | The SDK does not wrap it, so it escaped `ai.ask_model` and would have failed a check with no reason given. Now a network error |
| Stream ended without its last event (no stop reason, the text cut short) | 6 | It was parsed as an answer and failed as unusable JSON. Now a network error. Four were retried once and then answered; django-oscar#4624's generation ended this way twice and was answered on a third attempt, one more than planned, because the run was restarted with the fix |
| Answer cut off at `max_tokens` 8,000 (solver, probe) | 2 | Tokens are now counted for cut-off and declined answers. Limit raised to 16,000 and the two calls asked again |
| Empty, non-JSON body with no tokens, within seconds | 5 | Recorded as unusable, not retried |
| Non-streamed call timed out twice at 300 s | 2 | Retried once, then answered |
| Relay out of credit (403) | 7 | The three stress cases below |

The server-side fallback beta was accepted, streaming worked, and every answered call came from `claude-opus-5-5`. The
relay forwards no `ping` events and returned empty thinking with `display: "summarized"`, so nothing on Viva's side
keeps a long, silent call alive through it.

### Stress cases (outside the numbers)

- pretix#6448, no tests in the pull request: held, because the generator named tests that do not exist (7 checks). The
  judge would not show it either. US$1.09, 23 minutes.
- mealie#8200, 2,369 diff lines in Python, TypeScript and Vue: held (code not in the diff, code too long, no harness).
  The relay refused its repair (out of credit), so this is the first draft's check. US$0.45.
- FastGPT#7890, Chinese title and description: the generation read it and produced a pack; the relay then refused the
  probe, repair and solver calls (out of credit). Not judged.
- gitea#39719, a refactor with no behaviour change: the relay refused the generation (out of credit), so the skip path
  and its cost were not measured.

### Limits

- The relay is not Anthropic's API. It drops silent calls, hides stop reasons, reports usage oddly (input counted as
  cache writes on some calls), and its speed set the times. Every cost is a list-price estimate from its counts.
- Generation ran at medium effort, not production's high. The quality and cost at high were not measured.
- The generator, the probe, the solver and the judges are all Claude Opus 5.5, so their errors may correlate.
- Sixteen pull requests, one generation each (django-oscar#4624 three attempts), each pack judged once.
- Two changes landed during the round: the solver limit before the main run, and the stop-reason fix after the first
  pull request. The smoke test's two cut-off calls were asked again at the new limit.

### What it means

On this evidence Viva is not ready for a pilot: none of the quality bars was met. Round 3 also mixes four changes, so
it does not say which one did the damage. Before another round:

1. Question 3 and the test list: hide or neutralise test names that state the scenario's outcome, or stop listing every
   test as an option.
2. Find out why repair stopped fixing what the checks name.
3. Stop the injection check from flagging a pull request template's own instructions.
4. Run on the Anthropic API directly (or a relay without the two-minute limit) at production effort, and raise the
   generation `max_tokens` if calls keep ending at the limit, so quality can be told apart from the relay and the
   effort.

### Per pull request

| Pull request | Kind | Concept | Gate | Judge | Keys | US$ | Minutes |
|---|---|---|---|---|---|---|---|
| django-oscar/django-oscar#4624 | core | other | held | no | 5/6 | 1.40 | 64 |
| saleor/saleor#19891 | core | concurrency | held | no | 6/6 | 1.36 | 30 |
| pretix/pretix#6498 | core | empty-values | held | ship | 6/6 | 1.00 | 24 |
| mealie-recipes/mealie#8298 | core | input-validation | held | no | 6/6 | 0.66 | 9 |
| zulip/zulip#40226 | core | access-control | held | no | 6/6 | 0.64 | 3 |
| documenso/documenso#3326 | core | input-validation | held | no | 6/6 | 1.23 | 27 |
| documenso/documenso#3277 | core | access-control | held | no | 5/6 | 0.82 | 15 |
| go-gitea/gitea#39399 | core | access-control | held | ship | 6/6 | 1.66 | 41 |
| netbox-community/netbox#23347 | core | input-validation | held | no | 5/6 | 0.86 | 8 |
| netbox-community/netbox#23301 | core | time-zones | held | no | 4/6 | 1.03 | 43 |
| inventree/InvenTree#12927 | core | money-rounding | held | ship | 6/6 | 2.17 | 46 |
| inventree/InvenTree#12689 | core | access-control | held | no | 6/6 | 1.03 | 26 |
| paperless-ngx/paperless-ngx#14189 | core | concurrency | held | no | 5/6 | 0.69 | 20 |
| paperless-ngx/paperless-ngx#14065 | core | caching | held | no | 6/6 | 0.55 | 10 |
| goauthentik/authentik#26682 | core | authentication | held | no | 6/6 | 1.08 | 19 |
| goauthentik/authentik#26420 | core | caching | held | no | 6/6 | 1.25 | 19 |
| pretix/pretix#6448 | no-tests | concurrency | held | no | 6/6 | 1.09 | 23 |
| mealie-recipes/mealie#8200 | large | authentication | held | not judged | - | 0.45 | 2 |
| labring/FastGPT#7890 | non-english | access-control | held | not judged | - | 0.16 | 1 |
| go-gitea/gitea#39719 | docs-or-refactor | - | failed | not judged | - | 0.00 | 0 |

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
# round 3 on the real API (credentials in the environment; each PR is generated once, US$30 budget by default):
EVAL_LIVE=1 EVAL_PRS=prs_round3.json EVAL_ROUND=round3 EVAL_ONLY=<slug> uv run python eval/run.py step   # one PR
EVAL_LIVE=1 EVAL_PRS=prs_round3.json EVAL_ROUND=round3 uv run python eval/run.py step                    # all of them
# the round-1 baseline on the held-out set:
EVAL_TASKGEN=eval/protocol/taskgen_round1.py EVAL_SET=holdout EVAL_ROUND=round1 uv run python eval/run.py step
```

With `ANTHROPIC_API_KEY` set, `uv run python -m viva.taskgen generate --repo owner/name --pr N` makes the real calls for
one pull request. The cache, the recorded calls and the judgements are in `eval/cache/` and `eval/runs/` (not committed:
they hold other projects' code). `eval/report.py` reads all three rounds.
