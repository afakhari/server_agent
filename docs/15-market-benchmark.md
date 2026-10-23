# 15 · Benchmark محصولی و فرصت تمایز
**هدف:** استفاده از الگوهای اثبات‌شده صنعت برای طراحی MVP متمرکز بر لیارا؛ نه ادعای هم‌ترازی امکانات با محصولات بالغ.
## نمونه‌های مطالعه‌شده
| محصول | الگوی مستند | برداشت طراحی برای Sentinel |
|---|---|---|
| [Microsoft Azure SRE Agent](https://learn.microsoft.com/en-us/azure/sre-agent/incident-response) | ارتباط دادن logs/metrics/deployments، فرضیه و پیشنهاد رفع، حالت Review برای تأیید | time-correlated multi-source incident + approval |
| [Azure Deep Investigation](https://learn.microsoft.com/en-us/azure/sre-agent/tutorial-deep-investigation) | چند فرضیه، آزمایش هر فرضیه با evidence | reasoning loop bounded + falsification |
| [Datadog Bits AI](https://docs.datadoghq.com/bits_ai/bits_investigation/investigate_issues/) | observation → reasoning → action؛ خروجی evidence-backed یا inconclusive | صراحت در عدم قطعیت و نقص داده |
| [OWASP Agentic Risks](https://genai.owasp.org/2025/12/09/owasp-genai-security-project-releases-top-10-risks-and-mitigations-for-agentic-ai-security/) | تهدید tool misuse، credential و autonomy | محدودیت اختیار و audit مستقل |
## نقشه رقابتی
رابط چت‌محور به‌تنهایی کپی‌بردارپذیر است. محدودیت مسابقه پنج دقیقه دمو و یک API provider است؛ بنابراین ساخت agent عمومی چندابری، بردار پیچیدگی اضافه می‌کند. ارزش متفاوت در **محلی‌سازی لیارا، UX فارسی، بررسی دقیق انتشار، تصمیم متناسب با منابع/هزینه و اثبات نتیجه** است.
## نوآوری‌های اجرایی که می‌توان نشان داد
1. **Release Fingerprint:** release/commit/time + sanitized config and metrics baseline؛ تشخیص regression محتمل در چند کلیک.
2. **Evidence Graph:** ادعای قابل کلیک به شاهد، منبع و timestamp متصل؛ تضادها هم نمایان.
3. **Uncertainty Ledger:** API data missing ≠ healthy. Empty logs ≠ no errors.
4. **Safe Action Contract:** approval شامل resource, state, params, expiry و risk.
5. **Proof of Recovery:** submit, observed state, external health و error trend هرکدام status مستقل.
## تمایز از بازاریابی
تا وقتی آزمایش UX، latency یا دقت تشخیص نداریم، عبارت «سریع‌تر از رقبا»، «هم‌رده Datadog» یا «SRE خودکار تولیدی» قابل اثبات نیست. ادعای درست: «طراحی و آزمونِ یک MVP متمرکز بر Liara برای چرخه تشخیص تا راستی‌آزمایی». بخش `09-testing.md` روش اندازه‌گیری را تعیین می‌کند.
## تحقیقات بعدی
مقایسه UX با ۵ کاربر، اندازه‌گیری latency collection + diagnosis، سنجش accuracy و abstention، تاثیر ریزشدن نتایج API بر confidence و چگونگی ارائه قیمت جاری. تنها پس از benchmark واقعی، مزیت کمی اعلام شود.