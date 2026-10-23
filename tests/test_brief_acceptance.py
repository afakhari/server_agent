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
