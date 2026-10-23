"""Read-only release gate for the public, simulated competition showcase.

Run after npm install/build and after creating PRIVATE env files.
Does not print, transmit, or run any sensitive values.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = (
    "Dockerfile", "compose.server.yaml", "deploy/server/Caddyfile.competition",
    "frontend/dist/index.html", "frontend/package-lock.json",
)


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        data[key.strip()] = value
    return data


def is_tracked(path: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", path],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=3
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        # Unknown VCS state: block the release.
        return True


def evaluate(base: Path = ROOT) -> list[tuple[str, bool]]:
    results: list[tuple[str, bool]] = []
    for name in EXPECTED:
        results.append((f"required file: {name}", (base / name).is_file()))
    results.append((
        "built frontend assets",
        (base / "frontend" / "dist" / "assets").is_dir()
    ))
    for filename in ("app.env", "caddy.env"):
        path = base / "deploy" / "server" / filename
        results.append((f"private env file present: {filename}", path.is_file()))
        if os.name == "posix" and path.is_file():
            results.append((
                f"private env permissions: {filename}",
                path.stat().st_mode & 0o077 == 0
            ))
    app = read_env(base / "deploy/server/app.env")
    key = app.get("SENTINEL_ACCESS_KEY", "")
    results.append((
        "non-placeholder Sentinel secret",
        len(key) >= 32 and len(set(key)) >= 16 and
        not key.upper().startswith("REPLACE_")
    ))
    caddy = read_env(base / "deploy/server/caddy.env")
    domain = caddy.get("SENTINEL_DOMAIN", "")
    results.append((
        "real HTTPS DNS name",
        bool(re.fullmatch(r"[a-zA-Z0-9.-]{4,253}", domain)) and
        "." in domain and not domain.endswith((".example.com", ".localhost"))
    ))
    public_proxy = base / "deploy/server/Caddyfile.competition"
    proxy_config = public_proxy.read_text(encoding="utf-8") if public_proxy.is_file() else ""
    results.append((
        "competition proxy blocks operator routes",
        "basic_auth" not in proxy_config
        and "@operatorOnly path" in proxy_config
        and "respond @operatorOnly" in proxy_config
        and "reverse_proxy sentinel:8000" in proxy_config
    ))
    results.append((
        "no live writes on server",
        app.get("SENTINEL_ALLOW_LIVE_WRITES", "false").lower() != "true" and
        app.get("SENTINEL_CLI_DEPLOY_ENABLED", "false").lower() != "true"
    ))
    if base == ROOT:
        for name in ("deploy/server/app.env", "deploy/server/caddy.env"):
            results.append((f"not tracked by git: {name}", not is_tracked(name)))
    return results


def main() -> int:
    status = evaluate()
    for label, passed in status:
        print(("[PASS] " if passed else "[BLOCK] ") + label)
    if all(passed for _, passed in status):
        print("Preflight file/configuration gates passed. Runtime E2E and HTTPS checks are still required.")
        return 0
    print("RELEASE NO-GO: resolve all blockers before composing/staging.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
