# 17 · مسیر CLI رسمی لیارا در کنار API

**منابع:** https://developers.liara.ir/ و https://github.com/liara-cloud/cli/blob/master/README.md و https://github.com/liara-cloud/cli/blob/master/src/commands/deploy.ts.

**وضعیت:** کد MVP اضافه شده؛ اجرای واقعی با یک حساب لیارا هنوز تأیید نشده است. فقط پروژه آزمایشی قابل حذف، با سقف هزینه.

## دلیل تصمیم معماری

PaaS API بهترین منبع برای لاگ‌ها، رویدادها، نسخه‌ها، متریک‌ها، پروژه و دامنه است. CLI رسمی مسئول packaging و ارسال انتشار است و برای SRE Agent به‌عنوان مسیر جایگزین deploy مفید است.

| وظیفه | مسیر |
|---|---|
| لاگ/رویداد/متریک/دامنه | API خواندنی |
| تحلیل رخداد و شواهد | Evidence Engine |
| انتشار پروژه محلی | CLI اختیاری؛ فقط پروژه موجود |
| API source upload/release | مسیر قبلی، همچنان قابل استفاده |
| سنجش پس از اقدام | API و HTTPS health probe |
| تشخیص شناسه پلن و قیمت | پنل واقعی/تأیید کاربر؛ CLI plan list فقط مرجع کمکی |
| تغییر در ایرنیک/رجیسترار | راهنمای کاربر؛ خودکار نیست |

## احراز هویت بدون فاش‌کردن توکن

CLI گزینه `--api-token` دارد، اما Sentinel هرگز آن را به child process نمی‌دهد تا توکن در argv/process listing قرار نگیرد. به‌جای آن از HOME خصوصی و **حساب ازقبل لاگین‌شده، اختصاصی پروژه آزمایشی** استفاده می‌شود؛ هویت حساب هنگام preflight با `liara account whoami --json` بررسی می‌شود. خروجی آن به UI نمی‌رود.

1. Node.js و CLI را با نسخه کنترل‌شده نصب کنید. نسخه هنگام بررسی `@liara/cli@9.6.0` است.
2. پوشه HOME خصوصی، مثلاً `/srv/sentinel-cli-home`، با مالکیت صحیح و مجوز محدود ایجاد کنید.
3. اپراتور یک‌بار با `HOME=/srv/sentinel-cli-home liara login` در حساب آزمایشی وارد شود.
4. با `HOME=/srv/sentinel-cli-home liara account whoami --json --account ACCOUNT_ALIAS` صحت حساب را مستقل بررسی کند.
5. باینری مطلق CLI، حساب ثابت و HOME خصوصی را سمت سرور تعریف کند.

```dotenv
SENTINEL_CLI_DEPLOY_ENABLED=true
SENTINEL_CLI_BIN=/absolute/path/to/liara
SENTINEL_CLI_ACCOUNT=ACCOUNT_ALIAS
SENTINEL_CLI_HOME=/srv/sentinel-cli-home
```

چهار محافظ اصلی هم همچنان لازم‌اند: `SENTINEL_ALLOW_LIVE_WRITES=true`، `SENTINEL_ALLOWED_PROJECTS=my-disposable-project`، `SENTINEL_ACCESS_KEY` و `LIARA_API_TOKEN`. مسیر `SENTINEL_WORKSPACE` نیز باید روی یک workspace محدود باشد. توکن API برای خواندن مالکیت پروژه در Sentinel است و به فرایند CLI منتقل نمی‌شود.

## جریان عملیات

