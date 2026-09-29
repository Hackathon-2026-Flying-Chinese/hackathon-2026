# Viva · learning validation slice

Airwallex PS1 **Getting Good** — executable scoring, persistent cross-task review,
and a runnable controlled pilot. No external model, payment API or microphone needed.

**Current documentation lives in the [GitHub Wiki](https://github.com/Hackathon-2026-Flying-Chinese/hackathon-2026/wiki).**
The old `plan` branch is historical; do not sync it over the Wiki.

## Run locally

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required.

```sh
uv sync --frozen
uv run uvicorn viva.app:app --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765>. Choose **Try the learning loop**. Predict the current
code's output, evaluate the independent contract, choose evidence, then save a
reflection and answer a different artifact. SQLite preserves the gap and evidence
across reloads/restarts. Demo closure shows immediate transfer only, not retention.
Only curated trusted fixtures are executed; this is **not** an arbitrary-code sandbox.

## Prepare a human pilot

```sh
uv run python -m viva.cli init-study --participants 12
```

Give consenting participants the returned study code. Run 8 or 12 participants
(multiples of 4 balance A/B groups and two task forms). Keep each session link
private for the participant's next-day return. Do not reuse the same browser profile
for different participants without leaving the previous session.

The default flow is baseline (4 min limit), practice (6 min fixed window),
two unseen transfer tasks (4 min each), and retention tasks after at least 24 hours.
AI is permitted during practice in both groups; short assessment checkpoints use
the same supplied references and calculator without live AI help. Deviations are
recorded. Written rationales await blinded human review; objective scores do not
measure expertise or authorize merging code.

```sh
uv run python -m viva.cli export-blind STUDY_CODE --out data/review
uv run python -m viva.cli report STUDY_CODE
uv run python -m viva.cli report STUDY_CODE --reviews data/review/blind-review.csv
```

The facilitator shares only `blind-review.csv` with assessors, not the key or report.
Rationale rubric: 0 = unsupported/wrong, 1 = relevant rule without a valid causal
link, 2 = correct rule linked to behavior and relevant evidence. Assessor enters
`reasoning_score`, a pseudonymous `assessor`, and `review_seconds`; do not reveal the
group until scoring is complete. The report keeps objective and human scores separate.

Both arms receive the same code, contract, test choices, reference explanation,
and time. A inspects them freely and writes a normal review note; B commits a
prediction before feedback and records a reflection. The comparison tests the
structured workflow, not an intentionally careless control group.

Raw answers, allocation, session links and reports stay in ignored `data/`.
Use anonymous identifiers only; delete within 7 days of the pilot. Participants
can delete their session in the UI. Do not publish data, expose this local app on
the public internet, or interpret synthetic QA as human learning evidence.

## Verify

```sh
uv run python -m unittest discover -s tests -v
uv run python -m scripts.verify_pilot
node --check viva/static/app.js
```

See the Wiki's **Learning Validation** page for protocol, evidence, limitations,
and the current implementation status. No human pilot outcomes have been collected.
