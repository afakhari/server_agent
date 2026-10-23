"""Explainable, conservative multilingual request classification.

This classifier selects read-only workflows or guided answers ONLY. It cannot
authorize a deploy, restart, user-account mutation, or arbitrary shell action.

The multi-label result is for UI context; ambiguity is a first-class outcome.
No model calls, external calls, conversation retention or user profiling.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Certainty = Literal["clear", "ambiguous", "unknown", "blocked"]

# Persian half-space, Arabic character variants and Persian/Arabic numerals.
_TRANS = str.maketrans("كيى٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "کیي01234567890123456789")
_STOP = {"سلام", "لطفا", "لطفاً", "من", "را", "رو", "برام", "میخوام", "میخواهم",
         "که", "این", "اون", "چی", "چه", "از", "به", "در", "با", "روی", "واسه",
         "the", "my", "please", "how", "can", "you", "to", "a", "is", "in"}

def normalize(message: str) -> str:
    value = unicodedata.normalize("NFKC", message).translate(_TRANS).lower()
    value = value.replace("\u200c", " ").replace("\u200f", " ")
    return re.sub(r"\s+", " ", value).strip()

def _has(text: str, *patterns: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)

def redact_secrets(text: str) -> tuple[str, bool]:
    """Keep accidentally pasted credentials out of history, model calls and UI."""
    new = re.sub(
        r"(?i)\b(bearer)\s+[A-Za-z0-9_\-./+=]{12,}",
        r"\1 [REDACTED]", text
    )
    new = re.sub(
        r"(?i)\b((?:liara_api_token|sentinel_access_key|openai_api_key|api[_-]?key|"
        r"secret[_-]?key|password|authorization)(?:['\"])?\s*[:=]\s*)"
        r"(['\"]?)[^\s'\";,]{8,}\2",
        r"\1[REDACTED]", new
    )
    new = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,})\b",
                 "[REDACTED]", new)
    new = re.sub(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\b",
        "[REDACTED]", new
    )
    # Exact redaction of an operator key is handled in the service layer too.
    return new, new != text

@dataclass(frozen=True)
class Decision:
    intent: str
    route: str
    certainty: Certainty
    labels: tuple[str, ...]
    suggested_actions: tuple[tuple[str, str], ...] = ()
    message: str = ""

    def as_dict(self) -> dict:
        return {
            "intent": self.intent, "route": self.route,
            "certainty": self.certainty, "labels": list(self.labels),
            "suggested_actions": [
                {"label": label, "prompt": prompt}
                for label, prompt in self.suggested_actions
            ],
        }

_ACTIONS = {
    "incident": ("بررسی مشکل سایت", "سایتم خطا دارد؛ شواهد را بررسی کن"),
    "health": ("بررسی سلامت سرویس", "سلامت سرویس من را بررسی کن"),
    "deploy": ("آماده‌سازی انتشار", "می‌خواهم سایتم را منتشر کنم"),
    "projects": ("فهرست برنامه‌ها", "فهرست برنامه‌های حساب را نشان بده"),
    "releases": ("بررسی انتشارها", "وضعیت انتشارهای پروژه را نشان بده"),
    "domains": ("دامنه و SSL", "وضعیت دامنه و گواهی SSL را بررسی کن"),
    "logs": ("بررسی لاگ‌ها", "لاگ‌های خطای سرویس را تحلیل کن"),
    "billing": ("هزینه و پلن", "هزینه و پلن لیارا را چطور بررسی کنم؟"),
    "security": ("دسترسی و امنیت", "درباره مجوزها و امنیت توضیح بده"),
    "env": ("تنظیمات محیطی", "تنظیمات متغیرهای محیطی را چطور بررسی کنم؟"),
    "database": ("اتصال پایگاه داده", "نحوه بررسی اتصال دیتابیس چیست؟"),
    "backup": ("پشتیبان‌گیری", "روش امن بکاپ گرفتن از پروژه چیست؟"),
    "team": ("حساب تیمی", "دسترسی به برنامه‌های تیمی را چطور بررسی کنم؟"),
    "support": ("دریافت کمک", "چطور به پشتیبانی لیارا مراجعه کنم؟"),
    "notifications": ("تنظیم هشدار", "آیا می‌توانم هشدار خرابی تنظیم کنم؟"),
}

# Specific keywords win over generic ones; multi-label classification preserved.
_PATTERNS: dict[str, tuple[str, ...]] = {
    "incident": (r"خطا", r"خراب", r"کار نمی کن", r"از کار افتاد", r"\b(?:500|502|503|504|404|oom|crash|failed|error|exception|down|bug)\b",
                 r"باز نمی ش", r"کند شد", r"بالا نمیاد", r"تایم اوت", r"در دسترس نیست", r"مشکل",
                 r"\b(?:slow|unhealthy|unavailable|timeout|timed out|connection refused)\b"),
    "deploy": (r"دیپلوی", r"دپلوی", r"استقرار", r"منتشر", r"انتشار بده",
               r"دیپلو", r"راه انداز", r"ساخت پروژه", r"ساخت برنامه", r"ایجاد پروژه",
               r"\bdeploy\b", r"\bpublish\b", r"آپلود سورس"),
    "health": (r"سلامت", r"پایش", r"وضعیت سرویس", r"وضعیت پروژه",
               r"سایتم بالا هست", r"سرویس بالا هست", r"داون", r"\buptime\b", r"\bhealth\b", r"\bstatus\b"),
    "projects": (r"لیست پروژه", r"فهرست پروژه", r"لیست برنامه", r"فهرست برنامه", r"پروژه هام",
                 r"پروژه ها", r"\blist (?:apps|projects)\b"),
    "releases": (r"نسخه ها", r"انتشارها", r"تاریخچه انتشار", r"آخرین نسخه", r"نسخه جدید",
                 r"\breleases?\b", r"\brollbacks?\b"),
    "domains": (r"دامنه", r"دی ان اس", r"\bdns\b", r"\bssl\b", r"\btls\b", r"گواهی", r"\bcname\b"),
    "logs": (r"لاگ", r"لوگ", r"استک تریس", r"\blogs?\b", r"\btraceback\b"),
    "billing": (r"هزینه", r"قیمت", r"صورت حساب", r"پلن", r"تعرفه", r"\bbill(?:ing)?\b", r"\bprice\b", r"\bcost\b"),
    "security": (r"امنیت", r"مجوز", r"توکن", r"دسترسی", r"کلید", r"\bauth\b", r"\btoken\b", r"\bsecurity\b"),
    "env": (r"متغیر محیطی", r"انوایر", r"تنظیمات محیطی", r"\b(?:env|dotenv|environment)\b", r"کانفیگ"),
    "restart": (r"ری استارت", r"ریستارت", r"راه اندازی مجدد", r"\brestart\b"),
    "resources": (r"مصرف رم", r"مصرف cpu", r"حافظه", r"سی پی یو",
                  r"کندی", r"پرفورمنس", r"\b(?:ram|cpu|memory|disk|latency|metrics?)\b"),
    "database": (r"دیتابیس", r"پایگاه داده", r"پستگرس", r"ردیس",
                 r"\b(?:postgres|postgresql|mysql|mongodb|redis|database)\b"),
    "backup": (r"بکاپ", r"پشتیبان گیری", r"بازیابی داده",
               r"\b(?:backup|restore|snapshot)\b"),
    "team": (r"حساب تیمی", r"پروژه تیمی", r"اعضای تیم", r"\bworkspace\b",
             r"\bteam\b"),
    "support": (r"پشتیبانی", r"اپراتور", r"کارشناس", r"انسان واقعی", r"\bsupport\b"),
    "notifications": (r"هشدار", r"اعلان", r"خبرم کن", r"وقتی خراب شد", r"\b(?:alert|notify|notification)\b"),
}
_DESTRUCTIVE = (r"حذف (?:کن|بکن|پروژه|برنامه|سرویس|اطلاعات)", r"پاک (?:کن|کردن|بکن)",
                r"حذف دامنه", r"حذف دیتابیس", r"\b(?:delete|drop|destroy|terminate|wipe)\b", r"دیتابیس رو پاک", r"همه رو حذف")
_OUT_OF_SCOPE = (r"رمز عبورم رو عوض", r"پول (?:انتقال|واریز)", r"از حسابم پرداخت", r"دامنه رو خرید",
                 r"خرید دامنه", r"پرداخت کن", r"\b(?:buy domain|transfer funds)\b")
_CONFIRM = (r"^(?:بله|آره|اوکی|باشه|تایید|تأیید|yes|ok|confirm)\W*$",)
_CANCEL = (r"^(?:نه|لغو|انصراف|بی خیال|نمی خوام|cancel|stop|no)\W*$",)

def classify(message: str) -> Decision:
    t = normalize(message)
    if not t:
        return Decision("unknown", "guide", "unknown", (),
                        (_ACTIONS["incident"], _ACTIONS["deploy"]),
                        "درخواست خالی است؛ بگویید چه کاری مدنظر دارید.")
    if _has(t, *_DESTRUCTIVE):
        return Decision("destructive", "guide", "blocked", ("destructive",),
                        (), "حذف سرویس یا داده در این نسخه پشتیبانی نمی‌شود. هیچ اقدامی انجام نشده است.")
    if _has(t, *_OUT_OF_SCOPE):
        return Decision("unsupported", "guide", "blocked", ("unsupported",),
                        (), "این عملیات از توان و مجوزهای Sentinel خارج است. هیچ اقدامی انجام نشده است.")
    if _has(t, *_CONFIRM):
        return Decision("confirmation", "guide", "ambiguous", ("confirmation",),
                        (), "برای عملیات حساس، پاسخ «بله» در چت کافی نیست. تأیید فقط از کارت دارای نام پروژه و مجوز معتبر انجام می‌شود.")
    if _has(t, *_CANCEL):
        return Decision("cancellation", "guide", "ambiguous", ("cancellation",),
                        (), "پیام شما هیچ عملیاتی را اجرا نکرد. برای لغو مجوز پیشنهادی از دکمه «لغو» روی همان کارت استفاده کنید.")
    if _has(t, r"^\s*(?:سلام|درود|hello|hi)\W*$"):
        return Decision("greeting", "guide", "clear", ("greeting",),
                        (_ACTIONS["deploy"], _ACTIONS["incident"], _ACTIONS["projects"]),
                        "سلام! می‌توانم در انتشار، بررسی خطا و مشاهده وضعیت برنامه‌ها کمکتان کنم.")
    hits = {key for key, patterns in _PATTERNS.items() if _has(t, *patterns)}
    # The official brief expects guided first-time infrastructure selection.
    # "Which plan fits my website?" is not a request to buy a plan or deploy.
    if "incident" not in hits and _has(t, r"زیرساخت مناسب", r"چه زیرساخت", r"چه پلنی", r"کدوم پلن",
            r"پلن مناسب", r"انتخاب پلن", r"پلن پیشنهاد", r"منابع مورد نیاز",
            r"برای سایت.{0,30}(?:پلن|زیرساخت)", r"\b(?:which plan|sizing advice|capacity planning)\b"):
        return Decision("capacity", "deploy", "clear",
                        tuple(sorted(hits | {"capacity"})), (),
                        "ابتدا نیازهای پروژه و سورس را ارزیابی می‌کنم. انتخاب پلن، هزینه یا انتشار تا تأیید واقعی انجام نمی‌شود.")
    if not hits and _has(t, r"چیکار می تونی", r"چه کارهایی", r"راهنما", r"\bhelp\b", r"از کجا شروع"):
        return Decision("help", "guide", "clear", ("help",),
                        (_ACTIONS["deploy"], _ACTIONS["incident"], _ACTIONS["domains"]),
                        "از یکی از مسیرهای زیر شروع کنید. فقط اقدام‌های پشتیبانی‌شده را پیشنهاد می‌دهم.")
    if not hits:
        return Decision("unknown", "guide", "unknown", (),
                        (_ACTIONS["deploy"], _ACTIONS["incident"], _ACTIONS["projects"]),
                        "درخواست شما را با اطمینان کافی به یکی از قابلیت‌های موجود مرتبط نکردم. لطفاً یکی از مسیرهای مشخص را انتخاب کنید.")
    # Negative or hypothetical requests must not be interpreted as authorization.
    if _has(t, r"نمی خوام", r"نمی خواهم", r"اجرا نکن", r"منتشر نکن", r"دیپلوی نکن", r"فقط توضیح", r"بدون اجرا", r"don'?t (?:deploy|restart)"):
        return Decision("explain", "guide", "clear", tuple(sorted(hits)),
                        tuple(_ACTIONS[k] for k in ("billing", "security") if k in hits),
                        "درخواست شما را توضیحی در نظر گرفتم. هیچ عملیاتی اجرا یا برای تأیید ارسال نمی‌شود.")

    # Checking an earlier deployment is not requesting another deployment.
    if "incident" not in hits and "deploy" in hits and _has(t,
            r"(?:وضعیت|آخرین|تاریخچه|نتیجه|موفق شد|چه شد).{0,32}(?:دیپلوی|دپلوی|استقرار|انتشار|deploy)",
            r"(?:دیپلوی|دپلوی|استقرار|انتشار|deploy).{0,32}(?:چه شد|موفق شد|وضعیت|نتیجه)"):
        return Decision("releases", "releases", "clear", tuple(sorted(hits)))
    # Pricing questions about deployment must not open a write-oriented wizard.
    if "incident" not in hits and "deploy" in hits and "billing" in hits and _has(t, r"چقدر", r"هزینه", r"قیمت", r"\bcost\b", r"\bprice\b") and not _has(
            t, r"منتشر کن", r"دیپلوی کن", r"استقرار بده", r"\bdeploy it\b"):
        return Decision("billing", "guide", "clear", tuple(sorted(hits)))
    # Domain setup/how-to is not the same as an authorized DNS mutation.
    if "incident" not in hits and "domains" in hits and _has(t, r"چطور", r"چگونه", r"وصل کنم", r"تنظیم کنم", r"\bhow to\b"):
        return Decision("domain_setup", "guide", "clear", tuple(sorted(hits)))
    # Emergency signals and log text are evidence requests, not deployment.
    if "notifications" in hits and _has(t, r"وقتی", r"هر وقت", r"به محض", r"\bif\b"):
        return Decision("notifications", "guide", "clear", tuple(sorted(hits)))
    if "incident" in hits:
        return Decision("incident", "inspect", "clear", tuple(sorted(hits)))
    # Restart is always an investigation and never silently runs.
    if "restart" in hits:
        return Decision("restart", "inspect", "clear", tuple(sorted(hits)))
    # A deployment request can mention a plan, environment or recent release.
    if "deploy" in hits:
        return Decision("deploy", "deploy", "clear", tuple(sorted(hits)))

    # Mixed *independent* requests require an explicit task selection.
    read_tasks = hits & {"projects", "releases", "domains", "health", "logs",
                         "billing", "security", "env", "database", "backup",
                         "team", "support", "notifications"}
    if "resources" in hits:
        read_tasks.add("health")
    if "logs" in read_tasks and "health" in read_tasks:
        read_tasks.remove("logs")
    # These are modifiers of a more specific task, not separate goals.
    if "backup" in read_tasks and "database" in read_tasks:
        read_tasks.remove("database")
    if "projects" in read_tasks and "team" in read_tasks:
        read_tasks.remove("team")
    if len(read_tasks) > 1:
        ordered = sorted(read_tasks)
        return Decision("multi_intent", "guide", "ambiguous", tuple(sorted(hits)),
                        tuple(_ACTIONS[k] for k in ordered),
                        "چند درخواست مستقل در پیام وجود دارد. برای جلوگیری از بررسی پروژه یا اطلاعات اشتباه، ابتدا یکی را انتخاب کنید.")
    if "releases" in hits:
        return Decision("releases", "releases", "clear", tuple(sorted(hits)))
    if "domains" in hits:
        return Decision("domains", "domains", "clear", tuple(sorted(hits)))
    if "projects" in hits:
        return Decision("projects", "projects", "clear", tuple(sorted(hits)))
    if "logs" in hits or "health" in hits or "resources" in hits:
        return Decision("health", "inspect", "clear", tuple(sorted(hits)))
    # Prices, plans, security and env are educational guidance with verified
    # boundaries; they are not fabricated estimates or permission changes.
    for label in ("billing", "security", "env", "backup", "database", "team", "support", "notifications"):
        if label in hits:
            return Decision(label, "guide", "clear", tuple(sorted(hits)))
    return Decision("unknown", "guide", "unknown", tuple(sorted(hits)),
                    (_ACTIONS["deploy"], _ACTIONS["incident"]),
                    "برای شروع، درخواستتان را دقیق‌تر انتخاب کنید.")
