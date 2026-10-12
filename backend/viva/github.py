"""The GitHub App: a "Viva" check on every pull request that links its author to the interview for that change.

A pull request event creates the check straight away ("Preparing questions from your diff"). A background job then
reads the diff, works out how new the change is to its author (the Novelty of Risk x Novelty x Gap) and hands both to
task generation; the check then links to the interview, or says plainly why there is none. The engine's events
(finished, decided, retake) move the same check along, so the pull request always shows where its author is.

A push is cheap: the job waits a little first (VIVA_PUSH_WAIT seconds), so a burst of pushes is read once, and when the
code an earlier check asks about is still there unchanged, the new commit carries that check over, with its pack and
wherever its author got to, and no model call. Only a push that changes the checked code prepares a new check.

Every call to GitHub goes through GitHubApp: an app JWT, installation tokens cached until shortly before they expire,
and failures raised as GitHubError. Nothing here talks to the model.

Environment:
  GITHUB_APP_ID                  the app's id
  GITHUB_APP_PRIVATE_KEY         its private key (PEM text), or GITHUB_APP_PRIVATE_KEY_PATH, a file holding it
  GITHUB_WEBHOOK_SECRET          the webhook secret; deliveries without a matching signature are refused
  GITHUB_API                     https://api.github.com by default (GitHub Enterprise: https://host/api/v3)
  VIVA_PUBLIC_URL                where Viva is served, for the check's details link (e.g. https://viva.example)
  VIVA_PUSH_WAIT                 seconds a push waits before it is read (90 by default; 0 reads it at once)
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import httpx
import jwt
from starlette.concurrency import run_in_threadpool

log = logging.getLogger("viva.github")

CHECK_NAME = "Viva"
API_VERSION = "2022-11-28"
JSON = "application/vnd.github+json"
DIFF = "application/vnd.github.diff"
RAW = "application/vnd.github.raw+json"
TIMEOUT = 15
MAX_DIFF = 1 << 20  # far more than a reviewable change; anything past it is cut and flagged
MAX_FILES = 300
MAX_BODY = 4000
CONTENT_FILES = 20  # changed source files read whole at the head commit, so generation can show a whole function
CONTENT_BYTES = 500_000
MAX_HOOK = 25 << 20  # GitHub never delivers more than 25 MB
HISTORY_PATHS = 5
NO_HISTORY = "Could not check your history on these files."
SUPERSEDED = "A newer commit is on this pull request. Viva checks that one instead."
TOO_LARGE = "This change is too large for Viva to read. Review it as usual."
PUSH_WAIT = float(os.environ.get("VIVA_PUSH_WAIT") or 90)
PR_ACTIONS = ("opened", "reopened", "synchronize", "ready_for_review")

# A changed dependency list makes a change new to anyone. A lock file alone is a refresh, not a new dependency.
MANIFEST = re.compile(r"(?:^|/)(?:package\.json|pyproject\.toml|requirements[^/]*\.txt|go\.mod|Cargo\.toml|Gemfile|pom\.xml"
                      r"|build\.gradle[^/]*|composer\.json)$")
LOCK = re.compile(r"(?:^|/)(?:package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|uv\.lock|Pipfile\.lock"
                  r"|Cargo\.lock|Gemfile\.lock|go\.sum|composer\.lock)$")
TEST = re.compile(r"(?:^|/)(?:tests?|__tests__|specs?)/|(?:^|/)(?:test_[^/]*|conftest\.py)$|_test\.[^/]+$|\.(?:test|spec)\.[^/]+$"
                  r"|(?:^|/)[^/]*Tests?\.(?:java|kt|cs|swift)$")
VENDORED = re.compile(r"(?:^|/)(?:node_modules|vendor|third_party|fixtures|testdata)/")


class GitHubError(Exception):
    def __init__(self, status, message):
        super().__init__(f"GitHub {status}: {message}")
        self.status, self.message = status, message


class TooLarge(GitHubError):
    """GitHub will not serve the diff of a change this large (over 300 files or 20,000 lines); a re-run cannot help."""


@dataclass
class Config:
    app_id: str = ""
    private_key: str = field(default="", repr=False)
    webhook_secret: str = field(default="", repr=False)
    api: str = "https://api.github.com"
    public_url: str = ""

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        key, path = env.get("GITHUB_APP_PRIVATE_KEY") or "", env.get("GITHUB_APP_PRIVATE_KEY_PATH") or ""
        if not key and path:
            try:
                key = Path(path).expanduser().read_text()
            except OSError as e:
                log.warning("cannot read GITHUB_APP_PRIVATE_KEY_PATH: %s", e)
        if "\\n" in key and "\n" not in key.strip():  # a PEM pasted into one line of an .env file
            key = key.replace("\\n", "\n")
        return cls(app_id=(env.get("GITHUB_APP_ID") or "").strip(), private_key=key.strip(),
                   webhook_secret=env.get("GITHUB_WEBHOOK_SECRET") or "",
                   api=(env.get("GITHUB_API") or "https://api.github.com").rstrip("/"),
                   public_url=(env.get("VIVA_PUBLIC_URL") or "").rstrip("/"))

    @property
    def enabled(self):
        return bool(self.app_id and self.private_key and self.webhook_secret)


def verify_signature(secret, body, header):
    """X-Hub-Signature-256: "sha256=" and the HMAC of the raw body under the webhook secret, compared in constant time."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    want = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(want.encode(), header.encode())


