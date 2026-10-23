# Security Policy (design-stage repository)
This repository currently contains product and engineering specifications, **not a deployed production service**.

## Reporting
Do not open a public GitHub issue containing API tokens, user log excerpts or exploit details. Report privately to the repository maintainer through the agreed secure channel. Revoke exposed Liara tokens immediately through the provider if you suspect leakage.

## Mandatory development controls
- Secrets only server-side; `.env`, credentials and sanitized production logs never committed.
- Read-only by default; mutate only via server-side policy, atomic single-use approval and allowlisted target.
- LLM outputs and log/source content are untrusted; never execute free-form shell requests.
- All probes protect against SSRF and redirects to internal IP ranges.
- No production write tests; test credentials/accounts are isolated and disposable.
- No claims of success until independent health verification.
- PRs changing permissions, executor, adapter or probe require security-focused review.

Threat model and verification: [docs/06-security.md](docs/06-security.md) and [docs/09-testing.md](docs/09-testing.md).