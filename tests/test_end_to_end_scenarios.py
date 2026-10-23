"""End-to-end scenario matrix: from initial chat to safe outcome.

No network, account, SSH, billable app, or real Liara mutation is used here.
These scenarios cover workflow invariants, not browser visual appearance.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import app
from sentinel import conversation
from sentinel.liara import LiaraError
from sentinel.security import actor_digest

KEY = "ExampleOnlyForTesting0123456789abcdefABCDEF"
REQ = "repeatable-request-identifier-00000001"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "scenario.sqlite3"))
    monkeypatch.setenv("SENTINEL_EXPOSURE_MODE", "local")
    monkeypatch.setenv("SENTINEL_ALLOW_LIVE_WRITES", "false")
    monkeypatch.delenv("SENTINEL_ACCESS_KEY", raising=False)
    monkeypatch.delenv("LIARA_TEAM_ID", raising=False)
    monkeypatch.delenv("LIARA_API_TOKEN", raising=False)
    monkeypatch.setenv("SENTINEL_CHAT_LLM_ENABLED", "false")
    monkeypatch.setattr(conversation, "_GRAPH", None)
    original = conversation.importlib.util.find_spec
    monkeypatch.setattr(conversation.importlib.util, "find_spec",
                        lambda name: None if name == "langgraph" else original(name))


def payload(message, **opts):
    return {"mode": "demo", "message": message, **opts}


def test_new_user_to_evidence_to_one_use_approval_and_verification():
    with TestClient(app.app) as client:
        first = client.post("/api/chat/messages", json=payload(
            "سرویس worker crash کرده و خطای ۵۰۰ می‌دهد"))
        assert first.status_code == 200, first.text
        report = first.json()
        assert report["ui"]["type"] == "inspection"
        assert report["ui"]["report"]["mode"] == "demo"
        assert report["ui"]["report"]["evidence"]
        assert report["ui"]["report"]["coding_handoff"]["integration"] == "MANUAL_COPY_ONLY"
        proposals = report["ui"]["report"]["proposals"]
        assert len(proposals) == 1
        proposal_id = proposals[0]["proposal_id"]
        approved = client.post("/api/chat/approval", json={
            "thread_id": report["thread_id"], "proposal_id": proposal_id,
            "confirm_project": "demo-shop", "approved": True})
        assert approved.status_code == 200, approved.text
        assert approved.json()["ui"]["result"]["execution"] == "SIMULATED"
        assert approved.json()["ui"]["result"]["verification"] == "SIMULATED_RECOVERY"
        repeated = client.post("/api/chat/approval", json={
            "thread_id": report["thread_id"], "proposal_id": proposal_id,
            "confirm_project": "demo-shop", "approved": True})
        assert repeated.status_code != 200
        history = client.get("/api/chat/threads/" + report["thread_id"]).json()
        assert len(history["messages"]) == 3
        assert history["messages"][-1]["ui"]["type"] == "execution"


def test_first_response_lost_retry_with_same_id_reuses_same_result_and_thread():
    with TestClient(app.app) as client:
        body = payload("سلام", request_id=REQ)
        first = client.post("/api/chat/messages", json=body)
        assert first.status_code == 200
        replay = client.post("/api/chat/messages", json=body)
        assert replay.status_code == 200
        assert replay.json() == first.json()
        thread = client.get("/api/chat/threads/" + first.json()["thread_id"]).json()
        assert len(thread["messages"]) == 2
        assert len(client.get("/api/chat/threads").json()["threads"]) == 1


def test_same_id_different_message_rejected_without_extra_records():
    with TestClient(app.app) as client:
        first = client.post("/api/chat/messages",
                            json=payload("سلام", request_id=REQ))
        assert first.status_code == 200
        clash = client.post("/api/chat/messages",
                            json=payload("فهرست پروژه‌ها", request_id=REQ))
        assert clash.status_code == 409
        messages = client.get(
            "/api/chat/threads/" + first.json()["thread_id"]).json()["messages"]
        assert len(messages) == 2


def test_json_then_sse_same_turn_returns_identical_saved_result():
    with TestClient(app.app) as client:
        body = payload("راهنما", request_id=REQ)
        first = client.post("/api/chat/messages", json=body).json()
        stream = client.post("/api/chat/stream", json=body)
        assert stream.status_code == 200
        lines = stream.text.splitlines()
        completed = [
            json.loads(lines[i + 1].split("data: ", 1)[1])
            for i, line in enumerate(lines)
            if line == "event: complete"
        ]
        assert len(completed) == 1
        assert completed[0] == first


def test_team_credentials_demo_thread_and_approval_remain_accessible(monkeypatch):
    monkeypatch.setenv("SENTINEL_ACCESS_KEY", KEY)
    monkeypatch.setenv("LIARA_TEAM_ID", "team-scope-001")
    headers = {"X-Sentinel-Access-Key": KEY}
    with TestClient(app.app) as client:
        first = client.post("/api/chat/messages", headers=headers,
                            json=payload("خطای ۵۰۰ و worker crash دارم"))
        assert first.status_code == 200, first.text
        data = first.json()
        thread = client.get("/api/chat/threads/" + data["thread_id"], headers=headers)
        assert thread.status_code == 200
        listed = client.get("/api/chat/threads", headers=headers).json()["threads"]
        assert any(x["id"] == data["thread_id"] for x in listed)
        proposal = data["ui"]["report"]["proposals"][0]["proposal_id"]
        approved = client.post("/api/chat/approval", headers=headers, json={
            "thread_id": data["thread_id"], "proposal_id": proposal,
            "confirm_project": "demo-shop", "approved": True})
        assert approved.status_code == 200, approved.text
        assert approved.json()["ui"]["result"]["mode"] == "demo"


def test_team_account_can_list_demo_and_live_threads_without_crossing_mode(monkeypatch):
    monkeypatch.setenv("SENTINEL_ACCESS_KEY", KEY)
    monkeypatch.setenv("LIARA_TEAM_ID", "team-scope-001")
    demo, _ = conversation.open_thread(actor_digest(KEY, "demo"),
                                       "demo", None, None)
    live, _ = conversation.open_thread(actor_digest(KEY, "live"),
                                       "live", None, "testapp")
    headers = {"X-Sentinel-Access-Key": KEY}
    with TestClient(app.app) as client:
        ids = {x["id"] for x in
               client.get("/api/chat/threads", headers=headers).json()["threads"]}
        assert ids == {demo, live}
        assert client.get("/api/chat/threads/" + live, headers=headers).status_code == 200
        no_access = client.get("/api/chat/threads/" + demo)
        assert no_access.status_code == 403


def test_latest_250_messages_selected_not_oldest():
    thread_id, _ = conversation.open_thread("single-operator", "demo", None, None)
    conversation.add_message(thread_id, "assistant", "old-card",
                             {"type": "inspection", "report": {"project": "demo-shop",
                             "proposals": [{"proposal_id": "old-dangerous"}]}})
    for n in range(260):
        conversation.add_message(thread_id, "user", "turn-" + str(n))
    history = conversation.thread_data("single-operator", thread_id)
    assert len(history["messages"]) == 250
    assert history["messages"][-1]["content"] == "turn-259"
    assert all(m["content"] != "old-card" for m in history["messages"])


def test_topic_change_invalidates_earlier_proposal():
    with TestClient(app.app) as client:
        first = client.post("/api/chat/messages",
                            json=payload("خطای ۵۰۰ و crash دارم")).json()
        proposal = first["ui"]["report"]["proposals"][0]["proposal_id"]
        switched = client.post("/api/chat/messages", json=payload(
            "هزینه پلن چیست؟", thread_id=first["thread_id"]))
        assert switched.status_code == 200
        rejected = client.post("/api/chat/approval", json={
            "thread_id": first["thread_id"], "proposal_id": proposal,
            "confirm_project": "demo-shop", "approved": True})
        assert rejected.status_code == 403


def test_cross_mode_thread_rejected_even_when_actor_hash_identical():
    first = conversation.respond("anonymous-demo", "demo", "سلام")
    with pytest.raises(PermissionError):
        conversation.respond("anonymous-demo", "live", "فهرست پروژه‌ها",
                             thread_id=first["thread_id"])


def test_ambiguous_request_has_no_external_liara_reads(monkeypatch):
    def no_client(*_args, **_kwargs):
        raise AssertionError("unambiguous user selection required")
    monkeypatch.setattr(conversation, "LiaraClient", no_client)
    result = conversation.respond("operator", "live", "هزینه و وضعیت SSL چیست؟")
    assert result["ui"]["type"] == "guidance"
    assert result["ui"]["certainty"] == "ambiguous"
    assert result["ui"]["actions"]


def test_live_upstream_failure_is_persisted_as_error_not_fake_success(monkeypatch):
    class FailedClient:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def snapshot(self, *_args):
            raise LiaraError("HTTP 503 test stub")
    monkeypatch.setattr(conversation, "LiaraClient", FailedClient)
    outcome = conversation.respond("operator", "live",
                                   "خطای ۵۰۰ دارم", project="testapp")
    assert outcome["ui"]["type"] == "error"
    assert "توقف" in outcome["answer"]
    messages = conversation.thread_data("operator", outcome["thread_id"])["messages"]
    assert len(messages) == 2
    assert messages[-1]["ui"]["type"] == "error"


def test_accidental_secret_never_persisted_in_chat():
    outcome = conversation.respond("operator", "demo",
                                   "LIARA_API_TOKEN=EXAMPLEsecret0123456789",
                                   request_id=REQ)
    assert outcome["engine"] == "privacy-guard"
    saved = conversation.thread_data("operator", outcome["thread_id"])
    assert "EXAMPLEsecret0123456789" not in str(saved)
    assert "EXAMPLEsecret0123456789" not in str(outcome)


def test_private_server_config_truthfully_disables_write_prep(monkeypatch):
    monkeypatch.setenv("SENTINEL_EXPOSURE_MODE", "private-server")
    monkeypatch.setenv("SENTINEL_ALLOW_LIVE_WRITES", "true")
    monkeypatch.setenv("SENTINEL_ALLOWED_PROJECTS", "sandbox")
    monkeypatch.setenv("LIARA_API_TOKEN", "fake-api-token")
    monkeypatch.setenv("SENTINEL_ACCESS_KEY", KEY)
    assert app.config()["deployment_planning_available"] is False
    assert app.live_writes_permitted("sandbox") is False


def test_concurrent_duplicate_request_never_creates_two_message_pairs():
    def send(_):
        try:
            return conversation.respond("concurrent-actor", "demo", "سلام",
                                        request_id=REQ)
        except RuntimeError as exc:
            assert "قبلاً" in str(exc)
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))
    success = [x for x in results if x is not None]
    assert success
    threads = conversation.list_threads("concurrent-actor")
    assert len(threads) == 1
    assert len(conversation.thread_data(
        "concurrent-actor", threads[0]["id"])["messages"]) == 2



@pytest.mark.parametrize("secret", [
    "DATABASE_URL=postgres://admin:password@127.0.0.1:5432/appdb",
    "redis://supersecret:verysecret@cache.private:6379/0",
    "-----BEGIN PRIVATE KEY-----\nEXAMPLE-SECRET-PRIVATE-KEY-MATERIAL\n-----END PRIVATE KEY-----",
    "AWS_SECRET_ACCESS_KEY=INSECURE_DEMO_ONLY_EXAMPLE_VALUE",
])
def test_infrastructure_credentials_never_saved_or_sent_to_models(secret):
    index = str(abs(hash(secret)))[:8]
    outcome = conversation.respond("operator", "demo", secret,
                                   request_id="credential-fixture-" + index + "-000000000")
    assert outcome["engine"] == "privacy-guard"
    thread = conversation.thread_data("operator", outcome["thread_id"])
    assert "supersecret" not in str(thread)
    assert "INSECURE_DEMO_ONLY_EXAMPLE_VALUE" not in str(thread)
    assert "EXAMPLE-SECRET-PRIVATE-KEY-MATERIAL" not in str(thread)
    assert "password@" not in str(thread)



def test_changed_project_cannot_reuse_existing_chat_context():
    first = conversation.respond("operator", "live", "سلام", project="first-app")
    with pytest.raises(ValueError, match="گفت‌وگوی جدید"):
        conversation.respond("operator", "live", "وضعیت پروژه دوم",
                             thread_id=first["thread_id"], project="second-app")
    history = conversation.thread_data("operator", first["thread_id"])
    assert history["project"] == "first-app"
    assert len(history["messages"]) == 2


def test_failed_in_flight_request_is_never_blindly_executed_again():
    actor = "operator"
    payload_data = {
        "mode": "demo", "thread_id": None,
        "project": None, "scenario": "transient", "text": "سلام",
    }
    assert conversation.begin_request(actor, REQ, payload_data) is None
    with pytest.raises(RuntimeError, match="قبلاً"):
        conversation.begin_request(actor, REQ, payload_data)
    assert conversation.list_threads(actor) == []



def test_new_turn_really_consumes_old_proposal_even_on_legacy_endpoint():
    with TestClient(app.app) as client:
        first = client.post("/api/chat/messages",
                            json=payload("سرویس crash کرده")).json()
        proposed = first["ui"]["report"]["proposals"][0]["proposal_id"]
        followup = client.post("/api/chat/messages", json=payload(
            "میشه هزینه سرویس رو توضیح بدی؟", thread_id=first["thread_id"]))
        assert followup.status_code == 200
        # A UI-only disabled card is insufficient: the legacy route must
        # also reject a formerly valid actor/project-bound approval.
        legacy = client.post("/api/approve", json={
            "proposal_id": proposed, "confirm_project": "demo-shop"})
        assert legacy.status_code != 200
        assert client.post("/api/chat/approval", json={
            "thread_id": first["thread_id"],
            "proposal_id": proposed, "confirm_project": "demo-shop",
            "approved": True}).status_code != 200


def test_second_turn_after_completed_request_can_create_new_approval():
    with TestClient(app.app) as client:
        first = client.post("/api/chat/messages",
                            json=payload("worker crash", request_id=REQ)).json()
        proposal_1 = first["ui"]["report"]["proposals"][0]["proposal_id"]
        second = client.post("/api/chat/messages", json=payload(
            "worker crash", thread_id=first["thread_id"],
            request_id="other-valid-client-turn-id-123456789"))
        assert second.status_code == 200
        proposal_2 = second.json()["ui"]["report"]["proposals"][0]["proposal_id"]
        assert proposal_1 != proposal_2
        assert client.post("/api/approve", json={
            "proposal_id": proposal_1, "confirm_project": "demo-shop"}).status_code != 200
        assert client.post("/api/chat/approval", json={
            "thread_id": first["thread_id"],
            "proposal_id": proposal_2, "confirm_project": "demo-shop",
            "approved": True}).status_code == 200
