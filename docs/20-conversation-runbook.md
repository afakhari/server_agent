# 20 · راه‌اندازی و ارزیابی نسخه گفت‌وگومحور

## پیش‌نیازها
Python 3.11+، Node.js 20.19+ یا 22.12+، npm، و یک مرورگر مدرن. حساب واقعی لیارا فقط برای آزمون محدود خواندنی/نوشتنی روی پروژه قابل حذف لازم است. دستورها از ریشه مخزن اجرا شوند.

## نصب و اجرای Demo بدون کلید لیارا

ترمینال اول:

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn app:app --host 127.0.0.1 --port 8000
```

ترمینال دوم:

```bash
cd frontend
npm install
npm run dev
```

صفحه توسعه از Vite در `http://127.0.0.1:5173` در دسترس است؛ درخواست‌های `/api` به FastAPI پروکسی می‌شوند. `Demo Sandbox` و سناریوهای مصنوعی را امتحان کنید. در حالت Demo، عملیات «اجرا» فقط SIMULATED است.

برای ارائه یک‌پارچه روی پورت ۸۰۰۰ (پس از نصب Node):

```bash
cd frontend
npm run build
cd ..
uvicorn app:app --host 127.0.0.1 --port 8000
```

FastAPI اگر `frontend/dist/index.html` و `frontend/dist/assets` موجود باشند، خروجی React را سرو می‌کند؛ در غیر این صورت رابط قدیمی `static/index.html` نمایش داده می‌شود. **برای دیدن رابط جدید روی پورت ۸۰۰۰، build و راه‌اندازی مجدد سرور ضروری است.**

## فعال‌سازی LangGraph و LangChain

وابستگی‌های Python با `requirements.txt` نصب می‌شوند. با نصب صحیح، `engine=langgraph` در پاسخ API نمایش داده می‌شود. اگر کتابخانه graph در دسترس نباشد، مسیر read-only قاعده‌ای با `engine=rules-fallback` فعال می‌شود؛ آن حالت **پایدارسازی checkpoint و interrupt واقعی ندارد**. این fallback برای تاب‌آوری MVP است و نباید جایگزین آزمون LangGraph شود.

مدل اختیاری برای intent classification از LangChain/ChatOpenAI استفاده می‌کند:

```dotenv
SENTINEL_CHAT_LLM_ENABLED=true
SENTINEL_LLM_MODEL=your-model
SENTINEL_LLM_API_KEY=your-key
# فقط در صورت استفاده از gateway سازگار OpenAI
SENTINEL_LLM_BASE_URL=https://trusted-gateway.example/v1
```

تنظیم `SENTINEL_LLM_ENDPOINT` قدیمی برای narrative مشورتی مستقل باقی مانده و باید URL کامل endpoint تکمیل مکالمه باشد. بدون LLM، router قاعده‌محور فعال است و UI/ابزارها همچنان کار می‌کنند.

## اتصال زنده

به `RUNNING.md` و `docs/18-operator-steps-fa.md` رجوع کنید. `LIARA_API_TOKEN` هرگز وارد مرورگر نشود. فقط `SENTINEL_ACCESS_KEY` (حداقل ۲۴ نویسه) در کادر مربوطه وارد می‌شود و در حافظه React می‌ماند. حالت Live را انتخاب کنید؛ پروژه موجود را وارد یا در مکالمه فهرست پروژه‌ها را درخواست کنید. تغییرات تا زمان تنظیم صریح `SENTINEL_ALLOW_LIVE_WRITES=true`، `SENTINEL_ALLOWED_PROJECTS` و سایر قفل‌های سمت سرور ممنوع هستند.

## مسیرهای اصلی HTTP

| روش و مسیر | کاربرد |
|---|---|
| POST /api/chat/messages | پاسخ JSON با `thread_id,answer,ui,engine` |
| POST /api/chat/stream | SSE با رویدادهای `status,complete,error` |
| GET /api/chat/threads | فهرست گفت‌وگوهای مالک |
| GET /api/chat/threads/{id} | بازیابی متن و payload کارت‌ها |
| POST /api/chat/approval | تأیید/لغو پیشنهاد متعلق به thread |
| POST /api/deploy/plan | preview استقرار مجاز |
| POST /api/deploy/execute | عملیات پس از approval |
| POST /api/scout | تحلیل فایل‌های تنظیمات سورس مجاز |

نمونه فقط در حالت Demo:

```bash
curl -s http://127.0.0.1:8000/api/chat/messages \
  -H 'Content-Type: application/json' \
  -d '{"mode":"demo","message":"سایتم خطای ۵۰۰ دارد","scenario":"transient"}'
```

## سناریوهای اجباری دمو

۱. «سایتم خطای ۵۰۰ دارد» → evidence و hypothesis → approval محدود → SIMULATED در Demo / آزمایشی واقعی فقط پس از فراهم‌شدن شرایط.

۲. «پروژه‌ام را منتشر کن» → Scout و preview از workspace مجاز → approval → نتیجه submit؛ وضعیت release و health جداگانه بررسی شود.

۳. «فهرست برنامه‌های حساب» → در Demo فقط demo-shop مصنوعی، در Live فهرست واقعی یا پیام خطای اتصال.

در فیلم دمو پیش از نمایش نتایج mock، برچسب Demo را واضح نشان دهید. **هیچ تأیید زنده‌ای در این تغییر انجام نشده است.**

## معیار سنجش UX و امنیت

- بررسی RTL، عرض ۳۲۰ تا ۱۴۴۰ پیکسل، tab navigation و focus visible.
- عدم نمایش توکن یا raw environment values در DOM/API.
- تایید و لغو از یک thread دیگر رد شوند.
- دو کلیک تأیید = حداکثر یک write؛ لغو مجوز را می‌سوزاند.
- قطع مدل → مسیر قواعد؛ قطع API لیارا → خطای صادقانه؛ قطع verifier → وضعیت inconclusive.
- چت reload → بازیابی history از سرور، بدون ساخت پروژه خیالی.
- اجرای `pytest -q` و `npm run build` روی ماشین توسعه و ثبت خروجی در ارائه.

## مرز نسخه آزمایشی

نسخه برای localhost و یک اپراتور است. سرویس اینترنتی production، OAuth چندکاربره، CSP کامل برای frontend جدا، rate limiting، CSRF protection، queue توزیع‌شده، مانیتورینگ ۲۴/۷، تایید قیمت پلن، RAG اسناد، انتخاب خودکار سورس GitHub و rollback خودکار خارج از محدوده این پیاده‌سازی‌اند. قبل از استقرار عمومی باید جداگانه بررسی شوند.
