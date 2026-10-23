# 19 · معماری قطعی Conversational Liara Sentinel

**تاریخ تصمیم:** 2026-10-23  
**دامنه:** نمونه اولیه تک‌اپراتوره و حساب آزمایشی لیارا؛ **تولیدی نیست**  
**وضعیت:** مسیر اصلی مکالمه و رابط React روی شاخه توسعه پیاده‌سازی شده‌اند؛ پذیرش نهایی به تست، build فرانت‌اند و آزمون زنده کنترل‌شده وابسته است.

## ۱. مسئله و معیار پذیرش

از شرح چالش: ۱۰۰ امتیاز یکپارچه‌سازی واقعی لیارا؛ ۱۰۰ امتیاز تحلیل و رفع مشکل؛ ۵۰ امتیاز UX؛ ۵۰ امتیاز امنیت/پایداری؛ مجموع ۳۰۰. تحویل شامل MVP واقعی، مستند Markdown در GitHub و ویدیوی تقریبی ۵ دقیقه است. نباید صرفاً یک Chatbot نمایشی یا Dashboard با ده‌ها فیلد باشد.

**تصمیم محصول:** یک **Adaptive Conversation Workspace** تمام‌صفحه، RTL و mobile-responsive. نقطه ورود درخواست طبیعی است؛ پاسخ متناسب با context می‌تواند متن، کارت تشخیص، شواهد، تأیید یا استقرار هدایت‌شده باشد. کاربر فقط تصمیم‌های ضروری را می‌گیرد.

## ۲. معماری فنی منتخب

