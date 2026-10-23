"""Offline tests for server release gates. No real secrets or DNS calls."""
from pathlib import Path

from scripts.check_server_release import evaluate


def populate(root: Path):
    names = [
        "Dockerfile", "compose.server.yaml", "deploy/server/Caddyfile.competition",
        "frontend/dist/index.html", "frontend/package-lock.json",
    ]
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("sample", encoding="utf8")
    (root / "deploy/server/Caddyfile.competition").write_text(
        "example.com {\n  @operatorOnly path /api/projects\n"
        "  respond @operatorOnly 403\n  reverse_proxy sentinel:8000\n}\n",
        encoding="utf8"
    )
    (root / "frontend/dist/assets").mkdir(parents=True)
    app_env = root / "deploy/server/app.env"
    app_env.write_text(
        "SENTINEL_ACCESS_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789\n"
        "SENTINEL_ALLOW_LIVE_WRITES=false\n"
    )
    caddy_env = root / "deploy/server/caddy.env"
    caddy_env.write_text(
        "SENTINEL_DOMAIN=private.test-site.net\n"
        "SENTINEL_BASIC_AUTH_HASH='$2b$12$" + "A" * 53 + "'\n"
    )
    app_env.chmod(0o600)
    caddy_env.chmod(0o600)
    return app_env, caddy_env


def test_release_gate_requires_real_build_and_operator_secrets(tmp_path):
    status = dict(evaluate(tmp_path))
    assert status["required file: frontend/dist/index.html"] is False
    assert status["non-placeholder Sentinel secret"] is False
    assert status["competition proxy blocks operator routes"] is False


def test_release_gate_passes_safe_synthetic_fixture(tmp_path):
    populate(tmp_path)
    assert all(ok for _, ok in evaluate(tmp_path))


def test_release_gate_rejects_write_toggle_and_placeholder(tmp_path):
    app_env, _ = populate(tmp_path)
    app_env.write_text(
        "SENTINEL_ACCESS_KEY=REPLACE_WITH_RANDOM_SECRET_MIN_32_CHARACTERS\n"
        "SENTINEL_ALLOW_LIVE_WRITES=true\n"
    )
    assert dict(evaluate(tmp_path))["non-placeholder Sentinel secret"] is False
    assert dict(evaluate(tmp_path))["no live writes on server"] is False
