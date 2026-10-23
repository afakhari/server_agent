# Contributing / راهنمای مشارکت
## Workflow
۱. قبل از هر تغییر `AGENTS.md` و PRD/ADR مربوط را بخوانید؛ ۲. Issue همراه acceptance criteria تعریف کنید؛ ۳. در شاخه‌ای کوتاه‌عمر پیاده‌سازی کنید؛ ۴. unit/contract/security tests و docs را به‌روز کنید؛ ۵. PR با template باز کنید.
## PR quality bar
- A small, reviewable change with test evidence and no unrelated formatting churn.
- State exactly whether `SPECIFIED`, `MOCK_TESTED` or `LIVE_*_VERIFIED`. Do not call mock a production integration.
- Include source link for any added Liara operation; unknown fields must be probed or explicitly marked unknown.
- All mutation paths require policy tests and reviewer acknowledgement of blast radius.
- Check for accidental secrets and raw logs before pushing.
## Commit conventions
`docs: ...`، `feat: ...`، `fix: ...`، `test: ...`، `security: ...`، `chore: ...`.
## Documentation standards
Persian is primary for product-facing documents; identifier and code symbol names remain English. Use RFC3339 timestamps in UTC, stable evidence IDs, clear links and verified/unknown tags. Update `docs/11-decisions.md` when behavior or assumptions change.
## Reviews
No live deployment/write without a disposable test service and approval. Keep main protected when repository settings allow; ask for at least one code-review on security-sensitive paths.