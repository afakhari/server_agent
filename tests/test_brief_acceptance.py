"""Brief-to-implementation acceptance tests: first deploy and coding handoff.

All calls offline; no Liara credentials, billing or live mutations needed.
"""
import pytest
from fastapi.testclient import TestClient

import app
from sentinel.engine import diagnose, mock_snapshot
from sentinel.handoff import make_handoff
from sentinel.intent import classify
from sentinel.onboarding import AssessmentInput, assess


def fixture_scan(**values):
    data = {
        "framework": "FastAPI", "platform": "python", "port": 8000,
        "warnings": [], "required_env_names": ["DATABASE_URL"],
    }
    return {**data, **values}


def test_first_deploy_assessment_requires_verified_plan_and_payment():
    result = assess(fixture_scan(), AssessmentInput(
        traffic="low", needs_database=True, custom_domain=True, port=8000))
    assert result["readiness"] == "manual_review_required"
    assert result["liara_plan_id"] is None
    assert result["plan_price"] is None
    assert result["pricing_status"] == "NOT_VERIFIED"
    assert result["execution"] == "NOT_STARTED"
    tasks = {row["id"]: row for row in result["steps"]}
    for item in ("inspect", "account", "billing", "secrets", "approval",
                 "deployment", "verification", "dns", "tls"):
        assert item in tasks
    assert tasks["billing"]["responsible"] == "operator"
    assert tasks["deployment"]["status"] == "not_started"
    assert "قیمت" in result["disclaimer"]


@pytest.mark.parametrize("source,requested_port", [
    ({"platform": "نامشخص"}, 8000),
    ({"port": None}, None),
    ({"port": 8000}, 3000),
])
def test_first_deploy_blocks_unknown_platform_missing_or_conflicting_port(source, requested_port):
    result = assess(fixture_scan(**source), AssessmentInput(port=requested_port))
    assert result["readiness"] == "blocked"
    assert result["blockers"]
    assert result["execution"] == "NOT_STARTED"


def test_high_traffic_does_not_fabricate_resource_sizes():
    result = assess(fixture_scan(), AssessmentInput(
        traffic="high", uptime_critical=True))
    assert "ظرفیت‌سنجی" in result["resource_guidance"]
    assert result["liara_plan_id"] is None
    assert result["plan_price"] is None


@pytest.mark.parametrize("text", [
    "برای سایتم چه پلنی مناسب است؟",
    "کدوم پلن برای پروژه من مناسب‌تره",
    "انتخاب پلن سایت",
    "چه زیرساختی برای سایت من لازم است",
])
def test_sizing_request_enters_guided_onboarding(text):
    result = classify(text)
    assert (result.intent, result.route) == ("capacity", "deploy")


def test_coding_handoff_grounded_in_evidence_and_no_code_write():
    report = diagnose(mock_snapshot("env"))
    handoff = make_handoff(report)
    assert handoff["status"] == "HUMAN_REVIEW_REQUIRED"
    assert handoff["integration"] == "MANUAL_COPY_ONLY"
    assert handoff["coding_tasks"]
    assert handoff["evidence_ids"]
    assert set(handoff["evidence_ids"]).issubset(
        {row["id"] for row in report["evidence"]})
    assert "DATABASE_URL" not in str(handoff)
    assert "Pull Request" in handoff["disclaimer"]


def test_demo_onboarding_api_no_liara_or_secret(monkeypatch):
    monkeypatch.delenv("SENTINEL_ACCESS_KEY", raising=False)
    def denied(*_args, **_kwargs):
        raise AssertionError("onboarding demo must not contact Liara")
    monkeypatch.setattr(app, "LiaraClient", denied)
    with TestClient(app.app) as client:
        result = client.post("/api/onboarding/assess", json={
            "mode": "demo", "traffic": "low",
            "needs_database": True, "custom_domain": True,
            "port": 8000,
        })
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["mode"] == "demo"
    assert body["source"] == "synthetic-demo"
    assert body["scope"] == "STATIC_SOURCE_AND_OPERATOR_INPUT_ONLY"
    assert body["execution"] == "NOT_STARTED"
    assert body["pricing_status"] == "NOT_VERIFIED"
    assert "steps" in body


def test_live_onboarding_requires_operator_key_and_path(monkeypatch):
    monkeypatch.delenv("SENTINEL_ACCESS_KEY", raising=False)
    with TestClient(app.app) as client:
        result = client.post("/api/onboarding/assess", json={"mode": "live"})
    assert result.status_code == 403


