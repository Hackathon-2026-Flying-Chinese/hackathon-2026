"""SQLite storage. A session is one JSON document, the same shape the browser simulator keeps; reviewer tokens and
recordings get their own rows so they can be looked up without loading every session. Recordings live on disk."""
from contextlib import contextmanager
import json
from pathlib import Path
import secrets
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created REAL NOT NULL, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tokens (token TEXT PRIMARY KEY, sid TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS media (id TEXT PRIMARY KEY, sid TEXT NOT NULL, mime TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.media_dir = self.root / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.root / "viva.db", check_same_thread=False, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        with self.tx():
            if self.setting("secret") is None:
                self.set_setting("secret", secrets.token_hex(32))

    @contextmanager
    def tx(self):
        """One writer at a time; everything inside commits together or not at all."""
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    def _one(self, sql, *args):
        return self.conn.execute(sql, args).fetchone()

    # ----- sessions -----
    def session(self, sid):
        row = self._one("SELECT state FROM sessions WHERE id = ?", sid)
        return json.loads(row[0]) if row else None

    def sessions(self):
        return [json.loads(r[0]) for r in self.conn.execute("SELECT state FROM sessions ORDER BY created")]

    def save(self, s):
        self.conn.execute(
            "INSERT INTO sessions (id, created, state) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET state = excluded.state",
            (s["id"], s["created"], json.dumps(s)),
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
