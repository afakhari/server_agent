"""Deployment safety tests. No real server or Liara token is required."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as sentinel_app


def private_profile(monkeypatch, tmp_path):
    frontend = tmp_path / 'frontend' / 'dist'
    (frontend / 'assets').mkdir(parents=True)
    (frontend / 'index.html').write_text('<html>test bundle</html>', encoding='utf8')
    monkeypatch.setattr(sentinel_app, 'ROOT', tmp_path)
    monkeypatch.setenv('SENTINEL_EXPOSURE_MODE', 'private-server')
    monkeypatch.setenv('SENTINEL_ACCESS_KEY', 'safe' + '0123456789ABCDEFghijklmnopqrstuvXYZ')
    (tmp_path / 'persist').mkdir()
    monkeypatch.setenv('SENTINEL_DB_PATH', str(tmp_path / 'persist' / 'sentinel.sqlite3'))
    monkeypatch.setenv('SENTINEL_ALLOW_LIVE_WRITES', 'false')
    monkeypatch.setenv('SENTINEL_CLI_DEPLOY_ENABLED', 'false')
    return frontend


def test_local_mode_keeps_backward_compatibility(monkeypatch):
    monkeypatch.setenv('SENTINEL_EXPOSURE_MODE', 'local')
    monkeypatch.delenv('SENTINEL_ACCESS_KEY', raising=False)
    sentinel_app.validate_server_config()


@pytest.mark.parametrize('value', ['change-me', '', 'REPLACE_WITH_RANDOM_SECRET_MIN_32_CHARACTERS', 'a' * 70])
def test_private_server_rejects_placeholder_and_weak_keys(monkeypatch, tmp_path, value):
    private_profile(monkeypatch, tmp_path)
    monkeypatch.setenv('SENTINEL_ACCESS_KEY', value)
    with pytest.raises(RuntimeError):
        sentinel_app.validate_server_config()


def test_private_server_rejects_missing_frontend(monkeypatch, tmp_path):
    frontend = private_profile(monkeypatch, tmp_path)
    (frontend / 'index.html').unlink()
    with pytest.raises(RuntimeError, match='فرانت'):
        sentinel_app.validate_server_config()


def test_private_server_rejects_relative_db(monkeypatch, tmp_path):
    private_profile(monkeypatch, tmp_path)
    monkeypatch.setenv('SENTINEL_DB_PATH', 'sentinel.sqlite3')
    with pytest.raises(RuntimeError):
        sentinel_app.validate_server_config()


@pytest.mark.parametrize('variable', ['SENTINEL_ALLOW_LIVE_WRITES', 'SENTINEL_CLI_DEPLOY_ENABLED'])
def test_private_server_rejects_enabled_writes(monkeypatch, tmp_path, variable):
    private_profile(monkeypatch, tmp_path)
    monkeypatch.setenv(variable, 'true')
    with pytest.raises(RuntimeError):
        sentinel_app.validate_server_config()


def test_private_profile_can_start_with_healthy_config(monkeypatch, tmp_path):
    private_profile(monkeypatch, tmp_path)
    sentinel_app.validate_server_config()
    with TestClient(sentinel_app.app) as client:
        response = client.get('/healthz')
        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}
        assert "script-src 'self'" in response.headers['content-security-policy']
        assert "'unsafe-inline'" not in response.headers['content-security-policy']


def test_private_profile_never_allows_liara_write_even_if_flags_change(monkeypatch, tmp_path):
    private_profile(monkeypatch, tmp_path)
    monkeypatch.setenv('SENTINEL_ALLOW_LIVE_WRITES', 'true')
    monkeypatch.setenv('LIARA_API_TOKEN', 'not-a-real-token')
    monkeypatch.setenv('SENTINEL_ALLOWED_PROJECTS', 'sandbox-app')
    assert sentinel_app.live_writes_permitted('sandbox-app') is False


def test_docker_release_uses_lockfile_and_non_root():
    root = Path(__file__).resolve().parents[1]
    spec = (root / 'Dockerfile').read_text(encoding='utf8')
    assert 'frontend/package-lock.json' in spec
    assert 'npm ci ' in spec
    assert 'USER 10001:10001' in spec
    assert 'SENTINEL_EXPOSURE_MODE=private-server' in spec
    compose = (root / 'compose.server.yaml').read_text(encoding='utf8')
    assert 'read_only: true' in compose
    assert 'SENTINEL_ALLOW_LIVE_WRITES: "false"' in compose
    assert 'ports:' in compose
    assert '"8000:8000"' not in compose
