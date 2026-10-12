"""SQLite storage. A session is one JSON document, the same shape the browser simulator keeps; reviewer tokens and
recordings get their own rows so they can be looked up without loading every session. Recordings live on disk.
Users and their logins, the task pack of each pull request, and the results of sandbox runs have tables of their own."""
from contextlib import contextmanager
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created REAL NOT NULL, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tokens (token TEXT PRIMARY KEY, sid TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS media (id TEXT PRIMARY KEY, sid TEXT NOT NULL, mime TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, login TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT,
                                  avatar_url TEXT, github_id INTEGER UNIQUE, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS logins (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS packs (id TEXT PRIMARY KEY, repo TEXT NOT NULL COLLATE NOCASE, number INTEGER NOT NULL, sha TEXT NOT NULL,
                                  status TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, content TEXT, report TEXT);
CREATE INDEX IF NOT EXISTS packs_pr ON packs (repo, number, created);
CREATE TABLE IF NOT EXISTS runs (key TEXT PRIMARY KEY, result TEXT NOT NULL, created REAL NOT NULL);
"""


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.media_dir = self.root / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.depth = 0
        self.conn = sqlite3.connect(self.root / "viva.db", check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        # Sessions from before sign-in have no owner and stay out of every view.
        if "user_id" not in [r[1] for r in self.conn.execute("PRAGMA table_info(sessions)")]:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
        self.conn.execute("CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id, created)")
        with self.tx():
            if self.setting("secret") is None:
                self.set_setting("secret", secrets.token_hex(32))

    @contextmanager
    def tx(self):
        """One writer at a time; everything inside commits together or not at all. A tx inside a tx joins the outer one."""
        with self.lock:
            if self.depth:
                self.depth += 1
                try:
                    yield self
                finally:
                    self.depth -= 1
                return
            self.conn.execute("BEGIN IMMEDIATE")
            self.depth = 1
            try:
                yield self
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            finally:
                self.depth = 0

    def _one(self, sql, *args):
        return self.conn.execute(sql, args).fetchone()

    # ----- sessions -----
    def session(self, sid):
        row = self._one("SELECT state FROM sessions WHERE id = ?", sid)
        return json.loads(row[0]) if row else None

    def sessions(self, user_id):
        """One person's sessions, oldest first."""
        rows = self.conn.execute("SELECT state FROM sessions WHERE user_id = ? ORDER BY created", (user_id,))
        return [json.loads(r[0]) for r in rows]

    def save(self, s):
        self.conn.execute(
            "INSERT INTO sessions (id, created, user_id, state) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET state = excluded.state",
            (s["id"], s["created"], s["user_id"], json.dumps(s)),
        )

    def delete_session(self, sid):
        self.conn.execute("DELETE FROM sessions WHERE id = ?", (sid,))

    # ----- reviewer tokens -----
    def token(self, token):
        row = self._one("SELECT sid, created FROM tokens WHERE token = ?", token)
        return {"sid": row[0], "created": row[1]} if row else None

    def add_token(self, token, sid, created):
        self.conn.execute("INSERT INTO tokens (token, sid, created) VALUES (?, ?, ?)", (token, sid, created))

    def delete_token(self, token):
        self.conn.execute("DELETE FROM tokens WHERE token = ?", (token,))

    # ----- recordings -----
    def media(self, mid):
        row = self._one("SELECT sid, mime FROM media WHERE id = ?", mid)
        return {"sid": row[0], "mime": row[1]} if row else None

    def add_media(self, mid, sid, mime):
        self.conn.execute("INSERT INTO media (id, sid, mime) VALUES (?, ?, ?)", (mid, sid, mime))

    def delete_media(self, mid):
        self.conn.execute("DELETE FROM media WHERE id = ?", (mid,))

    def media_path(self, mid):
        return self.media_dir / mid

    def remove_files(self, ids):
        """After the rows are gone. Returns how many files could not be removed."""
        failed = 0
        for mid in ids:
            try:
                self.media_path(mid).unlink(missing_ok=True)
            except OSError:
                failed += 1
        return failed

    # ----- users and logins (a login row keeps only the hash of the cookie token) -----
    @staticmethod
    def _user(row):
        return {"id": row[0], "login": row[1], "name": row[2], "avatar_url": row[3], "github_id": row[4]} if row else None

    def user(self, uid):
        return self._user(self._one("SELECT id, login, name, avatar_url, github_id FROM users WHERE id = ?", uid))

    def user_by_login(self, login):
        return self._user(self._one("SELECT id, login, name, avatar_url, github_id FROM users WHERE login = ?", login))

    def upsert_user(self, login, name=None, avatar_url=None, github_id=None):
        """A GitHub account is matched by its id (a login can be renamed), anyone else by login."""
        row = github_id is not None and self._one("SELECT id FROM users WHERE github_id = ?", github_id)
        row = row or self._one("SELECT id FROM users WHERE login = ?", login)
        if row:
            self.conn.execute(
                "UPDATE users SET login = ?, name = COALESCE(?, name), avatar_url = COALESCE(?, avatar_url), "
                "github_id = COALESCE(?, github_id) WHERE id = ?", (login, name, avatar_url, github_id, row[0]))
            return self.user(row[0])
        uid = "u_" + secrets.token_hex(8)
        self.conn.execute("INSERT INTO users (id, login, name, avatar_url, github_id, created) VALUES (?, ?, ?, ?, ?, ?)",
                          (uid, login, name, avatar_url, github_id, time.time()))
        return self.user(uid)

    def add_login(self, token_hash, user_id, created, expires):
        self.conn.execute("DELETE FROM logins WHERE expires < ?", (created,))
        self.conn.execute("INSERT INTO logins (token_hash, user_id, created, expires) VALUES (?, ?, ?, ?)",
                          (token_hash, user_id, created, expires))

    def login_user(self, token_hash, at):
        row = self._one("SELECT user_id FROM logins WHERE token_hash = ? AND expires > ?", token_hash, at)
        return self.user(row[0]) if row else None

    def delete_login(self, token_hash):
        self.conn.execute("DELETE FROM logins WHERE token_hash = ?", (token_hash,))

    # ----- task packs: one row per pull request head; content and report are JSON -----
    @staticmethod
    def _pack(row):
        if not row:
            return None
        return {"id": row[0], "repo": row[1], "number": row[2], "sha": row[3], "status": row[4], "created": row[5],
                "updated": row[6], "pack": json.loads(row[7]) if row[7] else None, "report": json.loads(row[8]) if row[8] else None}

    PACK_COLS = "id, repo, number, sha, status, created, updated, content, report"

    def pack(self, pid):
        return self._pack(self._one(f"SELECT {self.PACK_COLS} FROM packs WHERE id = ?", pid))

    def find_pack(self, repo, number, sha=None):
        """The newest pack of a pull request; with a sha (full or a prefix of at least 7), the one for that head."""
        if sha:
            if not re.fullmatch(r"[0-9a-f]{7,40}", sha.lower()):
                return None
            return self._pack(self._one(
                f"SELECT {self.PACK_COLS} FROM packs WHERE repo = ? AND number = ? AND sha LIKE ? || '%' "
                "ORDER BY created DESC, rowid DESC LIMIT 1", repo, number, sha.lower()))
        return self._pack(self._one(
            f"SELECT {self.PACK_COLS} FROM packs WHERE repo = ? AND number = ? ORDER BY created DESC, rowid DESC LIMIT 1", repo, number))

    def put_pack(self, repo, number, sha, status, content=None, report=None):
        """Update the newest row of the same head, or insert one. A ready pack is never changed: sessions keep reading
        it, so preparing the same head again (a re-run check) starts a new row. Returns the pack id."""
        at, sha = time.time(), sha.lower()
        row = self._one("SELECT id, status FROM packs WHERE repo = ? AND number = ? AND sha = ? ORDER BY created DESC, rowid DESC LIMIT 1",
                        repo, number, sha)
        if row and row[1] == "ready":
            row = None
        pid = row[0] if row else "p_" + secrets.token_hex(6)
        if content is not None:
            content = {**content, "id": pid}
        content = json.dumps(content) if content is not None else None
        report = json.dumps(report) if report is not None else None
        if row:
            self.conn.execute("UPDATE packs SET status = ?, updated = ?, content = ?, report = ? WHERE id = ?",
                              (status, at, content, report, pid))
        else:
            self.conn.execute(f"INSERT INTO packs ({self.PACK_COLS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (pid, repo, number, sha, status, at, at, content, report))
        return pid

    # ----- sandbox runs, by the hash of what ran -----
    def run(self, key):
        row = self._one("SELECT result FROM runs WHERE key = ?", key)
        return json.loads(row[0]) if row else None

    def put_run(self, key, result):
        self.conn.execute("INSERT INTO runs (key, result, created) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET "
                          "result = excluded.result, created = excluded.created", (key, json.dumps(result), time.time()))

    # ----- settings -----
    def setting(self, key, default=None):
        row = self._one("SELECT value FROM settings WHERE key = ?", key)
        return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )

    def reset(self):
        """Every session, token and recording; the signing secret stays."""
        ids = [r[0] for r in self.conn.execute("SELECT id FROM media")]
        for table in ("sessions", "tokens", "media"):
            self.conn.execute(f"DELETE FROM {table}")
        self.conn.execute("DELETE FROM settings WHERE key != 'secret'")
        return ids
