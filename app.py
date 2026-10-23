"""Liara Sentinel: explicitly demo-first incident assistant.

All real modifications are restricted to explicitly allowlisted disposable projects.
This is a local evaluation server, not a production multi-user SaaS.
"""
import hashlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sentinel.engine import diagnose, mock_snapshot
from sentinel.health import verify_http
from sentinel.deployer import DeployError, make_plan, claim_plan, perform_deploy
from sentinel.cli import make_cli_plan, claim_cli_plan, perform_cli_deploy, configured as cli_enabled
from sentinel.liara import LiaraClient, LiaraError, validate_name
from sentinel.reasoner import narrative
from sentinel.scout import inspect_repo, repo_from_workspace
from sentinel.security import (
    actor_digest, authorized, audit, cancel_approval, consume_approval, create_approval,
    inspect_approval, read_audit
)

ROOT = Path(__file__).resolve().parent


def validate_server_config() -> None:
    """Fail closed before binding a private staging service.

    The reverse proxy MUST authenticate users. This is not multi-tenant.
    """
    profile = os.getenv('SENTINEL_EXPOSURE_MODE', 'local')
    if profile not in ('local', 'private-server'):
        raise RuntimeError('SENTINEL_EXPOSURE_MODE نامعتبر است')
    if profile == 'local':
        return
    access = os.getenv('SENTINEL_ACCESS_KEY', '')
    if len(access) < 32 or len(set(access)) < 16 or access.upper().startswith('REPLACE_') or access.isspace() or access.lower() in {
        'change-me', 'changeme', 'your-secret', 'your-key',
    }:
        raise RuntimeError('حالت سرور نیازمند کلید Sentinel تصادفی حداقل ۳۲ نویسه است')
    if os.getenv('SENTINEL_ALLOW_LIVE_WRITES', '').lower() == 'true':
        raise RuntimeError('عملیات نوشتنی لیارا روی سرور آزمایشی خصوصی غیرفعال باید بماند')
    if os.getenv('SENTINEL_CLI_DEPLOY_ENABLED', '').lower() == 'true':
        raise RuntimeError('انتشار CLI در حالت سرور آزمایشی خصوصی مجاز نیست')
    db = Path(os.getenv('SENTINEL_DB_PATH', ''))
    if not db.is_absolute() or str(db) in ('/', ''):
        raise RuntimeError('SENTINEL_DB_PATH باید فایل مطلق داخل volume دائمی باشد')
    if not (ROOT / 'frontend' / 'dist' / 'index.html').is_file():
        raise RuntimeError('نسخه production فرانت‌اند ساخته نشده است؛ npm run build لازم است')
    if not (ROOT / 'frontend' / 'dist' / 'assets').is_dir():
        raise RuntimeError('فایل‌های static فرانت‌اند موجود نیستند')


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_server_config()
    yield


app = FastAPI(
    title='Liara Sentinel', version='0.3.0',
    description='Evidence-first, human-approved operations',
    lifespan=lifespan,
)

@app.middleware('http')
async def secure_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    if os.getenv('SENTINEL_EXPOSURE_MODE') == 'private-server':
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; base-uri 'none'; form-action 'self'; "
            "script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        )
    else:
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        )
    return response

class InspectRequest(BaseModel):
    mode: str = 'demo'
    project: str = Field(default='demo-shop', min_length=1, max_length=63)
    scenario: str = 'transient'

class ApproveRequest(BaseModel):
    proposal_id: str = Field(min_length=20, max_length=120)
    confirm_project: str = Field(min_length=1, max_length=63)

class DeployPlanRequest(BaseModel):
    backend: str = 'api'
    project: str = Field(min_length=1, max_length=63)
    path: str = Field(min_length=1, max_length=200)
    plan_id: str = Field(min_length=1, max_length=80)
    platform: str
    port: int = Field(ge=1, le=65535)