- **Frontend:** React + TypeScript + Vite + @assistant-ui/react (ExternalStoreRuntime) با اجزای تخصصی و CSS tokens. React state فقط بازنمایی thread است؛ منبع اصلی داده SQLite سرور است.
- **Backend:** FastAPI موجود، بدون بازنویسی LiaraAdapter، Scout، تشخیص قواعدی، approval و verifier.
- **Agent:** LangGraph StateGraph با router و شاخه‌های read-only برای inspection، projects و deployment preparation؛ checkpoint مستقل SQLite. در نبود کتابخانه یک fallback قاعده‌محور **صریح** فعال است.
- **LangChain + Generative AI:** ChatOpenAI فقط برای دسته‌بندی انتخابی intent؛ narrative موجود، در صورت پیکربندی، شواهد محدود و پاک‌سازی‌شده را توضیح می‌دهد. هیچ مدل زبانی اجازه صدور مجوز عملیات را ندارد.
- **UI:** کارت‌های Typed؛ هیچ HTML یا JavaScript تولیدشده توسط مدل اجرا نمی‌شود.
- **API:** POST /api/chat/messages ،POST /api/chat/stream (SSE status + complete/error)، GET /api/chat/threads، GET /api/chat/threads/{id}، POST /api/chat/approval.
- **Execution:** POST /api/approve و /api/deploy/* موجود، فقط با access key سمت اپراتور، لیست پروژه‌های مجاز و مجوز atomic/one-use.
- **Storage:** chat_threads و chat_messages در همان SQLite تنظیم‌پذیر approvals؛ checkpoint graph در فایل SQLite مجزا. هر thread با digest مالک و mode محدود می‌شود.

## ۳. جریان عیب‌یابی

۱) درخواست فارسی → router با intent قاعده‌ای و LLM اختیاری. ۲) mode و project معتبر → جمع‌آوری از API لیارا یا شبیه‌سازی آشکار. ۳) diagnose مبتنی بر شواهد و ID؛ LLM اختیاری توضیح مشورتی. ۴) کارت شواهد و اقدام پیشنهادی. ۵) اگر پیشنهاد restart معتبر باشد graph با interrupt متوقف می‌شود. ۶) رابط نام هدف، ریسک و اثر را نمایش می‌دهد. ۷) endpoint تایید ابتدا مالک thread، proposal ID، actor و project را بررسی می‌کند؛ policy موجود مجوز را atomic مصرف می‌کند و سپس نتیجه توسط resume به گراف برمی‌گردد. ۸) گزارش خروجی **submitted** را از **health verified** جدا می‌کند. لغو مجوز را سمت سرور ابطال می‌کند.

### قاعده حیاتی

Graph interrupt **authorization نیست**؛ سیاست اجرا همچنان در sentinel/security.py و app.py اعمال می‌شود. عملیات خارجی باید خارج از نقاط وقفه باقی بماند. اگر فراخوانی خارجی موفق شود ولی checkpoint بعدی شکست بخورد، فقط sync وضعیت اصلاح می‌شود، **نه اجرای دوباره همان عملیات**.

## ۴. جریان استقرار

گفت‌وگوی «سایتم را منتشر کن» → کارت Deployment دارای مسیر نسبی سورس مجاز، پلتفرم، پورت و نوع backend. Project Scout و Deployment Plan فقط با اجازه لازم و اطلاعات واقعی فراخوانی می‌شوند؛ ساخت و انتشار جدید به تأیید دقیق نیاز دارند. پیشنهاد قیمت در نسخه حاضر اعتبارسنجی نشده و «تأییدنشده» نمایش داده می‌شود.

این MVP هنوز انتخاب خودکار پلن بر اساس تعرفه زنده یا دریافت مخزن GitHub دلخواه را پیاده نکرده است. «ایجاد پروژه»، «ارسال release»، «آماده‌بودن» و «سلامت وب‌سایت» نتیجه‌های متفاوتی‌اند؛ UI و خروجی API نباید یکی را به جای دیگری نشان دهند.

## ۵. قرارداد امنیت و حریم خصوصی

- توکن اصلی لیارا فقط در سرور است. مرورگر صرفاً کلید عملیاتی Sentinel را در حافظه نشست جاری نگاه می‌دارد؛ آن را در localStorage یا query string ذخیره نکنید.
- localhost، single operator، بدون multi-tenancy و auth/session production. اجرای عمومی ممنوع تا رفع این نقص‌ها.
- اطلاعات از log و repository داده نامطمئن است؛ redaction، سقف حجم و parsing ساختاری اعمال شوند. Prompt injection نباید تبدیل به ابزار اجرایی شود.
- مجوز restart محدود به actor + project + fingerprint و مهلت ۳ دقیقه است؛ تایید دوباره رد می‌شود.
- هر عملیات write تنها با flags و allowlist سرور؛ بدون shell دلخواه توسط مدل.
- در API read غیرقابل‌دسترس باید وضعیت unknown/no evidence برگردد؛ جایگزینی داده مصنوعی به‌جای live ممنوع است.
- frontend generated cards برای عملیات حساس فقط از قرارداد backend معتبر تغذیه می‌شود.
- استعلام health یک مشاهده در زمان مشخص است و اثبات پایداری طولانی‌مدت نیست.
- فایل SQLite و checkpointها باید در فضای محدود با مجوز مناسب باشند؛ حذف thread و سیاست نگهداری داده برای محصول نهایی هنوز لازم است.

## ۶. انتخاب فنی و دلایل

| گزینه | نتیجه |
|---|---|
| Dashboard فرم‌محور | رد: مسئولیت انتخاب ابزار را به کاربر منتقل می‌کند |
| Chat text-only | رد: تایید، مراحل و داده‌های پیچیده را مبهم می‌کند |
| React + assistant-ui | انتخاب: component primitives و runtime متصل به history سرور |
| LangChain-only | مناسب برای routing ساده، ناکافی برای چرخه تأیید/بازگشت پیچیده |
| LangGraph | انتخاب: state، conditional edges، checkpoint و interrupt |
| Deep Agents / Multi-Agent آزاد | فعلاً رد: هزینه و خطر اجرای ناخواسته |
| MCP / AG-UI | قابل افزودن در آینده؛ نیازی برای اثبات MVP نیست |
| Rules + LLM | انتخاب: مبنای آزمون‌پذیر همراه با فهم درخواست آزاد |

## ۷. معیار Done

- `npm run build` و `pytest -q` با گزارش موفق روی نسخه مشخص.
- سه سناریوی متفاوت: deploy، HTTP 500، فشار RAM؛ حداقل یک چرخه کامل با پروژه آزمایشی لیارا.
- تست‌های replay، expiry، actor/thread isolation، cancel، error، streaming و disconnect.
- UX با کاربران غیرفنی؛ زمان تکمیل، درک ریسک، اشتباه submitted=verified و خوانایی موبایل.
- ویدیوی حدود ۵ دقیقه؛ هر داده مصنوعی با برچسب Demo؛ رفرنس به نسخه commit و تاریخ تست.
- حداکثر مجوز فقط در محدوده پروژه آزمایشی disposable؛ بررسی هزینه واقعی قبل از submit.

## ۸. محدودیت‌ها و وضعیت ادعا

کد مسیر مکالمه و UI اضافه شده است، اما **نه آزمون مرورگر واقعی، نه بیلد وابستگی‌های Node/Python در این محیط، نه اجرای زنده API لیارا** در این مرحله انجام نشده است. Streaming فعلی eventهای وضعیت/پایان را ارسال می‌کند، نه token delta پیوسته مدل. بعضی مسیرهای دیپلوی همچنان نیازمند انتخاب دستی تنظیمات‌اند. هیچ ادعایی درباره نمره مسابقه، مدل production-ready، هزینه پلن معتبر یا SRE خودمختار ۲۴/۷ وجود ندارد.

## ۹. مراجع اصلی

- شرح چالش داخلی `شرح-چالش.txt` و متن ویدیو `متن-ترجمه-ویدیو.txt`.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- [assistant-ui ExternalStoreRuntime](https://www.assistant-ui.com/docs/runtimes/custom/external-store)
- [assistant-ui Thread primitives](https://www.assistant-ui.com/docs/primitives/thread)
- [Liara developers](https://developers.liara.ir/)

برای نصب گام‌به‌گام، مستند `docs/20-conversation-runbook.md` را بخوانید.
