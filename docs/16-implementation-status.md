# 16 · وضعیت یکپارچه توسعه · 2026-10-23

**مرجع اجرایی:** app.py به همراه بسته sentinel/، فایل static/index.html و tests/. این پروژه یک Prototype تک‌اپراتوره است؛ نه یک سرویس عمومی یا تولیدی.

| قابلیت | وضعیت کد | سطح ادعای مجاز |
|---|---|---|
| UI فارسی با رخداد، شواهد و اقدام | پیاده‌سازی‌شده | Mock-tested according to prior commit; live UX not benchmarked |
| Project Scout ایستای FastAPI/Node/PHP | پیاده‌سازی‌شده | Mock-tested |
| تحلیل لاگ و شناسایی خطا/هم‌زمانی release | پیاده‌سازی‌شده | Rules + mock; added temporal tests await rerun |
| Adapter projects/logs/events/releases/metrics | پیاده‌سازی‌شده | LIVE_UNVERIFIED |
| تأیید یک‌بارمصرف، SQLite audit، deny-by-default | پیاده‌سازی‌شده | Mock-tested |
| create/upload/release روی حساب آزمایشی | در کد وجود دارد | LIVE_UNVERIFIED |
| ری‌استارت با تأیید محدود | در کد وجود دارد | LIVE_UNVERIFIED |
| پروب HTTPS مستقل بعد از ری‌استارت | در کد وجود دارد | عدم اثبات بازیابی پایدار؛ LIVE_UNVERIFIED |
| پیشنهاد قیمت، planID قطعی، ایرنیک/DNS، rollback | در مرحله طراحی | NOT IMPLEMENTED / NOT VERIFIED |
| مدیریت multi-tenant و امنیت production | در مرحله طراحی | NOT PRODUCTION READY |

**سیاست توسعه:** بدون CI. تست‌ها در repository حفظ می‌شوند تا بررسی نهایی انجام شود. هیچ اجرای زنده یا credential در این نوبت دریافت یا استفاده نشده است. برای اعتبارسنجی runtime، فقط پروژه و حساب آزمایشی disposable با سقف هزینه مناسب به‌کار گرفته شود.

**پیش‌نیاز دمو:** اتصال real read، وقوع کنترل‌شده خطا، جمع‌آوری evidence، عملیات مجاز با تأیید و نتیجه verification. اگر دسترسی API واقعی نداریم، ویدئو باید به‌صراحت mock را نشان دهد.

### افزوده‌شده در تکمیل بررسی منابع برگزارکننده
- مرجع رسمی API: `https://developers.liara.ir/`؛ مرجع CLI: `liara-cloud/cli`.
- مسیر CLI به‌عنوان transport دوم در کد افزوده می‌شود: preview + source fingerprint + تأیید یک‌بارمصرف + اجرا بدون shell + حساب اختصاصی. **LIVE_UNVERIFIED**.
- هیچ CLI واقعی روی حساب لیارا در این گفت‌وگو اجرا نشده و اتصال/هزینه/رابط auth باید روی حساب آزمایشی تأیید شود.

### بازبینی اجرایی بعدی
- راه‌انداز محلی `scripts/run_local.py` با چهار حالت demo/read/test-cli/test-api افزوده شد؛ وضعیت پیش‌فرض deny write.
- CLI identity با JSON whoami و API `/v1/me` بررسی می‌شود؛ تیم فعال و تنظیمات team override از بسته رد می‌شود.
- راهنمای کامل صاحب پروژه در `docs/18-operator-steps-fa.md` قرار دارد.
- آزمون‌های جدید نوشته شده‌اند؛ هنوز آزمون زنده با حساب لیارا و اجرای مجدد کل تست‌های repository در این تغییر انجام نشده است.


## افزوده‌شده در شاخه Conversational Agent · 2026-10-23

- طراحی React/assistant-ui تمام‌صفحه و RTL به `frontend/` اضافه شد؛ requires npm install/build، مرورگر **آزمون نشده**.
- `sentinel/conversation.py`: SQLite conversation history، context per project، LangGraph conditional workflow، SQLite checkpoint، interrupt برای approval، LangChain intent classifier اختیاری.
- API گفت‌وگو/فهرست/stream/approval افزوده شد؛ استفاده از policy/one-use approval قبلی حفظ شده است.
- کارت‌های تشخیص، شواهد، استقرار، تأیید و وضعیت اجرا به frontend اضافه شدند؛ streaming فعلاً رویداد وضعیت و پایان است، نه delta متن.
- آزمون‌های `tests/test_conversation.py` نوشته شده‌اند؛ **هنوز در محیط ادغام با پکیج‌های LangGraph و Node اجرا نشده‌اند**.
- حساب واقعی لیارا، قیمت/پلن واقعی، پایش چندمرحله‌ای و release-ready verification هنوز LIVE_UNVERIFIED هستند. محصولات production multi-user و coding agent خارج از این vertical slice هستند.


### وضعیت آزمون خودکار شاخه Conversational
GitHub Actions workflow در PR #26 ایجاد شد. اجرای اولیه در تاریخ 2026-10-23 با نتیجه failure و **بدون هیچ step گزارش‌شده** پایان یافت؛ متن log از رابط GitHub در این نشست در دسترس نبود. بنابراین هیچ نتیجه‌ای درباره موفقیت یا شکست واقعی unit tests / frontend build نمی‌توان گرفت؛ QA همچنان BLOCKED / UNVERIFIED است و باید با دسترسی به runner یا اجرای محلی تکمیل شود.