class DeployExecuteRequest(BaseModel):
    proposal_id: str = Field(min_length=20, max_length=120)
    confirm_project: str = Field(min_length=1, max_length=63)

class ScoutRequest(BaseModel):
    path: str = Field(min_length=1, max_length=200)


def credentials(request: Request, mode: str):
    try:
        return actor_digest(request.headers.get('X-Sentinel-Access-Key'), mode)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def fp(snap):
    p = snap.get('project') or {}
    r = snap.get('releases') or {}
    state = {'name': snap.get('name'), 'status': p.get('status'),
             'isDeployed': p.get('isDeployed'), 'scale': p.get('scale'),
             'currentRelease': r.get('currentRelease')}
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def live_writes_permitted(project: str) -> bool:
    projects = {p.strip() for p in os.getenv('SENTINEL_ALLOWED_PROJECTS', '').split(',') if p.strip()}
    return (os.getenv('SENTINEL_EXPOSURE_MODE', 'local') != 'private-server'
            and os.getenv('SENTINEL_ALLOW_LIVE_WRITES', '').lower() == 'true'
            and len(os.getenv('SENTINEL_ACCESS_KEY', '')) >= 24
            and project in projects and bool(os.getenv('LIARA_API_TOKEN')))


def fail_from_approval(exc):
    mapping = {LookupError: 404, PermissionError: 403, RuntimeError: 409,
               TimeoutError: 410, ValueError: 409}
    return HTTPException(mapping.get(type(exc), 400), str(exc))

@app.get('/healthz', include_in_schema=False)
def healthz():
    """Internal liveness probe: no credentials, token checks or upstream calls."""
    return {'status': 'ok'}


@app.get('/')
def home():
    built = ROOT / 'frontend' / 'dist' / 'index.html'
    return FileResponse(built if built.is_file() else ROOT / 'static' / 'index.html')

if (ROOT / 'frontend' / 'dist' / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=ROOT / 'frontend' / 'dist' / 'assets'), name='frontend-assets')

@app.get('/api/config')
def config():
    return {'live_read_enabled': bool(os.getenv('LIARA_API_TOKEN')) and len(os.getenv('SENTINEL_ACCESS_KEY','')) >= 24,
            'live_write_enabled': False,  # Per-project gates are checked on every operation, never advertise globally.
            'auth_required': bool(os.getenv('SENTINEL_ACCESS_KEY')),
            'liara_scope': 'team' if os.getenv('LIARA_TEAM_ID') else 'personal',
            'model': 'evidence-first rules + optional advisory LLM',
            'warning': 'نسخه آزمایشی؛ برای محیط عمومی و چندکاربره آماده نیست'}

@app.get('/api/projects')
def projects(request: Request):
    credentials(request, 'live')
    try:
        with LiaraClient() as client:
            return client.list_projects()
    except LiaraError as exc:
        raise HTTPException(502, str(exc)) from exc

@app.post('/api/inspect')
def inspect(request: Request, payload: InspectRequest):
    if payload.mode not in ('demo', 'live'):
        raise HTTPException(400, 'حالت نامعتبر')
    actor = credentials(request, payload.mode)
    try:
        if payload.mode == 'demo':
            if payload.scenario not in {'transient', 'env', 'memory', 'release', 'healthy'}:
                raise HTTPException(400, 'سناریوی نمایشی نامعتبر')
            snap = mock_snapshot(payload.scenario)
        else:
            with LiaraClient() as client:
                snap = client.snapshot(validate_name(payload.project))
    except LiaraError as exc:
        raise HTTPException(502, str(exc)) from exc
    report = diagnose(snap)
    report['ai_commentary'] = narrative(report)
    for proposal in report['proposals']:
        proposal['proposal_id'] = create_approval(actor, payload.mode, snap['name'],
                                                  proposal['operation'], fp(snap))
        proposal['expires_in_seconds'] = 180
    audit('inspection', payload.mode, snap['name'])
    return report