@pytest.mark.parametrize("invalid", [
    {"traffic": "infinite"},
    {"port": 0},
    {"mode": "production"},
    {"path": "x" * 201},
])
def test_invalid_onboarding_input_fails_validation(invalid, monkeypatch):
    monkeypatch.delenv("SENTINEL_ACCESS_KEY", raising=False)
    with TestClient(app.app) as client:
        result = client.post("/api/onboarding/assess",
                             json={"mode": "demo", **invalid})
    assert result.status_code == 422


def test_inspection_report_contains_human_review_only_coding_handoff(monkeypatch):
    monkeypatch.delenv("SENTINEL_ACCESS_KEY", raising=False)
    with TestClient(app.app) as client:
        result = client.post("/api/inspect", json={
            "mode": "demo", "scenario": "env"
        })
    assert result.status_code == 200
    report = result.json()
    assert report["coding_handoff"]["status"] == "HUMAN_REVIEW_REQUIRED"
    assert report["coding_handoff"]["integration"] == "MANUAL_COPY_ONLY"


def test_live_raw_metrics_are_evidence_not_invented_percentages():
    snapshot = mock_snapshot("healthy")
    snapshot["mode"] = "live"
    snapshot["derived_metrics"] = {}
    snapshot["raw_metrics"] = {
        "cpuUsage": 245, "memoryUsage": 1048576,
        "disksUsage": "18.5", "malicious": "TOKEN=shouldneverreach"
    }
    report = diagnose(snapshot)
    raw = [e for e in report["evidence"] if e["kind"] == "metric_raw"]
    assert len(raw) == 3
    assert not any("cpu_pct" in row["text"] or "memory_pct" in row["text"]
                   for row in raw)
    assert all("تأیید نشده" in row["text"] for row in raw)
    assert "shouldneverreach" not in str(report)


def test_raw_metric_objects_not_exposed_as_untrusted_serialized_text():
    snapshot = mock_snapshot("healthy")
    snapshot["raw_metrics"] = {
        "cpuUsage": {"Authorization": "Bearer SENSITIVEEXAMPLE12345"},
        "memoryUsage": [1, 2, 3],
    }
    report = diagnose(snapshot)
    assert not any(row["kind"] == "metric_raw" for row in report["evidence"])
    assert "SENSITIVEEXAMPLE" not in str(report)


def test_incident_priority_over_plan_question():
    result = classify("سایتم خطای 500 می‌دهد، آیا باید پلن مناسب‌تری بگیرم؟")
    assert result.intent == "incident"
    assert result.route == "inspect"


def test_legacy_inspect_does_not_offer_live_write_on_private_vps(monkeypatch):
    from starlette.requests import Request

    monkeypatch.setenv("SENTINEL_EXPOSURE_MODE", "private-server")
    monkeypatch.setenv("SENTINEL_ALLOW_LIVE_WRITES", "true")
    monkeypatch.setenv("SENTINEL_ALLOWED_PROJECTS", "demo-shop")
    monkeypatch.setenv("SENTINEL_ACCESS_KEY", "a" * 48)
    monkeypatch.setenv("LIARA_API_TOKEN", "fake-test-only")
    monkeypatch.setattr(app, "credentials", lambda request, mode: "operator")
    monkeypatch.setattr(app, "create_approval",
                        lambda *args: (_ for _ in ()).throw(AssertionError("must not grant approval")))

    class FakeClient:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def snapshot(self, project):
            assert project == "demo-shop"
            snapshot = mock_snapshot("transient")
            snapshot["mode"] = "live"
            return snapshot

    monkeypatch.setattr(app, "LiaraClient", FakeClient)
    request = Request({"type": "http", "method": "POST",
                       "path": "/api/inspect", "headers": []})
    result = app.inspect(request, app.InspectRequest(
        mode="live", project="demo-shop"))
    assert not result["proposals"]
    assert any("عملیات" in x for x in result["limitations"])


def test_unknown_database_does_not_become_false_confirmation():
    result = assess(fixture_scan(), AssessmentInput(
        needs_database=None, traffic="unknown"))
    assert any("دیتابیس" in warning for warning in result["warnings"])


def test_worker_request_is_not_silently_treated_as_web_deployment():
    result = assess(fixture_scan(), AssessmentInput(
        workload="worker", traffic="low", port=8000))
    assert result["readiness"] == "blocked"
    assert any("worker" in reason for reason in result["blockers"])


def test_new_app_and_existing_app_have_different_owner_tasks():
    existing = assess(fixture_scan(), AssessmentInput(existing_app=True))
    creating = assess(fixture_scan(), AssessmentInput(existing_app=False))
    assert next(x["title"] for x in existing["steps"] if x["id"] == "target") != (
        next(x["title"] for x in creating["steps"] if x["id"] == "target"))
