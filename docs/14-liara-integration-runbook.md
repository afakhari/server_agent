# 14 · Runbook اتصال و اعتبارسنجی لیارا
**هدف:** تبدیل OpenAPI عمومی به یک adapter آزموده با شواهد قابل بررسی، بدون به خطرانداختن پروژه‌های تولیدی.
## پیش‌نیازهای اپراتور
۱. حساب آزمایشی لیارا، توکن API با دسترسی محدودِ موجود، یک app قابل حذف و سقف هزینه مشخص؛ ۲. فضای اجرای local backend با TLS در محیط online؛ ۳. تعریف host allowlist و ممنوعیت production target؛ ۴. همه secrets در محیط سرور، نه کامیت یا چت.
## مرحله A · read-only
- روی سرور `LIARA_API_TOKEN` را از secret manager ست کن؛ هرگز در URL و log و shell history نگذار.
- request GET `/v1/projects` را با Bearer اجرا و شکل پاسخ را با `Projects` در spec تطبیق بده.
- یک پروژه disposable را انتخاب و GET project، logs با since، releases با page/count، events و metrics/summary را به ترتیب تست کن.
- برای هر درخواست timestamp، status، schema version، response shape و redacted fixture را ثبت کن. مقادیر env را در همان سطح adapter حذف کن.
- هر داده با format متفاوت را در `11-decisions.md` به‌عنوان مسئله Qxx و fixture جدید ثبت کن.
## مرحله B · write gated
- قبل از فعال‌سازی، unit tests امنیتی AP-01 تا AP-07 و SEC-01 تا SEC-04 پاس شوند.
- only test app allowlist و `LIARA_WRITES_ENABLED=false` پیش‌فرض. UI در mode live-read دکمه write فعال نکند.
- اپراتور پس از review preflight، flag را **صرفاً برای test session** فعال کند.
- action restart را با approved operation و پایش side effect انجام دهد؛ status submitted را ثبت کند.
- health probe independent و app state را تا timeout bounded مشاهده کن؛ وضعیت را به verified/failed/inconclusive دسته‌بندی کن.
- پس از اتمام تست write مجدداً disabled و credentials rotation در صورت نیاز.
## مرحله C · deploy
- نسخه CLI را lock؛ دستور `liara deploy --help` را در محیط توسعه با نسخه lockشده تأیید کن.
- source sample app را statically scan؛ malicious scripts و secrets را در archive نپذیر.
- app test با planID معتبر که از پلتفرم verified شده بساز و تنها پس از consent کاربر.
- CLI را با argv ثابت و `shell=False` اجرا کن، یا upload .gz to `/v2/projects/{name}/sources` و استفاده از `sourceID` در release؛ یکی را انتخاب و evidence بگیر.
- polling release readiness و سپس probe health؛ تنها موفقیت HTTP app به همراه release readiness را `VERIFIED` اعلام کن.
- برای دامنه، DNS guidance فقط با owned domain و CNameRecord واقعی؛ بیرون رفتن از کنسول/ایرنیک handoff به کاربر.
## نمونه درخواست صرفاً آموزشی
```bash
# Never paste a real token into shell history or commit it.
# In code, use an HTTP client with Authorization header from secret storage.
curl --fail-with-body --silent --show-error \
  --header "Authorization: Bearer <REDACTED_TEST_TOKEN>" \
  "https://api.liara.ir/v1/projects"
```
در اجرای عملی بهتر است کد adapter خودش header را تولید کند و خروجی command mask شود. دستور بالا برای نمایش شکل HTTP است، نه توصیه به گذاشتن توکن در shell history.
## محدودیت‌های صریح
- spec زمان و units متریک و قیمت/plan ID را برای همه سناریوها تضمین نمی‌کند.
- success API restart یا release create، proof of health نیست.
- rollback automated یا دسترسی ثبت DNS در ایرنیک بدون عملیات مستند/آزمون نمی‌تواند اجرا شود.
- برای تیم‌های چندنفره tenant/team scoping باید مستقل آزمایش شود.
## Evidence record template
```json
{
 "tested_at_utc":"<timestamp>",
 "source_revision":"liara/openapi spec commit",
 "mode":"LIVE_READ_VERIFIED",
 "project_alias":"disposable-test-app",
 "operation":"project.list",
 "http_status":200,
 "response_schema_valid":true,
 "evidence_file":"artifacts/redacted/...",
 "secret_scan_passed":true,
 "verified_by":"<reviewer>"
}
```
**این نمونه فقط قالب است؛ یک آزمایش واقعی را توصیف نمی‌کند.**
## Incident emergency stop
در صورت API behavior نامعمول، احتمال دسترسی cross-tenant، آسیب به پروژه یا تکرار عملیات: live writes را خاموش کن، صف را متوقف، token را revoke/rotate و وضعیت سرویس را از پنل مستقل بررسی کن. اطلاعات لازم برای forensic بدون secrets ثبت شود.