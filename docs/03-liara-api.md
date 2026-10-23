# 03 · قراردادهای Liara PaaS و وضعیت قابلیت‌ها
**منبع حقیقت:** [OpenAPI رسمی PaaS](https://github.com/liara-cloud/openapi/blob/main/spec/paas.yaml) (بازبینی 2026-10-23)؛ [CLI رسمی](https://github.com/liara-cloud/cli/blob/master/README.md).
**نکته:** این سند **بررسی استاتیک specification** است. اجرای زنده با حساب لیارا هنوز تأیید نشده. در زمان کدنویسی spec را pin و قرارداد را با test account بررسی کنید.
## ۱. اصول Adapter
Base URL مستند: `https://api.liara.ir`؛ احراز هویت `Authorization: Bearer <TOKEN>`؛ خواندن توکن فقط در server-side secret store. فیلدهای path از project_name allowlist انتخاب و URL-encode شوند. برای تیم‌ها `teamID` در مقدمه spec ذکر شده اما شیوه اعمال در هر endpoint باید در smoke test مشخص گردد.
هر ابزار دارای: `operation_id`، input schema، response schema، side_effect، max_timeout، required_scope، risk، observed_support، audit. هیچ URL انتخابی توسط مدل به HTTP client تزریق نشود.
## ۲. Inventory قابل اتکا در specification
| عملیات | Method + path | ورودی ضروری طبق spec | خروجی یا نکته |
|---|---|---|---|
| projects.list | GET /v1/projects | bearer | projects[] |
| project.get | GET /v1/projects/{name} | name | project با envs؛ **مقادیر را حذف کن** |
| project.create | POST /v1/projects | JSON name, planID, platform (property؛ required در schema تصریح نشده) | 200 submit |
| logs.read | GET /v1/projects/{name}/logs | query: since (string, required) | آرایه type/datetime/message |
| events.read | GET /v1/projects/{name}/events | search/start/end اختیاری | data با metaData/values (نیازمند نرمال‌سازی) |
| releases.list | GET /v1/projects/{name}/releases | page, count هر دو required؛ پیش‌فرض spec 1 و 10 | total/currentRelease/releases |
| metrics.summary | GET /v1/projects/{name}/metrics/summary | name | cpuUsage, memoryUsage, disksUsage |
| metrics.cpu | GET /v1/projects/{name}/metrics/cpu | since (number, required) | Reports |
| metrics.memory | GET /v1/projects/{name}/metrics/memory | since (number, required) | Reports |
| applets.list | GET /v1/projects/{name}/applets | name | applets[] |
| source.upload | POST /v2/projects/{name}/sources | multipart field file؛ .gz در description | sourceID |
| release.create | POST /v2/projects/{name}/releases | JSON sourceID/port/type (properties) | releaseID |
| app.restart | POST /v1/projects/{name}/actions/restart | name | 200 request submitted |
| app.scale | POST /v1/projects/{name}/actions/scale | JSON scale (required) | توان روشن/خاموش؛ پرریسک |
| app.resize | POST /v1/projects/{name}/resize | JSON planID (required) | تغییر پلن؛ پرریسک |
| env.update | POST /v1/projects/update-envs | JSON project, variables[{key,value}] | اسرار ورودی؛ حساس |
| domain.list | GET /v1/domains | query project (required) | domains[] |
| domain.create | POST /v1/domains | JSON name/project/type (required) | 201 / domain._id |
| domain.check | GET /v1/domains/{id}/check | id | domain, status, certificate |
| domain.ssl | POST /v1/domains/provision-ssl-certs | مطابق spec | اثر نوشتنی؛ تأیید |
**قانون:** required بودن requestBody با required بودن تک‌تک فیلدهای schema یکسان نیست. الزامات کسب‌وکار باید جداگانه در application validation تعریف شوند.
## ۳. payloadهای نمونه (نمونه‌سازی از spec، نه تراکنش تأییدشده)
```http
GET /v1/projects/my-test-project/logs?since=2026-10-23T10%3A00%3A00Z
Authorization: Bearer <server-side secret>
```
```json
{"project":"my-test-project","variables":[{"key":"DATABASE_URL","value":"<VALUE_INPUT_SECURELY>"}]}
```
```json
{"sourceID":"<ID_FROM_UPLOAD>","port":8000,"type":"python"}
```
نوع دقیق مقدار `since` برای لاگ و enum قابل قبولِ `type` در live smoke test باید روشن شود. در هیچ فایلی مقدار واقعی secret قرار نگیرد. پایان موفق POST فقط accepted/submitted است.
## ۴. Validation matrix قبل از enable کردن live write
| سوال قراردادی | نوع آزمایش | حالت شکست امن |
|---|---|---|
| توکن/تیم و دسترسی | GET projects در حساب تست | disable live |
| format since و timezone | بازه معلوم log + compare | mark logs unavailable |
| واحد و نمونه‌برداری metrics | مقایسه داده پنل + raw | عدم نمایش درصد ساختگی |
| معنای release state | deploy آزمایشی و polling | unknown نه successful |
| schema source archive | آپلود سورس بی‌خطر | fallback CLI رسمی |
| اثر env.update (merge/replace/restart) | app disposable و مقایسه قبل/بعد | عدم فعال‌سازی در UI |
| اثر restart/resize و شرایط planID | app disposable | disable mutation |
| rate-limit و error body | آزمون محدود / کنترل‌شده | circuit breaker |
| team scope/header | یک حساب team آزمایشی | single-account only |
| DNS/SSL readiness | domain disposable با مالکیت واقعی | handoff/manual |
## ۵. خطا، retry و consistency
- 401: مشکل credential؛ نادیده گرفتن و retry بی‌پایان ممنوع.
- 403: scope ناکافی؛ راهنمای محدودیت.
- 404: پروژه/دامنه در scope موجود نیست؛ secret existence leak نده.
- 409: conflict؛ state refresh و درخواست تأیید جدید.
- 429/5xx: bounded exponential backoff با jitter و deadline، برای GET.
- POST timeout: ممکن است عملیات اجرا شده باشد؛ **بدون اثبات idempotency هرگز تکرار کورکورانه نکن**؛ با polling و event correlation نتیجه را بازیابی کن.
- JSON malformed: schema_validation_error و توقف action path.
- اگر source unavailable شد، evidence completeness کاهش یابد؛ LLM حق جایگزینی با داده تخیلی ندارد.
## ۶. CLI deploy
دستور رسمی `npm install -g @liara/cli` و `liara deploy` با flagهای `--path`، `--app`، `--port` و `--platform` مستند شده‌اند. CLI نسخه‌های جدید ممکن است تغییر کنند؛ نسخه اجرا را pin و در گزارش ذکر کن. دستورها با `subprocess.run([binary, "deploy", ...], shell=False)` و working-directory allowlisted اجرا شوند؛ stdout/stderr sanitize و timeout گردد. user-supplied args و script آزاد نپذیر.
## ۷. قابلیت‌های اثبات‌نشده
Rollback خودکار به release قبلی، قیمت‌های جاری و نگاشت planID، credential scoped per project، extension healthcheck لیارا، محدودیت نرخ واقعی و قرارداد تیم‌ها در این بررسی **تأیید runtime ندارند**. تا پایان تحقیق جداگانه وضعیت `UNKNOWN` داشته باشند. «rollback» را بدون test واقعاً قابل‌اجرا به کاربر وعده نده.
## ۸. نگاشت اپلیکیشن
`LiaraAdapter`: typed `list_projects(), read_project(), fetch_logs(since), fetch_events(start,end), fetch_releases(page,count), fetch_metrics(), restart()`. توابع write زیر namespace جدا `LiaraMutations` با dependency روی `AuthorizedExecutionContext` باشند. mock client fixture برای همه پاسخ‌ها و خطاها الزامی است.