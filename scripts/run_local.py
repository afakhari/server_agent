"""Interactive, localhost-only launcher for the Liara Sentinel MVP.

Credentials are read from the terminal, passed only to the child server process,
and never written into this repository or stored by this launcher.
"""
from __future__ import annotations
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")


def choices(mode: str, project: str | None) -> tuple[bool, bool]:
    if mode not in {"demo", "read", "test-cli", "test-api"}:
        raise ValueError("Unknown mode")
    writing = mode.startswith("test-")
    if writing and (not project or not PROJECT_RE.fullmatch(project)):
        raise ValueError("A valid disposable Liara project is required for write mode")
    return mode != "demo", writing


def cli_values(home: str | None, account: str | None, binary: str | None) -> dict[str, str]:
    if os.name == "nt":
        raise ValueError("CLI bridge requires Linux/macOS or WSL2; demo/read work on Windows")
    b = Path(binary or shutil.which("liara") or "").expanduser()
    h = Path(home or "").expanduser()
    if not b.is_absolute() or not b.is_file():
        raise ValueError("CLI executable not found: install @liara/cli@9.6.0 and pass --cli-bin")
    if not h.is_absolute() or not h.is_dir():
        raise ValueError("CLI home must exist; pass --cli-home")
    if h.stat().st_mode & 0o077:
        raise ValueError("CLI home is not private; run chmod 700 on the directory")
    if not account or not re.fullmatch(r"[A-Za-z0-9._@-]{1,100}", account):
        raise ValueError("Provide the exact account alias using --cli-account")
    return {
        "SENTINEL_CLI_DEPLOY_ENABLED": "true",
        "SENTINEL_CLI_BIN": str(b),
        "SENTINEL_CLI_HOME": str(h),
        "SENTINEL_CLI_ACCOUNT": account,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Liara Sentinel on localhost safely")
    parser.add_argument("--mode", choices=["demo", "read", "test-cli", "test-api"], default="demo")
    parser.add_argument("--project", help="Exact, disposable, budget-limited Liara test app")
    parser.add_argument("--cli-home", help="Private HOME with a CLI login")
    parser.add_argument("--cli-account", help="Account alias from liara account whoami")
    parser.add_argument("--cli-bin", help="Absolute Liara CLI executable")
    parser.add_argument("--workspace", default=str(ROOT / "examples"), help="Allowed local source root")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--health-url", help="Optional public HTTPS health URL for --project")
    parser.add_argument("--check", action="store_true", help="Check dependencies; no credentials needed")
    args = parser.parse_args(argv)
    try:
        has_live, writing = choices(args.mode, args.project)
        if args.health_url:
            url = urlsplit(args.health_url)
            if not args.project or url.scheme != "https" or not url.hostname or url.username or url.password or url.port not in (None, 443):
                raise ValueError("--health-url needs --project and a public HTTPS URL without credentials")
        if not 1024 <= args.port <= 65535:
            raise ValueError("Choose an unprivileged port between 1024 and 65535")
        source_root = Path(args.workspace).expanduser().resolve(strict=True)
        if not source_root.is_dir():
            raise ValueError("Workspace must be a directory")
        import fastapi, httpx, uvicorn  # noqa: F401
        if args.check:
            print("OK: local Python dependencies and workspace; no live API checked.")
            return 0
        cli_config = cli_values(args.cli_home, args.cli_account, args.cli_bin) if args.mode == "test-cli" else {}
    except (ValueError, OSError, ImportError) as exc:
        print(f"Preflight failed: {exc}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    for key in (
        "LIARA_API_TOKEN", "SENTINEL_ACCESS_KEY", "SENTINEL_ALLOWED_PROJECTS",
        "SENTINEL_CLI_DEPLOY_ENABLED", "SENTINEL_CLI_BIN",
        "SENTINEL_CLI_HOME", "SENTINEL_CLI_ACCOUNT",
        "SENTINEL_HEALTH_URLS", "SENTINEL_LLM_ENDPOINT",
        "SENTINEL_LLM_API_KEY", "SENTINEL_LLM_MODEL",
    ):
        env.pop(key, None)
    env.update({
        "SENTINEL_ALLOW_LIVE_WRITES": "false",
        "SENTINEL_WORKSPACE": str(source_root),
        "SENTINEL_DB_PATH": str(ROOT / "sentinel.sqlite3"),
    })
    if args.health_url and args.project:
        env["SENTINEL_HEALTH_URLS"] = json.dumps({args.project: args.health_url})
    if has_live:
        token = getpass.getpass("Liara API token (hidden input; never share it in chat): ")
        if len(token.strip()) < 10:
            print("Token not entered; nothing started.", file=sys.stderr)
            return 2
        env["LIARA_API_TOKEN"] = token.strip()
        access_key = secrets.token_urlsafe(32)
        env["SENTINEL_ACCESS_KEY"] = access_key
        print("\nLocal Sentinel access key (paste into your local browser prompt only):")
        print(access_key)
        print("Never include secrets in screenshots, chat, GitHub, or your demo video.\n")
    if writing:
        assert args.project is not None
        print(f"TEST WRITE MODE on '{args.project}'. Writes can incur charges or downtime.")
        answer = input(f"Type ARM {args.project} to enable test-only writes: ").strip()
        if answer != f"ARM {args.project}":
            print("Cancelled. No writes enabled.")
            return 2
        env["SENTINEL_ALLOWED_PROJECTS"] = args.project
        env["SENTINEL_ALLOW_LIVE_WRITES"] = "true"
        env.update(cli_config)
    print(f"Starting {args.mode} on http://127.0.0.1:{args.port}")
    print("Stop with Ctrl+C; no background task is created.")
    try:
        child = subprocess.run(
            [sys.executable, "-m", "uvicorn", "app:app",
             "--host", "127.0.0.1", "--port", str(args.port)],
            cwd=str(ROOT), env=env, check=False,
        )
        return child.returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
