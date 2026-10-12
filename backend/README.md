# Viva server

FastAPI and SQLite. It signs people in, serves the pages in `../frontend`, keeps the answer key and the scoring, runs
the viva (with Claude when a key is set), transcribes spoken answers, runs the code in a sandbox, and connects to
GitHub as an App: a "Viva" check on every pull request that links its author to the interview for that change.

```bash
cd backend
uv sync --extra stt          # without --extra stt the server runs, without speech-to-text
VIVA_DEMO=1 uv run uvicorn viva.app:app --port 8792
uv run pytest -q             # the tests never call the model; the audio and docker tests skip when those are missing
```

## Modules

| File | Job |
|---|---|
| `viva/app.py` | Routes, the sign-in dependency, the cross-site write guard, and wiring for the GitHub App |
| `viva/auth.py` | Sign-in with GitHub (OAuth), and a plain sign-in by GitHub login in demo or dev mode. The cookie is a random token; the database keeps its SHA-256 |
| `viva/engine.py` | The interview rules, views and scoring. Every session belongs to one person and reads one task pack; the concept level is per person and per concept |
| `viva/store.py` | SQLite: sessions, users and logins, task packs, sandbox runs, reviewer tokens, recordings |
| `viva/ai.py` | The model calls: the follow-up question, the rubric assessment, and the structured calls task generation makes |
| `viva/taskgen.py` | Task generation from a pull request's diff, with the checks that decide whether a pack reaches a learner |
| `viva/concepts.json` | The concepts a pack is filed under, with their lowest risk, so levels compare across pull requests |
| `viva/sandbox.py` | Runs a task's harness against its code in a locked-down container |
| `viva/stt.py` | Speech-to-text with faster-whisper, on the server |
| `viva/github.py` | The GitHub App: webhook, check runs, diff and whole files at the head commit, novelty from the author's history |

## Environment

| Variable | What it does |
|---|---|
| `VIVA_DATA` | Where the database and the recordings live (`backend/data` by default) |
| `VIVA_DEMO=1` | Presenter controls, stand-in answers, the reviewer link on the learner page, and the plain sign-in. Off for real use |
| `VIVA_DEV_LOGIN=1` | The plain sign-in without demo mode, for local use only |
| `VIVA_PUBLIC_URL` | This server's public address: the OAuth callback and the links in GitHub checks |
| `ANTHROPIC_API_KEY` | The live viva and task generation. Without it the viva is simulated, labelled so, and generation fails cleanly |
| `VIVA_MODEL` | The viva's model (`claude-sonnet-5-5`) |
| `VIVA_GEN_MODEL`, `VIVA_GEN_EFFORT` | Task generation (`claude-opus-5-5`, `high`) |
| `VIVA_SOLVE_MODEL` | The blind solver that checks a generated pack (`claude-opus-5-5`) |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | Sign-in with GitHub. The GitHub App's own client id and secret work |
| `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` or `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_WEBHOOK_SECRET` | The GitHub App. All three turn it on |
| `VIVA_PUSH_WAIT` | Seconds a push waits before Viva reads it, so a burst of pushes is read once (`90`; `0` reads it at once) |
| `GITHUB_API`, `GITHUB_WEB` | For GitHub Enterprise (`https://api.github.com`, `https://github.com` by default) |
| `VIVA_SANDBOX` | `docker` (default when the daemon answers and `python:3.12-slim` is present), `local` (a plain subprocess, not isolation: development only), `off` |
| `VIVA_STT` | `off` turns speech-to-text off; on by default when faster-whisper is installed |
| `VIVA_WHISPER_MODEL`, `VIVA_WHISPER_DEVICE`, `VIVA_STT_LANGUAGE` | `base`, `cpu`, `en` (`auto` detects the language) |

## Sign-in

Real use signs in with GitHub, so the person taking a check is the GitHub author of the pull request: a generated check
can only be taken by that login (anyone may take the sample). Register an OAuth callback of
`$VIVA_PUBLIC_URL/api/auth/github/callback`. Writes are refused when the browser says they come from another site; the
webhook is the one exception, and it is signed.

## The GitHub App

1. Create the app from the manifest: `uv run python -c "import json; from viva.github import manifest; print(json.dumps(manifest('https://viva.example')))"` gives the settings (permissions: checks write, pull requests and contents read; events: pull request, check run; webhook `$VIVA_PUBLIC_URL/api/github/webhook`). Or enter the same values by hand on GitHub's "New GitHub App" page.
2. On the app's page, generate a private key and set a webhook secret. Set `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH` and `GITHUB_WEBHOOK_SECRET`, and `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` from the same page for sign-in.
3. Install the app on a repository. Opening a pull request creates the check "Preparing questions from your diff"; a background job reads the diff, the changed files whole at the head commit, and the author's history on them, generates the pack, and the check then links to the interview, or says plainly why there is none. The interview moves the same check along: a second attempt is available, waiting for a senior, passed with the senior's correction. A later push that leaves the checked code and its tests unchanged (`taskgen.still_holds()`) carries the check over to the new commit, with its pack and wherever the author got to, and makes no model call; a push that changes them prepares a new check. Re-run always prepares a new one.

## Task generation

`taskgen.build_pack()` turns a diff into a pack of two sets (the first attempt and the retake). No pack reaches a learner
on the model's word alone: the code checks the answer (set 1's code is copied verbatim from the diff, the tests it names
exist, nothing the learner reads first gives an answer away, the rubric patterns are safe and tell a strong answer from a
vague one); each Python set's harness must print the keyed answer in the sandbox, and must not when the function bodies
are gutted; and a blind solver that sees only the question side must reach the same three answers. A pack that fails any
of these is kept as `needs_review` with the reasons, and its check says Viva will not ask.

```bash
uv run python -m viva.taskgen generate --repo owner/name --pr 123 --out pack.json    # needs ANTHROPIC_API_KEY
uv run python -m viva.taskgen prompt --pr pr.json --diff d.patch --out DIR           # the prompt, no model call
uv run python -m viva.taskgen check --pr pr.json --diff d.patch --raw gen.json --solve s1.json s2.json
```

`eval/` holds a small eval on real pull requests through the same code path (`eval/run.py`, results in `eval/REPORT.md`).

## Sandbox and speech

The sandbox needs Docker and the `python:3.12-slim` image (`docker pull python:3.12-slim`); runs have no network, a
read-only file system, capped memory, CPU and processes, and a time limit. Only Python code runs; other languages are
checked by the blind solver alone. Speech-to-text loads the faster-whisper model on first use (the `base` model is about
140 MB, downloaded once); recordings never leave the server.
