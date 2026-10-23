"""Golden utterance suite: Persian/English, ambiguity, privacy, safety and mode boundaries."""
import pytest
from fastapi.testclient import TestClient

import app
from sentinel import conversation
from sentinel.discovery import discover_unknown_topics
from sentinel.intent import classify, normalize, redact_secrets


@pytest.mark.parametrize(("utterance", "intent", "route"), [
    ("سلام", "greeting", "guide"),
    ("درود", "greeting", "guide"),
    ("hello", "greeting", "guide"),
    ("چیکار می تونی بکنی؟", "help", "guide"),
    ("راهنما", "help", "guide"),
    ("سایتم خطای ۵۰۰ میده", "incident", "inspect"),
    ("سایتم بعد از دیپلوی 500 میده", "incident", "inspect"),
    ("Server error 503", "incident", "inspect"),
    ("سرویس من crash کرده", "incident", "inspect"),
    ("لاگ های پروژه خطا دارن", "incident", "inspect"),
    ("به نظرم سایتم خراب شده", "incident", "inspect"),
    ("سرویس کند شده", "incident", "inspect"),
    ("ری‌استارت پروژه", "restart", "inspect"),
    ("Restart app", "restart", "inspect"),
    ("گزارش سلامت سرویس", "health", "inspect"),
    ("مصرف رم رو ببین", "health", "inspect"),
    ("CPU usage", "health", "inspect"),
    ("فهرست برنامه‌های حساب", "projects", "projects"),
    ("list projects", "projects", "projects"),
    ("فهرست پروژه‌های تیمی", "projects", "projects"),
    ("می‌خوام سایتم رو منتشر کنم", "deploy", "deploy"),
    ("دپلوی کن", "deploy", "deploy"),
    ("deploy my app", "deploy", "deploy"),
    ("استقرار سایت", "deploy", "deploy"),
    ("ایجاد پروژه جدید", "deploy", "deploy"),
    ("وضعیت دیپلوی من چه شد", "releases", "releases"),
    ("چقدر هزینه دیپلوی میشه", "billing", "guide"),
    ("چطور دامنه وصل کنم", "domain_setup", "guide"),
    ("وضعیت پروژه", "health", "inspect"),
    ("سایتم بالا هست", "health", "inspect"),
    ("چرا دامنه خطا داره", "incident", "inspect"),
    ("حذف دامنه", "destructive", "guide"),
    ("آخرین نسخه پروژه", "releases", "releases"),
    ("تاریخچه انتشار برنامه", "releases", "releases"),
    ("show releases", "releases", "releases"),
    ("وضعیت SSL دامنه", "domains", "domains"),
    ("CNAME سایت", "domains", "domains"),
    ("وضعیت DNS", "domains", "domains"),
    ("هزینه برنامه چقدر میشه", "billing", "guide"),
    ("پلن‌های سرویس", "billing", "guide"),
    ("price", "billing", "guide"),
    ("توکن لیارا رو چطور امن کنم", "security", "guide"),
    ("مجوزهای امنیت", "security", "guide"),
    ("متغیر محیطی رو چطور تنظیم کنم", "env", "guide"),
    ("ENV", "env", "guide"),
    ("نحوه اتصال postgres", "database", "guide"),
    ("بکاپ دیتابیس", "backup", "guide"),
    ("حساب تیمی من", "team", "guide"),
    ("چطور با پشتیبانی تماس بگیرم", "support", "guide"),
    ("وقتی خراب شد خبرم کن", "notifications", "guide"),
    ("حذف پروژه را انجام بده", "destructive", "guide"),
    ("delete the entire app", "destructive", "guide"),
    ("خرید دامنه", "unsupported", "guide"),
    ("پرداخت کن", "unsupported", "guide"),
    ("بله", "confirmation", "guide"),
    ("confirm", "confirmation", "guide"),
    ("لغو", "cancellation", "guide"),
    ("no", "cancellation", "guide"),
    ("می‌خوام منتشر نکنم", "explain", "guide"),
    ("لطفا فقط توضیح بده چطور دیپلوی کنم", "explain", "guide"),
    ("موضوعی که به لیارا مربوط نیست", "unknown", "guide"),
])
def test_golden_utterances(utterance, intent, route):
    decision = classify(utterance)
    assert (decision.intent, decision.route) == (intent, route), decision.as_dict()


