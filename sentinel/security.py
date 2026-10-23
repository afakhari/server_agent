"""Persistent, one-use, project-bound approvals. No authority is granted by an LLM."""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

DB = Path(__file__).resolve().parents[1] / 'sentinel.sqlite3'


def db_path() -> Path:
    return Path(os.environ.get('SENTINEL_DB_PATH') or str(DB))


def connection() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5, isolation_level=None)
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('''CREATE TABLE IF NOT EXISTS proposals (
      id TEXT PRIMARY KEY, actor TEXT NOT NULL, mode TEXT NOT NULL,
      project TEXT NOT NULL, operation TEXT NOT NULL,
      fingerprint TEXT NOT NULL, params_digest TEXT NOT NULL,
      expires_at REAL NOT NULL, consumed_at REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
      mode TEXT NOT NULL, project TEXT NOT NULL, at REAL NOT NULL)''')
    return conn


@contextmanager
def session():
    conn = connection()
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

def authorized(access_key: str | None) -> bool:
    expected = os.environ.get('SENTINEL_ACCESS_KEY', '')
    return bool(len(expected) >= 24 and access_key and hmac.compare_digest(expected, access_key))


def actor_digest(access_key: str | None, mode: str) -> str:
    if mode == 'demo' and not os.environ.get('SENTINEL_ACCESS_KEY'):
        return 'anonymous-demo'
    if not authorized(access_key):
        raise PermissionError('برای استفاده از حالت واقعی یا عملیات مدیریتی کلید دسترسی معتبر لازم است')
    return hashlib.sha256(access_key.encode()).hexdigest()


def payload_digest(operation: str, project: str, fingerprint: str) -> str:
    value = json.dumps({'operation': operation, 'project': project, 'state': fingerprint}, sort_keys=True)
    return hashlib.sha256(value.encode()).hexdigest()


def create_approval(actor: str, mode: str, project: str, operation: str, fingerprint: str) -> str:
    if operation != 'restart':
        raise PermissionError('عملیات در فهرست مجاز نیست')
    identifier = secrets.token_urlsafe(32)
    with session() as conn:
        conn.execute('INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,NULL)',
                     (identifier, actor, mode, project, operation, fingerprint,
                      payload_digest(operation, project, fingerprint), time.time() + 180))
    return identifier


def inspect_approval(identifier: str, actor: str, confirmation: str) -> dict:
    """Read only; does not consume. Do not use its result as permission to mutate."""
    with session() as conn:
        row = conn.execute('SELECT actor,mode,project,operation,fingerprint,params_digest,expires_at,consumed_at FROM proposals WHERE id=?', (identifier,)).fetchone()
    if not row:
        raise LookupError('پیشنهاد وجود ندارد')
    owner, mode, project, operation, fingerprint, digest, expires, consumed = row
    if owner != actor or confirmation != project:
        raise PermissionError('مالک یا پروژه با مجوز مطابقت ندارد')
    if consumed is not None:
        raise RuntimeError('مجوز قبلاً مصرف شده است')
    if time.time() >= expires:
        raise TimeoutError('مهلت مجوز منقضی شده است')
    if digest != payload_digest(operation, project, fingerprint):
        raise PermissionError('پارامترهای مجوز تغییر کرده‌اند')
    return {'mode': mode, 'project': project, 'operation': operation, 'fingerprint': fingerprint}


def consume_approval(identifier: str, actor: str, confirmation: str, fingerprint: str) -> dict:
    """Atomic compare-and-swap prevents double execution across workers."""
    conn = connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT actor,mode,project,operation,fingerprint,params_digest,expires_at,consumed_at FROM proposals WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise LookupError('پیشنهاد وجود ندارد')
        owner, mode, project, operation, bound_state, digest, expires, consumed = row
        if owner != actor or project != confirmation:
            raise PermissionError('مجوز با این کاربر یا پروژه تطابق ندارد')
        if consumed is not None:
            raise RuntimeError('این مجوز قبلاً استفاده شده است')
        if time.time() >= expires:
            raise TimeoutError('اعتبار مجوز پایان یافته است')
        if bound_state != fingerprint or digest != payload_digest(operation, project, fingerprint):
            raise ValueError('وضعیت سرویس تغییر کرده است؛ بررسی مجدد لازم است')
        if operation != 'restart':
            raise PermissionError('عملیات مجاز نیست')
        conn.execute('UPDATE proposals SET consumed_at=? WHERE id=? AND consumed_at IS NULL', (time.time(), identifier))
        conn.commit()
        return {'mode': mode, 'project': project, 'operation': operation}
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def audit(event: str, mode: str, project: str):
    with session() as conn:
        conn.execute('INSERT INTO audit(event,mode,project,at) VALUES (?,?,?,?)', (event, mode, project, time.time()))


def read_audit(limit: int = 30) -> list[dict]:
    with session() as conn:
        rows = conn.execute('SELECT event,mode,project,at FROM audit ORDER BY id DESC LIMIT ?', (min(limit, 100),)).fetchall()
    return [{'event': e, 'mode': m, 'project': p, 'at': t} for e, m, p, t in rows]
