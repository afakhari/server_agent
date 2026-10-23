# Running the functional Liara Sentinel prototype

**Maturity:** prior development reported local mock-tests (33 tests); newly added tests require a fresh local run before final submission; live read/write and real deployment remain **unverified**. Designed for **localhost and disposable test accounts**. Do not place on a public network or connect production projects.

## Install and run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Visit http://127.0.0.1:8000. The default mode is DEMO with synthetic evidence. Choose scenarios: process crash, missing env, memory fault, bad release or healthy. The incident page contains evidence IDs, hypotheses, an optional advisory LLM and a one-use simulated restart approval. Project Scout analyzes the bundled sample without executing it.

## Connecting real Liara **read-only**

1. In the **server environment**, set `LIARA_API_TOKEN` and generate a long random `SENTINEL_ACCESS_KEY` (≥24 characters). Do not expose either through Git, screenshots, chat or browser storage.
2. Restart the local application. Choose **live** mode and enter the **Sentinel access key** when prompted. This is **not** the Liara token.
3. Enter an existing project name; reads include project details, logs, releases, events and metrics. Missing source data is disclosed and raw metrics are not presented as percentages.

This prototype is single-operator and uses a shared key: **not a production multi-user authentication architecture**.

## Enabling a live **write on disposable test resources only**

Writes are disabled by default. The explicit local gates are:

```dotenv
SENTINEL_ALLOW_LIVE_WRITES=true
SENTINEL_ALLOWED_PROJECTS=your-disposable-test-app
SENTINEL_ACCESS_KEY=<long-random-agent-access-key>
LIARA_API_TOKEN=<real-token-in-server-secret-store>
SENTINEL_HEALTH_URLS={"your-disposable-test-app":"https://your-owned-domain.example/health"}
SENTINEL_WORKSPACE=/absolute/path/to/local/allowed-workspace
```

Before enabling: have a billing limit and a fully disposable app, verify backup/recovery plan, and check the actual API contract. The restart action is only proposed when rule-based diagnostics find signs of a crashed process, and always requires one-use confirmation. The health URL is optional, server-specified and must resolve to globally routed addresses; when unavailable, outcome is `INCONCLUSIVE`. No response body is stored.

### Deployment endpoints (API-driven, **untested against live Liara**)

First create a proposal via `POST /api/deploy/plan` with JSON:

```json
{"project":"your-disposable-test-app","path":"sample","platform":"python","port":8000,"plan_id":"your-verified-plan-id"}
```

Send `X-Sentinel-Access-Key` header. The workspace path must be relative to `SENTINEL_WORKSPACE` and contain a supported manifest. The response includes `proposal_id`, source SHA256, included files and pricing warning. Verify the plan and billable effects manually.

After exact human approval, submit `POST /api/deploy/execute` with `{ "proposal_id": "...", "confirm_project": "..." }` and the same key. It consumes approval atomically and attempts `POST /v1/projects` → multipart `POST /v2/projects/{name}/sources` → `POST /v2/projects/{name}/releases`. **Returned SUBMITTED is not a successful release or successful HTTP deployment**. If any stage fails or times out, inspect the Liara panel before repeating: partial side effects are possible. This workflow is API-accessible; the visual guided deployment wizard remains to be built.

## Environment and safeguards

- `SENTINEL_DB_PATH` optional path for persistent SQLite approvals/audit. Store this outside Git, and restrict file permissions.
- `SENTINEL_LLM_ENDPOINT`, `SENTINEL_LLM_API_KEY`, `SENTINEL_LLM_MODEL` enable optional **advisory only** LLM reasoning; it cannot authorize a write.
- All models/logs are untrusted. Logs shown to the user are redacted and bounded; env values are removed at the adapter boundary.
- Current HTTP probing is a conservative best-effort diagnostic, not a complete SSRF-proof network sandbox. Do **not** expose it publicly before egress pinning, real authentication, CSRF/session handling, tenant isolation and comprehensive reviews.

## Tests

```bash
python -m pytest -q
```

Tests use fixtures and local SQLite with no external API calls. Automated GitHub CI has been removed to focus on fast development; run this command manually before submission. See `docs/09-testing.md` for broader required acceptance tests that are not fully automated yet.

## Important limitations

The current service does not provide a durable distributed workflow queue, tenancy, full job progress, production-safe DNS pinning, billing/pricing verification, domain registrar changes, automatic rollback or proven live deployment. The only runtime-verified capability is local mock behavior. See `docs/11-decisions.md` and `docs/14-liara-integration-runbook.md` for validation gates.

## Optional official CLI transport

Select "CLI رسمی" in the deployment wizard. Configure a dedicated isolated CLI account and the binary according to [docs/17-cli-integration.md](docs/17-cli-integration.md). This mode deploys **only to an existing, allowed disposable app** and does not pass the Liara token through process arguments. It still requires Sentinel's existing write and approval gates. The submitted result is not verified recovery.

### Simple local launcher (no saved token)

For step-by-step owner actions, see [docs/18-operator-steps-fa.md](docs/18-operator-steps-fa.md).

    python scripts/run_local.py --mode demo --check
    python scripts/run_local.py --mode demo
    python scripts/run_local.py --mode read --project YOUR_EXISTING_TEST_PROJECT

The launcher prompts for the API token invisibly and prints a distinct local Sentinel access key. Only `--mode test-cli` or `--mode test-api`, after exact terminal confirmation, enables test writes. No production use. Optional `--health-url https://your-owned-domain/health` binds an owned HTTPS probe to `--project`.
