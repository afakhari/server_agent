# Liara Sentinel · Server Agent

**Executable, single-operator MVP** for Liara PaaS: inspect logs and recent releases, build evidence-backed hypotheses, propose bounded actions, request human approval, then independently assess the result.

**Status on 2026-10-23:** the application and offline demo are implemented in this repository. Liara real read/write actions **have not yet been validated with a live test account**. This is not production-ready. No credentials are included.

## Quick start (no token needed)

Requirements: Python 3.12+ recommended.

    git clone https://github.com/afakhari/server_agent.git
    cd server_agent
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app:app --host 127.0.0.1 --port 8000

Windows activation: .venv\Scripts\activate

Open http://127.0.0.1:8000 . The RTL interface defaults to a synthetic offline demo. Change failure scenarios, inspect evidence and hypotheses, preview a restart, and issue a **single-use approval**. Simulated actions are explicitly labeled. Inspect the bundled FastAPI sample and preview a controlled release.

## Implemented today
- Focused Persian RTL incident and release interface.
- Five simulated incident classes plus a healthy baseline.
- Typed read-only Liara adapter: projects, logs, events, releases, applets, summary metrics; no made-up CPU/RAM percentage.
- Rule-based diagnostic engine with Evidence IDs, log scrubbing and explicit uncertainty.
- SQLite operational ledger with expiry, target-specific single-use approval, drift check and audit.
- Live restart for a **single preapproved disposable test project** (off by default).
- Guarded creation of a disposable project using a **user-provided planID**; price is explicitly UNVERIFIED. Live behavior not yet tested.
- Upload/release of a **fixed audited sample** to an **existing test app** using documented Liara API operations (off by default; live API contract pending test).
- Independent post-operation project read + optional operator-bound HTTPS probe; missing probe means INCONCLUSIVE.
- Static Scout for package config/platform/port/environment key **names**, never environment values.
- Offline smoke tests without CI.

## Connect a Liara test account

Use server-side environment variables or a secret manager. Never commit a real token.

    export LIARA_API_TOKEN="YOUR_SECRET_TOKEN"
    export SENTINEL_ACCESS_KEY="LONG_RANDOM_OPERATOR_KEY"
    uvicorn app:app --host 127.0.0.1 --port 8000

The access key is typed in the web UI and remains in page memory; do not expose this app to the internet without HTTPS and hardened authentication. Live access depends on the API contract and the permissions of your Liara account.

**Live write guard:** all of LIARA_ENABLE_WRITES=true, LIARA_TEST_PROJECT=(exact project name), LIARA_API_TOKEN and SENTINEL_ACCESS_KEY must be present. Only that exact disposable project may be changed. Every mutation requires per-operation human approval.

**Verification:** configure SENTINEL_HEALTH_PROJECT, SENTINEL_HEALTH_URL (an HTTPS endpoint you own), and LIARA_ALLOWED_HEALTH_HOSTS (exact host). Without a bound safe probe, API acknowledgement is **NOT** proof of recovery. The current probe safeguards are not a full production egress firewall.

See [.env.example](.env.example) and [Live test runbook](docs/14-liara-integration-runbook.md).

## Honest boundaries
- Guarded project creation with a **user-selected planID** is implemented, but plan costs are NOT verified. No automated billing management, registrar actions or autonomous rollback.
- No production-grade user authentication, multi-tenant security or around-the-clock monitoring.
- No LLM free-form tools or uncontrolled commands.
- API success means submitted, not necessarily recovered.
- The bundled example deploys to an **existing** Liara test project; project creation is a separately approved step.

## Manual smoke tests (no CI)

    pytest -q

The included tests are a **starting safety net**, not a completed validation campaign. Only describe a capability as live-verified after collecting redacted, reproducible evidence from a disposable Liara service.

## Development references
- [Competition requirements](docs/00-competition-traceability.md)
- [Product specification](docs/01-product-prd.md)
- [Architecture](docs/02-architecture.md)
- [Liara API contract](docs/03-liara-api.md)
- [Workflows](docs/04-workflows.md)
- [Diagnosis](docs/05-diagnostics.md)
- [Security](docs/06-security.md)
- [UX](docs/07-ux.md)
- [Engineering](docs/08-engineering.md)
- [Testing](docs/09-testing.md)
- [Five-minute demo](docs/10-demo.md)
- [Decisions](docs/11-decisions.md)
- [Roadmap](docs/13-delivery-roadmap.md)
- [Integration runbook](docs/14-liara-integration-runbook.md)
- [Coding agent conventions](AGENTS.md)

**Priority next:** run real read-only Liara contract probes in a disposable account, then complete one approved test mutation with independent verification. No CI workflows have been added.
