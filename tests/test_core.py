"""Focused offline smoke tests: no CI and no Liara token required."""
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from server_agent.diagnosis import analyze, demo_snapshot, redact
from server_agent.liara import LiaraClient, LiaraError
from server_agent.scout import scan
from server_agent.store import Ledger, StoreError
from server_agent.verify import safe_probe_url

def test_diagnosis_has_evidence():
    result = analyze(demo_snapshot("env"))
    ids = {e["id"] for e in result["evidence"]}
    assert result["hypotheses"][0]["code"] == "missing_env"
    assert all(set(h["supporting_evidence_ids"]) <= ids for h in result["hypotheses"])
    assert not result["proposals"]

def test_no_unnecessary_restart():
    assert not analyze(demo_snapshot("healthy"))["proposals"]
    assert not analyze(demo_snapshot("memory"))["proposals"]
    assert analyze(demo_snapshot("transient"))["proposals"][0]["requires_approval"]

def test_redaction():
    sample = "Bearer verylongsupersecrettoken token=abc123456 password=hidden"
    data = redact(sample)
    assert "verylongsupersecrettoken" not in data
    assert "abc123456" not in data
    assert "hidden" not in data

def test_liara_contract_and_env_mask():
    def handler(request):
        path = request.url.path
        if path.endswith("/logs"):
            assert request.url.params.get("since")
            return httpx.Response(200, json=[{"message": "error"}])
        if path.endswith("/releases"):
            assert request.url.params.get("page") == "1"
            return httpx.Response(200, json={"releases":[],"currentRelease":"a"})
        if path.endswith("/projects/demo"):
            return httpx.Response(200, json={"project":{"project_id":"demo","status":"running",
                "envs":[{"key":"DATABASE_URL","value":"SHOULD_NOT_LEAK"}]}})
        if path.endswith("/metrics/summary"):
            return httpx.Response(200, json={})
        if path.endswith("/events"):
            return httpx.Response(200, json={"data":[]})
        if path.endswith("/applets"):
            return httpx.Response(200, json={"applets":[]})
        return httpx.Response(404)
    client = LiaraClient(token="test", transport=httpx.MockTransport(handler))
    snap = client.snapshot("demo")
    client.close()
    assert snap["project"]["environment_keys"] == ["DATABASE_URL"]
    assert "SHOULD_NOT_LEAK" not in repr(snap)

def test_bad_project():
    from server_agent.liara import project_name
    with pytest.raises(LiaraError):
        project_name("../../oops")

def test_single_use_and_target_binding(tmp_path):
    store = Ledger(str(tmp_path / "data.sqlite3"))
    token = store.propose("demo","demo-shop","restart","hash",{"action":"restart"})
    with pytest.raises(StoreError):
        store.consume(token["proposal_id"],"wrong")
    assert store.consume(token["proposal_id"],"demo-shop")["action"] == "restart"
    with pytest.raises(StoreError):
        store.consume(token["proposal_id"],"demo-shop")

def test_probe_not_ssrf(monkeypatch):
    monkeypatch.setenv("LIARA_ALLOWED_HEALTH_HOSTS","app.example.com")
    for url in ("http://127.0.0.1/", "https://localhost/", "https://169.254.169.254/"):
        with pytest.raises(ValueError):
            safe_probe_url(url)

def test_demo_http_end_to_end(monkeypatch,tmp_path):
    import app as service
    monkeypatch.setattr(service,"ledger",Ledger(str(tmp_path/"http.sqlite3")))
    monkeypatch.delenv("SENTINEL_ACCESS_KEY",raising=False)
    client = TestClient(service.app)
    assert client.get("/").status_code == 200
    r = client.post("/api/inspect",json={"mode":"demo","scenario":"transient"})
    assert r.status_code == 200
    token = r.json()["proposals"][0]["approval"]
    body = {"proposal_id":token["proposal_id"],"confirm_project":"demo-shop"}
    assert client.post("/api/approve",json=body).json()["execution"] == "SIMULATED"
    assert client.post("/api/approve",json=body).status_code == 409

def test_live_requires_auth(monkeypatch):
    import app as service
    monkeypatch.delenv("SENTINEL_ACCESS_KEY",raising=False)
    client=TestClient(service.app)
    assert client.get("/api/projects").status_code == 403
    assert client.post("/api/inspect",json={"mode":"live","project":"demo"}).status_code == 403

def test_demo_deploy(monkeypatch,tmp_path):
    import app as service
    monkeypatch.setattr(service,"ledger",Ledger(str(tmp_path/"deploy.sqlite3")))
    monkeypatch.delenv("SENTINEL_ACCESS_KEY",raising=False)
    client=TestClient(service.app)
    result=client.post("/api/deploy/plan",json={"mode":"demo"})
    assert result.status_code == 200
    assert result.json()["analysis"]["port"] == 8000
    token=result.json()["approval"]
    execution=client.post("/api/approve",json={
        "proposal_id":token["proposal_id"],"confirm_project":"demo-shop"})
    assert execution.status_code == 200
    assert execution.json()["execution"] == "SIMULATED"

def test_scout_static():
    p=Path(__file__).resolve().parents[1]/"examples"/"fastapi-shop"
    result=scan(p)
    assert result["deployment_ready"]
    assert "APP_ENV" in result["env_key_names"]

def test_provision_plan_demo(monkeypatch,tmp_path):
    import app as service
    monkeypatch.setattr(service,"ledger",Ledger(str(tmp_path/"new.sqlite3")))
    monkeypatch.delenv("SENTINEL_ACCESS_KEY",raising=False)
    client=TestClient(service.app)
    plan=client.post("/api/provision/plan",json={
        "mode":"demo","project":"demo-shop","plan_id":"test-plan","platform":"python"})
    assert plan.status_code == 200
    assert plan.json()["price"] == "UNVERIFIED"
    token=plan.json()["approval"]
    accepted=client.post("/api/approve",json={
        "proposal_id":token["proposal_id"],"confirm_project":"demo-shop"})
    assert accepted.status_code == 200
    assert accepted.json()["execution"] == "SIMULATED"

def test_release_time_correlation():
    snap=demo_snapshot("release")
    snap.pop("recent_change")
    snap["releases"]["releases"][0]["createdAt"]="2026-10-23T11:55:00Z"
    report=analyze(snap)
    assert "release_correlation" in [h["code"] for h in report["hypotheses"]]
