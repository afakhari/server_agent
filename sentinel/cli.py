"""Optional official Liara CLI transport for an already-existing disposable app.

Authentication comes from an operator-provisioned, isolated CLI home/account,
NOT from --api-token arguments or the Liara HTTP token environment variable.
No arbitrary shell, commands, paths or model-generated flags are accepted.
The source is staged from a vetted archive rather than deploying a raw repo.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
import time
import secrets

from sentinel.deployer import DeployError, safe_tree
from sentinel.liara import LiaraClient, validate_name
from sentinel.scout import inspect_repo, repo_from_workspace
from sentinel.security import connection, session

ACCOUNT_RE = re.compile(r'^[A-Za-z0-9._@-]{1,100}$')
PLATFORMS = {'python', 'node', 'php', 'docker'}
MAX_CLI_SECONDS = 300


def configured() -> bool:
    return os.getenv('SENTINEL_CLI_DEPLOY_ENABLED', '').lower() == 'true'


def cli_settings() -> tuple[str, str, Path]:
    if not configured():
        raise DeployError('استقرار CLI در این سرور غیرفعال است')
    binary = os.getenv('SENTINEL_CLI_BIN', '')
    account = os.getenv('SENTINEL_CLI_ACCOUNT', '')
    home = Path(os.getenv('SENTINEL_CLI_HOME') or '/nonexistent-sentinel-cli-home')
    if not binary or not Path(binary).is_absolute():
        raise DeployError('مسیر مطلق باینری رسمی CLI باید پیکربندی شود')
    executable = Path(binary)
    if not executable.is_file() or not os.access(binary, os.X_OK):
        raise DeployError('باینری CLI در مسیر مورد انتظار موجود یا اجرایی نیست')
    if not ACCOUNT_RE.fullmatch(account):
        raise DeployError('نام حساب اختصاصی CLI نامعتبر است')
    if not home.is_absolute() or not home.is_dir() or home.is_symlink():
        raise DeployError('پوشه خصوصی حساب CLI وجود ندارد')
    if os.name == 'posix' and home.stat().st_mode & 0o077:
        raise DeployError('مجوز HOME اختصاصی CLI باید خصوصی باشد: chmod 700')
    # Owner-managed directory; npm may install the CLI launcher as a symlink.
    # Never silently fall back to the developer home.
    return str(executable), account, home


def invoke(args: list[str], *, timeout: int, cwd: str | None = None) -> subprocess.CompletedProcess:
    binary, _account, home = cli_settings()
    # Tokens from this API service are not forwarded to child processes.
    env = {
        'HOME': str(home),
        'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
        'LANG': 'C.UTF-8',
        'NO_COLOR': '1',
        'CI': 'true',
    }
    try:
        return subprocess.run(
            [binary, *args], shell=False, stdin=subprocess.DEVNULL,
            cwd=cwd, env=env, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        # A timeout after a write is indeterminate. Never automatically retry.
        raise DeployError('اجرای CLI قطع شد یا زمان آن پایان یافت؛ وضعیت پروژه را قبل از تکرار بررسی کنید') from exc


def preflight() -> dict:
    binary, account, _ = cli_settings()
    version = invoke(['--version'], timeout=10)
    if version.returncode != 0 or '@liara/cli/9.6.0' not in version.stdout:
        raise DeployError('نسخه یا اصالت خروجی Liara CLI قابل تأیید نیست')
    identity = invoke(['account', 'whoami', '--json', '--account', account], timeout=20)
    if identity.returncode != 0:
        raise DeployError('حساب تعریف‌شده در CLI معتبر نیست؛ ابتدا ورود CLI را انجام دهید')
    try:
        whoami = json.loads(identity.stdout)
        identity_data = whoami.get('account') if isinstance(whoami, dict) else None
        actual_alias = identity_data.get('name') if isinstance(identity_data, dict) else None
        email = identity_data.get('email') if isinstance(identity_data, dict) else None
    except (ValueError, TypeError, AttributeError) as exc:
        raise DeployError('قالب JSON هویت CLI معتبر نیست') from exc
    if actual_alias != account or not isinstance(email, str) or '@' not in email:
        raise DeployError('هویت پاسخ CLI با نام حساب تنظیم‌شده مطابقت ندارد')
    if whoami.get('team') is not None:
        raise DeployError('نسخه آزمایشی فقط حساب شخصی CLI را پشتیبانی می‌کند؛ تیم انتخاب‌شده است')
    # Email stays server-side and is never returned in the proposal/UI.
    return {'binary': binary, 'account': account, 'email': email.lower(),
            'version': version.stdout.strip()[:120],
            'authentication': 'cli_account_checked', 'pricing': 'NOT_VERIFIED'}


def _ensure_existing_test_app(project: str) -> None:
    # A test project must already exist and both credentials must belong to
    # the same personal Liara account; mismatched accounts can surprise users.
    cli_identity = preflight()
    with LiaraClient() as client:
        me = client.request('GET', '/v1/me')
        user = me.get('user') if isinstance(me, dict) else None
        email = user.get('email') if isinstance(user, dict) else None
        if not isinstance(email, str) or email.lower() != cli_identity['email']:
            raise DeployError('حساب CLI و توکن API متعلق به یک حساب تأییدشده نیستند')
        app = client.get_project(project)
        if not app.get('project_id'):
            raise DeployError('وجود پروژه آزمایشی از طریق API تأیید نشد')


def validate_cli_archive(data: bytes) -> None:
    """Prevent liara.json from overriding the fixed project account/team/build."""
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        members = [m for m in archive.getmembers() if m.name == 'liara.json']
        for member in members:
            if not member.isfile() or member.size > 100_000:
                raise DeployError('liara.json نامعتبر یا بیش از حد بزرگ است')
            stream = archive.extractfile(member)
            if stream is None:
                raise DeployError('خواندن liara.json ممکن نیست')
            try:
                config = json.loads(stream.read(100_001))
            except (ValueError, UnicodeError) as exc:
                raise DeployError('liara.json معتبر نیست') from exc
            if not isinstance(config, dict) or set(config) - {'platform', 'port'}:
                raise DeployError('liara.json دارای تنظیمات پیشرفته است؛ قبل از CLI به بررسی دستی نیاز دارد')


def approval_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS cli_deploy_approvals (
      id TEXT PRIMARY KEY, actor TEXT NOT NULL, project TEXT NOT NULL,
      relative_path TEXT NOT NULL, archive_sha TEXT NOT NULL,
      account TEXT NOT NULL, platform TEXT NOT NULL, port INTEGER NOT NULL,
      expires_at REAL NOT NULL, used REAL)''')


def make_cli_plan(actor: str, project: str, relative_path: str,
                  platform: str, port: int) -> dict:
    project = validate_name(project)
    if platform not in PLATFORMS or not isinstance(port, int) or not 1 <= port <= 65535:
        raise DeployError('پلتفرم یا پورت نامعتبر است')
    pre = preflight()
    _ensure_existing_test_app(project)
    directory = repo_from_workspace(relative_path)
    inspected = inspect_repo(directory)
    if inspected['platform'] != platform:
        raise DeployError('پلتفرم انتخاب‌شده با فایل‌های پروژه مطابقت ندارد')
    if inspected['port'] is not None and inspected['port'] != port:
        raise DeployError('پورت انتخاب‌شده با فایل liara.json مطابقت ندارد')
    _archive, digest, filenames = safe_tree(directory)
    validate_cli_archive(_archive)
    identifier = 'cli_' + secrets.token_urlsafe(28)
    with session() as conn:
        approval_schema(conn)
        conn.execute(
            'INSERT INTO cli_deploy_approvals VALUES (?,?,?,?,?,?,?,?,?,NULL)',
            (identifier, actor, project, relative_path, digest, pre['account'],
             platform, port, time.time() + 180),
        )
    return {
        'backend': 'cli', 'proposal_id': identifier, 'project': project,
        'platform': platform, 'port': port,
        'plan_id': 'EXISTING_PROJECT_ONLY', 'pricing_status': 'NOT_VERIFIED',
        'cli_account': pre['account'], 'cli_version': pre['version'],
        'source_sha256': digest, 'included_files': filenames,
        'requires_approval': True, 'expires_in_seconds': 180,
        'warning': 'CLI با حساب جداگانه روی همین پروژه موجود انتشار می‌دهد. انتشار ممکن است هزینه داشته باشد؛ هزینه و حساب را در پنل لیارا تأیید کنید. هنوز هیچ اقدامی انجام نشده است.',
    }


def claim_cli_plan(actor: str, identifier: str, project: str) -> tuple[str, str, int, bytes]:
    """Atomically consume immutable approval and recheck source and CLI identity."""
    conn = connection()
    try:
        approval_schema(conn)
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('''SELECT actor, project, relative_path, archive_sha, account,
                                     platform, port, expires_at, used
                              FROM cli_deploy_approvals WHERE id=?''', (identifier,)).fetchone()
        if not row:
            raise DeployError('طرح انتشار CLI وجود ندارد')
        owner, target, path, saved_sha, saved_account, platform, port, expires, used = row
        if owner != actor or target != project:
            raise DeployError('مجوز CLI برای این کاربر یا سرویس نیست')
        if used is not None:
            raise DeployError('این مجوز انتشار قبلاً استفاده شده است')
        if time.time() >= expires:
            raise DeployError('اعتبار طرح انتشار CLI پایان یافته است')
        current_account = cli_settings()[1]
        if saved_account != current_account:
            raise DeployError('حساب CLI پس از تأیید تغییر کرده است')
        data, current_sha, _ = safe_tree(repo_from_workspace(path))
        if current_sha != saved_sha:
            raise DeployError('سورس پس از پیش‌نمایش تغییر کرده است')
        validate_cli_archive(data)
        cur = conn.execute(
            'UPDATE cli_deploy_approvals SET used=? WHERE id=? AND used IS NULL',
            (time.time(), identifier),
        )
        if cur.rowcount != 1:
            raise DeployError('مجوز انتشار قبلاً مصرف شده است')
        conn.commit()
        return target, platform, port, data
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def perform_cli_deploy(project: str, platform: str, port: int, archive: bytes) -> dict:
    """Deploy only whitelisted archived files; do not pass user repo directly to CLI."""
    project = validate_name(project)
    _, account, _home = cli_settings()
    validate_cli_archive(archive)
    _ensure_existing_test_app(project)
    with tempfile.TemporaryDirectory(prefix='sentinel-cli-') as temp:
        root = Path(temp)
        root.chmod(0o700)
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
            for member in tar:
                rel = PurePosixPath(member.name)
                if (not member.isfile() or rel.is_absolute() or '..' in rel.parts or
                    member.issym() or member.islnk()):
                    raise DeployError('فایل ناامن در بسته سورس وجود دارد')
                dest = root.joinpath(*rel.parts)
                if not dest.resolve().is_relative_to(root.resolve()):
                    raise DeployError('مسیر فایل خارج از فضای موقت است')
                dest.parent.mkdir(parents=True, exist_ok=True)
                stream = tar.extractfile(member)
                if stream is None or member.size > 8 * 1024 * 1024:
                    raise DeployError('محتوای بسته انتشار معتبر نیست')
                dest.write_bytes(stream.read(8 * 1024 * 1024 + 1))
                dest.chmod(0o600)
        args = [
            'deploy', '--app', project, '--path', str(root),
            '--platform', platform, '--port', str(port), '--account', account,
            '--detach', '--no-app-logs',
        ]
        completed = invoke(args, timeout=MAX_CLI_SECONDS, cwd=str(root))
    if completed.returncode != 0:
        # Never leak child stdout/stderr, which may contain source or account data.
        raise DeployError('فرمان CLI خطا داد؛ امکان اثرگذاری جزئی وجود دارد. وضعیت واقعی انتشار را قبل از تکرار بررسی کنید')
    return {
        'backend': 'cli', 'project': project,
        'execution': 'SUBMITTED', 'verification': 'NOT_VERIFIED',
        'message': 'CLI فرمان انتشار را پذیرفت؛ آماده‌بودن نسخه و پاسخ HTTP باید جدا از API/پروب بررسی شوند.',
    }
