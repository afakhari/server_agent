# 12 · منابع، منشأ ادعاها و سطح قطعیت
**آخرین بازبینی پژوهش:** 2026-10-23. دسترسی به spec عمومی به معنای تست live نیست.
## الزامات اصلی
- «شرح-چالش.txt»؛ بریف مسابقه ارائه‌شده از سوی کاربر، معیارهای ۳۰۰ امتیازی، MVP/Markdown/GitHub/دمو.
- «متن-ترجمه-ویدیو.txt»؛ معرفی چالش و تأکید بر Human-in-the-Loop، SRE agent و تجربه کاربری. این دو فایل در گفت‌وگو ارائه شده‌اند و لینک عمومی تأییدشده ندارند؛ متن کامل در این repo بازنشر نشده.
## منابع رسمی لیارا
1. [Liara OpenAPI repository](https://github.com/liara-cloud/openapi)؛ authoritative public service specification catalog.
2. [PaaS OpenAPI YAML](https://github.com/liara-cloud/openapi/blob/main/spec/paas.yaml)؛ endpoints، headers، request/response shapes.
3. [Liara API documentation](https://developers.liara.ir/)؛ docs and authentication.
4. [Official CLI README](https://github.com/liara-cloud/cli/blob/master/README.md)؛ commands، `liara deploy` و flags.
5. [Official Liara documentation repository](https://github.com/liara-cloud/docs)؛ platform deployment and guide context.
**قاعده:** release/metric/env/rollback behavior را با fixture قابل ارزیابی و live test اثبات کنید؛ spec ممکن است کامل یا runtime-aligned نباشد.
## استانداردهای امنیت و عملیات
6. [OWASP Top 10 for Agentic Applications (2026)](https://genai.owasp.org/2025/12/09/owasp-genai-security-project-releases-top-10-risks-and-mitigations-for-agentic-ai-security/)؛ تهدیدهای agent و کنترل مجوز.
7. [OWASP LLM Top 10 2026 and Agent Control Standard](https://genai.owasp.org/2026/09/01/owasp-genai-security-project-unveils-2026-top-10-for-llm-applications-new-agent-control-standard-and-sponsors-as-community-tops-30000-members/)؛ دفاع از injection و tool abuse.
8. [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)؛ ارزیابی ریسک و govern (مرجع تکمیلی پیشنهادی).
9. [Google SRE Book](https://sre.google/sre-book/table-of-contents/)؛ concepts incident response/monitoring (مرجع تکمیلی).
## قواعد استناد داخلی
ادعاهای «مستند‌شده» به لینک API/بریف؛ ادعاهای «اندازه‌گیری‌شده» به test artifact و commit SHA؛ ادعاهای «پیشنهادی» به ADR؛ unknown به Qxx. مستندات مسابقه نباید نتیجه mock را واقعیت live معرفی کنند.