def message_of(r):
    try:
        data = r.json()
    except ValueError:
        data = None
    return (data.get("message") if isinstance(data, dict) else None) or r.text[:200] or r.reason_phrase


def too_large(r):
    """GitHub's answer to a diff it will not build: 406, with an error whose code is too_large."""
    try:
        data = r.json()
    except ValueError:
        return False
    errors = data.get("errors") if isinstance(data, dict) else None
    return r.status_code == 406 and isinstance(errors, list) and any(isinstance(e, dict) and e.get("code") == "too_large" for e in errors)


def name_of(f):  # a pack file {name, add, del} or a GitHub file {filename, additions, deletions}
    return f.get("name") or f.get("filename") or ""


def size_of(f):
    return (f.get("add") or f.get("additions") or 0) + (f.get("del") or f.get("deletions") or 0)


class GitHubApp:
    def __init__(self, config, http=None, clock=None):
        self.config, self.now = config, clock or time.time
        self.http = http or httpx.Client(timeout=TIMEOUT)
        self.tokens, self.lock = {}, threading.Lock()  # installation id -> (token, expires at)
        self.fetching = {}  # installation id -> the lock held while its token is fetched

    # ---------- auth ----------
    def app_jwt(self):
        t = int(self.now())  # iat a minute back, for clock drift; GitHub refuses an exp more than ten minutes ahead
        return jwt.encode({"iat": t - 60, "exp": t + 540, "iss": str(self.config.app_id)}, self.config.private_key, algorithm="RS256")

    def cached(self, inst):
        with self.lock:
            tok, exp = self.tokens.get(inst, (None, 0))
            return tok if exp - 60 > self.now() else None

    def token(self, inst):
        """An installation access token, reused until a minute before it expires. One fetch per installation at a time;
        a cached token, or another installation's, never waits on it."""
        if tok := self.cached(inst):
            return tok
        with self.lock:
            fetch = self.fetching.setdefault(inst, threading.Lock())
        with fetch:
            if tok := self.cached(inst):  # fetched while this one waited
                return tok
            data = self.request("POST", f"/app/installations/{inst}/access_tokens").json()
            tok, exp = data["token"], datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00")).timestamp()
            with self.lock:
                self.tokens[inst] = (tok, exp)
            return tok

    def headers(self, inst=None, accept=JSON):
        """inst: the installation to act as; without one, the call is made as the app itself."""
        auth = self.token(inst) if inst else self.app_jwt()
        return {"Accept": accept, "Authorization": f"Bearer {auth}", "X-GitHub-Api-Version": API_VERSION, "User-Agent": "viva"}

    def fail(self, r, inst):
        if r.status_code == 401 and inst:  # revoked or expired early: fetch a new token next time
            with self.lock:
                self.tokens.pop(inst, None)
        raise GitHubError(r.status_code, message_of(r))

    def request(self, method, path, inst=None, accept=JSON, **kw):
        headers = self.headers(inst, accept)
        try:
            r = self.http.request(method, self.config.api + path, headers=headers, timeout=TIMEOUT, **kw)
        except httpx.HTTPError as e:
            raise GitHubError(0, f"network error: {e}") from e
        if r.status_code >= 400:
            self.fail(r, inst)
        return r

    # ---------- pull requests ----------
    def pull(self, inst, repo, number):
        return self.request("GET", f"/repos/{repo}/pulls/{number}", inst).json()

    def pr_diff(self, inst, repo, number):
        """The unified diff, at most MAX_DIFF bytes: (text, truncated). A cut diff ends on a whole line. Raises TooLarge
        when GitHub will not build the diff at all."""
        headers, buf, cut = self.headers(inst, DIFF), bytearray(), False
        try:
            with self.http.stream("GET", f"{self.config.api}/repos/{repo}/pulls/{number}", headers=headers, timeout=TIMEOUT) as r:
                if r.status_code >= 400:
                    r.read()
                    if too_large(r):
                        raise TooLarge(r.status_code, message_of(r))
                    self.fail(r, inst)
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > MAX_DIFF:
                        cut = True
                        break
        except httpx.HTTPError as e:
            raise GitHubError(0, f"network error: {e}") from e
        if cut:
            buf = buf[:MAX_DIFF]
            buf = buf[: buf.rfind(b"\n") + 1] or buf
        return buf.decode("utf-8", "replace"), cut

    def read_capped(self, inst, path, accept, cap, **kw):
        """A response body of at most cap bytes: (bytes, cut). A body past the cap is not read any further."""
        headers, buf, cut = self.headers(inst, accept), bytearray(), False
        try:
            with self.http.stream("GET", self.config.api + path, headers=headers, timeout=TIMEOUT, **kw) as r:
                if r.status_code >= 400:
                    r.read()
                    self.fail(r, inst)
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > cap:
                        cut = True
                        break
        except httpx.HTTPError as e:
            raise GitHubError(0, f"network error: {e}") from e
        return bytes(buf[:cap]), cut

    def contents(self, inst, repo, sha, files):
        """{path: whole text at sha} of the source files the change modified. A diff shows 3 lines around each change, so
        a change inside a long function never shows all of it; task generation widens the diff from these (tests too, so
        a test's note can say what its whole body checks). Added files are whole in the diff already; lock files and
        anything missing or too large are left out."""
        out = {}
        for f in sorted(files, key=lambda f: bool(TEST.search(f.get("filename") or ""))):  # source files first
            name = f.get("filename") or ""
            if len(out) >= CONTENT_FILES:
                break
            if f.get("status") not in ("modified", "renamed", "changed") or LOCK.search(name):
                continue
            try:
                body, cut = self.read_capped(inst, f"/repos/{repo}/contents/{quote(name)}", RAW, CONTENT_BYTES, params={"ref": sha})
            except GitHubError as e:
                log.info("%s at %s: %s", name, sha[:7], e)
                continue
            if not cut:
                out[name] = body.decode("utf-8", "replace")
        return out

    def pr_files(self, inst, repo, number):
        files = []
        for page in range(1, MAX_FILES // 100 + 1):
            got = self.request("GET", f"/repos/{repo}/pulls/{number}/files", inst, params={"per_page": 100, "page": page}).json()
            files += got
            if len(got) < 100:
                break
        return files[:MAX_FILES]

    # ---------- check runs ----------
    def create_check(self, inst, repo, sha, payload):
        return self.request("POST", f"/repos/{repo}/check-runs", inst, json={**payload, "head_sha": sha}).json()

    def update_check(self, inst, repo, run_id, payload):
        return self.request("PATCH", f"/repos/{repo}/check-runs/{run_id}", inst, json=payload).json()

    def get_check(self, inst, repo, run_id):
        return self.request("GET", f"/repos/{repo}/check-runs/{run_id}", inst).json()

    # ---------- novelty ----------
    def novelty(self, inst, repo, author, files, before_iso):
        """How new the change is to its author, from their own commits before the pull request: (n, why). 3 for a changed
        dependency list or files they never changed, 2 when they changed some of them, 1 when they changed all of them.
        Only the most-changed non-test files are looked up (at most five calls)."""
        names = [name_of(f) for f in sorted(files, key=size_of, reverse=True) if name_of(f)]
        # A manifest among the tests, fixtures or vendored code is not the project's own dependency list.
        dep = next((n for n in names if MANIFEST.search(n) and not TEST.search(n) and not VENDORED.search(n)), None)
        if dep:
            return 3, f"You changed the dependencies in {dep.rsplit('/', 1)[-1]}."
        kept = [n for n in names if not LOCK.search(n)]
        paths = ([n for n in kept if not TEST.search(n)] or kept)[:HISTORY_PATHS]
        if not paths or not author:
            return 2, NO_HISTORY
        seen = 0
        try:
            for p in paths:
                params = {"author": author, "path": p, "per_page": 1, **({"until": before_iso} if before_iso else {})}
                seen += bool(self.request("GET", f"/repos/{repo}/commits", inst, params=params).json())
        except (GitHubError, ValueError) as e:
            log.warning("history of %s in %s: %s", author, repo, e)
            return 2, NO_HISTORY
        one = len(paths) == 1
        if seen == 0:
            return 3, "You have not changed this file before." if one else "You have not changed these files before."
        if seen == len(paths):
            return 1, "You changed this file before." if one else "You changed these files before."
        return 2, f"You changed {seen} of these {len(paths)} files before."


def pr_meta(pull, files=()):
    """A GitHub pull request as a pack's "pr", plus its description (capped) for task generation."""
    return {"repo": pull["base"]["repo"]["full_name"], "number": pull["number"], "title": pull.get("title") or "",
            "author": (pull.get("user") or {}).get("login") or "", "branch": pull["head"]["ref"], "base": pull["base"]["ref"],
            "sha": pull["head"]["sha"], "files": [{"name": f["filename"], "add": f.get("additions", 0), "del": f.get("deletions", 0)} for f in files],
            "url": pull.get("html_url") or "", "body": (pull.get("body") or "")[:MAX_BODY]}


# ---------- what the check says ----------
# One function per state. Each returns the check-run payload; a conclusion makes it completed.
def details_url(base, pr):
    if not base:
        return None
    q = {"repo": pr.get("repo"), "pr": pr.get("number"), "sha": pr.get("sha"), "title": pr.get("title"),
         "author": pr.get("author"), "branch": pr.get("branch")}
    return f"{base}/index.html?" + urlencode({k: v for k, v in q.items() if v not in (None, "")})


def check_payload(base, pr, title, summary, conclusion=None, pack_id=None, text=None):
    p = {"name": CHECK_NAME, "status": "completed" if conclusion else "in_progress", "output": {"title": title, "summary": summary}}
    if conclusion:
        p["conclusion"] = conclusion
    if url := details_url(base, pr):
        p["details_url"] = url
    if pack_id:
        p["external_id"] = str(pack_id)
    if text:
        p["output"]["text"] = text
    return p


def points_line(sc):
    parts = [f"{name} {sc[k]}" for k, name in (("r", "Risk"), ("n", "Novelty"), ("g", "Gap")) if sc.get(k) is not None]
    line = " × ".join(parts)
    if sc.get("s") is not None:
        line += f" = {sc['s']} points" if parts else f"{sc['s']} points"
    if sc.get("band"):
        line += f" ({str(sc['band']).capitalize()} check)"
    return line + "." if line else ""


def preparing(base, pr, pack_id=None):
    return check_payload(base, pr, "Preparing questions from your diff",
                         "Viva is reading this change and writing a few questions about it. This usually takes a few minutes; "
                         "after a push, a check whose code did not change carries over.", pack_id=pack_id)


def carried(run, old_sha):
    """An earlier commit's check, as it stands, for a new commit that left the checked code alone."""
    out = run.get("output") or {}
    p = {"name": CHECK_NAME, "status": "completed" if run.get("conclusion") else "in_progress",
         "output": {"title": out.get("title") or "Viva",
                    "summary": (out.get("summary") or "").rstrip()
                    + f"\n\nCarried over from {old_sha[:7]}: this push did not change the code the questions are about."}}
    if run.get("conclusion"):
        p["conclusion"] = run["conclusion"]
    if out.get("text"):
        p["output"]["text"] = out["text"]
    for k in ("details_url", "external_id"):
        if run.get(k):
            p[k] = run[k]
    return p


def ready(base, pr, pack_id=None, concept=None, scoring=None, why=None):
    lines = [f"This change is about {concept}." if concept else "This change is ready for a short viva.",
             "Read the code, lock three predictions about what it does, then answer two short questions. It takes about ten minutes."]
    if scoring and points_line(scoring):
        lines.append(points_line(scoring))
    text = "\n".join(f"- {name}: {why[k]}" for k, name in (("r", "Risk"), ("n", "Novelty"), ("g", "Gap")) if why.get(k)) if why else None
    return check_payload(base, pr, "Explain this change before it merges", "\n\n".join(lines), "action_required", pack_id, text)


def skipped(base, pr, pack_id=None, reason=None):
    return check_payload(base, pr, "No viva for this change", reason or "This change does not need a viva.", "neutral", pack_id)


def not_verified(base, pr, pack_id=None):
    return check_payload(base, pr, "No questions for this change",
                         "Viva could not verify its questions for this change, so it will not ask them. Review it as usual.",
                         "neutral", pack_id)


def failed(base, pr, pack_id=None):
    return check_payload(base, pr, "Viva could not prepare questions",
                         "Something went wrong while reading this change. Re-run this check to try again.", "neutral", pack_id)


def waiting_review(base, pr, pack_id=None, shown=True):
    summary = ("You explained this change. A senior will read your answers, then pass the check or ask for a short conversation."
               if shown else "Both attempts are done. A senior will read your answers and decide what helps next.")
    return check_payload(base, pr, "Waiting for a senior review", summary, pack_id=pack_id)


def retake(base, pr, pack_id=None):
    return check_payload(base, pr, "A second attempt is available",
                         "The first attempt did not show it yet. Try again: the same idea, in different code.", "action_required", pack_id)


def passed(base, pr, pack_id=None, note=""):
    summary = "A senior reviewed your explanation and passed this check."
    return check_payload(base, pr, "Explained and reviewed", summary + (f"\n\nTheir correction: {note}" if note else ""), "success", pack_id)


def followup(base, pr, pack_id=None, note=""):
    summary = "Talk it through with them before this merges."
    return check_payload(base, pr, "A senior asked for a short follow-up conversation",
                         summary + (f"\n\nTheir note: {note}" if note else ""), "action_required", pack_id)


# "superseded" reads as skipped, but a commit that becomes the head again (a force-push back) is prepared afresh.
PRESENTERS = {"preparing": preparing, "ready": ready, "skipped": skipped, "superseded": skipped, "not_verified": not_verified,
              "failed": failed, "waiting_review": waiting_review, "retake": retake, "passed": passed, "followup": followup}
IN_PROGRESS = ("preparing", "waiting_review")  # every other state is a completed run, which GitHub will not reopen
OUTCOME = {"ready": "ready", "needs_review": "not_verified", "failed": "failed", "skipped": "skipped"}
PREPARE_AGAIN = ("failed", "superseded")  # a pull request event for a commit in any other state leaves its check as it is
CARRY = ("ready", "waiting_review", "retake", "passed", "followup", "not_verified")  # states with a pack behind them


# ---------- the check runs Viva created ----------
CHECKS_TABLE = """CREATE TABLE IF NOT EXISTS gh_checks (id INTEGER PRIMARY KEY, repo TEXT NOT NULL COLLATE NOCASE, number INTEGER NOT NULL,
  sha TEXT NOT NULL, installation_id INTEGER NOT NULL, check_run_id INTEGER NOT NULL UNIQUE, pack_id TEXT, state TEXT NOT NULL,
  created REAL NOT NULL, updated REAL NOT NULL)"""
CHECKS_INDEX = "CREATE INDEX IF NOT EXISTS gh_checks_pr ON gh_checks (repo, number, id)"
COLS = ("repo", "number", "sha", "installation_id", "check_run_id", "pack_id", "state", "created", "updated")


class CheckStore:
    """One row per check run, so later events find the run to move along. The newest row of a PR and sha is the one
    GitHub shows."""

    def __init__(self, store):
        self.store = store
        with store.tx():
            store.conn.execute(CHECKS_TABLE)
            store.conn.execute(CHECKS_INDEX)

    def _one(self, where, args):
        with self.store.tx():
            row = self.store.conn.execute(f"SELECT {', '.join(COLS)} FROM gh_checks WHERE {where} ORDER BY id DESC LIMIT 1", args).fetchone()
        return dict(zip(COLS, row)) if row else None

    def add(self, repo, number, sha, installation_id, check_run_id, pack_id, state):
        t = time.time()
        with self.store.tx():
            self.store.conn.execute(f"INSERT INTO gh_checks ({', '.join(COLS)}) VALUES ({', '.join('?' * len(COLS))})",
                                    (repo, int(number), sha.lower(), installation_id, check_run_id, pack_id, state, t, t))

    def set(self, check_run_id, state, pack_id=None):
        with self.store.tx():
            self.store.conn.execute("UPDATE gh_checks SET state = ?, pack_id = COALESCE(?, pack_id), updated = ? WHERE check_run_id = ?",
                                    (state, pack_id, time.time(), check_run_id))

    def latest(self, repo, number, sha=None):
        """sha may be a prefix (a session keeps a short one)."""
        if sha:
            sha = sha.lower()
            return self._one("repo = ? AND number = ? AND substr(sha, 1, length(?)) = ?", (repo, int(number), sha, sha))
        return self._one("repo = ? AND number = ?", (repo, int(number)))

    def run(self, check_run_id):
        return self._one("check_run_id = ?", (check_run_id,))

    def for_pack(self, repo, number, pack_id):
        """The newest run of a pull request that shows this pack: after a push that carried the check over, the new
        commit's."""
        return self._one("repo = ? AND number = ? AND pack_id = ?", (repo, int(number), pack_id))

    def carry_source(self, repo, number, sha):
        """The newest run of another commit of this pull request that has a pack behind it."""
        marks = ", ".join("?" * len(CARRY))
        return self._one(f"repo = ? AND number = ? AND sha != ? AND pack_id IS NOT NULL AND state IN ({marks})",
                         (repo, int(number), sha.lower(), *CARRY))

    def preparing(self, before):
        """Runs still Preparing that were created before a time."""
        with self.store.tx():
            rows = self.store.conn.execute(f"SELECT {', '.join(COLS)} FROM gh_checks WHERE state = 'preparing' AND created < ? ORDER BY id",
                                           (before,)).fetchall()
        return [dict(zip(COLS, r)) for r in rows]


# ---------- the job: from a pull request to a pack ----------
def default_holds(pack, pr, diff):
    from . import taskgen  # only a server with the GitHub App reads diffs
    return taskgen.still_holds(pack, pr, diff)


def carry_over(engine, app, checks, holds, inst, meta, diff, run_id):
    """Carry an earlier commit's check over to this one when its pack still holds here. True when it did."""
    src = checks.carry_source(meta["repo"], meta["number"], meta["sha"])
    if not src:
        return False
    with engine.store.tx():
        got = engine.store.pack(src["pack_id"])
    if not got or got["status"] not in ("ready", "needs_review") or not got["pack"]:
        return False
    changed = holds(got["pack"], meta, diff)
    if changed:
        log.info("%s#%s %s: new check, %s", meta["repo"], meta["number"], meta["sha"][:7], " ".join(changed))
        return False
    payload = carried(app.get_check(src["installation_id"], src["repo"], src["check_run_id"]), src["sha"])
    # This commit's own pack row points at the pack it carries, so a link to this commit opens the same check.
    engine.packs.put(meta, "carried", None, {"from": src["pack_id"], "from_sha": src["sha"]})
    app.update_check(inst, meta["repo"], run_id, payload)
    checks.set(run_id, src["state"], src["pack_id"])
    log.info("%s#%s %s: carried over %s from %s", meta["repo"], meta["number"], meta["sha"][:7], src["state"], src["sha"][:7])
    return True


def run_job(engine, app, generate, checks, inst, pr, run_id, fresh=False, holds=default_holds):
    """Read the pull request, carry an earlier check over or ask for a pack, and finish the check. fresh (a re-run)
    always asks for a new pack. Never raises: a failure ends in a neutral check."""
    base, repo, number = app.config.public_url, pr["repo"], pr["number"]
    pack_id, stored = None, False

    def head_is_ours(pull):
        return pull["head"]["sha"].lower() == pr["sha"].lower()
    try:
        pull = app.pull(inst, repo, number)
        meta, state, reason = {**pr_meta(pull), "sha": pr["sha"]}, None, None
        # The diff and files GitHub serves are always the newest head's, so the head is read before and after them: a
        # push in between means they are not this commit's. The newer commit gets its own check.
        if not head_is_ours(pull):
            state, reason = "superseded", SUPERSEDED
        else:
            try:
                diff, cut = app.pr_diff(inst, repo, number)
            except TooLarge:
                state, reason = "skipped", TOO_LARGE
            else:
                files = app.pr_files(inst, repo, number)
                meta = {**pr_meta(pull, files), **({"diff_truncated": True} if cut else {})}
                if not head_is_ours(app.pull(inst, repo, number)):
                    state, reason = "superseded", SUPERSEDED
                else:  # read at the sha itself, so a later push cannot change them
                    meta["contents"] = app.contents(inst, repo, pr["sha"], files)
        if state:  # recorded, so the check's link says why rather than "still preparing"
            pack_id, stored = engine.packs.put(meta, "skipped", None, {"reason": reason}), True
            kw = {"reason": reason}
        elif not fresh and carry_over(engine, app, checks, holds, inst, meta, diff, run_id):
            return
        else:
            out = generate(meta, diff, app.novelty(inst, repo, meta["author"], meta["files"], pull.get("created_at"))) or {}
            status, pack, report = out.get("status"), out.get("pack"), out.get("report")
            if status not in OUTCOME:
                raise ValueError(f"task generation returned status {status!r}")
            pack_id, stored = engine.packs.put(meta, status, pack, report), True  # the store's id is the pack's id
            state, kw = OUTCOME[status], {}
            if state == "ready":
                kw = {"concept": ((pack or {}).get("concept") or {}).get("name"), "scoring": out.get("scoring"),
                      "why": ((pack or {}).get("scoring") or {}).get("why")}
            elif state == "skipped":
                kw = {"reason": out.get("reason") or (report or {}).get("reason")}
        app.update_check(inst, repo, run_id, PRESENTERS[state](base, meta, pack_id, **kw))
        checks.set(run_id, state, pack_id)
        log.info("%s#%s %s: %s", repo, number, pr["sha"][:7], state)
    except Exception as e:
        log.exception("%s#%s %s: preparing the check failed", repo, number, pr["sha"][:7])
        try:
            if not stored:
                engine.packs.put(pr, "failed", None, {"error": str(e)[:500]})
        except Exception:
            log.exception("could not mark the pack as failed")
        try:
            app.update_check(inst, repo, run_id, failed(base, pr, pack_id))
            checks.set(run_id, "failed", pack_id)
        except Exception:
            log.exception("could not mark the check as failed")


def sweep(engine, app, checks, before):
    """Fail the runs a restart left Preparing: their jobs are gone, and GitHub offers no Re-run on a run in progress."""
    for row in checks.preparing(before):
        pr = {k: row[k] for k in ("repo", "number", "sha")}
        try:
            with engine.store.tx():  # one connection for every thread
                got = engine.packs.find(row["repo"], row["number"], row["sha"])
            if got and got["status"] == "generating":
                engine.packs.put(pr, "failed", None, {"error": "Viva restarted while preparing this check."})
            app.update_check(row["installation_id"], row["repo"], row["check_run_id"], failed(app.config.public_url, pr, row["pack_id"]))
            checks.set(row["check_run_id"], "failed")
        except Exception:
            log.exception("%s#%s %s: could not fail a check left preparing", row["repo"], row["number"], row["sha"][:7])


class Deliveries:
    """Delivery ids already handled; GitHub can deliver an event twice. Bounded: the oldest are forgotten first."""

    def __init__(self, size=4096):
        self.ids, self.size, self.lock = OrderedDict(), size, threading.Lock()

    def add(self, d):
        """False when this delivery was seen before."""
        with self.lock:
            if d in self.ids:
                return False
            self.ids[d] = None
            if len(self.ids) > self.size:
                self.ids.popitem(last=False)
            return True

    def discard(self, d):  # a failed delivery can be redelivered by hand, with the same id
        with self.lock:
            self.ids.pop(d, None)


def make_router(engine, app, generate, submit=None, push_wait=None, holds=default_holds):
    """POST /api/github/webhook. generate(pr, diff, (n, why)) -> {"status", "pack", "report", "scoring"?} runs in the
    background through submit(fn, *args) (a small thread pool by default). A push waits push_wait seconds before its
    job is queued (PUSH_WAIT by default). A check a restart left Preparing (or waiting) is failed in the background
    first, so its author can re-run it."""
    router, checks, seen = APIRouter(), CheckStore(engine.store), Deliveries()
    push_wait = PUSH_WAIT if push_wait is None else push_wait
    if submit is None:
        submit = ThreadPoolExecutor(max_workers=4, thread_name_prefix="viva-github").submit
    if app and app.config.enabled:
        submit(sweep, engine, app, checks, time.time())

    def start(inst, pr, wait=0, fresh=False):
        """The Preparing check first, so the pull request shows Viva at once; then the job, after wait seconds. A push
        that lands in the meantime makes the job find a newer head and stop before it reads anything."""
        run = app.create_check(inst, pr["repo"], pr["sha"], preparing(app.config.public_url, pr))
        try:
            pid = engine.packs.put(pr, "generating")
            checks.add(pr["repo"], pr["number"], pr["sha"], inst, run["id"], pid, "preparing")
            args = (run_job, engine, app, generate, checks, inst, pr, run["id"], fresh, holds)
            if wait > 0:
                timer = threading.Timer(wait, submit, args)
                timer.daemon = True
                timer.start()
            else:
                submit(*args)
        except Exception:
            app.update_check(inst, pr["repo"], run["id"], failed(app.config.public_url, pr))  # never leave it spinning
            raise
        return 202, {"queued": True, "check_run_id": run["id"]}

    def handle(event, data):
        action, inst = data.get("action"), (data.get("installation") or {}).get("id")
        if event == "ping":
            return 200, {"pong": True}
        if event in ("installation", "installation_repositories"):
            log.info("%s %s by %s", event, action, ((data.get("installation") or {}).get("account") or {}).get("login"))
            return 200, {"ok": True}
        if event == "pull_request" and inst:
            pull = data.get("pull_request") or {}
            if action not in PR_ACTIONS:
                return 202, {"ignored": f"pull_request.{action}"}
            if pull.get("draft") and action != "ready_for_review":
                return 200, {"skipped": "draft"}
            pr = pr_meta(pull)
            # A commit Viva already checked (a reopened pull request, a force-push back) keeps its check: GitHub still
            # shows it on that commit, and preparing again would reset a reviewed pass. Re-run asks for it explicitly.
            row = checks.latest(pr["repo"], pr["number"], pr["sha"])
            if row and row["state"] not in PREPARE_AGAIN:
                return 200, {"unchanged": row["state"], "check_run_id": row["check_run_id"]}
            return start(inst, pr, wait=push_wait if action == "synchronize" else 0)
        if event == "check_run" and inst:
            run = data.get("check_run") or {}
            if action != "rerequested" or run.get("name") != CHECK_NAME:
                return 202, {"ignored": f"check_run.{action}"}
            repo, prs = data["repository"]["full_name"], run.get("pull_requests") or []
            # Pull requests from forks are not listed on the run; the row of the run says which one it was.
            number = prs[0]["number"] if prs else (checks.run(run["id"]) or {}).get("number")
            if not number:
                return 202, {"ignored": "check_run without a pull request"}
            return start(inst, {**pr_meta(app.pull(inst, repo, number)), "sha": run["head_sha"]}, fresh=True)
        return 202, {"ignored": event}

    @router.post("/api/github/webhook")
    async def webhook(request: Request):
        if not (app and app.config.enabled):
            return JSONResponse({"detail": "The GitHub App is not configured."}, status_code=503)
        # Anyone can post here, so the body is capped before the signature is checked.
        too_big = JSONResponse({"detail": "The body is too large."}, status_code=413)
        length = request.headers.get("content-length") or ""
        if length.isdigit() and int(length) > MAX_HOOK:
            return too_big
        body = bytearray()
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_HOOK:
                return too_big
        body = bytes(body)
        if not verify_signature(app.config.webhook_secret, body, request.headers.get("X-Hub-Signature-256")):
            return JSONResponse({"detail": "The signature does not match."}, status_code=401)
        delivery, event = request.headers.get("X-GitHub-Delivery"), request.headers.get("X-GitHub-Event", "")
        if delivery and not seen.add(delivery):
            return JSONResponse({"duplicate": True})
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("not an object")
        except ValueError:
            seen.discard(delivery)
            return JSONResponse({"detail": "The body is not a JSON object."}, status_code=400)
        try:
            status, out = await run_in_threadpool(handle, event, data)
        except GitHubError as e:
            seen.discard(delivery)
            log.warning("%s %s: %s", event, data.get("action"), e)
            return JSONResponse({"detail": f"GitHub answered {e.status}: {e.message}"}, status_code=502)
        except Exception:
            seen.discard(delivery)
            log.exception("%s %s could not be handled", event, data.get("action"))
            return JSONResponse({"detail": "Viva could not handle this event."}, status_code=500)
        return JSONResponse(out, status_code=status)

    return router


# ---------- the engine's events ----------
def state_for(event, s):
    """The check state an engine event leads to, and what it needs: (state, kwargs), or (None, {}) for no change."""
    rv = s.get("review") or {}
    if event == "finished":
        verdict = (s.get("assessment") or {}).get("verdict")
        # A pass, or a failed last attempt, goes to a senior; a first failure is a second chance.
        if verdict == "shown" or rv.get("status") == "pending":
            return "waiting_review", {"shown": verdict == "shown"}
        return "retake", {}
    if event == "decided" and rv.get("verdict") in ("correction", "followup"):
        return ("passed" if rv["verdict"] == "correction" else "followup"), {"note": rv.get("note") or ""}
    if event == "retake":  # the second attempt has begun: the retake check stays as it is
        return "retake", {}
    return None, {}


def listener(engine, app, submit=None):
    """fn(event, session) for engine.listeners. Moves the check of the session's pull request along, for its author's
    own sessions only. Sessions with no check of ours (the sample) are ignored, and so is every session in demo mode,
    where anyone may take a check and the presenter sees the reviewer link. Never raises: a GitHub failure must not
    fail the learner's request. submit(fn, *args), when given, makes the GitHub calls off the request thread."""
    checks = CheckStore(engine.store)

    def by_author(s, pr):
        with engine.store.tx():
            u = engine.store.user(s["user_id"]) if s.get("user_id") else None
        author = str(pr.get("author") or "")
        return bool(u and author and u["login"].lower() == author.lower())

    def apply(event, s):
        if not (app and app.config.enabled) or getattr(engine, "demo", False) or s.get("pack_id") == "sample":
            return
        pr = s.get("pr") or {}
        if not (pr.get("repo") and pr.get("number") and pr.get("sha")):
            return
        # The commit that shows this session's pack now: after a push carried the check over, the new one. Its newest
        # run is the one to move along, as for the session's own commit.
        carrier = checks.for_pack(pr["repo"], pr["number"], s["pack_id"]) if s.get("pack_id") else None
        row = checks.latest(pr["repo"], pr["number"], carrier["sha"] if carrier else pr["sha"])
        state, kw = state_for(event, s)
        if not row or not state or (state == "retake" and row["state"] == "retake") or not by_author(s, pr):
            return
        inst, repo, sha, pack_id = row["installation_id"], row["repo"], row["sha"], s.get("pack_id") or row["pack_id"]
        payload = PRESENTERS[state](app.config.public_url, {**pr, "repo": repo, "sha": sha}, pack_id, **kw)
        if row["state"] == "waiting_review":  # the one open run of ours; a Preparing run belongs to its job
            app.update_check(inst, repo, row["check_run_id"], payload)
            checks.set(row["check_run_id"], state, pack_id)
        else:  # GitHub shows the newest run of a name, so a new run replaces a completed one
            run = app.create_check(inst, repo, sha, payload)
            checks.add(repo, row["number"], sha, inst, run["id"], pack_id, state)

    def safe(event, s):
        try:
            apply(event, s)
        except Exception:
            log.exception("check update after %s failed", event)

    def on_event(event, s):
        try:
            if submit:
                submit(safe, event, s)
            else:
                safe(event, s)
        except Exception:
            log.exception("check update after %s could not be queued", event)

    return on_event


def manifest(public_url):
    """The GitHub App manifest (https://docs.github.com/apps/sharing-github-apps/registering-a-github-app-from-a-manifest).
    It has no redirect_url: Viva serves no page that exchanges the one-time code (its routes exist only once the app is
    configured). Once the app exists, generate its private key and set its webhook secret on the app's settings page,
    then set the environment above."""
    base = public_url.rstrip("/")
    return {
        "name": "Viva",
        "url": base,
        "description": "Explain a change before it merges: a short check on what the code does and why.",
        "hook_attributes": {"url": base + "/api/github/webhook", "active": True},
        "callback_urls": [base + "/api/auth/github/callback"],
        "request_oauth_on_install": False,
        "public": False,
        "default_permissions": {"checks": "write", "pull_requests": "read", "contents": "read", "metadata": "read"},
        "default_events": ["pull_request", "check_run"],
    }