@app.post('/api/approve')
def approve(request: Request, payload: ApproveRequest):
    # No trusting client-supplied action, mode, target, plan or state.
    try:
        actor = actor_digest(request.headers.get('X-Sentinel-Access-Key'), 'live'
                             if os.getenv('SENTINEL_ACCESS_KEY') else 'demo')
        proposal = inspect_approval(payload.proposal_id, actor, payload.confirm_project)
    except (PermissionError, LookupError, RuntimeError, TimeoutError, ValueError) as exc:
        raise fail_from_approval(exc) from exc
    mode, project = proposal['mode'], proposal['project']
    if mode == 'live':
        if not live_writes_permitted(project):
            audit('write_denied', mode, project)
            raise HTTPException(403, 'نوشتن زنده غیرفعال یا پروژه خارج از فهرست آزمایشی است')
        try:
            with LiaraClient() as client:
                current = client.snapshot(project)
        except LiaraError as exc:
            raise HTTPException(502, str(exc)) from exc
        observed_fingerprint = fp(current)
    else:
        observed_fingerprint = proposal['fingerprint']
    try:
        consume_approval(payload.proposal_id, actor, project, observed_fingerprint)
    except (PermissionError, LookupError, RuntimeError, TimeoutError, ValueError) as exc:
        audit('approval_rejected', mode, project)
        raise fail_from_approval(exc) from exc

    if mode == 'demo':
        audit('simulated_restart', mode, project)
        return {'mode': 'demo', 'operation': 'restart', 'execution': 'SIMULATED',
                'verification': 'SIMULATED_RECOVERY', 'message': 'صرفاً شبیه‌سازی؛ هیچ تغییری در لیارا انجام نشده است.',
                'before': {'app_status': 'crashed', 'http_status': 500},
                'after': {'app_status': 'running', 'http_status': 200}}
    try:
        with LiaraClient() as client:
            client.restart(project)
        audit('restart_submitted', mode, project)
        # Probe is a separate HTTPS request to an owner-configured, allowlisted service URL.
        outcome = verify_http(project)
        audit('verify_' + outcome['status'].lower(), mode, project)
        return {'mode': 'live', 'operation': 'restart', 'execution': 'SUBMITTED',
                'verification': outcome['status'], 'verification_detail': outcome,
                'message': 'درخواست ری‌استارت ارسال شد؛ وضعیت بازیابی بر اساس پروب مستقل گزارش می‌شود. صرف API 200 موفقیت نیست.'}
    except LiaraError as exc:
        audit('restart_unknown_or_failed', mode, project)
        raise HTTPException(502, f'{exc}؛ وضعیت نهایی عملیات نامشخص است؛ بدون بررسی مجدد درخواست را تکرار نکنید') from exc

@app.get('/api/audit')
def audit_history(request: Request):
    credentials(request, 'live' if os.getenv('SENTINEL_ACCESS_KEY') else 'demo')
    return {'events': read_audit()}

@app.get('/api/scout/demo')
def scout_demo():
    return {'mode': 'demo-repository', 'analysis': inspect_repo(ROOT / 'examples' / 'fastapi-shop'),
            'disclaimer': 'فقط تحلیل ایستای سورس؛ هیچ دیپلویی انجام نشده است.'}

@app.post('/api/scout')
def scout_workspace(request: Request, payload: ScoutRequest):
    credentials(request, 'live')
    try:
        return {'mode': 'workspace', 'analysis': inspect_repo(repo_from_workspace(payload.path)),
                'disclaimer': 'این مرحله دیپلوی واقعی انجام نمی‌دهد.'}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/deploy/plan')
