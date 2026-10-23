# 21 · پیش‌پرواز استقرار Sentinel روی VPS لینوکسی (Private Staging)

**وضعیت: آماده‌سازی کد و پیکربندی، نه مجوز انتشار عمومی.**  
**هدف:** نمایش MVP چالش در یک سرور خصوصی تک‌اپراتوره با HTTPS.  
**پلتفرم منتخب در نبود مشخصات سرور:** Linux VPS + Docker Compose + Caddy.
این روش برای PaaS یا Kubernetes بدون تغییر مستقیم قابل استفاده نیست.

## ۱. حدود ایمنی و معماری

- سرویس Sentinel، **خودِ دستیار** است، نه یکی از برنامه‌هایی که Sentinel در Liara مدیریت می‌کند.
- هیچ route بک‌اند روی host publish نمی‌شود؛ تنها Caddy پورت‌های 80 و 443 را باز می‌کند.
- Caddy برای **کل سایت و تمام APIها** HTTP Basic Auth دارد و با دامنه معتبر HTTPS خودکار برقرار می‌کند. این حفاظت با کلید مستقل `SENTINEL_ACCESS_KEY` که در چت وارد می‌شود تفاوت دارد.
- `SENTINEL_EXPOSURE_MODE=private-server` موجب می‌شود FastAPI بدون کلید ۳۲ نویسه‌ای، فایل فرانت buildشده، مسیر مطلق دیتابیس یا با قابلیت write روشن **بالا نیاید**.
- `live_writes_permitted` در profile خصوصی سرور، تغییر واقعی روی Liara را بدون توجه به سایر flags رد می‌کند. CLI هم قفل و disable است.
- SQLite approvals/chat و فایل checkpoint در Docker volume `sentinel_data` ذخیره می‌شوند؛ فقط **یک Uvicorn worker** با یک process انتخاب شده است. این استقرار چندکاربره، HA و production نیست.
- Container برنامه با UID 10001، `read_only`، `cap_drop: ALL` و بدون publish پورت اجرا می‌شود. فقط یک volume داده و یک tmpfs وجود دارد.
- اگر Live Read تنظیم شود، Liara API token فقط در سرور است. عملیات Write در این profile مجاز نیست.
- لاگ‌ها و promptهای خارجی داده نامطمئن‌اند؛ اتصال LLM به صورت پیش‌فرض غیرفعال است.

## ۲. پیش‌نیاز

یک Linux VPS با Docker Engine + Docker Compose plugin، یک دامنه مستقل زیر کنترل شما، DNS A/AAAA درست به سرور و بازبودن پورت‌های 80 و 443. ورود SSH ترجیحاً با کلید، فایروال فعال و دسترسی Docker تنها برای اپراتور مجاز باشد. **Docker socket را به Sentinel وصل نکنید.**

دستورهای زیر روی سرور لینوکسی و از شاخه تأییدشده مخزن اجرا شوند، نه Windows CMD. نسخه را فقط بعد از عبور تست‌ها انتخاب کنید.

## ۳. آماده‌سازی سرور و Secret

