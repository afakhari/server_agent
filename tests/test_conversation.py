"""Conversation-level tests: persistence, orchestration, isolation, SSE, HITL."""
import pytest
from fastapi.testclient import TestClient

import app
from sentinel import conversation


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "chat.sqlite3"))
    monkeypatch.delenv("SENTINEL_ACCESS_KEY", raising=False)
    monkeypatch.delenv("SENTINEL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SENTINEL_CHAT_LLM_ENABLED", raising=False)
    monkeypatch.setattr(conversation, "_GRAPH", None)


@pytest.fixture
def client():
    return TestClient(app.app)


def send(client, message, **extra):
    return client.post("/api/chat/messages", json={"message": message, "mode": "demo", **extra})


def test_natural_language_inspection_and_evidence(client):
    response = send(client, "سایتم خطای ۵۰۰ دارد")
    assert response.status_code == 200
    data = response.json()
    assert data["thread_id"]
    assert data["ui"]["type"] == "inspection"
    report = data["ui"]["report"]
    assert report["mode"] == "demo"
    assert report["evidence"]
    assert any(h["evidence_ids"] for h in report["hypotheses"])
    assert report["limitations"]
    saved = client.get("/api/chat/threads/" + data["thread_id"]).json()
    assert len(saved["messages"]) == 2
    assert saved["messages"][0]["role"] == "user"
    assert saved["messages"][1]["role"] == "assistant"


def test_thread_context_and_routing(client):
    first = send(client, "پروژه‌ام را منتشر کن").json()
    assert first["ui"]["type"] == "deploy"
    second = send(client, "فهرست برنامه‌های حساب", thread_id=first["thread_id"]).json()
    assert second["thread_id"] == first["thread_id"]
    assert second["ui"]["type"] == "projects"
    assert len(client.get("/api/chat/threads/" + first["thread_id"]).json()["messages"]) == 4


def test_thread_isolation():
    thread_id, _ = conversation.open_thread("owner", "demo", None, None)
    with pytest.raises(PermissionError):
        conversation.thread_data("attacker", thread_id)
    with pytest.raises(PermissionError):
        conversation.open_thread("attacker", "demo", thread_id, None)


def test_demo_never_claims_live_deploy(client):
    data = send(client, "می‌خواهم برنامه‌ام را دیپلوی کنم").json()
    assert data["ui"]["type"] == "deploy"
    assert data["ui"]["mode"] == "demo"
    assert "شبیه‌سازی" in data["answer"] or "نمایشی" in data["answer"]


def test_restart_approval_is_project_bound_and_one_use(client):
    data = send(client, "خطای 500 بعد از crash").json()
    proposal = data["ui"]["report"]["proposals"][0]
    bad = client.post("/api/chat/approval", json={
        "thread_id": data["thread_id"], "proposal_id": proposal["proposal_id"],
        "confirm_project": "another-project", "approved": True
    })
    assert bad.status_code in (403, 409)
    good = client.post("/api/chat/approval", json={
        "thread_id": data["thread_id"], "proposal_id": proposal["proposal_id"],
        "confirm_project": "demo-shop", "approved": True
    })
    assert good.status_code == 200
    assert good.json()["ui"]["type"] == "execution"
    assert good.json()["ui"]["result"]["mode"] == "demo"
    assert good.json()["ui"]["result"]["execution"] == "SIMULATED"
    repeat = client.post("/api/chat/approval", json={
        "thread_id": data["thread_id"], "proposal_id": proposal["proposal_id"],
        "confirm_project": "demo-shop", "approved": True
    })
    assert repeat.status_code != 200


def test_unrelated_thread_cannot_approve(client):
    report = send(client, "مشکل در سرویس و خطای 500").json()
    other = send(client, "سلام").json()
    proposal = report["ui"]["report"]["proposals"][0]
    response = client.post("/api/chat/approval", json={
        "thread_id": other["thread_id"], "proposal_id": proposal["proposal_id"],
        "confirm_project": "demo-shop", "approved": True
    })
    assert response.status_code == 403


def test_cancel_invalidates_approval(client):
    data = send(client, "سایتم crash شده و خطا دارد").json()
    proposal = data["ui"]["report"]["proposals"][0]
    cancel = client.post("/api/chat/approval", json={
        "thread_id": data["thread_id"], "proposal_id": proposal["proposal_id"],
        "confirm_project": "demo-shop", "approved": False
    })
    assert cancel.status_code == 200
    again = client.post("/api/chat/approval", json={
        "thread_id": data["thread_id"], "proposal_id": proposal["proposal_id"],
        "confirm_project": "demo-shop", "approved": True
    })
    assert again.status_code != 200


def test_sse_has_status_and_completed_events(client):
    with client.stream("POST", "/api/chat/stream",
                       json={"mode": "demo", "message": "سلام"}) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    assert "event: status\n" in body
    assert "event: complete\n" in body
    assert "data:" in body
