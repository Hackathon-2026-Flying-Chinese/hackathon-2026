"""The interview, on the server. Same rules and view shapes as the browser simulator (frontend/js/sim.js), so the
answer key, the run facts and the scoring never reach the browser: a session view carries the question side of the
task only, and the right answers come back in the assessment after the viva.

Content only: never face, voice tone or expression, and never who wrote the code or how much AI helped.

Every session belongs to a signed-in person and reads one task pack: the sample from tasks.json, or the pack generated
from the diff of a real pull request (taskgen.py). The concept level is per person and per concept.
"""
import base64
import hashlib
import hmac
import logging
import math
import re
import secrets
import time
from urllib.parse import quote, unquote

from . import ai, sandbox, stt

log = logging.getLogger("viva.engine")

ITEMS = ("behaviour", "requirement", "evidence")
CONF = ("low", "medium", "high")
CHECK = {"behaviour": "Behaviour", "requirement": "Requirement", "evidence": "Evidence"}
HEAD = {
    "shown": "You predicted what the code does, and explained why.",
    "gaps": "Part of this is still a guess.",
    "not_shown": "The code did something you did not expect.",
}
PROBE_LABEL = {"concrete": "Be concrete", "reasoning": "Why this way", "consequence": "What could go wrong"}
STALE = "This interview has already changed. Reload to continue; nothing was overwritten."
LINK_TTL = 300
PR_KEYS = ("repo", "number", "title", "author", "branch", "base", "sha", "files", "url")
PACK_STATUS = {
    "generating": "Viva is reading your diff and writing the questions. This takes a few minutes.",
    "needs_review": "Viva could not verify its questions for this change, so it will not ask them.",
    "failed": "Viva could not prepare questions for this change.",
    "skipped": "This change needs no check.",
}


