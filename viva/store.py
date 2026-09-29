import json
from pathlib import Path
import sqlite3


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize(path):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS studies (
            code TEXT PRIMARY KEY, settings TEXT NOT NULL, allocation TEXT NOT NULL, next_slot INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
            stage TEXT NOT NULL, task_id TEXT NOT NULL, answer TEXT NOT NULL, result TEXT NOT NULL,
            started REAL NOT NULL, submitted REAL NOT NULL, wall_seconds REAL NOT NULL,
            excluded INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
            kind TEXT NOT NULL, recorded REAL NOT NULL, payload TEXT NOT NULL
        );
        ''')


def read_state(db, sid):
    row = db.execute("SELECT state FROM sessions WHERE id=?", (sid,)).fetchone()
    return json.loads(row["state"]) if row else None


def save(db, state):
    db.execute("INSERT INTO sessions VALUES (?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state",
               (state["id"], json.dumps(state)))


def event(db, sid, kind, now, payload=None):
    db.execute("INSERT INTO events(session_id,kind,recorded,payload) VALUES (?,?,?,?)",
               (sid, kind, now, json.dumps(payload or {})))