@pytest.mark.parametrize("utterance", [
    "سلامت و وضعیت دامنه",
    "هزینه و وضعیت دامنه",
    "فهرست برنامه ها و وضعیت SSL",
    "بررسی امنیت و هزینه",
])
def test_ambiguous_requests_require_user_selection(utterance):
    decision = classify(utterance)
    assert decision.certainty == "ambiguous"
    assert decision.route == "guide"
    assert len(decision.suggested_actions) >= 2


def test_priority_of_incident_over_deploy_and_release():
    decision = classify("بعد از انتشار نسخه جدید سایتم خطای 500 میده")
    assert decision.intent == "incident"
    assert {"incident", "releases"}.issubset(set(decision.labels))


def test_destructive_message_never_approves_maintenance():
    assert classify("همه رو حذف کن").certainty == "blocked"
    assert classify("بله").route == "guide"


def test_persian_arabic_digits_and_zwnj():
    assert "500" in normalize("خطای ۵۰۰")
    assert classify("ری‌استارت").intent == "restart"


@pytest.mark.parametrize("secret", [
    "Authorization: Bearer SENSITIVEEXAMPLESTRING123456789",
    "LIARA_API_TOKEN=EXAMPLECONNECTIONSECRET123",
    "OPENAI_API_KEY=abc123456789EXAMPLE987654",
    "sk-ABCDEFGHIJKLMNOPQRST1234567890",
    '{"LIARA_API_TOKEN": "JSONEXAMPLESECRET123456789"}',
    "eyJABCDEFGHIJKL123456.eyJMNOPQRSTUVWX123456.abcdefghijklmno123456",
])
def test_secret_filter_detects_common_credentials(secret):
    scrubbed, changed = redact_secrets(secret)
    assert changed
    assert "EXAMPLECONNECTION" not in scrubbed
    assert "SENSITIVEEXAMPLE" not in scrubbed
    assert "JSONEXAMPLESECRET" not in scrubbed
    assert "eyJABCDEFGHI" not in scrubbed


def test_offline_cluster_discards_sensitive_input_and_never_returns_raw_messages():
    samples = [
        "اتصال تونل پرداخت کند است",
        "پرداخت با تونل خطا میکند",
        "حسابداری هزینه",  # classified as billing, not a new topic
        "OPENAI_API_KEY=SENSITIVEVALUE123456789",
    ]
    output = discover_unknown_topics(samples, threshold=0.2, min_samples=2)
    assert output["skipped_sensitive"] == 1
    assert output["sample_count"] == 4
    assert "clusters" in output
    assert "SENSITIVEVALUE" not in str(output)
    assert all(cluster["decision"] == "human_review_only" for cluster in output["clusters"])


def test_unknown_clustering_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        discover_unknown_topics(["a"], threshold=0, min_samples=2)


def test_messages_do_not_store_pasted_token(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "privacy.sqlite3"))
    monkeypatch.delenv("SENTINEL_ACCESS_KEY", raising=False)
    monkeypatch.setattr(conversation, "_GRAPH", None)
    with TestClient(app.app) as client:
        response = client.post("/api/chat/messages", json={
            "message": "LIARA_API_TOKEN=EXAMPLECONNECTIONSECRET123", "mode": "demo"
        })
        assert response.status_code == 200
        payload = response.json()
        assert payload["engine"] == "privacy-guard"
        saved = client.get("/api/chat/threads/" + payload["thread_id"]).json()
        assert "EXAMPLECONNECTION" not in str(saved)
        assert len(saved["messages"]) == 2