- UI در بخش انتشار روش **CLI رسمی · فقط انتشار روی پروژه موجود** را انتخاب می‌کند.
- Scout بستر/پورت/نام فایل‌ها را بررسی می‌کند؛ سرور hash بسته قابل‌انتشار را ثبت می‌کند.
- پروژه باید در PaaS API وجود داشته باشد؛ CLI این مسیر اجازه ساخت برنامه جدید ندارد.
- پیش‌نمایش شامل project، platform، port، هش، حساب CLI، نسخه CLI و اخطار هزینه نامشخص است.
- کاربر با نام پروژه تأیید می‌کند؛ approval یک‌بارمصرف و محدود به source SHA است.
- archive پاک‌سازی‌شده در پوشه خصوصی موقت استخراج می‌شود؛ سورس اصلی به CLI داده نمی‌شود.
- اجرا فقط با argv ثابت و `shell=False`، مسیر CLI ثابت، حساب ثابت، timeout و بدون free-form flags انجام می‌شود.
- exit 0 از CLI فقط `SUBMITTED` است، نه بازیابی/سلامت تأییدشده.
- رصد release و پروب مستقل توسط API/HTTP پیگیری می‌شود.

## محدودیت‌ها

- این نسخه CLI خودکار را روی تولید فعال نکنید؛ احراز هویت سازمانی، sandbox شبکه، secret scanning تکمیلی و اجرای زنده هنوز بررسی نشده‌اند.
- اگر اجرای POST/CLI وسط عملیات timeout شود، نباید بدون مشاهده state واقعی retry شود.
- خروجی stdout/stderr CLI ممکن است داده حساس داشته باشد؛ در log عمومی یا UI نمایش داده نمی‌شود.
- `liara shell`، تغییر خودکار DNS، دستورات arbitrary، تغییر account و flagهای ورودی مدل در Executor مجاز نیستند.
- `liara plan list` ممکن است فقط زیرمجموعه‌ای از پلن‌ها را نمایش دهد؛ کد رسمی فیلتر منطقه‌ای دارد. قیمت قبل از عملیات با پنل کاربر تطبیق داده شود.
- هیچ هزینه‌ای از طریق خود CLI نصب دریافت نمی‌شود، ولی استفاده از PaaS و منابع ممکن است صورتحساب داشته باشد.

## آزمون‌های نزدیک تحویل

مسدودشدن قابلیت بدون flag؛ اعتبارسنجی حساب CLI؛ عدم انتقال token به argv/env؛ رد approval تکراری و تغییر منبع؛ عدم کپی .env به staging؛ اجرا بدون Shell؛ گزارش صادقانه NOT_VERIFIED؛ کنترل واقعی سرویس از API بعد deploy.

فایل آزمون سبک: `tests/test_cli.py`. هنوز هیچ عملیات واقعی CLI در این جلسه انجام نشده است.

## کنترل هویت سخت‌گیرانه افزوده‌شده
قبل از preflight، نام alias و ایمیل واقعی خروجی JSON فرمان whoami بررسی می‌شود. برای نمونه آزمایشی، team غیر-null رد می‌شود. ایمیل CLI با endpoint رسمی `GET /v1/me` برای توکن API تطبیق می‌یابد. اگر حساب‌ها مطابقت نداشته باشند، دیپلوی متوقف می‌شود. `liara.json` ارسال‌شده فقط `platform` و `port` دارد و نمی‌تواند team-id یا تنظیمات اجرای آزاد را override کند. نسخه CLI به 9.6.0 محدود است. آزمون‌های تکمیلی: `tests/test_cli_identity.py`. رابط جدید `scripts/run_local.py` کلیدها را در دیسک ذخیره نمی‌کند.

## محدوده تیم‌ها
`LIARA_TEAM_ID` فقط برای HTTP API سمت سرور است. مسیر CLI محافظت‌شده MVP به‌صورت عمدی **فقط حساب شخصی** را می‌پذیرد و اگر context تیم انتخاب شده باشد، اجرای CLI رد می‌شود. پشتیبانی ایمن از `--team-id` در CLI نیازمند توسعه و آزمون جداگانه است. برای برنامه تیمی روی Windows از `--mode read` و پس از اعتبارسنجی از مسیر مستقیم API استفاده کن. [راهنمای تیم](19-team-access.md).
