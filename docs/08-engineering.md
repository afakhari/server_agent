# 08 · Engineering Blueprint و قرارداد توسعه
## ۱. انتخاب پیشنهادی فنی
**Backend:** Python 3.12، FastAPI، Pydantic v2، httpx، SQLAlchemy 2، Alembic؛ **Storage:** PostgreSQL؛ **Frontend:** React/Next.js یا frontend سبک با RTL؛ **Test:** pytest، pytest-asyncio، respx/httpx mocks؛ **Tooling:** Ruff، mypy/pyright، pre-commit و آزمون دستی سبک. CI در این مرحله اجرا نمی‌شود؛ این‌ها انتخاب طراحی‌اند، هنوز در ریپو نصب/قفل نشده‌اند. پیچیدگی Redis/Celery را تا نیاز عملی عقب بیندازیم.
## ۲. ساختار هدف
```text
server_agent/
  README.md
  AGENTS.md
  docs/                      # product, contracts, threats, tests, demo
  backend/
    pyproject.toml
    src/server_agent/
      api/                    # auth, incidents, approvals, services, runs
      core/                   # config, logging, policy, state
      domain/                 # typed models
      connectors/liara/       # http client, schemas, capability probes
      evidence/               # collectors, normalization, masking
      diagnosis/              # rules, optional LLM analyst
      workflows/              # deploy + incident state machines
      actions/                # executor and verification
      persistence/            # sqlalchemy repositories + migrations
    tests/{unit,contract,integration,security,e2e}/
  frontend/
    src/{app,components,features,lib}/
  examples/                   # deliberately broken disposable sample app
  fixtures/                   # sanitized synthetic Liara responses
  .github/workflows/
```
## ۳. Contracts between layers
API request validated at boundary → Domain command → Workflow, never raw JSON forwarding to HTTP. Adapter returns typed `Result[T]` with source status, observed_at and redacted error code. Evidence IDs stable for the analysis run. Policy takes fully specified immutable `ProposedOperation` and authenticated principal; provides `ALLOW_READ | REQUIRE_APPROVAL | DENY`. Executor requires a server-issued `AuthorizedExecutionContext` impossible to construct from model response.
## ۴. Configuration
```dotenv
APP_ENV=local
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/server_agent
LIARA_API_BASE_URL=https://api.liara.ir
LIARA_API_TOKEN=
LIARA_WRITES_ENABLED=false
LIARA_ALLOWED_PROJECTS=
AGENT_LLM_ENABLED=false
MAX_TOOL_CALLS_PER_RUN=15
DEFAULT_INCIDENT_LOOKBACK_MINUTES=30
```
این مقادیر فقط مثال‌اند؛ `.env` را commit نکنید. در محیط CI credential واقعی نباشد. tenant secret storage در production باید طراحی جداگانه داشته باشد.
## ۵. مراحل پیاده‌سازی کوچک و تحویل‌پذیر
**M0:** skeleton، typed config، SQLite ledger، تست‌های دود سبک به‌صورت دستی و fixtureهای مصنوعی؛ CI به مرحله نهایی موکول شده است.
**M1:** read-only adapter با پروژه/لاگ/event/release/metrics، contract snapshots، خطای 401/404/429.
**M2:** evidence ledger + timeline + rules و hypothesis citations؛ UX گزارش diagnosis.
**M3:** durable workflow + risk classification + parameter-bound approval + audit.
**M4:** restart با permission فقط روی disposable app + verifier + independent HTTP probe.
**M5:** Project Scout و guided deploy با CLI رسمی، source boundary، plan confirmation و domain handoff.
**M6:** اختیاری LLM محدود + coding patch/PR + regression eval؛ presentation-ready.
هر milestone باید خودش تست، نمایش و معیار DoD داشته باشد؛ کدهای mock نباید به‌عنوان live نمایش داده شوند.
## ۶. برنامه PRها
- PR-001 scaffold and quick local validation
- PR-002 Liara read-only adapter + fixture contract tests
- PR-003 Evidence model + diagnostics
- PR-004 RTL incident UI
- PR-005 Durable approvals and action policy
- PR-006 Disposable restart + verifier
- PR-007 Scout + deploy workflow
- PR-008 Hardening, injection/SSRF tests and demo
هیچ PR قابلیت بزرگ چندگانه را بدون تست جمع نکند.
## ۷. قواعد Git
شاخه کوتاه‌عمر، PR کوچک، عنوان conventional commit، ≥۱ review برای live mutation path، protected main پس از امکان تنظیم GitHub. مرور کد و تست‌های دود سبک هنگام توسعه کافی‌اند؛ پوشش کامل آزمون‌ها قبل از تحویل نهایی الزامی است. PR template شامل «هدف/تغییر API/ریسک امنیتی/معیار پذیرش/مدرک دمو».
## ۸. Acceptance technical
- typed response decode با malformed sample.
- همه toolها timeout و bytes cap.
- POST retry ممنوع مگر semantics ثابت.
- secrets never logged.
- database approval atomic.
- independent verifier fail-closed.
- tests بدون API secret از صفر اجرا شوند.
## ۹. Deploy خود Server Agent
برای نسخه آزمون، خود سرور Agent در محیط محدود deploy شود؛ اتصال HTTPS و secret store لازم است. **تفاوت بین deploy کردن خود Agent و deploy کردن برنامه کاربر روی Liara** در کد و مستندات روشن باشد.
## ۱۰. مهاجرت از نمونه اثبات مفهوم قبلی
نمونه محلی `liara-sentinel-mvp` سابق در مکالمه وجود داشته ولی در این ریپو درج نشده است. قبل از انتقال: audit dependency، حذف demo switches پرخطر، جداکردن web/engine/client، port test behavior و افزودن DB approvals، tenancy و verifier. کپی مستقیم آن به production ممنوع است.