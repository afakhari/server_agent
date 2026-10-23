"""Guarded API deployment of a small local source tree to a disposable Liara app.

This is an unverified live integration until exercised on a real test account.
Unknown billing, plan IDs and source archive compatibility must be checked first.
"""
from __future__ import annotations
import gzip
import hashlib
import io
import os
from pathlib import Path
import re
import secrets
import sqlite3
import tarfile
import time

from sentinel.liara import LiaraClient, LiaraError, validate_name
from sentinel.scout import inspect_repo, repo_from_workspace
from sentinel.security import connection, session

FILE_EXTENSIONS = {'.py', '.txt', '.json', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.yml', '.yaml', '.md', '.lock', '.toml', '.ini', '.sh'}
EXCLUDED_DIRS = {'.git', '.venv', 'venv', 'node_modules', '.next', '__pycache__', 'dist', 'build', '.pytest_cache', 'secrets', '.idea'}
EXCLUDED_FILES = {'.env', '.env.local', '.env.production', '.npmrc', '.pypirc', '.git-credentials', 'id_rsa', 'id_ed25519'}
PLAN_RE = re.compile(r'^[A-Za-z0-9._-]{1,80}$')
MAX_ARCHIVE = 8 * 1024 * 1024
MAX_FILES = 300

class DeployError(ValueError):
    pass


def safe_tree(folder: Path) -> tuple[bytes, str, list[str]]:
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise DeployError('پوشه سورس معتبر نیست')
    buffer = io.BytesIO()
    total = 0
    filenames = []
    with gzip.GzipFile(fileobj=buffer, mode='wb', mtime=0, filename='') as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as archive:
            for base, dirs, names in os.walk(folder, topdown=True, followlinks=False):
                dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.') and not (Path(base) / d).is_symlink())
                for name in sorted(names):
                    path = Path(base) / name
                    relative = path.relative_to(folder)
                    if path.is_symlink() or not path.is_file():
                        continue
                    if name in EXCLUDED_FILES or name.startswith('.env') or name.startswith('id_'):
                        continue
                    if name.startswith('.') or (path.suffix.lower() not in FILE_EXTENSIONS and name not in {'Dockerfile', 'Procfile'}):
                        continue
                    if len(filenames) >= MAX_FILES:
                        raise DeployError('تعداد فایل‌های بسته بیش از حد مجاز است')
                    size = path.stat().st_size
                    total += size
                    if total > MAX_ARCHIVE:
                        raise DeployError('حجم بسته بیش از حد مجاز است')
                    contents = path.read_bytes()
                    if b'-----BEGIN PRIVATE KEY-----' in contents or b'-----BEGIN OPENSSH PRIVATE KEY-----' in contents:
                        raise DeployError('کلید خصوصی در سورس پیدا شد؛ بسته ارسال نمی‌شود')
                    info = tarfile.TarInfo(relative.as_posix())
                    info.size, info.mtime, info.mode = len(contents), 0, 0o644
                    archive.addfile(info, io.BytesIO(contents))
                    filenames.append(relative.as_posix())
    if not filenames:
        raise DeployError('فایل قابل انتشار در سورس پیدا نشد')
    data = buffer.getvalue()
    return data, hashlib.sha256(data).hexdigest(), filenames


def proposal_conn(conn: sqlite3.Connection):
    conn.execute('''CREATE TABLE IF NOT EXISTS deploy_approvals (
        id TEXT PRIMARY KEY, actor TEXT NOT NULL, project TEXT NOT NULL,
        relative_path TEXT NOT NULL, archive_sha TEXT NOT NULL,
        plan_id TEXT NOT NULL, platform TEXT NOT NULL, port INTEGER NOT NULL,
        expires_at REAL NOT NULL, used REAL)''')


def make_plan(actor: str, project: str, relative_path: str, plan_id: str, platform: str, port: int) -> dict:
    validate_name(project)
    if not PLAN_RE.fullmatch(plan_id):
        raise DeployError('شناسه پلن نامعتبر است')
    if platform not in {'python', 'node', 'php', 'docker'} or not 1 <= port <= 65535:
        raise DeployError('پلتفرم یا پورت نامعتبر است')
    directory = repo_from_workspace(relative_path)
    scan = inspect_repo(directory)
    if scan['platform'] != platform:
        raise DeployError('پلتفرم با تحلیل سورس مطابقت ندارد؛ ابتدا تنظیمات را بررسی کنید')
    if scan['port'] is not None and scan['port'] != port:
        raise DeployError('پورت با پیکربندی سورس مطابقت ندارد')
    _, digest, filenames = safe_tree(directory)
    # A separate explicit mode is required for an already-created application.
    if plan_id == 'existing':
        with LiaraClient() as client:
            current = client.get_project(project)
        if current.get('type') != platform:
            raise DeployError('پلتفرم پروژه موجود با سورس مطابقت ندارد')
        if not current.get('project_id'):
            raise DeployError('شناسه پروژه موجود از API تأیید نشده است')
    identifier = secrets.token_urlsafe(32)
    with session() as conn:
        proposal_conn(conn)
        conn.execute('INSERT INTO deploy_approvals VALUES (?,?,?,?,?,?,?,?,?,NULL)',
                     (identifier, actor, project, relative_path, digest, plan_id, platform, port, time.time() + 180))
    return {'proposal_id': identifier, 'project': project, 'platform': platform, 'port': port,
            'plan_id': plan_id, 'source_sha256': digest, 'included_files': filenames,
            'requires_approval': True, 'expires_in_seconds': 180,
            'warning': ('فقط انتشار روی پروژه موجود: پروژه جدید ساخته نمی‌شود؛ سورس برنامه ممکن است جایگزین شود و مصرف منابع هزینه داشته باشد.'
                        if plan_id == 'existing' else
                        'ایجاد برنامه جدید و انتشار ممکن است هزینه داشته باشد؛ شناسه و قیمت پلن باید در حساب لیارا تأیید شوند.')}


def claim_plan(actor: str, identifier: str, project: str):
    """Atomic consume; immutable parameters come from SQLite, never the execute request."""
    conn = connection()
    try:
        proposal_conn(conn)
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT actor,project,relative_path,archive_sha,plan_id,platform,port,expires_at,used FROM deploy_approvals WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise DeployError('طرح استقرار پیدا نشد')
        owner, target, relative_path, digest, plan_id, platform, port, expiry, used = row
        if actor != owner or project != target:
            raise DeployError('مجوز به مالک یا پروژه دیگری تعلق دارد')
        if used is not None:
            raise DeployError('تأیید قبلاً استفاده شده است')
        if time.time() >= expiry:
            raise DeployError('مهلت تأیید استقرار پایان یافته است')
        directory = repo_from_workspace(relative_path)
        contents, current_sha, _ = safe_tree(directory)
        if current_sha != digest:
            raise DeployError('سورس از زمان صدور تأیید تغییر کرده است')
        conn.execute('UPDATE deploy_approvals SET used=? WHERE id=? AND used IS NULL', (time.time(), identifier))
        conn.commit()
        return target, plan_id, platform, port, contents
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def perform_deploy(project: str, plan_id: str, platform: str, port: int, contents: bytes) -> dict:
    """Explicitly choose existing-app upload or new-app create, then release."""
    stage = 'check-project'
    with LiaraClient() as client:
        try:
            if plan_id == 'existing':
                current = client.get_project(project)
                if not current.get('project_id') or current.get('type') != platform:
                    raise DeployError('پلتفرم یا شناسه پروژه موجود معتبر نیست')
            else:
                # Creating a new app requires an independently approved plan ID.
                stage = 'create-project'
                client.request('POST', '/v1/projects', json={
                    'name': project, 'planID': plan_id, 'platform': platform})
            stage = 'upload-source'
            result = client.http.post(f'/v2/projects/{project}/sources', files={'file': ('source.tar.gz', contents, 'application/gzip')})
            result.raise_for_status()
            if not isinstance(result.json(), dict) or not result.json().get('sourceID'):
                raise DeployError('آپلود شناسه sourceID معتبر برنگرداند')
            source_id = result.json()['sourceID']
            stage = 'create-release'
            release = client.request('POST', f'/v2/projects/{project}/releases', json={
                'sourceID': source_id, 'port': port, 'type': platform})
            if not isinstance(release, dict) or not release.get('releaseID'):
                raise DeployError('انتشار شناسه releaseID معتبر برنگرداند')
            return {'execution': 'SUBMITTED', 'verification': 'NOT_VERIFIED',
                    'project': project, 'release_id': release['releaseID'],
                    'message': ('درخواست انتشار روی پروژه موجود ارسال شد؛ آماده‌بودن نسخه و پاسخ HTTP باید جدا بررسی شوند.'
                                if plan_id == 'existing' else
                                'درخواست ایجاد پروژه و انتشار ارسال شد؛ سلامت وب‌سایت هنوز تأیید نشده است.')}
        except (LiaraError, httpx.HTTPError, ValueError, KeyError) as exc:
            # Unknown partial writes are expected after transport failure. Never auto-delete.
            raise DeployError(f'مرحله {stage} ناموفق یا نامعلوم است ({type(exc).__name__})؛ وضعیت پروژه را پیش از هر تکرار بررسی کنید') from exc

import httpx
