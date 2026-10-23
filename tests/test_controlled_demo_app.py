"""Check real HTTP app behavior without Liara credentials."""
import importlib.util
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def load_demo():
    path = Path(__file__).resolve().parents[1] / 'examples' / 'fastapi-shop' / 'main.py'
    spec = importlib.util.spec_from_file_location('sentinel_demo_sample', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_demo_healthy_by_default(monkeypatch):
    monkeypatch.delenv('SENTINEL_REQUIRE_DEMO_FLAG', raising=False)
    client = TestClient(load_demo().app)
    assert client.get('/health').status_code == 200
    assert client.get('/').status_code == 200


def test_demo_controlled_failure_and_recovery(monkeypatch):
    monkeypatch.setenv('SENTINEL_REQUIRE_DEMO_FLAG', 'true')
    monkeypatch.delenv('SENTINEL_DEMO_FLAG', raising=False)
    with pytest.raises(RuntimeError, match='missing environment variable SENTINEL_DEMO_FLAG'):
        load_demo().health()
    monkeypatch.setenv('SENTINEL_DEMO_FLAG', 'ready')
    client = TestClient(load_demo().app)
    assert client.get('/health').status_code == 200
