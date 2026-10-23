# Server Agent · Liara Sentinel

> **Status:** architecture and implementation specification / طراحی و نقشه اجرای محصول. **No production integration is claimed.**

Liara Sentinel is a proposed **evidence-driven deployment and site-reliability assistant** for Liara PaaS. This repository is the **single source of truth** for development and the competition deliverable.

**Product promise:** understand the project or incident → collect real evidence → propose the safest useful action → require exact human approval for impactful changes → execute through a verified adapter → independently verify the outcome.

## Run the functional prototype

See [RUNNING.md](RUNNING.md) for environment setup, how to run, live-read access, deliberately gated test-only writes and limitations.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn app:app --host 127.0.0.1 --port 8000
```

The UI is in Persian and starts in explicitly simulated mode. Actual deployment requires user-controlled test account credentials and validation.

## Start here / راهنمای مطالعه
0. [Official challenge traceability](docs/00-competition-traceability.md)
1. [Product requirements and competition alignment](docs/01-product-prd.md)
2. [Architecture and boundaries](docs/02-architecture.md)
3. [Liara API contracts and capability validation](docs/03-liara-api.md)
4. [Agent workflows and state machine](docs/04-workflows.md)
5. [Evidence-led troubleshooting](docs/05-diagnostics.md)
6. [Action authorization and threat model](docs/06-security.md)
7. [User experience and design specification](docs/07-ux.md)
8. [Engineering setup and implementation plan](docs/08-engineering.md)
9. [Testing and acceptance rubric](docs/09-testing.md)
10. [Five-minute demo and submission](docs/10-demo.md)
11. [Decisions, assumptions, and unknowns](docs/11-decisions.md)
12. [Source references](docs/12-references.md)
13. [Delivery roadmap](docs/13-delivery-roadmap.md)
14. [Live integration runbook](docs/14-liara-integration-runbook.md)
15. [Market benchmark](docs/15-market-benchmark.md)
16. [Working agreement for coding agents](AGENTS.md)
17. [Security policy](SECURITY.md) and [contribution guide](CONTRIBUTING.md)

## Truthfulness and maturity
- **SPECIFIED:** behavior is documented; not proof of implementation.
- **MOCK-TESTED:** tested with fixtures or simulations; not proof of live operation.
- **LIVE-READ VERIFIED:** actual Liara read API exercised on a test account, with redacted evidence.
- **LIVE-WRITE VERIFIED:** authorized mutation performed on a designated disposable test project, with evidence.
- **RECOVERY VERIFIED:** independent health and regression checks passed after a change.

**Functional prototype now lives in this repository:** `app.py`, `sentinel/`, `static/`, `tests/` and `examples/`. The current implementation has been **locally mock-tested with 33 passing tests**, but **no live Liara operations have been verified**. Start at [RUNNING.md](RUNNING.md). Development continues through small, testable pull requests.

## Non-negotiable rules
- Deny-by-default for mutations. No free-form shell commands via LLM.
- Never put API tokens, environment secret values or sensitive raw logs in Git, model prompts or browser responses.
- API 200/202 does **not** mean deployment or recovery succeeded.
- Treat logs, repository content and tool responses as **untrusted data**.
- Validate Liara OpenAPI operations in a safe test account before claiming live support.
- No production writes during demos.

## Design priorities
The competition scores 300 points: Liara integration 100; intelligence and troubleshooting 100; UX 50; reliability/security 50. Highest-priority vertical slice: **real evidence → diagnosis → exact approval → safe action → verified outcome**; then complete first deployment.

Primary API spec: https://github.com/liara-cloud/openapi/blob/main/spec/paas.yaml

Documentation review date: **2026-10-23**. Details must be revalidated against the API spec and runtime responses as development proceeds.

## Delivery policy for this development phase
No automated GitHub CI runs by design. New focused offline checks are in tests/; run locally when preparing a release. Live Liara operations remain unverified. Canonical implementation is app.py + sentinel/ (not the superseded parallel experimental branch). See docs/16-implementation-status.md.

### New read-only operations: domain + release status
The UI has a 'دامنه، SSL و وضعیت انتشار' panel using read-only GET domain listing and release status. Deployment verification reports OBSERVED_HEALTHY_ONCE at most, never sustained recovery without continued observation. Requires configured server-side Liara credentials and operator key. Real-world responses must still be tested on a disposable account.

## Official Liara CLI as a second deployment transport

The project supports two **separately approved** publication paths:
1. API backend for create → upload → release (existing experimental flow).
2. CLI backend to deploy a vetted staged archive to an **already existing, disposable test app**. CLI authentication uses an explicitly configured account in a private HOME directory; no HTTP API token is sent as a command-line argument.

The CLI path is **off by default**, and both paths remain unverified against a live account in this development session. See [CLI integration runbook](docs/17-cli-integration.md). Read-only SRE collection still uses the API.

Official docs: https://developers.liara.ir/ and https://github.com/liara-cloud/cli

## راهنمای دقیق صاحب پروژه / Operator quick start

راهنمای فارسی گام‌به‌گام: [docs/18-operator-steps-fa.md](docs/18-operator-steps-fa.md). برای اجرای محلی امن و بدون نوشتن کلید در فایل:

    python scripts/run_local.py --mode demo --check
    python scripts/run_local.py --mode demo

پس از ساخت پروژه و توکن آزمایشی توسط مالک، حالت‌های `--mode read` و سپس `--mode test-cli` تنها با تأیید محدود فعال می‌شوند. **توکن را در چت یا ریپو قرار ندهید.** آزمون زنده هنوز انجام نشده است؛ CI نیز عمداً فعال نیست.

### Real, controlled test incident
The bundled disposable FastAPI example now supports an **opt-in missing-env failure**: set `SENTINEL_REQUIRE_DEMO_FLAG=true` and leave `SENTINEL_DEMO_FLAG` unset to produce a real HTTP 500 and explicit stacktrace; setting `SENTINEL_DEMO_FLAG=ready` restores `/health`. This requires changes **only** on the disposable test app in Liara Console and is NOT an autonomous env fix. See [operator walkthrough](docs/18-operator-steps-fa.md).

### Windows users: deploy to an existing Liara test app
The guided deployment wizard now defaults to **API: publish to existing application**, so no extra app creation or CLI/WSL is required. Launch locally with `python scripts/run_local.py --mode test-api --project YOUR_DISPOSABLE_APP` only after understanding billable effects. Pick path `fastapi-shop`, platform Python, port 8000, and the exact allowlisted project ID. A preview and an exact one-use approval are mandatory. The request result is SUBMITTED, not independently VERIFIED.

### Existing application platform check
The wizard validates the API project's `type` against the selected source platform. Platform spelling differs only by letter case? Both `Python` and `python` are accepted. An actual mismatch (for instance `node` vs `python`), missing metadata, or a different project ID **blocks all writes**, showing a safe non-secret diagnostic. The account's read-only project dropdown now labels actual platform types. Do not bypass a mismatch by editing request parameters blindly.

### Existing Liara Node application (Windows, no CLI)
The real account project may be **Node.js**, not Python. Do not upload the Python
FastAPI example to a Node application. Choose the new zero-dependency
[Node Sentinel demo](examples/node-sentinel-demo/README.md). In the existing-app
API wizard, use path `node-sentinel-demo`, platform `node`, port `8000`
and the **exact project ID returned by the Liara API**. The project picker now
populates the matching platform and source path automatically for Node or Python.
Node packaging follows Liara's documented `package.json` start script.
The API upload and release write paths remain live-unverified until tested
against a disposable account. Inspect costs and preview before approval.

## Team-owned Liara apps (critical for correct account context)
When the Console shows an app under a **team** but the regular API returns a different personal app, use an explicit team ID from that team's API page. On Windows CMD run `python scripts\run_local.py --mode read --team-id YOUR_TEAM_ID --project YOUR_TEAM_APP_ID` using the server-side bearer token prompt. First verify only read access and the exact target/platform; do not enable writes until the list shows the expected team app. `LIARA_TEAM_ID` is automatically merged into all Liara GET/POST requests including source uploads. Team CLI subprocess mode is deliberately disabled. [Full Persian team runbook](docs/19-team-access.md).


## Conversational Agent Workspace (new, branch feature/conversational-agent-langgraph)

A full-screen Persian/RTL React + assistant-ui client and a LangGraph-backed conversation API have been added alongside the previous single-page diagnostic console. The server keeps its existing policy-bound, one-use write approvals and Liara adapters. **This branch is an implementation candidate; neither live Liara writes nor browser builds have been independently verified in this editing environment.**

Quick start after installing Python and Node dependencies:

```bash
python -m pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
# separate terminal
cd frontend && npm install && npm run dev
```

For a single host, run `cd frontend && npm run build`, then restart FastAPI to serve `frontend/dist`. New API endpoints: `/api/chat/messages`, `/api/chat/stream`, `/api/chat/threads`, `/api/chat/threads/{id}`, `/api/chat/approval`.

- [Decision and architecture](docs/19-conversational-architecture.md)
- [Installation, validation, security and demo runbook](docs/20-conversation-runbook.md)
