# 22 · Security / Release Readiness Audit · 2026-10-23

**Verdict: NO-GO for internet production. CONDITIONAL GO for private VPS staging after passing the release gate.**

Scope: private repository source on branch `feature/conversational-agent-langgraph`; historical Windows test log; static inspection of FastAPI, Liara adapters, LangGraph conversation, React, health probing, deployment configuration. This assessment does **not** claim execution of the current full test suite or Docker image, a browser audit, live Liara operation, penetration testing, or possession of a server.

## Verified from source

- FastAPI exposes typed read operations and keeps privileged restart/deployment behind operator key and one-use, parameter-bound approval, plus server-side allowlist.
- Chat conversations persist in SQLite and LangGraph checkpoints use an adjacent SQLite file. A single worker is chosen in the staging container.
- Demo fixtures are labeled, and submitted operations are not equated with independently verified site health.
- New `private-server` startup gate enforces a strong non-placeholder secret, an absolute writable volume, graph dependency presence, frontend build files and explicit no-write/no-CLI.
- Docker image defaults to `private-server`, runs as nonroot, drops capabilities, mounts writable data and temporary volume only; Compose publishes Caddy's TLS ports, not Uvicorn.
- Caddy authenticates all UI and API traffic. No password/hash/token has been committed in these example files.
- `scripts/check_server_release.py` inspects the private environment setup, package-lock and frontend build without echoing credentials.

## Outstanding findings / remediations

| Severity | Finding | Risk | Status / required proof |
|---|---|---|---|
| Blocker | No successful current React/TypeScript build | Browser may not function at all | Generate and commit package-lock, npm ci, npm run build |
| Blocker | GitHub Actions previously failed before any job steps; no logs | CI has not validated tests | Fix runner availability/permissions and run offline pytest and npm build locally |
| Blocker | No target server, DNS, TLS, reverse-proxy smoke results | No evidence of an actually working HTTPS service | Run Compose and authenticate; record redacted curl status |
| Blocker | Actual Liara API/write contracts and post-action recovery not tested live | Cannot promise real deploy/recovery | Disposable project tests with operator consent, separate from public staging |
| High | Shared Sentinel key / single operator; no tenant/user identity infrastructure | Not appropriate for public multi-user SaaS | Restrict to private operator or implement dedicated identity, session and RBAC |
| High | Caddy Basic Auth has no configured brute-force throttling in this Compose | Attack surface if accessible to all internet | Strong unique secret, optional VPN/IP allowlist, proxy rate control and access monitoring |
| High | Health probe pre-resolves DNS but does not pin TCP dial to validated IP | DNS rebinding/SSRF for a wrongly configured health host | Keep owner-only URLs and restrict egress; implement IP-pinned transport before production |
| High | SQLite snapshots and graph checkpoint require single writer and backup strategy | Data loss/inconsistency during multi-worker scale | One worker, persistent volume, offline backup and restore exercise |
| Medium | Some dependencies permit floating ranges; no committed npm lock yet | Supply chain and nonreproducible builds | Commit reviewed package-lock and reproducible image build; pin digests for formal release |
| Medium | SSE sends stage/end events, not token deltas; network disconnect behavior not browser-tested | UX may feel stalled, duplicate attempts possible | Manual browser tests, block concurrent actions, accurate retry handling |
| Medium | Logs and model narrative may include limited redacted evidence | Sensitive operational data retention | Review retention, redaction, audit, and encrypted backup handling |
| Medium | No distributed background queue / migrations / rollback automation | Crash and rollout recovery limits | Restrict private staging; add release process before scaling |
| Medium | Security headers and edge auth need real-browser verification | CSP may block any dynamically injected UI styles | Test in desktop/mobile browser over HTTPS and watch console errors |

## Release go/no-go sequence

1. Do **not** merge the Draft PR until server-specific tests and frontend build pass.
2. Generate `frontend/package-lock.json`, commit it, build with npm ci. Do not run unreviewed global installs or unknown generated shell commands.
3. Install feature requirements in an isolated Python environment and run `python -m pytest -q` on Windows and Python 3.12 Linux.
4. Run `python scripts/check_server_release.py` using privately configured, gitignored app.env and caddy.env.
5. Run `docker compose -f compose.server.yaml config --quiet && docker compose -f compose.server.yaml build`.
6. Deploy only to a disposable **private single-operator** VPS using the runbook in docs/21; keep LIARA write flags false.
7. Confirm HTTPS and 401 without Caddy credentials, authenticated page loads, 403 without Sentinel header and 200 authenticated /healthz, persistent chats and denial of write.
8. Test cold restart, restore from backup and roll back to an earlier reviewed commit.
9. Collect redacted evidence of all checks; only then mark staging release GO.

**Explicit distinction:** Running Sentinel **on the server** is different from granting Sentinel permission to modify arbitrary Liara applications. The latter requires separately validated Liara credentials, resource ownership, restricted test app allowlisting and approvals.
