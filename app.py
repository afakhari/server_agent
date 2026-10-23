"""Liara Sentinel API. Single-operator MVP; bind only to loopback unless HTTPS/auth are configured.

Start: uvicorn app:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from server_agent import __version__
from server_agent.diagnosis import analyze, demo_snapshot
from server_agent.liara import LiaraClient, LiaraError, project_name
from server_agent.scout import scan, sample_archive, workspace_path
from server_agent.store import Ledger, StoreError, digest
from server_agent.verify import probe

BASE = Path(__file__).resolve().parent
SAMPLE = BASE / "examples" / "fastapi-shop"
DATA_DIR = Path(os.getenv("SENTINEL_DATA_DIR", str(BASE / ".sentinel-data")))
ledger = Ledger(str(DATA_DIR / "operations.sqlite3"))
app = FastAPI(title="Liara Sentinel", version=__version__, docs_url=None, redoc_url=None)

class InspectInput(BaseModel):
    mode: Literal["demo", "live"] = "demo"
    project: str = "demo-shop"
    scenario: Literal["transient", "env", "memory", "dependency", "release", "healthy"] = "transient"
    minutes: int = Field(default=30, ge=5, le=180)

class ApprovalInput(BaseModel):
    proposal_id: str = Field(min_length=32, max_length=32)
    confirm_project: str = Field(min_length=1, max_length=63)

class DeployInput(BaseModel):
    mode: Literal["demo", "live"] = "demo"
    project: str = "demo-shop"

class ProvisionInput(BaseModel):
    mode: Literal["demo", "live"] = "demo"
    project: str = "demo-shop"
    plan_id: str = Field(min_length=2, max_length=80)
    platform: Literal["python", "node", "docker"] = "python"

class ScoutInput(BaseModel):
    relative_path: str = Field(min_length=1, max_length=256)

def error(exc: Exception):
    if isinstance(exc, LiaraError):
        status = 401 if exc.status == 401 else 403 if exc.status == 403 else 502
        if exc.code in ("invalid_project", "missing_liara_token"):
            status = 400
        return HTTPException(status, exc.code + (":" + str(exc.status) if exc.status else ""))
    if isinstance(exc, StoreError):
        status = 410 if "expired" in str(exc) else 409
        if str(exc) == "operation_not_found":
            status = 404
        return HTTPException(status, str(exc))
    return HTTPException(400, str(exc))

def access(key: str | None, *, live: bool = False):
    expected = os.getenv("SENTINEL_ACCESS_KEY", "")
    if live and not expected:
        raise HTTPException(403, "live_requires_access_key")
    if expected and not hmac.compare_digest(key or "", expected):
        raise HTTPException(401, "invalid_access_key")

def writes_ready(project: str) -> bool:
    return (
        os.getenv("LIARA_ENABLE_WRITES", "").lower() == "true" and
        bool(os.getenv("LIARA_API_TOKEN")) and
        bool(os.getenv("SENTINEL_ACCESS_KEY")) and
        os.getenv("LIARA_TEST_PROJECT", "") == project
    )

def state_fingerprint(snapshot: dict) -> str:
    proj = snapshot.get("project") or {}
    releases = snapshot.get("releases") or {}
    stable = {
        "project": snapshot.get("name"),
        "status": proj.get("status"), "deployed": proj.get("isDeployed"),
        "scale": proj.get("scale"), "planID": proj.get("planID"),
        "release": releases.get("currentRelease") if isinstance(releases, dict) else None
    }
    return digest(stable)

def live_client() -> LiaraClient:
    return LiaraClient()

def live_snapshot(project: str, minutes: int = 30):
    client = live_client()
    try:
        return client.snapshot(project_name(project), minutes=minutes)
    finally:
        client.close()

def proposal(report: dict, snapshot: dict, action: str):
    payload = {"action": action, "project": snapshot["name"], "scope": "single_operator_test"}
    token = ledger.propose(snapshot["mode"], snapshot["name"], action,
                           state_fingerprint(snapshot), payload)
    return {**token,
            "risk": "ممکن است سرویس قطع شود یا نسخه جدید منتشر شود.",
            "requires_approval": True,
            "reversible": False}

@app.get("/")
def index():
    return FileResponse(BASE / "web" / "index.html")

@app.get("/api/config")
def config():
    return {
        "version": __version__, "demo_available": True,
        "live_read_available": bool(os.getenv("LIARA_API_TOKEN")),
        "live_write_available": bool(os.getenv("LIARA_ENABLE_WRITES", "").lower() == "true"
                                     and os.getenv("LIARA_TEST_PROJECT")),
        "access_key_required": bool(os.getenv("SENTINEL_ACCESS_KEY")),
        "write_policy": "test-project-only", "status": "MVP — not production ready"
    }

@app.get("/api/projects")
def projects(x_sentinel_key: str | None = Header(default=None)):
    access(x_sentinel_key, live=True)
    try:
        client = live_client()
        try:
            return client.projects()
        finally:
            client.close()
    except LiaraError as exc:
        raise error(exc)

@app.post("/api/inspect")
def inspect(body: InspectInput, x_sentinel_key: str | None = Header(default=None)):
    access(x_sentinel_key, live=(body.mode == "live"))
    try:
        snap = demo_snapshot(body.scenario) if body.mode == "demo" else live_snapshot(body.project, body.minutes)
    except (LiaraError, ValueError) as exc:
        raise error(exc)
    report = analyze(snap)
    if report["proposals"]:
        if body.mode == "demo" or writes_ready(snap["name"]):
            report["proposals"][0]["approval"] = proposal(report, snap, "restart")
        else:
            report["limitations"].append("تغییر واقعی غیرفعال است؛ فقط پروژه آزمایشی مجاز است.")
            report["proposals"] = []
    ledger.log("inspection", project=snap["name"], detail={
        "mode": body.mode, "verdict": report["verdict"],
        "evidence_count": len(report["evidence"])
    })
    return report

@app.get("/api/scout/sample")
def scout_sample():
    return {"mode": "demo", "analysis": scan(SAMPLE),
            "notice": "فقط بررسی فایل است. هنوز روی لیارا دیپلوی نشده است."}

@app.post("/api/scout")
def scout_repo(body: ScoutInput, x_sentinel_key: str | None = Header(default=None)):
    access(x_sentinel_key, live=True)
    workspace = os.getenv("SENTINEL_WORKSPACE_ROOT", "")
    if not workspace:
        raise HTTPException(403, "workspace_not_configured")
    try:
        return {"mode": "local_readonly",
                "analysis": scan(workspace_path(body.relative_path, Path(workspace)))}
    except (OSError, ValueError) as exc:
        raise error(exc)

@app.post("/api/provision/plan")
def provision_plan(body: ProvisionInput, x_sentinel_key: str | None = Header(default=None)):
    access(x_sentinel_key, live=(body.mode == "live"))
    try:
        project = project_name(body.project)
        if not __import__("re").fullmatch(r"[A-Za-z0-9_-]{2,80}", body.plan_id):
            raise HTTPException(400, "invalid_plan_id")
        if body.mode == "live":
            if not writes_ready(project):
                return {"status":"blocked","reason":"only_allowlisted_live_test_project"}
            client = live_client()
            try:
                try:
                    client.project(project)
                except LiaraError as exc:
                    if exc.status != 404:
                        raise
                else:
                    raise HTTPException(409, "project_already_exists")
            finally:
                client.close()
        payload = {"action":"create_project","project":project,
                   "plan_id":body.plan_id,"platform":body.platform}
        approval = ledger.propose(body.mode,project,"create_project",
                                  digest({"project":project,"state":"absent"}),payload)
        return {"status":"awaiting_approval","project":project,"mode":body.mode,
                "action":"create_project","plan_id":body.plan_id,"platform":body.platform,
                "price":"UNVERIFIED","notice":"این اقدام ممکن است هزینه ایجاد کند؛ پلن و موجودی را پیش از تأیید در پنل لیارا بررسی کنید.",
                "approval":approval}
    except LiaraError as exc:
        raise error(exc)

@app.post("/api/deploy/plan")
def deploy_plan(body: DeployInput, x_sentinel_key: str | None = Header(default=None)):
    access(x_sentinel_key, live=(body.mode == "live"))
    try:
        inspection = scan(SAMPLE)
        if not inspection["deployment_ready"]:
            raise HTTPException(400, "sample_not_deployment_ready")
        snap = demo_snapshot() if body.mode == "demo" else live_snapshot(body.project)
        project = snap["name"]
        if body.mode == "live" and not writes_ready(project):
            return {"status": "blocked", "reason": "only_allowlisted_live_test_project",
                    "analysis": inspection}
        approval = proposal({}, snap, "deploy_sample")
        return {
            "status": "awaiting_approval", "mode": body.mode, "project": project,
            "source": "bundled-audited-sample", "analysis": inspection,
            "operation": "publish_sample_to_existing_project",
            "notice": "انتشار روی سرویس موجود، کد فعلی آن را جایگزین می‌کند؛ ایجاد پروژه/پرداخت انجام نمی‌شود.",
            "approval": approval
        }
    except (OSError, LiaraError, ValueError) as exc:
        raise error(exc)

def execute_approved(row: dict):
    project = row["project"]
    if row["mode"] == "demo":
        before = demo_snapshot()
        if row["action"] == "restart":
            before = demo_snapshot("transient")
        if row["action"] != "create_project" and state_fingerprint(before) != row["state_digest"]:
            ledger.status(row["id"], "blocked", {"reason": "state_changed"})
            raise HTTPException(409, "state_changed_reinspect")
        ledger.status(row["id"], "verified", {"mode": "demo", "simulated": True})
        return {"operation_id": row["id"], "mode": "demo", "execution": "SIMULATED",
                "verification": "SIMULATED", "message": "تغییر و بازیابی صرفاً شبیه‌سازی شدند."}
    if not writes_ready(project):
        ledger.status(row["id"], "blocked", {"reason": "live_writes_disabled"})
        raise HTTPException(403, "live_writes_disabled")
    client = live_client()
    try:
        if row["action"] == "create_project":
            try:
                client.project(project)
            except LiaraError as exc:
                if exc.status != 404:
                    raise
            else:
                ledger.status(row["id"], "blocked", {"reason": "project_now_exists"})
                raise HTTPException(409, "project_now_exists")
            data = row["payload"]
            client.create_project(project, data["plan_id"], data["platform"])
            ledger.status(row["id"], "submitted", {"project":project,"action":"create_project"})
            return {"operation_id":row["id"],"mode":"live","execution":"SUBMITTED",
                    "verification":"NOT_VERIFIED","message":"درخواست ایجاد پروژه ارسال شد؛ وضعیت آن باید جدا بررسی شود. هزینه پلن ممکن است اعمال شود."}
        latest = client.snapshot(project)
        if state_fingerprint(latest) != row["state_digest"]:
            ledger.status(row["id"], "blocked", {"reason": "state_changed"})
            raise HTTPException(409, "state_changed_reinspect")
        if row["action"] == "restart":
            client.restart(project)
        elif row["action"] == "deploy_sample":
            archive = sample_archive(SAMPLE)
            uploaded = client.upload_archive(project, archive)
            if not isinstance(uploaded, dict) or not isinstance(uploaded.get("sourceID"), str):
                raise LiaraError("source_upload_unknown_result")
            result = client.release(project, uploaded["sourceID"], "python", 8000)
            if not isinstance(result, dict) or not isinstance(result.get("releaseID"), str):
                raise LiaraError("release_creation_unknown_result")
        else:
            ledger.status(row["id"], "blocked", {"reason": "unknown_action"})
            raise HTTPException(403, "unknown_action")
        ledger.status(row["id"], "submitted", {"project": project, "action": row["action"]})
        return {"operation_id": row["id"], "mode": "live", "execution": "SUBMITTED",
                "verification": "NOT_VERIFIED",
                "message": "درخواست ارسال شد؛ نتیجه سلامت باید مستقل بررسی شود."}
    except LiaraError as exc:
        ledger.status(row["id"], "inconclusive", {"reason": exc.code})
        raise error(exc)
    except (ValueError, OSError) as exc:
        ledger.status(row["id"], "inconclusive", {"reason": "local_execution_error"})
        raise HTTPException(502, "local_execution_error") from exc
    finally:
        client.close()

@app.post("/api/approve")
def approve(body: ApprovalInput, x_sentinel_key: str | None = Header(default=None)):
    try:
        preview = ledger.get(body.proposal_id)
        access(x_sentinel_key, live=(preview["mode"] == "live"))
        # Atomic consumption happens before the outbound mutation; requests cannot be replayed.
        row = ledger.consume(body.proposal_id, body.confirm_project)
        return execute_approved(row)
    except (LiaraError, StoreError) as exc:
        raise error(exc)

@app.post("/api/operations/{operation_id}/verify")
def verify(operation_id: str, x_sentinel_key: str | None = Header(default=None)):
    try:
        row = ledger.get(operation_id)
        access(x_sentinel_key, live=(row["mode"] == "live"))
        if row["mode"] == "demo":
            return {"operation_id": operation_id, "result": "SIMULATED", "evidence": []}
        if row["status"] not in ("submitted", "inconclusive"):
            raise HTTPException(409, "operation_not_submitted")
        client = live_client()
        try:
            p = client.project(row["project"])
        finally:
            client.close()
        evidence = [{"source": "liara.project", "status": p.get("status"),
                     "isDeployed": p.get("isDeployed")}]
        if row["action"] == "create_project":
            result = "verified" if p.get("project_id") == row["project"] else "inconclusive"
            ledger.status(operation_id, result, {"project":row["project"],"verification":result})
            return {"operation_id":operation_id,"result":result,"evidence":evidence,
                    "notice":"فقط ایجاد پروژه بررسی شده؛ دیپلوی و سلامت وب‌سایت هنوز تأیید نشده است."}
        health_url = os.getenv("SENTINEL_HEALTH_URL", "")
        health_project = os.getenv("SENTINEL_HEALTH_PROJECT", "")
        if health_url and health_project == row["project"]:
            try:
                health = probe(health_url)
                evidence.append({"source": "operator_bound_https_probe", **health})
                if health["healthy"] is True and p.get("isDeployed") is True and str(p.get("status", "")).lower() in ("running", "active"):
                    result = "verified"
                elif health["healthy"] is False:
                    result = "failed"
                else:
                    result = "inconclusive"
            except ValueError:
                result = "inconclusive"
                evidence.append({"source": "health_probe", "error": "unsafe_or_unavailable_configuration"})
        else:
            result = "inconclusive"
            evidence.append({"source": "health_probe", "error": "no_project_bound_health_url"})
        ledger.status(operation_id, result, {"project": row["project"],
                                             "verification": result})
        return {"operation_id": operation_id, "result": result, "evidence": evidence,
                "notice": "وضعیت API به‌تنهایی اثبات سلامت برنامه نیست."}
    except (LiaraError, StoreError) as exc:
        raise error(exc)

@app.get("/api/operations/{operation_id}")
def operation(operation_id: str, x_sentinel_key: str | None = Header(default=None)):
    try:
        row = ledger.get(operation_id)
        access(x_sentinel_key, live=(row["mode"] == "live"))
        return {"id": row["id"], "project": row["project"], "action": row["action"],
                "mode": row["mode"], "status": row["status"], "created": row["created"],
                "detail": row["detail"]}
    except StoreError as exc:
        raise error(exc)

@app.get("/api/audit")
def audit(x_sentinel_key: str | None = Header(default=None)):
    access(x_sentinel_key, live=True)
    return {"events": ledger.history()}
