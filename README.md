# Server Agent · Liara Sentinel

> **Status:** architecture and implementation specification / طراحی و نقشه اجرای محصول. **No production integration is claimed.**

Liara Sentinel is a proposed **evidence-driven deployment and site-reliability assistant** for Liara PaaS. This repository is the **single source of truth** for development and the competition deliverable.

**Product promise:** understand the project or incident → collect real evidence → propose the safest useful action → require exact human approval for impactful changes → execute through a verified adapter → independently verify the outcome.

## Start here / راهنمای مطالعه
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
13. [Working agreement for coding agents](AGENTS.md)

## Truthfulness and maturity
- **SPECIFIED:** behavior is documented; not proof of implementation.
- **MOCK-TESTED:** tested with fixtures or simulations; not proof of live operation.
- **LIVE-READ VERIFIED:** actual Liara read API exercised on a test account, with redacted evidence.
- **LIVE-WRITE VERIFIED:** authorized mutation performed on a designated disposable test project, with evidence.
- **RECOVERY VERIFIED:** independent health and regression checks passed after a change.

The earlier local proof of concept discussed in planning is **not currently installed in this repository**; review and port it only after verifying behavior and dependencies. Development should happen here via small, testable pull requests.

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
