# 00 · ردیابی نیازمندی‌های بریف مسابقه تا خروجی اجرایی
**منشأ:** فایل «شرح-چالش.txt» و متن پیاده‌سازی‌شده ویدیوی معرفی ارائه‌شده توسط برگزارکننده. این سند نیازمندی مسابقه است، نه ادعای پیاده‌سازی.
## معیارها و امتیازهای رسمی
| معیار | امتیاز | راه اثبات پیشنهادی | مدرک |
|---|---:|---|---|
| اتصال و عملیات واقعی لیارا | 100 | فهرست projects، deploy test app، monitoring و عمل اصلاحی | API call evidence + demo |
| هوشمندی و رفع مشکل | 100 | لاگ+events+release+metrics، فرضیه‌های دارای evidence، آزمون پس از fix | Incident report |
| UX | 50 | سه مأموریت روشن، پیشرفت و تأیید حساس | Usability script |
| پایداری و امنیت | 50 | بهداشت اسرار، approval، failure handling، محدودیت API | Security tests |
| **کل** | **300** | | |
## نگاشت بندهای بریف
| نیازمندی | قابلیت/سند | سطح تحویل |
|---|---|---|
| اولین راه‌اندازی | Scout + guided deploy؛ `04-workflows.md` | P1 |
| پیشنهاد plan/زیرساخت | نیازسنجی + live pricing validation؛ `03-liara-api.md` | P1, data dependent |
| متغیر محیطی و پیکربندی | risk-preview + env handling | P1, sensitive |
| دامنه و ایرنیک | DNS/SSL guidance و handoff | P1 |
| انتشار نسخه جدید | official CLI/API source+release | P1 |
| مدیریت سرویس و وضعیت | API read endpoints | P0 |
| پایش CPU/RAM | Metric adapter، واحدهای validateشده | P0 |
| خطای HTTP 500 / کندی | Diagnostic engine / evidence graph | P0 |
| گزارش و راهکار | explanation with citations | P0 |
| اقدام اصلاحی + تأیید | Policy/approval + bounded executor | P0 |
| بررسی نتیجه اقدام | independent verifier | P0 |
| محدودیت API | uncertainty/unknown status | P0 |
| نمونه MVP اجراشدنی | actual vertical slice | gate submission |
| مستندات Markdown در GitHub | همین مجموعه | docs |
| ویدیوی تقریباً ۵ دقیقه‌ای | `10-demo.md` | submission mandatory |
## تفکیک انتظارها
برگزارکننده پایش ۲۴ساعته را الزامی نکرده و UX را بالاتر از پیچیدگی UI دانسته است؛ بنابراین monitoring دائم و dashboard پرزرق‌وبرق در اولویت قرار ندارند. Human-in-the-loop، عملیات واقعی و ارائه یک سناریوی end-to-end در اولویت‌اند.
## خط قرمز ارائه
فقط داشتن spec و mock به معنی گرفتن امتیاز فنی واقعی نیست. لازم است قابلیت live حداقل روی test account ارزیابی و با شواهد قابل‌ممیزی نشان داده شود. سند 09 گیت‌های عبور را تعریف می‌کند.