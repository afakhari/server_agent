"""Small durable single-operator action ledger. Denies replay and payload tampering."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

def digest(payload: object) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()

class StoreError(Exception):
    pass

class Ledger:
    def __init__(self, path: str):
        db = Path(path)
        db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db), check_same_thread=False, isolation_level=None,
                                    timeout=10)
        self.lock = threading.RLock()
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS operations (
            id TEXT PRIMARY KEY, mode TEXT NOT NULL, project TEXT NOT NULL,
            action TEXT NOT NULL, state_digest TEXT NOT NULL, payload_digest TEXT NOT NULL,
            payload TEXT NOT NULL, status TEXT NOT NULL, expires REAL NOT NULL,
            created TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}'
        )""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS audit (
            id TEXT PRIMARY KEY, time TEXT NOT NULL, event TEXT NOT NULL,
            operation_id TEXT, project TEXT, detail TEXT NOT NULL
        )""")

    def log(self, event, operation_id=None, project=None, detail=None):
        with self.lock:
            self.conn.execute("INSERT INTO audit VALUES (?,?,?,?,?,?)",
                              (uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(),
                               event, operation_id, project,
                               json.dumps(detail or {}, ensure_ascii=False)))

    def propose(self, mode, project, action, state_digest, payload, ttl=180):
        id_ = uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        with self.lock:
            self.conn.execute("""INSERT INTO operations
             (id, mode, project, action, state_digest, payload_digest, payload,
              status, expires, created, detail) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
             (id_, mode, project, action, state_digest, digest(payload),
              json.dumps(payload, ensure_ascii=False, sort_keys=True),
              "awaiting_approval", time.time() + ttl, created, "{}"))
            self.log("proposal_created", id_, project, {"action": action, "mode": mode})
        return {"proposal_id": id_, "expires_in_seconds": ttl, "action": action,
                "project": project, "mode": mode}

    def get(self, id_):
        with self.lock:
            row = self.conn.execute("SELECT * FROM operations WHERE id=?", (id_,)).fetchone()
        if not row:
            raise StoreError("operation_not_found")
        keys = ("id", "mode", "project", "action", "state_digest", "payload_digest",
                "payload", "status", "expires", "created", "detail")
        result = dict(zip(keys, row))
        result["payload"] = json.loads(result["payload"])
        result["detail"] = json.loads(result["detail"])
        return result

    def consume(self, id_, confirm_project: str):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                row = self.get(id_)
                if row["status"] != "awaiting_approval":
                    raise StoreError("approval_already_used")
                if row["project"] != confirm_project:
                    raise StoreError("approval_project_mismatch")
                if row["expires"] < time.time():
                    raise StoreError("approval_expired")
                if digest(row["payload"]) != row["payload_digest"]:
                    raise StoreError("approval_payload_modified")
                cur = self.conn.execute(
                    "UPDATE operations SET status='executing' WHERE id=? AND status='awaiting_approval'",
                    (id_,))
                if cur.rowcount != 1:
                    raise StoreError("approval_already_used")
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
        self.log("approval_consumed", id_, row["project"], {"action": row["action"]})
        return row

    def status(self, id_, status, detail=None):
        allowed = {"executing", "submitted", "verified", "failed", "inconclusive", "blocked"}
        if status not in allowed:
            raise StoreError("invalid_status")
        sanitized = json.dumps(detail or {}, ensure_ascii=False)
        with self.lock:
            self.conn.execute("UPDATE operations SET status=?,detail=? WHERE id=?",
                              (status, sanitized, id_))
        self.log("operation_" + status, id_, detail.get("project") if detail else None,
                 {"status": status})

    def history(self, limit=20):
        with self.lock:
            rows = self.conn.execute("""SELECT time,event,operation_id,project FROM audit
                                        ORDER BY time DESC LIMIT ?""", (limit,)).fetchall()
        return [{"at": a, "event": b, "operation_id": c, "project": d} for a,b,c,d in rows]
