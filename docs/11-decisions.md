# 11 · ADR، فرضیه‌ها، محدودیت‌ها و سؤال‌های باز
## ADR-001: One workflow orchestrator, not free-roaming multi-agent
**تصمیم:** orchestration قطعی با typed tools و چند evaluator تخصصی؛ LLM نقش تحلیلگر مشورتی. **دلیل:** تست‌پذیری، هزینه کمتر، کنترل امنیت و ارائه قانع‌کننده در زمان محدود. **هزینه:** آزادی خودمختاری کمتر؛ با plug-in analyst قابل توسعه.
## ADR-002: Proof-of-recovery first
**تصمیم:** تعریف success بر اساس مستقل بودن verifier از executor. **دلیل:** API 200 فقط درخواست را پذیرفته؛ ممکن است سرویس همچنان خراب باشد. **هزینه:** latency و خطای false-negative در probe؛ برچسب inconclusive راه‌حل صادقانه است.
## ADR-003: Liara OpenAPI is contract source, runtime is arbiter
**تصمیم:** endpointها از OpenAPI رسمی استخراج شوند، ولی payload و semantics با disposable test account تایید گردند. **دلیل:** نسخه spec ممکن است با runtime تفاوت داشته باشد. **هزینه:** smoke test و fixtures لازم است.
## ADR-004: Default deny and atomic approvals
**تصمیم:** read-only پیش‌فرض، mutation فقط با payload-bound approval ذخیره‌شده تراکنشی. **دلیل:** prompt injection، replay و race. **هزینه:** UX شامل یک مرحله تایید بیشتر.
## ADR-005: No automatic rollback promise yet
**تصمیم:** مشاهده history انتشار مجاز؛ rollback اجرایی در MVP تا تایید API/CLI disabled. **دلیل:** spec بررسی‌شده endpoint واضح activation release قبلی ندارد. **هزینه:** برای recovery ممکن است redeploy از artifact verified لازم شود؛ آن هم فقط بعد از تحقیق.
## ADR-006: CLI-first guided deployment
**تصمیم:** برای P1 از CLI رسمی version-pinned، bounded argv استفاده شود؛ direct upload API در صورت قرارداد تاییدشده. **دلیل:** بسته‌بندی سورس/compatibility. **هزینه:** dependency Node CLI و sandbox.
## ADR-007: Modular monolith
**تصمیم:** یک backend با interfaceهای مستقل؛ Postgres durable store. **دلیل:** سرعت ساخت MVP و tracing خطا. **هزینه:** تفکیک serviceهای مستقل در مقیاس آینده.
## ADR-008: Rules baseline + optional LLM
**تصمیم:** قواعد قابل آزمون اول؛ LLM برای فرضیه/توضیح افزوده شود، نه authority یا اجرای مستقیم. **دلیل:** قابلیت دمو حتی در نبود API مدل؛ جلوگیری از پاسخ بی‌شاهد.
## سؤالات باز (بلوک اجرایی)
| شناسه | موضوع | مرجع پاسخ | تاثیر | مالک پیشنهادی |
|---|---|---|---|---|
| Q01 | exact logs since syntax | live read | parsing | Backend |
| Q02 | unit CPU/RAM + plan resource denominator | API response/panel | diagnostics | Backend |
| Q03 | planIDs/pricing current | official price and live plan selection | costing | Product |
| Q04 | release submit/ready semantics | disposable deployment | verifier | Backend |
| Q05 | env.update merge/replace و restart effect | test project | security | Backend |
| Q06 | teamID auth scoping | Liara docs/live test | tenancy | Security |
| Q07 | deploy rollback via verified support | CLI/spec/support | recovery | Backend |
| Q08 | DNS/SSL issuance latencies | owned test domain | domain UX | Frontend |
| Q09 | health endpoint selection and ownership | app config/user | SSRF and correctness | Security |
| Q10 | available time, budget and skills | project owner | plan | Product |
## وضعیت قابلیت‌ها
`SPECIFIED`، `MOCK_TESTED`، `LIVE_READ_VERIFIED`، `LIVE_WRITE_VERIFIED`، `RECOVERY_VERIFIED`. انتقال وضعیت فقط با شماره test/evidence ممکن است. نبود داده به معنی UNKNOWN است، نه SUCCESS.
## فرضیات معماری
- امکان دریافت API token از صاحب حساب؛ صحت دسترسی با آزمون.
- پروژه disposable و منابع مالی محدود برای smoke test در دسترس قرار می‌گیرد؛ هنوز تضمین نشده.
- یک کاربر و یک workspace برای اولین MVP؛ multi-tenant rollout جدا.
- تاریخ ویدیو/ثبت مسابقه از بریف ما مشخص نیست؛ هیچ deadline اختراع نشود.
## تغییر تصمیم
هر ADR با PR شامل alternative، rationale، impact on tests/security/UX و تاریخ بازبینی جایگزین شود.

## Implementation checkpoint · 2026-10-23
A local, single-operator FastAPI prototype, guarded Liara adapter, SQLite one-use approval, rules diagnosis, optional explanatory LLM, owner-configured HTTPS probe and guarded API source upload/release are now implemented and mock-tested (33 tests). UI includes incident analysis, static scout and gated guided deployment preview. **No production auth, tenant isolation, live API contract, pricing validation, release-ready polling, DNS-pinned probe or sustained recovery verification is claimed.** Next objective is live-read contract testing with a disposable account and hardened integration.