def test_old_approval_is_not_active_after_topic_change(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "approvals.sqlite3"))
    monkeypatch.delenv("SENTINEL_ACCESS_KEY", raising=False)
    monkeypatch.setattr(conversation, "_GRAPH", None)
    with TestClient(app.app) as client:
        initial = client.post("/api/chat/messages", json={
            "mode": "demo", "message": "خطای 500 دارم", "scenario": "transient"
        }).json()
        proposal = initial["ui"]["report"]["proposals"][0]["proposal_id"]
        followup = client.post("/api/chat/messages", json={
            "mode": "demo", "message": "راهنما", "thread_id": initial["thread_id"]
        })
        assert followup.status_code == 200
        denied = client.post("/api/chat/approval", json={
            "thread_id": initial["thread_id"], "proposal_id": proposal,
            "confirm_project": "demo-shop", "approved": True
        })
        assert denied.status_code == 403


def test_demo_domain_read_makes_no_live_api_calls(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "readonly.sqlite3"))
    monkeypatch.delenv("SENTINEL_ACCESS_KEY", raising=False)
    monkeypatch.setattr(conversation, "_GRAPH", None)
    def no_client():
        raise AssertionError("unexpected live Liara adapter")
    monkeypatch.setattr(conversation, "LiaraClient", no_client)
    with TestClient(app.app) as client:
        answer = client.post("/api/chat/messages", json={
            "mode": "demo", "message": "وضعیت SSL دامنه"
        }).json()
    assert answer["ui"]["type"] == "guidance"
    assert "واقعی" in answer["answer"]



def test_missing_live_project_requests_selection_without_liara_call(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "project-picker.sqlite3"))
    monkeypatch.setattr(conversation, "_GRAPH", None)
    def no_client():
        raise AssertionError("must ask for target project before connecting")
    monkeypatch.setattr(conversation, "LiaraClient", no_client)
    result = conversation.respond(
        "validated-operator", "live", "وضعیت پروژه را بررسی کن"
    )
    assert result["ui"]["type"] == "project_picker"
    assert "پروژه" in result["answer"]


def test_private_server_live_read_only_never_issues_restart_proposal(monkeypatch):
    from sentinel.engine import mock_snapshot

    monkeypatch.setenv("SENTINEL_EXPOSURE_MODE", "private-server")
    monkeypatch.setenv("SENTINEL_ALLOW_LIVE_WRITES", "true")
    monkeypatch.setenv("LIARA_API_TOKEN", "dummy-value")
    monkeypatch.setenv("SENTINEL_ALLOWED_PROJECTS", "demo-shop")

    class FakeClient:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def snapshot(self, project):
            assert project == "demo-shop"
            return mock_snapshot("transient")

    monkeypatch.setattr(conversation, "LiaraClient", FakeClient)
    def forbidden_approval(*args, **kwargs):
        raise AssertionError("never issue a write approval on read-only server")
    monkeypatch.setattr(conversation, "create_approval", forbidden_approval)
    outcome = conversation.inspect_node({
        "text": "خطای 500", "actor": "operator",
        "mode": "live", "project": "demo-shop"
    })
    assert outcome["awaiting_approval"] is False
    assert not outcome["ui"]["report"]["proposals"]
    assert any("غیرفعال" in item for item in outcome["ui"]["report"]["limitations"])


def test_independent_goals_do_not_call_any_live_adapter(monkeypatch, tmp_path):
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "multi-intent.sqlite3"))
    monkeypatch.setattr(conversation, "_GRAPH", None)
    def no_client():
        raise AssertionError("ambiguous requests must not query live services")
    monkeypatch.setattr(conversation, "LiaraClient", no_client)
    answer = conversation.respond("operator", "live", "هزینه و وضعیت SSL دامنه")
    assert answer["ui"]["type"] == "guidance"
    assert answer["ui"]["certainty"] == "ambiguous"
    assert len(answer["ui"]["actions"]) >= 2