def deploy_plan(request: Request, payload: DeployPlanRequest):
    actor = credentials(request, 'live')
    if not live_writes_permitted(payload.project):
        raise HTTPException(403, 'طرح انتشار فقط برای پروژه آزمایشی مجاز با پرچم نوشتن فعال قابل ایجاد است')
    try:
        if payload.backend in ('api', 'api-existing'):
            plan = 'existing' if payload.backend == 'api-existing' else payload.plan_id
            result = make_plan(actor, payload.project, payload.path, plan,
                               payload.platform, payload.port)
            result['backend'] = payload.backend
        elif payload.backend == 'cli':
            result = make_cli_plan(actor, payload.project, payload.path,
                                   payload.platform, payload.port)
        else:
            raise DeployError('مسیر انتشار انتخاب‌شده معتبر نیست')
        audit('deployment_proposed', 'live', payload.project)
        return result
    except (DeployError, ValueError, LiaraError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/deploy/execute')
def deploy_execute(request: Request, payload: DeployExecuteRequest):
    actor = credentials(request, 'live')
    if not live_writes_permitted(payload.confirm_project):
        raise HTTPException(403, 'اجازه انتشار زنده برای این پروژه وجود ندارد')
    try:
        if payload.proposal_id.startswith('cli_'):
            project, platform, port, contents = claim_cli_plan(
                actor, payload.proposal_id, payload.confirm_project)
            audit('deployment_cli_approved', 'live', project)
            result = perform_cli_deploy(project, platform, port, contents)
        else:
            project, plan_id, platform, port, contents = claim_plan(
                actor, payload.proposal_id, payload.confirm_project)
            audit('deployment_approved', 'live', project)
            result = perform_deploy(project, plan_id, platform, port, contents)
        audit('deployment_submitted', 'live', project)
        return result
    except (DeployError, ValueError, LiaraError) as exc:
        audit('deployment_failed_or_unknown', 'live', payload.confirm_project)
        raise HTTPException(502, str(exc)) from exc


@app.get('/api/domains/{project}')
def list_domains(request: Request, project: str):
    """Read-only domain and certificate statuses. Never changes DNS."""
    credentials(request, 'live')
    try:
        with LiaraClient() as client:
            return client.domains(validate_name(project))
    except LiaraError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get('/api/domains/check/{domain_id}')
def inspect_domain(request: Request, domain_id: str):
    credentials(request, 'live')
    try:
        with LiaraClient() as client:
            return client.check_domain(domain_id)
    except LiaraError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get('/api/deploy/status/{project}')
def deployment_status(request: Request, project: str):
    """Follow up deployment without equating release submission with success."""
    credentials(request, 'live')
    project = validate_name(project)
    try:
        with LiaraClient() as client:
            releases = client.releases(project)
            details = client.get_project(project)
    except LiaraError as exc:
        raise HTTPException(502, str(exc)) from exc
    history = []
    for item in (releases.get('releases') or [])[:10]:
        if not isinstance(item, dict):
            continue
        history.append({key: item[key] for key in
                        ('_id', 'tag', 'state', 'createdAt', 'finishedAt')
                        if key in item})
    # An optional HTTPS health probe belongs to a server-configured, owned URL.
    observed = verify_http(project)
    if observed['status'] == 'FAILED':
        judgment = 'OBSERVED_UNHEALTHY'
    elif observed['status'] == 'HEALTHY_NOW' and details.get('isDeployed') is True:
        judgment = 'OBSERVED_HEALTHY_ONCE'
    else:
        judgment = 'INCONCLUSIVE'
    return {
        'project': project, 'currentRelease': releases.get('currentRelease'),
        'isDeployed': details.get('isDeployed'),
        'app_status': details.get('status'), 'recent_releases': history,
        'health_observation': observed, 'judgment': judgment,
        'note': 'یک HTTP 200 یا وضعیت آماده نسخه، به‌تنهایی اثبات بازیابی پایدار نیست.'
    }


# Conversational API: graph tools are read-only; writes stay behind existing policies.
from sentinel import conversation as chat_service


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    thread_id: str | None = None
    mode: str = 'demo'
    project: str | None = None
    scenario: str = 'transient'


class ChatApprovalRequest(BaseModel):
    thread_id: str
    proposal_id: str
    confirm_project: str
    approved: bool


@app.post('/api/chat/messages')
def chat_message(request: Request, payload: ChatMessageRequest):
    actor = credentials(request, payload.mode)
    try:
        return chat_service.respond(actor, payload.mode, payload.message,
                                    payload.thread_id, payload.project, payload.scenario)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(403 if isinstance(exc, PermissionError) else 400, str(exc)) from exc


@app.post('/api/chat/stream')
def chat_stream(request: Request, payload: ChatMessageRequest):
    actor = credentials(request, payload.mode)
    def iterate():
        yield 'event: status\ndata: ' + json.dumps({'label': 'در حال تحلیل درخواست و انتخاب ابزار'}) + '\n\n'
        try:
            output = chat_service.respond(actor, payload.mode, payload.message,
                                          payload.thread_id, payload.project, payload.scenario)
            yield 'event: complete\ndata: ' + json.dumps(output, ensure_ascii=False) + '\n\n'
        except (ValueError, PermissionError, LiaraError) as exc:
            yield 'event: error\ndata: ' + json.dumps({'detail': str(exc)}, ensure_ascii=False) + '\n\n'
        except Exception:
            yield 'event: error\ndata: ' + json.dumps(
                {'detail': 'خطای داخلی در جریان گفت‌وگو رخ داد؛ وضعیت را بررسی کنید و عملیات حساس را خودکار تکرار نکنید.'},
                ensure_ascii=False) + '\n\n'
    return StreamingResponse(iterate(), media_type='text/event-stream',
                             headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-store'})


@app.get('/api/chat/threads')
def chat_threads(request: Request):
    actor = credentials(request, 'live' if os.getenv('SENTINEL_ACCESS_KEY') else 'demo')
    return {'threads': chat_service.list_threads(actor)}


@app.get('/api/chat/threads/{thread_id}')
def chat_thread(request: Request, thread_id: str):
    actor = credentials(request, 'live' if os.getenv('SENTINEL_ACCESS_KEY') else 'demo')
    try:
        return chat_service.thread_data(actor, thread_id)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@app.post('/api/chat/approval')
def chat_approval(request: Request, payload: ChatApprovalRequest):
    actor = credentials(request, 'live' if os.getenv('SENTINEL_ACCESS_KEY') else 'demo')
    try:
        thread = chat_service.thread_data(actor, payload.thread_id)
        # Proposal must belong to this exact thread; the model cannot invent approvals.
        valid = any(m['role'] == 'assistant' and
                    any(p.get('proposal_id') == payload.proposal_id
                        for p in m['ui'].get('report', {}).get('proposals', []))
                    for m in thread['messages'])
        if not valid:
            raise PermissionError('این عملیات متعلق به گفت‌وگوی جاری نیست.')
        if payload.approved:
            execution = approve(request, ApproveRequest(
                proposal_id=payload.proposal_id, confirm_project=payload.confirm_project))
        else:
            cancel_approval(payload.proposal_id, actor, payload.confirm_project)
            audit('approval_cancelled', thread['mode'], payload.confirm_project)
            execution = None
        try:
            return chat_service.resume(payload.thread_id, execution)
        except Exception:
            # A successful mutation must never be retried because UI checkpoint failed.
            outcome = {'type': 'execution', 'result': execution} if execution else {'type': 'notice', 'text': 'عملیات لغو شد.'}
            chat_service.add_message(payload.thread_id, 'assistant',
                                     'وضعیت عملیات ثبت شد؛ همگام‌سازی گراف نیازمند بررسی است.', outcome)
            return {'thread_id': payload.thread_id, 'answer': 'وضعیت عملیات ثبت شد؛ همگام‌سازی گراف نیازمند بررسی است.', 'ui': outcome, 'engine': 'recovery'}
    except (RuntimeError, LookupError, TimeoutError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