class Fail(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status, self.detail = status, detail


def fail(status, detail):
    raise Fail(status, detail)


# ---------- helpers ----------
now = time.time
b64u = lambda n: base64.urlsafe_b64encode(secrets.token_bytes(n)).rstrip(b"=").decode()
jsround = lambda x: math.floor(x + 0.5)  # Math.round, so the simulator and the server agree to the point
round1 = lambda x: math.floor(x * 10 + 0.5) / 10
words = lambda s: len(re.findall(r"\S+", str(s).strip()))
clamp = lambda x, lo=6, hi=97: max(lo, min(hi, x))

# ---------- word signals: only used to aim the template follow-up when the model is not available ----------
RE = {
    "num": re.compile(r"\$?\b\d[\d,]*(?:\.\d+)?%?"),
    "id": re.compile(r"`[^`]+`|\b[a-z]+(?:_[a-z0-9]+)+\b|\b[a-z]+[A-Z][A-Za-z0-9]*\b|\b[\w-]+\.(?:py|js|ts|go|java|rb|rs|sql|json|ya?ml)\b"),
    "reason": re.compile(r"\b(?:because|so that|therefore|instead of|rather than|otherwise|that way|which means|trade-?offs?|the reason|to avoid|avoids?|in order to|since)\b", re.I),
    "alt": re.compile(r"\b(?:considered|alternatives?|another option|other option|could have|other approach|weighed|compared|tiers?|tiered|instead)\b", re.I),
    "generic": re.compile(r"\b(?:best practices?|clean and robust|clean(?:er)? code|robust(?:ly)?|scalab(?:le|ility)|seamless(?:ly)?|leverag(?:e|es|ed|ing)|maintainab(?:le|ility)|in conclusion|overall|furthermore|as expected|properly|correctly|efficient(?:ly)?|(?:industry )?standard (?:and )?(?:scalable )?(?:solution|approach)|well-structured)\b", re.I),
}


def uniq(text, rx):
    return {(m.group(0)[1:] if m.group(0).startswith("$") else m.group(0)).lower() for m in rx.finditer(text)}


def count(text, rx):
    return sum(1 for _ in rx.finditer(text))


def features(text):
    return {"words": words(text), "nums": uniq(text, RE["num"]), "ids": uniq(text, RE["id"]), "reason": count(text, RE["reason"]),
            "alt": count(text, RE["alt"]), "generic": uniq(text, RE["generic"])}


def sat(x):  # saturating: more evidence helps less and less, and never reaches 1
    return 1 - math.exp(-1.6 * x)


def score_texts(texts):
    n, f = max(1, len(texts)), [features(t) for t in texts]
    total = lambda k: sum(len(x[k]) if isinstance(x[k], set) else x[k] for x in f)
    nums, ids, reason, alt, generic, w = (total(k) for k in ("nums", "ids", "reason", "alt", "generic", "words"))
    dims = {
        "specific": clamp(jsround(10 + 90 * sat((nums + 1.5 * ids) / (3 * n)) - 3 * generic)),
        "reasoning": clamp(jsround(10 + 90 * sat((reason + 0.6 * alt) / (2.5 * n)) - 2.5 * generic)),
        "detail": clamp(jsround(10 + 90 * sat(w / (45 * n)) - 1.5 * generic)),
    }
    return {"dims": dims, "score": jsround(0.375 * dims["specific"] + 0.375 * dims["reasoning"] + 0.25 * dims["detail"])}


def sentences(text):
    guarded = re.sub(r"(\d)\.(\d)", "\\1\x00\\2", text)
    return [x.replace("\x00", ".").strip() for x in re.split(r"(?<=[.!?])\s+", guarded) if x.replace("\x00", ".").strip()]


def opt_text(item, oid):
    return next((o["text"] for o in item["options"] if o["id"] == oid), "")


# ---------- assessment ----------
# The three checks are decided by the task data: what the code really returns, the rule, the test that covers it.
# The viva is assessed against the task's fixed rubric: by the model when it is available (every credited point quotes
# the answer, checked in ai.py), otherwise from the rubric's patterns, labelled Simulated.
def simulated_viva(task_set, answered):
    points = []
    for p in task_set["rubric"]:
        res = [re.compile(x, re.I) for x in p["sim"]]
        hit = None
        for t in answered:
            s = next((x for x in sentences(t["answer_text"]) if all(r.search(x) for r in res)), None)
            if s:
                hit = {"id": p["id"], "text": p["text"], "met": True, "quote": s, "turn": t["turn"]}
                break
        points.append(hit or {"id": p["id"], "text": p["text"], "met": False, "quote": "", "turn": 0})
    return {"source": "simulated", "model": None, "flagged": False, "points": points}


def model_viva(task_set, got):
    points = []
    for p in task_set["rubric"]:
        g = next((x for x in got["points"] if x["id"] == p["id"]), {})
        met = bool(g.get("met")) and bool(g.get("quote"))
        points.append({"id": p["id"], "text": p["text"], "met": met, "quote": g["quote"] if met else "", "turn": int(g["turn"]) if met else 0})
    return {"source": "ai", "model": got.get("model"), "flagged": bool(got.get("injection_attempt")), "points": points}


def quote_marks(text, quotes):
    """The answer split into plain runs and the runs the viva assessment quoted, so the pages can mark them."""
    low, spans = text.lower(), []
    for q in quotes:
        i = low.find(q.lower())
        if i >= 0:
            spans.append((i, i + len(q)))
    spans.sort()
    out, at = [], 0
    for a, b in spans:
        if a < at:
            continue
        if a > at:
            out.append({"text": text[at:a], "kind": None})
        out.append({"text": text[a:b], "kind": "quote"})
        at = b
    if at < len(text):
        out.append({"text": text[at:], "kind": None})
    return out


def segments_for(text, duration):
    """Simulated transcriber: a stand-in text split into timestamped segments."""
    guarded = re.sub(r"(\d)\.(\d)", "\\1\x00\\2", text)
    raw = [x.replace("\x00", ".").strip() for x in (re.findall(r"[^.!?\n]+[.!?]*", guarded) or [guarded])]
    raw = [x for x in raw if x]
    parts = []
    for sent in raw:
        if words(sent) <= 14:
            parts.append(sent)
            continue
        cut = sent.find(",", int(len(sent) / 3))
        if 0 < cut < len(sent) - 8:
            parts += [sent[: cut + 1].strip(), sent[cut + 1 :].strip()]
        else:
            parts.append(sent)
    total = sum(words(p) for p in parts) or 1
    lead = min(0.6, duration * 0.05)
    span = max(duration - lead - 0.2, 1)
    at, out = lead, []
    for p in parts:
        d = span * words(p) / total
        out.append({"start": round1(at), "end": round1(at + d), "text": p})
        at += d
    return out


def sample_pack(content):
    """The sample pull request of tasks.json as a pack, the same shape as a generated one."""
    sc = content["scoring"]
    return {"id": "sample", "source": "sample", "pr": content["pr"],
            "concept": {"key": sc["concept"].get("key", "access-control"), "name": sc["concept"]["name"]},
            "scoring": {"r": sc["r"], "n": sc["n"], "why": sc["why"]},
            "sets": content["sets"], "predictions": content.get("predictions", [])}


class Packs:
    """Task packs: the sample, and one per pull request head in the store. Only a ready pack is ever served."""

    def __init__(self, store, sample):
        self.store, self.sample, self.cache = store, sample, {}

    def get(self, pid):
        if pid == "sample":
            return self.sample
        if pid not in self.cache:
            row = self.store.pack(pid)
            if not row or row["status"] != "ready":
                fail(404, "This check is no longer available.")
            self.cache[pid] = row["pack"]
        return self.cache[pid]

    def find(self, repo, number, sha=None):
        return self.store.find_pack(repo, int(number), sha)

    def put(self, pr, status, pack=None, report=None):
        """Record a pack (or just its status) for the pull request head in pr. Returns the pack id."""
        # Only what the pages show: the description and the files' whole text were for the generator.
        pr = {k: v for k, v in pr.items() if k in PR_KEYS}
        pack = {k: v for k, v in pack.items() if k != "quality"} if pack else None  # the report is kept on its own
        content = {**pack, "pr": {**{k: v for k, v in (pack.get("pr") or {}).items() if k in PR_KEYS}, **pr}} if pack else {"pr": pr}
        with self.store.tx():
            pid = self.store.put_pack(pr["repo"], int(pr["number"]), pr["sha"], status, content, report)
        self.cache.pop(pid, None)
        return pid


class Engine:
    def __init__(self, store, content, demo=False):
        self.store, self.demo = store, demo
        self.L, self.SC = content["limits"], content["scoring"]  # the interview limits and the scoring standard, for every pack
        self.packs = Packs(store, sample_pack(content))
        self.listeners = []  # fn(event, session), called after a change commits: "finished", "decided", "retake"

    def emit(self, event, s):
        for fn in list(self.listeners):
            try:
                fn(event, s)
            except Exception:  # a listener (the GitHub check) never breaks the interview
                log.exception("listener failed on %s", event)

    # ---------- task lookups ----------
    def pack_of(self, s):
        return self.packs.get(s.get("pack_id") or "sample")

    def concept_of(self, s):
        return s.get("concept") or self.packs.sample["concept"]

    def set_of(self, s):
        """Attempt 1 reads the first task and the retake the second (same concept, different code), so no question repeats."""
        sets = self.pack_of(s)["sets"]
        return sets[min(s["attempt"], len(sets)) - 1]

    def task_view(self, s):
        """The question side of the task: what the person reads before the viva. No answers, facts or rubric."""
        st = self.set_of(s)
        t = st["task"]
        return {
            "fn": t["fn"], "file": t["file"], "code": t["code"], "rule": t["rule"], "tests": t["tests"],
            "origin": t.get("origin", "diff"),  # "variant": written for the retake, not code from the pull request
            # The retake line says whether the code needs fixing, which is question 2's answer: only with the results.
            "retake": t["retake"] if s["stage"] == "results" else "",
            "items": {k: {"q": t["items"][k]["q"], "options": t["items"][k]["options"]} for k in ITEMS},
            "questions": {k: {"label": v["label"]} for k, v in st["questions"].items()},
        }

    def settings(self):
        return {"camera_required": self.store.setting("camera_required", True), "voice": self.store.setting("voice", "specific")}

    # ---------- scoring: what a reviewed check adds to the portfolio ----------
    # Points = Risk x Novelty x Gap (1 to 27). Gap follows the concept level, which a pass raises and a second failure lowers.
    @staticmethod
    def clamp_level(x):
        return max(0, min(3, x))

    def band_of(self, n):
        return next(b["key"] for b in self.SC["bands"] if b["from"] <= n <= b["to"])

    def level_events(self, sessions, key=None):
        """One person's level changes, oldest first; with a key, on that concept only."""
        evs = [{**e, "title": s["pr"]["title"], "concept": self.concept_of(s)["key"]} for s in sessions for e in s["level_events"]
               if key is None or self.concept_of(s)["key"] == key]
        return sorted(evs, key=lambda e: e["at"])

    def level_of(self, sessions, key):
        lv = self.SC["concept"]["start"]
        for e in self.level_events(sessions, key):
            lv = self.clamp_level(lv + e["delta"])
        return lv

    def level_for_login(self, login, key):
        """The level of a GitHub login on a concept, for a check prepared before its author ever signed in."""
        with self.store.tx():
            u = self.store.user_by_login(login) if login else None
            return self.level_of(self.store.sessions(u["id"]), key) if u else self.SC["concept"]["start"]

    def points_for(self, pack, level):
        r, nov = pack["scoring"]["r"], pack["scoring"]["n"]
        g = 1 if level >= 3 else 2 if level == 2 else 3
        n = r * nov * g
        band, floor = self.band_of(n), None
        if r == 3 and band == "skip":  # the plan's hard rule for the highest risk
            band, floor = "light", "Money flow is never skipped."
        return {"r": r, "n": nov, "g": g, "s": n, "band": band, "floor": floor, "level": level}

    @staticmethod
    def why(pack, level):
        w = pack["scoring"]["why"]
        return {"r": w["r"], "n": w["n"], "g": f"{pack['concept']['name']} is at level {level} of 3."}

    def can_retake(self, s):
        return s["stage"] == "results" and bool(s["assessment"]) and s["assessment"]["verdict"] != "shown" and s["attempt"] < self.L["maxAttempts"]

    def scoring_view(self, sessions, s):
        """sessions: the same person's, for the level now and the next similar change."""
        sc, rv, pack, concept = s["scoring"], s["review"], self.pack_of(s), self.concept_of(s)
        status = ("none" if s["stage"] != "results" else "retake" if not rv or rv["status"] == "not_requested"
                  else "pending" if rv["status"] == "pending" else "earned" if rv.get("verdict") == "correction" else "declined")
        ev = s["level_events"][-1] if s["level_events"] else None
        return {
            **sc, "max": self.SC["max"], "status": status, "points": sc["s"] if status == "earned" else 0,
            "why": self.why(pack, sc["level"]), "rubric": self.SC["rows"], "bands": self.SC["bands"],
            "concept": {"key": concept["key"], "name": concept["name"], "before": sc["level"],
                        "after": self.clamp_level(sc["level"] + ev["delta"]) if ev else sc["level"], "reason": ev["reason"] if ev else None},
            "next": self.points_for(pack, self.level_of(sessions, concept["key"])),
        }

    # ---------- state and views ----------
    @staticmethod
    def pr_text(v, mx):
        return v.strip()[:mx] if isinstance(v, str) and v.strip() else None

    @staticmethod
    def pr_number(inp):
        try:
            number = int(inp.get("number"))
        except (TypeError, ValueError):
            return 0
        return number if number > 0 else 0

    def clean_pr(self, inp=None):
        """The sample pull request, with what the link carries laid over it (a demo can show any PR name)."""
        d, inp, text = self.packs.sample["pr"], inp or {}, self.pr_text
        number = self.pr_number(inp)
        return {"repo": text(inp.get("repo"), 80) or d["repo"], "number": number or d["number"],
                "title": text(inp.get("title"), 120) or d["title"], "author": text(inp.get("author"), 40) or d["author"],
                "branch": text(inp.get("branch"), 60) or d["branch"], "base": text(inp.get("base"), 40) or d["base"],
                "sha": text(inp.get("sha"), 12) or d["sha"], "files": d["files"]}

    def pack_for(self, inp):
        """The pack a check link points at: (pack, None) for the sample, (pack or None, row) for a generated one. A pack
        that is not ready comes back as None with its row, so the page can say why. Unknown pull requests get the
        sample only in demo mode."""
        inp = inp or {}
        repo, number = self.pr_text(inp.get("repo"), 120), self.pr_number(inp)
        sample = self.packs.sample
        if not repo or not number:
            return sample, None
        sha = self.pr_text(inp.get("sha"), 40)
        row = self.packs.find(repo, number, sha if sha and re.fullmatch(r"[0-9a-fA-F]{7,40}", sha) else None)
        if row and row["status"] == "carried":  # a push that left the checked code alone: the earlier commit's pack
            row = self.store.pack((row["report"] or {}).get("from")) or row
        if row:
            return (self.packs.get(row["id"]) if row["status"] == "ready" else None), row
        if self.demo or (repo.lower() == sample["pr"]["repo"].lower() and number == sample["pr"]["number"]):
            return sample, None
        fail(404, "Viva has no check for this pull request.")

    def pr_for(self, pack, inp):
        if pack["source"] == "sample":
            return self.clean_pr(inp)
        return {k: v for k, v in pack["pr"].items() if k in PR_KEYS}

    def may_take(self, user, pack):
        """A generated check is for the author of its pull request; the sample, and every check in demo mode, for anyone."""
        if pack["source"] != "generated" or self.demo:
            return True, None
        author = str(pack["pr"].get("author") or "")
        if author and user["login"].lower() == author.lower():
            return True, None
        return False, f"Only the author of this pull request ({author or 'unknown'}) can take its check."

    @staticmethod
    def turn_view(t):
        keys = ("turn", "key", "label", "question", "source", "by", "answered", "answer_text", "mode", "media_id")
        return {k: t.get(k) for k in keys}

    def view(self, s, presenter=False):
        sessions = self.store.sessions(s["user_id"])
        results = s["stage"] == "results"
        return {
            "id": s["id"], "stage": s["stage"], "version": s["version"], "created": s["created"],
            "finished": s.get("finished") if results else None, "pr": s["pr"],
            "attempt": s["attempt"], "max_attempts": self.L["maxAttempts"], "can_retake": self.can_retake(s),
            "previous": [{"attempt": a["attempt"], "score": a["assessment"]["score"], "verdict": a["assessment"]["verdict"]} for a in s["attempts"]],
            "camera_required": self.settings()["camera_required"] is not False,
            "limits": self.limits(),
            "task": self.task_view(s),
            "predict": {"answers": dict(s["predict"]["answers"]), "confidence": s["predict"]["confidence"]} if s["predict"] else None,
            "interview": {"standard": self.L["standardTurns"], "max_turns": self.L["maxTurns"], "done": s["interview"]["done"],
                          "turns": [self.turn_view(t) for t in s["interview"]["turns"]]},
            "assessment": s["assessment"] if results else None,
            "review": s["review"] if results else None,
            "scoring": self.scoring_view(sessions, s),
            "access_log": [dict(e) for e in s["access_log"]],
            "media": [{"id": m["id"], "turn": m["turn"], "attempt": m["attempt"], "kind": m["kind"], "duration": m["duration"]} for m in s["media"].values()],
            # The reviewer link goes to the senior, never to the learner; only the demo presenter sees it.
            "reviewer_link": f"review.html#{s['reviewer_token']}" if presenter and self.demo and s["reviewer_token"] else None,
        }

    def limits(self):
        return {k: self.L[k] for k in ("minAnswerChars", "clipSeconds", "vivaPass")}

    def get(self, sid, user):
        """A session, only for the person it belongs to. Anyone else gets the same answer as for no session at all."""
        s = self.store.session(sid)
        if not s or s.get("user_id") != user["id"]:
            fail(404, "Session not found")
        return s

    @staticmethod
    def check_version(s, version):
        if s["version"] != version:
            fail(409, STALE)

    @staticmethod
    def log_access(s, actor, action, mid=None, turn=None, attempt=None):
        s["access_log"].append({"actor": actor, "action": action, "media_id": mid, "turn": turn, "attempt": attempt, "at": now()})

    @staticmethod
    def open_turn(s, turn):
        iv = s["interview"]
        cur = iv["turns"][-1] if iv["turns"] else None
        if s["stage"] != "interview":
            fail(409, "The interview is over.")
        if not cur or cur["turn"] != turn or cur["answered"]:
            fail(409, "That question is not open.")
        return cur

    # ---------- interview ----------
    def make_turn(self, s, key, turn, source):
        st = self.set_of(s)
        spec = st["probes"][key[6:]] if key.startswith("probe:") else st["questions"][key]
        return {"turn": turn, "key": key, "label": spec["label"], "question": spec["text"].replace("{title}", s["pr"]["title"]), "source": source,
                "by": "template" if source == "follow-up" else None, "answered": False, "answer_text": None, "mode": None, "media_id": None, "asked_at": now()}

    def weakest(self, s):
        """The template follow-up aims at the weaker of the two word signals, and is skipped when neither is weak."""
        dims = score_texts([t["answer_text"] for t in s["interview"]["turns"] if t["answered"]])["dims"]
        dim, v = sorted([("specific", dims["specific"]), ("reasoning", dims["reasoning"])], key=lambda x: x[1])[0]
        return dim if v < 55 else None

    def advance(self, s):
        """The two standard questions. The follow-up is decided after the second answer (see interview_answer)."""
        turns, n = s["interview"]["turns"], len(s["interview"]["turns"])
        if n >= self.L["standardTurns"]:
            return None
        t = self.make_turn(s, "implementation" if n == 0 else "rationale", n + 1, "standard")
        turns.append(t)
        return t

    def follow_up(self, s, got):
        """At most one follow-up: the model's question when it passed the checks in ai.py; the template when the model is
        not available or its question was filtered out; none when the model finds the answers need no follow-up."""
        if got and got.get("needs_follow_up") is False:
            return None
        if got and got.get("question"):
            t = self.make_turn(s, "probe:specific", self.L["standardTurns"] + 1, "follow-up")
            return {**t, "key": "probe:ai", "label": PROBE_LABEL.get(got.get("target"), "Follow-up"), "question": got["question"], "by": "ai"}
        dim = self.weakest(s)
        return self.make_turn(s, "probe:" + dim, self.L["standardTurns"] + 1, "follow-up") if dim else None

    def stand_in(self, s, key):
        """Demo only: speaking is answered with a stand-in text when speech-to-text is not available. Generated packs
        have no stand-ins."""
        answers = self.set_of(s).get("answers")
        if not answers:
            return None
        return answers[self.settings()["voice"]]["probe" if key.startswith("probe") else key]

    def viva_turns(self, s):
        return [{"turn": t["turn"], "question": t["question"], "answer": t["answer_text"]} for t in s["interview"]["turns"] if t["answered"]]

    def followup_body(self, s):
        t = self.set_of(s)["task"]  # the follow-up never gets the answer key
        return {"file": t["file"], "code": t["code"], "rule": t["rule"], "turns": self.viva_turns(s), "leak_terms": t["leak"]}

    def grade_body(self, s):
        st = self.set_of(s)
        t = st["task"]  # the assessment gets the facts of the run, so it can tell a right explanation from a wrong one
        return {"file": t["file"], "code": t["code"], "rule": t["rule"], "facts": t["facts"],
                "rubric": [{"id": p["id"], "text": p["text"]} for p in st["rubric"]], "turns": self.viva_turns(s)}

    def run_of(self, task):
        """The sandbox run of a task's behaviour scenario, kept in the store by what ran. None when the task has no
        harness or no sandbox is available; then the reveal shows the task's own account, labelled simulated."""
        spec = task.get("run")
        if not isinstance(spec, dict) or not sandbox.available():
            return None
        key = sandbox.key_of(spec.get("lang") or "", spec.get("harness") or "", task.get("code") or "")
        with self.store.tx():
            hit = self.store.run(key)
        if hit:
            return hit
        res = sandbox.run_task(task)
        if res and res["ok"]:
            with self.store.tx():
                self.store.put_run(key, res)
        return res

    @staticmethod
    def reveal_of(task, run):
        """What came back: from the run when it ran and printed the keyed option, else the task's own account."""
        reveal = dict(task["reveal"])
        if not run:
            return reveal
        obs = run.get("observed") or {}
        agrees = bool(run["ok"]) and obs.get("option") == task["items"]["behaviour"]["correct"]
        reveal["run"] = {"runner": run["runner"], "image": run.get("image"), "duration_ms": run["duration_ms"], "ok": bool(run["ok"]),
                         "agrees": agrees, "stdout": (run.get("stdout") or "")[-2000:], "error": run.get("error"), "at": run["at"]}
        if agrees:
            for k in ("status", "result", "owner", "note"):
                if isinstance(obs.get(k), str):
                    reveal[k] = obs[k][:300]
            rows = obs.get("rows")
            if isinstance(rows, list) and all(isinstance(r, list) for r in rows):
                reveal["rows"] = [[str(c)[:100] for c in r[:8]] for r in rows[:20]]
        return reveal

    def assess(self, s, got, run=None):
        st = self.set_of(s)
        task, answered = st["task"], [t for t in s["interview"]["turns"] if t["answered"]]
        checks = []
        for key in ITEMS:
            it, chosen = task["items"][key], s["predict"]["answers"][key]
            checks.append({"key": key, "label": CHECK[key], "question": it["q"], "chosen": chosen, "chosen_text": opt_text(it, chosen),
                           "correct_text": opt_text(it, it["correct"]), "ok": chosen == it["correct"]})
        viva = model_viva(st, got) if got and isinstance(got.get("points"), list) else simulated_viva(st, answered)
        right, met = sum(c["ok"] for c in checks), sum(p["met"] for p in viva["points"])
        verdict = "shown" if right == len(ITEMS) and met >= self.L["vivaPass"] else "gaps" if right + met >= 3 else "not_shown"
        return {
            "simulated": viva["source"] != "ai", "score": jsround(right / len(ITEMS) * 100), "verdict": verdict, "headline": HEAD[verdict],
            "checks": checks, "right": right, "confidence": s["predict"]["confidence"], "fn": task["fn"], "rule": task["rule"],
            "reveal": self.reveal_of(task, run), "viva": viva, "met": met, "rubric_size": len(st["rubric"]), "viva_pass": self.L["vivaPass"],
            "questions": [{"turn": t["turn"], "label": t["label"], "question": t["question"], "source": t["source"], "by": t.get("by"),
                           "mode": t["mode"], "answer": t["answer_text"],
                           "segments": quote_marks(t["answer_text"], [p["quote"] for p in viva["points"] if p["met"] and p["turn"] == t["turn"]])}
                          for t in answered],
        }

    # ---------- API ----------
    def check(self, user, pr=None):
        """What the GitHub check links to: the pull request, whether its questions are ready, whether this person may take
        it, and why it needs a check (Risk x Novelty x Gap at their current level on its concept)."""
        with self.store.tx():
            pack, row = self.pack_for(pr)
            if pack is None:
                content = row["pack"] or {}
                return {"pr": self.pr_for({"source": "generated", "pr": content.get("pr") or {"repo": row["repo"], "number": row["number"], "sha": row["sha"]}}, None),
                        "pack": {"status": row["status"], "source": "generated", "message": PACK_STATUS.get(row["status"], "")},
                        "can_start": False, "reason": PACK_STATUS.get(row["status"], ""), "scoring": None}
            ok, reason = self.may_take(user, pack)
            concept = pack["concept"]
            sc = self.points_for(pack, self.level_of(self.store.sessions(user["id"]), concept["key"]))
            return {"pr": self.pr_for(pack, pr), "pack": {"status": "ready", "source": pack["source"], "message": None},
                    "can_start": ok, "reason": reason,
                    "scoring": {**sc, "max": self.SC["max"], "why": self.why(pack, sc["level"]), "rubric": self.SC["rows"],
                                "bands": self.SC["bands"], "concept": {"key": concept["key"], "name": concept["name"], "level": sc["level"]}}}

    def start(self, user, pr=None):
        with self.store.tx():
            pack, row = self.pack_for(pr)
            if pack is None:
                fail(409, PACK_STATUS.get(row["status"], "This check is not ready."))
            ok, reason = self.may_take(user, pack)
            if not ok:
                fail(403, reason)
            t = now()
            level = self.level_of(self.store.sessions(user["id"]), pack["concept"]["key"])
            s = {"id": b64u(24), "user_id": user["id"], "pack_id": pack["id"], "concept": dict(pack["concept"]),
                 "stage": "interview", "version": 0, "created": t, "pr": self.pr_for(pack, pr),
                 "attempt": 1, "attempts": [], "scoring": self.points_for(pack, level), "first_score": None,
                 "level_events": [], "predict": None, "interview": {"turns": [], "done": False}, "assessment": None, "review": None,
                 "finished": None, "reviewer_token": None, "access_log": [], "media": {}}
            self.store.save(s)
            return self.view(s)

    def session(self, user, sid, presenter=False):
        with self.store.tx():
            return self.view(self.get(sid, user), presenter)

    def predict(self, user, sid, body, presenter=False):
        """Lock the three checks before the viva. Nothing about the right answers comes back until the results."""
        with self.store.tx():
            s = self.get(sid, user)
            task = self.set_of(s)["task"]
            self.check_version(s, body.get("version"))
            if s["stage"] != "interview":
                fail(409, "The interview is over.")
            if s["predict"]:
                fail(409, "Your answers are already locked.")
            answers, picked = body.get("answers") or {}, {}
            for key in ITEMS:
                if not any(o["id"] == answers.get(key) for o in task["items"][key]["options"]):
                    fail(422, "Answer all three questions first.")
                picked[key] = answers[key]
            if body.get("confidence") not in CONF:
                fail(422, "Say how sure you are about question 1.")
            s["predict"] = {"answers": picked, "confidence": body["confidence"], "at": now()}
            self.store.save(s)
            return self.view(s, presenter)

    def interview_next(self, user, sid, body, presenter=False):
        """First question, or the open one after a reload."""
        with self.store.tx():
            s = self.get(sid, user)
            self.check_version(s, body.get("version"))
            if s["stage"] != "interview":
                fail(409, "The interview is over.")
            if not s["predict"]:
                fail(409, "Lock your answers to the three questions first.")
            iv = s["interview"]
            last = iv["turns"][-1] if iv["turns"] else None
            if iv["done"]:
                fail(409, "The interview is complete.")
            if last and not last["answered"]:
                return {**self.turn_view(last), "view": self.view(s, presenter)}
            t = self.advance(s) or fail(409, "The interview is complete.")
            self.store.save(s)
            return {**self.turn_view(t), "view": self.view(s, presenter)}

    def interview_answer(self, user, sid, body, presenter=False):
        turn, mode, media_id = body.get("turn"), body.get("mode", "text"), body.get("media_id")
        with self.store.tx():
            s = self.get(sid, user)
            self.check_version(s, body.get("version"))
            cur = self.open_turn(s, turn)
            answer = str(body.get("text") or "").strip()
            if len(answer) < self.L["minAnswerChars"]:
                fail(422, f"Say a little more (at least {self.L['minAnswerChars']} characters).")
            if mode not in ("voice", "text"):
                fail(422, "Unknown answer mode.")
            m = s["media"].get(media_id) if media_id else None
            if self.settings()["camera_required"] is not False and not m:
                fail(422, "The camera recording is required for every answer.")
            if media_id and (not m or m["turn"] != turn or m["used"]):
                fail(403, "That recording does not belong to this question.")
            cur.update(answered=True, answer_text=answer, mode=mode, media_id=m["id"] if m else None)
            if m:
                m["used"], m["mode"] = True, mode
                # Real segments stay when the answer is the transcript as heard; an edited transcript gets estimated
                # timings, and the reviewer is told it was edited.
                heard = mode == "voice" and str(m.get("transcriber") or "").startswith("faster-whisper")
                kept = heard and " ".join(answer.split()) == " ".join(str(m.get("transcript") or "").split())
                m["edited"] = heard and not kept
                m["segments"] = (m["segments"] if kept else segments_for(answer, m["duration"])) if mode == "voice" else None
            n = len(s["interview"]["turns"])
            if n != self.L["standardTurns"]:
                if n < self.L["standardTurns"]:
                    nxt = self.advance(s)
                    self.store.save(s)
                    return {"done": False, **self.turn_view(nxt), "view": self.view(s, presenter)}
                s["interview"]["done"] = True
                self.store.save(s)
                return {"done": True, "view": self.view(s, presenter)}
            self.store.save(s)  # after the second answer: decide on the follow-up, outside the lock
            snap = s
        got = ai.followup(self.followup_body(snap))
        with self.store.tx():
            s = self.get(sid, user)
            if s["stage"] != "interview" or s["interview"]["done"] or len(s["interview"]["turns"]) != self.L["standardTurns"]:
                fail(409, STALE)
            nxt = self.follow_up(s, got)
            if nxt:
                s["interview"]["turns"].append(nxt)
            else:
                s["interview"]["done"] = True
            self.store.save(s)
            return {"done": not nxt, **(self.turn_view(nxt) if nxt else {}), "view": self.view(s, presenter)}

    def _ready_to_finish(self, s, version):
        self.check_version(s, version)
        if s["stage"] != "interview":
            fail(409, "The interview is over.")
        if not s["interview"]["done"] or any(not t["answered"] for t in s["interview"]["turns"]):
            fail(409, "Answer every question first.")

    def interview_finish(self, user, sid, body, presenter=False):
        version = body.get("version")
        with self.store.tx():
            snap = self.get(sid, user)
            self._ready_to_finish(snap, version)
        got = ai.grade(self.grade_body(snap))
        run = self.run_of(self.set_of(snap)["task"])  # both slow, so both outside the lock
        with self.store.tx():
            s = self.get(sid, user)
            self._ready_to_finish(s, version)
            t = now()
            s["assessment"] = self.assess(s, got, run)
            passed, last = s["assessment"]["verdict"] == "shown", s["attempt"] >= self.L["maxAttempts"]
            if s["attempt"] == 1:  # only a first attempt counts toward the trend
                s["first_score"] = {"score": s["assessment"]["score"], "at": t}
            # A first failure is feedback and a second chance: nothing goes to a senior yet. A pass, or a failed retake, does.
            if passed or last:
                s["review"] = {"status": "pending"}
                if not s["reviewer_token"]:
                    s["reviewer_token"] = b64u(18)
                    self.store.add_token(s["reviewer_token"], s["id"], t)
            else:
                s["review"] = {"status": "not_requested"}
            # The concept level: a pass moves it up, a failed retake moves it down, a first failure leaves it alone.
            if passed:
                s["level_events"].append({"at": t, "delta": 1, "attempt": s["attempt"],
                                          "reason": "Passed the interview." if s["attempt"] == 1 else "Passed the second attempt."})
            elif last:
                s["level_events"].append({"at": t, "delta": -1, "attempt": s["attempt"],
                                          "reason": "The second attempt did not pass. It needs more practice or a person to help."})
            s.update(stage="results", finished=t, version=s["version"] + 1)
            self.store.save(s)
            out = self.view(s, presenter)
        self.emit("finished", s)
        return out

    def retake(self, user, sid, body, presenter=False):
        """Second chance after a failed first attempt: the same change, a different set of questions."""
        with self.store.tx():
            s = self.get(sid, user)
            self.check_version(s, body.get("version"))
            if not self.can_retake(s):
                fail(409, "A second attempt is not available.")
            s["attempts"].append({"attempt": s["attempt"], "assessment": s["assessment"], "predict": s["predict"], "turns": s["interview"]["turns"], "finished": now()})
            s.update(attempt=s["attempt"] + 1, predict=None, interview={"turns": [], "done": False}, assessment=None, review=None,
                     finished=None, stage="interview", version=s["version"] + 1)
            self.store.save(s)
            out = self.view(s, presenter)
        self.emit("retake", s)
        return out

    def owned(self, sid, user):
        """For leave and delete: the session if it is this person's, None if it is gone, 404 if it is someone else's."""
        s = self.store.session(sid)
        if s and s.get("user_id") != user["id"]:
            fail(404, "Session not found")
        return s

    def leave(self, user, sid):
        """Leave: delete the recordings, keep the answers."""
        with self.store.tx():
            s = self.owned(sid, user)
            ids = list(s["media"]) if s else []
            if s:
                s["media"] = {}
                for t in s["interview"]["turns"]:
                    t["media_id"] = None
                self.store.save(s)
            for mid in ids:
                self.store.delete_media(mid)
        return {"left": True, "media_deleted": len(ids), "failed": self.store.remove_files(ids)}

    def remove(self, user, sid):
        with self.store.tx():
            s = self.owned(sid, user)
            ids = list(s["media"]) if s else []
            if s and s["reviewer_token"]:
                self.store.delete_token(s["reviewer_token"])
            for mid in ids:
                self.store.delete_media(mid)
            self.store.delete_session(sid)
        return {"deleted": True, "failed": self.store.remove_files(ids)}

    # ----- media -----
    def media_upload(self, user, sid, turn, kind, duration, mode, mime, write):
        """write(path) stores the upload and returns its size; it runs before the row exists, and the file goes if the row fails."""
        if duration > self.L["clipSeconds"] + 1:
            fail(413, f"A single recording can be at most {self.L['clipSeconds']} seconds.")
        with self.store.tx():
            self.open_turn(self.get(sid, user), turn)
        mid = "m_" + secrets.token_hex(6)
        path = self.store.media_path(mid)
        # In demo mode the presenter picks a stand-in answer (Specific or Generic) or real transcription; outside it,
        # a spoken answer is always transcribed on the server when speech-to-text is available.
        stand_in = self.demo and self.settings()["voice"] != "transcribe"
        try:
            write(path)
            heard = stt.transcribe(path, duration) if mode == "voice" and not stand_in else None  # slow: outside the lock
            with self.store.tx():
                s = self.get(sid, user)
                cur = self.open_turn(s, turn)
                text, segments, by = None, None, None
                if heard is not None:
                    text, segments, by = heard["text"], heard["segments"], heard["model"]
                elif mode == "voice" and stand_in:
                    text = self.stand_in(s, cur["key"])
                    segments, by = (segments_for(text, duration), "simulated") if text else (None, None)
                m = {"id": mid, "sid": sid, "turn": turn, "attempt": s["attempt"], "kind": kind, "duration": round1(duration), "mode": mode,
                     "transcript": text, "segments": segments, "transcriber": by, "created": now(), "used": False}
                s["media"][mid] = m
                self.store.add_media(mid, sid, mime)
                self.store.save(s)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return {"media_id": mid, "transcript": m["transcript"], "segments": m["segments"], "duration": m["duration"],
                "transcriber": by}

    def media_discard(self, user, sid, mid):
        """The learner discarded a recording before submitting (for example "Speak again")."""
        with self.store.tx():
            s = self.get(sid, user)
            m = s["media"].get(mid)
            if not m:
                return {"discarded": False}
            if m["used"]:
                fail(409, "That recording is already part of an answer.")
            del s["media"][mid]
            self.store.delete_media(mid)
            self.store.save(s)
        self.store.remove_files([mid])
        return {"discarded": True}

    def _sign(self, msg):
        return hmac.new(self.store.setting("secret").encode(), msg.encode(), hashlib.sha256).hexdigest()

    def media_link(self, mid, token=None, user=None):
        """A five-minute link to a recording: for the senior through the reviewer token, or for the person who recorded it."""
        exp = int(now() + LINK_TTL)
        with self.store.tx():
            meta = self.store.media(mid) or fail(404, "Recording not found")
            s = self.store.session(meta["sid"])
            if token:
                rt = self.store.token(token)
                owner = rt is not None and rt["sid"] == meta["sid"]
            else:
                owner = user is not None and s is not None and s.get("user_id") == user["id"]
            if not owner:
                fail(403, "You cannot open this recording.")
            m = s["media"][mid]
            actor = "reviewer:" + token[:6] if token else "learner"
            self.log_access(s, actor, "sign", mid, m["turn"], m["attempt"])
            self.store.save(s)
            sig = self._sign(f"{mid}.{exp}.{actor}")
        return {"url": f"api/media/{mid}?exp={exp}&a={quote(actor, safe='')}&sig={sig}", "expires_at": exp}

    def media_open(self, mid, exp, actor, sig):
        """Check a signed link and log the play. Returns the file path and its type."""
        actor = unquote(actor)
        if not hmac.compare_digest(sig, self._sign(f"{mid}.{exp}.{actor}")):
            fail(403, "This link is not valid.")
        if int(exp) < now():
            fail(410, "This link has expired. Request a new one.")
        with self.store.tx():
            meta = self.store.media(mid) or fail(404, "Recording not found")
            path = self.store.media_path(mid)
            if not path.exists():
                fail(404, "Recording not found")
            s = self.store.session(meta["sid"])
            m = s["media"][mid]
            self.log_access(s, actor, "play", mid, m["turn"], m["attempt"])
            self.store.save(s)
        return path, meta["mime"]

    # ----- reviewer -----
    def review_view(self, s, token):
        turns = []
        for t in s["interview"]["turns"]:
            if not t["answered"]:
                continue
            m = s["media"].get(t["media_id"]) if t["media_id"] else None
            marks = next((q["segments"] for q in s["assessment"]["questions"] if q["turn"] == t["turn"]), None)
            turns.append({
                "turn": t["turn"], "label": t["label"], "question": t["question"], "source": t["source"], "mode": t["mode"], "answer_text": t["answer_text"],
                "media": {"id": m["id"], "kind": m["kind"], "duration": m["duration"]} if m else None,
                "transcribed_by": m.get("transcriber") if m and t["mode"] == "voice" else None,
                "edited": bool(m.get("edited")) if m else False,
                "segments": [{**sg, "flag": "Generic phrasing." if count(sg["text"], RE["generic"]) else None} for sg in m["segments"]]
                if t["mode"] == "voice" and m and m.get("segments") else None,
                "marks": marks or [{"text": t["answer_text"], "kind": None}],
            })
        u = self.store.user(s["user_id"]) or {}
        return {
            "role": "senior", "banner": "Reviewer link. Not SSO yet.", "token_hint": token[:6],
            "learner": {"login": u.get("login"), "name": u.get("name") or u.get("login"), "avatar_url": u.get("avatar_url")},
            "pr": s["pr"], "assessment": s["assessment"], "decision": s["review"], "requested": s.get("finished"),
            "attempt": s["attempt"], "max_attempts": self.L["maxAttempts"],
            "previous": [{"attempt": a["attempt"], "score": a["assessment"]["score"], "verdict": a["assessment"]["verdict"]} for a in s["attempts"]],
            "turns": turns,
            "access_log": [dict(e) for e in s["access_log"] if e["media_id"] or e["action"] == "open_review"],
        }

    def review(self, token, silent=False):
        """silent: refresh the page data without logging another "opened the review page" entry."""
        with self.store.tx():
            rt = self.store.token(token) or fail(403, "This link does not open a review.")
            s = self.store.session(rt["sid"]) or fail(404, "This review is no longer available.")
            if not silent:
                self.log_access(s, "reviewer:" + token[:6], "open_review")
                self.store.save(s)
            return self.review_view(s, token)

    def decide(self, token, body):
        """The role comes from the token; a role field in the body is ignored."""
        with self.store.tx():
            rt = self.store.token(token) or fail(403, "Only a senior reviewer can decide.")
            s = self.store.session(rt["sid"]) or fail(404, "This review is no longer available.")
            if s["stage"] != "results" or not s["review"] or s["review"]["status"] == "not_requested":
                fail(409, "This interview is not waiting for a review.")
            # A senior either passes the check with a one-line correction on the concept, or asks for a follow-up.
            verdict = body.get("verdict")
            if verdict not in ("correction", "followup"):
                fail(422, "Choose a decision.")
            note = str(body.get("note") or "").strip()[:500]
            if verdict == "correction" and not note:
                fail(422, "Write the one-line correction.")
            s["review"] = {"status": "decided", "verdict": verdict, "note": note, "at": now(), "reviewer": token[:6]}
            self.store.save(s)
        self.emit("decided", s)
        return s["review"]

    # ----- portfolio -----
    def portfolio(self, user):
        with self.store.tx():
            every = self.store.sessions(user["id"])
        entries = []
        for s in reversed([x for x in every if x["stage"] == "results" and x["assessment"]]):
            v = self.scoring_view(every, s)
            entries.append({"sid": s["id"], "title": s["pr"]["title"], "repo": s["pr"]["repo"], "number": s["pr"]["number"], "at": s["created"],
                            "attempt": s["attempt"], "score": s["assessment"]["score"], "verdict": s["assessment"]["verdict"],
                            "r": s["scoring"]["r"], "n": s["scoring"]["n"], "g": s["scoring"]["g"], "s": s["scoring"]["s"], "band": s["scoring"]["band"],
                            "status": v["status"], "points": v["points"]})
        # Judgment score: the three code checks of first attempts only, the last ten, weighted by risk. Fewer than five shows no score at all.
        firsts = [{"at": s["first_score"]["at"], "score": s["first_score"]["score"], "w": s["scoring"]["r"]} for s in every if s["first_score"]]
        recent, need = firsts[-10:], 5
        value = jsround(sum(p["score"] * p["w"] for p in recent) / sum(p["w"] for p in recent)) if len(recent) >= need else None
        concepts = [self.concept_view(every, key) for key in self.concept_keys(every)] or [self.concept_view(every, None)]
        return {
            "points": {"total": sum(e["points"] for e in entries), "max_per_change": self.SC["max"],
                       "confirmed": sum(e["status"] == "earned" for e in entries), "entries": entries},
            "score": {"value": value, "n": len(firsts), "needed": need, "real": [{"at": p["at"], "score": p["score"]} for p in firsts]},
            "concept": concepts[0], "concepts": concepts,
            "rubric": self.SC["rows"], "bands": self.SC["bands"],
        }

    def concept_keys(self, sessions):
        """The concepts this person has met, the most recent first."""
        keys = []
        for s in reversed(sessions):
            k = self.concept_of(s)["key"]
            if k not in keys:
                keys.append(k)
        return keys

    def concept_view(self, sessions, key):
        """Level, history and the next similar change on one concept. key None: the sample concept, before any session."""
        mine = [s for s in sessions if self.concept_of(s)["key"] == key]
        pack = self.pack_of(mine[-1]) if mine else self.packs.sample
        concept = self.concept_of(mine[-1]) if mine else pack["concept"]
        lv, events = self.SC["concept"]["start"], []
        for e in self.level_events(mine):
            frm, lv = lv, self.clamp_level(lv + e["delta"])
            events.append({"at": e["at"], "from": frm, "to": lv, "reason": e["reason"], "title": e["title"]})
        return {"key": concept["key"], "name": concept["name"], "level": lv, "max": 3, "events": list(reversed(events)),
                "next": self.points_for(pack, lv)}

    # ----- presenter controls (demo mode only) -----
    def demo_info(self):
        sample = self.packs.sample
        return {"predictions": sample["predictions"], "answers": [st["answers"] for st in sample["sets"]], **self.settings()}

    def set_settings(self, body):
        with self.store.tx():
            if "camera_required" in body:
                self.store.set_setting("camera_required", bool(body["camera_required"]))
            if "voice" in body:
                self.store.set_setting("voice", body["voice"] if body["voice"] in ("generic", "transcribe") else "specific")
            return self.settings()

    def reset(self):
        with self.store.tx():
            ids = self.store.reset()
        self.store.remove_files(ids)
        return {"reset": True}
