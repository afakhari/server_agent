# 04 · گردش‌کارها، وضعیت‌ها و قرارداد ابزارها
## ۱. ماشین حالت سراسری
`CREATED → SCOPING → COLLECTING → ANALYZING → PLANNED → AWAITING_APPROVAL → EXECUTING → VERIFYING → VERIFIED | FAILED | INCONCLUSIVE | CANCELLED`.
- مراحل read-only می‌توانند `ANALYZING → COLLECTING` را برای حداکثر ۲ دور تکرار کنند (مقدار اولیه پیشنهادی).
- عملیات بدون تغییر از `PLANNED → VERIFIED` فقط با نتیجه read-only موجه عبور می‌کند.
- هر run دارای deadline، `run_id`، owner، target و snapshot hash است.
- `VERIFIED` تنها با آزمون مستقل؛ `API_ACCEPTED` event میانی است، نه state نهایی.
## ۲. Incident workflow (P0)
1. مالک سرویس و محیط از UI انتخاب؛ اجازه cross-tenant در تمام پرس‌وجوها بررسی شود.
2. زمان رخداد و symptom جمع؛ اگر زمان نامعلوم، بازه پیش‌فرض کوچک و قابل‌تغییر تعیین شود.
3. درخواست typed و bounded به project/log/events/release/metrics/applets، با کنترل partial failure.
4. داده‌ها redact، timestamp UTC، fingerprint و evidence ID می‌گیرند.
5. Rules candidateها را می‌سازند؛ LLM در صورت اتصال فقط explanation/hypotheses structured به دست می‌دهد.
6. Investigation View: hypothesis + supporting/contradicting + next check.
7. RecommendedAction از allowlist ساخته می‌شود؛ Policy قبل از پیش‌نمایش action class را چک می‌کند.
8. کاربر preview دقیق (target, before/after, risk, price effect if proven, expiry) را می‌بیند و تأیید/رد می‌کند.
9. هنگام execution، digest دوباره محاسبه می‌شود؛ mismatch/expiry/cancel → توقف.
10. API result ثبت، verifier با پنجره‌های محدود state و health probe را می‌سنجد؛ outcome: verified/failed/inconclusive. postmortem کوتاه تولید شود.
## ۳. Deployment workflow (P1)
`SOURCE_SELECTED → STATIC_SCANNED → PLATFORM_PROPOSED → PLAN_PROPOSED → HUMAN_FUNDS_OR_LOGIN → APPROVED → PROJECT_CREATED → SOURCE_UPLOADED → RELEASE_SUBMITTED → RELEASE_READY → HEALTH_CHECKED → DOMAIN_GUIDANCE → COMPLETE`.
- ایجاد پروژه و هزینه/پلن پیش از انجام تأیید شوند. وضعیت موجودی حساب را بدون API تأییدشده حدس نزن.
- platform و port از فایل‌های پیکربندی/manifest استخراج شود؛ هر ambiguity سؤال هدفمند یا انتخاب تاییدپذیر.
- برای source: اول CLI رسمی، یا API فایل .gz + release با قرارداد runtime اعتبارسنجی‌شده.
- برای دامنه/ایرنیک، تغییر در پنل شخص ثالث handoff با دستورالعمل متناسب با رکورد واقعی ارائه شود.
- release آماده ≠ وب‌سایت سالم؛ probe کاربردی با allowlist لازم است.
## ۴. approval binding
Canonical payload پیشنهادی:
```json
{
  "workspace_id":"ws_123",
  "actor_id":"usr_123",
  "service_id":"srv_123",
  "operation":"restart",
  "parameters":{},
  "expected_service_state_digest":"sha256:...",
  "policy_version":"v1",
  "approval_expires_at":"2026-10-23T12:05:00Z"
}
```
شناسه تصادفی cryptographically secure، digest از JSON canonical با کلیدهای مرتب، atomic consume در یک تراکنش DB، ممنوعیت reuse و cross-service، invalidate on drift. TTL نمونه ۳ دقیقه و قابل تنظیم. خود مدل قادر به ساخت authorization نیست.
## ۵. الگوی declarative tool
```json
{
  "name":"liara.logs.read",
  "side_effect":"none",
  "allowed_modes":["demo","live_read"],
  "input_schema":{"project_name":"allowlisted string","since":"RFC3339 or validated contract"},
  "timeout_seconds":10,
  "max_result_bytes":262144,
  "redact":["credential","personal_data"],
  "output":"EvidenceBatch"
}
```
`liara.app.restart`: `side_effect=service_disruption`, `mode=live_write_test_only`, `approval_required=true`, `retry=never_without_status_check`. `liara.project.delete` در MVP وجود ندارد.
## ۶. Exit criteria هر گام
- read: schema-valid evidence یا explicit unavailable_reason.
- analyze: حداقل یک hypothesis همراه supporting evidence یا inconclusive.
- plan: schema valid + blast radius + verification plan.
- approval: actor/resource/digest/expiry مطابق.
- execute: traced request_id و status submitted/failed.
- verify: independent checks ثبت و نتیجه توضیح‌پذیر.
## ۷. نمونه failure recovery
LLM timeout → rule engine ادامه؛ API 429 → backoff read؛ DB down → mutate ممنوع؛ click دوباره تأیید → 409/Already Consumed؛ state تغییر کرده → مجوز باطل؛ probe SSRF attempted → URL blocked؛ 500 ادامه دارد → «رفع نشده» و escalation/next safe action.