```bash
umask 077
cp deploy/server/app.env.example deploy/server/app.env
cp deploy/server/caddy.env.example deploy/server/caddy.env
chmod 600 deploy/server/app.env deploy/server/caddy.env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

خروجی دستور آخر یک کلید تصادفی Sentinel است؛ **خروجی را در GitHub، چت یا لاگ عمومی قرار ندهید**. آن را جایگزین `SENTINEL_ACCESS_KEY` در فایل خصوصی `deploy/server/app.env` کنید.

برای رمز ورود Caddy، به شکل تعاملی hash ایجاد کنید:

```bash
docker run --rm -it caddy:2 caddy hash-password
```

hash چاپ‌شده را در `SENTINEL_BASIC_AUTH_HASH` داخل `deploy/server/caddy.env` قرار دهید. hashهای bcrypt معمولاً `$` دارند؛ داخل فایل env مقدار را **داخل single quotes** بگذارید. مقدار `SENTINEL_DOMAIN` را با FQDN خودتان جایگزین کنید.

رمز Caddy و کلید Sentinel باید **مستقل** باشند. اگر خواندن واقعی حساب لیارا لازم است، `LIARA_API_TOKEN` و در صورت استفاده `LIARA_TEAM_ID` تنها در app.env سمت سرور قرار گیرند. برای نمایش Demo به هیچ توکن لیارا نیاز نیست.

**محدودیت امنیتی:** Docker Compose `env_file` مقادیر را به environment کانتینر منتقل می‌کند و مدیر میزبان Docker می‌تواند آن‌ها را ببیند؛ محدودیت دسترسی میزبان، Docker و فایل‌ها ضروری است. برای سطح production از مدیریت secrets مناسب استفاده کنید. <https://docs.docker.com/compose/how-tos/use-secrets/>

## ۴. بررسی پیش از بالا آوردن

```bash
python -m pytest -q
cd frontend
npm install --package-lock-only
npm ci
npm run build
cd ..
# Save and commit frontend/package-lock.json before building the release image.
python scripts/check_server_release.py
docker compose -f compose.server.yaml config --quiet
docker compose -f compose.server.yaml build
```

فایل `frontend/package-lock.json` هنوز در این شاخه تولید و commit نشده است؛ تولید واقعی آن به npm با دسترسی به registry نیاز دارد. Dockerfile عمداً از `npm ci` استفاده می‌کند و **تا آماده‌شدن lockfile معتبر، build انتشار متوقف می‌شود**. `scripts/check_server_release.py` همین وضعیت و نبود فایل‌های secret غیرفرضی را با exit code غیرصفر گزارش می‌کند.

خطا در **هر یک** از موارد بالا یعنی انتشار متوقف می‌شود. چون `config` در حالت verbose می‌تواند envها را چاپ کند، تنها `--quiet` را اجرا کنید. در CI نیز وابستگی‌ها و lockfile باید قبل از انتشار قابل تکرار باشند.

## ۵. بالا آوردن staging خصوصی

```bash
docker compose -f compose.server.yaml up -d
docker compose -f compose.server.yaml ps
docker compose -f compose.server.yaml logs --tail=100 sentinel
```

کنترل‌های بیرونی:

```bash
curl -I https://sentinel.example.com/
# پیش از لاگین باید 401 باشد.
curl -u operator https://sentinel.example.com/healthz
# curl رمز را تعاملی درخواست می‌کند؛ پس از ورود انتظار JSON {"status":"ok"} داریم.
```

نام دامنه مثال را تغییر دهید. سپس با مرورگر از HTTPS وارد شوید، رمز Caddy را وارد کنید و در خود چت کلید Sentinel را قرار دهید. Demo را آزمایش کنید. API key واقعی لیارا را در browser وارد نکنید.

در صورت خطای 502: ابتدا سلامت کانتینر sentinel و خطاهای startup را بررسی کنید. خطای 403 اغلب به معنی واردنکردن کلید Sentinel است؛ خطای 401 از لایه Caddy می‌آید. حالت private-server نباید هیچ write واقعی انجام دهد.

## ۶. انتشار مجدد، نسخه ثابت و rollback

ابتدا commit موردنظر را با SHA ثبت کنید، از پایگاه داده پشتیبان بگیرید و سپس با گیت نسخه جدید را دریافت کنید:

```bash
git rev-parse HEAD
docker compose -f compose.server.yaml stop sentinel
mkdir -p backups
docker run --rm -v liara-sentinel-staging_sentinel_data:/data:ro \
  -v "$PWD/backups:/backup" alpine:3 \
  tar -czf /backup/sentinel-before-update.tar.gz -C /data .
docker compose -f compose.server.yaml start sentinel
```

برای deploy جدید:

```bash
docker compose -f compose.server.yaml build
docker compose -f compose.server.yaml up -d --no-deps sentinel
docker compose -f compose.server.yaml ps
```

در rollback، نسخه کد قبلی را checkout و دوباره build کنید. **بازگرداندن دیتابیس** فقط پس از توقف سرویس و بررسی سازگاری schema، با پشتیبان سازگار انجام شود؛ اجرای موازی دو نسخه روی یک SQLite ممنوع است. در طول توقف sentinel ممکن است Caddy موقتاً 502 برگرداند.

برای توقف کامل: `docker compose -f compose.server.yaml down`. از `down -v` استفاده نکنید، چون volume و داده‌ها حذف می‌شوند.

## ۷. گیت‌های اجباری قبل از اعلام آماده‌بودن

- [ ] Python unit + API mock tests سبز، بدون skip کردن آزمون‌های امنیتی به صورت کور.
- [ ] `npm run build` و بررسی مرورگر/موبایل و RTL سبز.
- [ ] `docker compose ... build` و `config --quiet` بدون خطا.
- [ ] HTTPS معتبر، URL مشخص، 401 بدون Basic Auth، 403 بدون Sentinel key و 200 برای healthz با Basic Auth.
- [ ] دیتابیس پس از container recreation باقی می‌ماند.
- [ ] تلاش با `SENTINEL_ALLOW_LIVE_WRITES=true` موجب **Fail Startup** در private-server می‌شود.
- [ ] `/api/deploy/plan` و سایر writeها در profile خصوصی سرور رد می‌شوند.
- [ ] هیچ secret در repo، HTML، URL، لاگ، console output یا تصاویر دمو موجود نیست.
- [ ] تست قطع شبکه/LLM، replay approval، cancellation و recoverable thread انجام شده.
- [ ] ریسک هزینه و قابلیت‌های live به‌درستی در دمو بیان شده‌اند.
- [ ] نسخه commit/SHA، اسکرین‌شات و گزارش واقعی smoke تست ثبت شده است.

## ۸. محدوده واقعی این تغییر

این تغییر فقط **زیرساخت و قفل‌های پیش‌استقرار** را فراهم می‌کند. طراحی اصلی همچنان چندکاربره نیست؛ بازبینی امنیتی واقعی، rate limit در edge، دفاع در برابر DNS rebinding در health probe، نگهداری داده و حذف نشست‌ها و تست live در حساب آزمایشی لازم‌اند. GitHub Actions قبلی بدون گزارش مراحل failed شد؛ در این محیط **هیچ build/test واقعی کانتینر یا frontend و هیچ SSH به سرور انجام نشده است**. وضعیت release تا اجرای گیت‌ها **NO-GO** است.
