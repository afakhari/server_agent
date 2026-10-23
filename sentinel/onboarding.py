"""Source-grounded first-deployment readiness and capacity guidance.

Read-only: never returns an invented Liara plan ID, price, size, or invoice.
A human checks the actual plan catalog and billing in their Liara account.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field
from sentinel.scout import inspect_repo

Traffic = Literal["unknown", "low", "medium", "high"]
Workload = Literal["web", "static", "worker", "unknown"]

class AssessmentInput(BaseModel):
    traffic: Traffic = "unknown"
    workload: Workload = "unknown"
    needs_database: bool | None = None
    custom_domain: bool = False
    uptime_critical: bool = False
    existing_app: bool = True
    port: int | None = Field(default=None, ge=1, le=65535)

def assess(inspection: dict, req: AssessmentInput) -> dict:
    """Only grounded source facts + operator-entered requirements.

    'ready' means ready for a separate review, NOT authenticated release.
    """
    platform = str(inspection.get("platform") or "نامشخص")
    framework = str(inspection.get("framework") or "نامشخص")
    configured_port = inspection.get("port")
    needs_port = platform in {"python", "node", "php", "docker"}
    candidate_port = req.port or configured_port
    blockers: list[str] = []
    warnings: list[str] = list(inspection.get("warnings") or [])
    if platform not in {"python", "node", "php", "docker"}:
        blockers.append("پلتفرم پروژه از فایل‌های موجود قابل‌تشخیص نیست؛ انتخاب خودکار امن نیست.")
    if needs_port and candidate_port is None:
        blockers.append("پورت برنامه مشخص نیست؛ ابتدا پورت واقعی برنامه را بررسی کنید.")
    if configured_port is not None and req.port is not None and configured_port != req.port:
        blockers.append("پورت انتخاب‌شده با مقدار liara.json همخوانی ندارد؛ بدون اصلاح تنظیمات انتشار نکنید.")

    env_names = list(inspection.get("required_env_names") or [])
    if env_names:
        warnings.append("متغیرهای محیطی لازم را به‌صورت امن در پنل لیارا مقداردهی کنید؛ مقادیر را در چت نفرستید.")
    if req.needs_database is None:
        warnings.append("نیاز به دیتابیس هنوز معلوم نیست؛ قبل از استقرار وابستگی‌های برنامه را بررسی کنید.")
    if req.needs_database and not any(
        key in env_names for key in ("DATABASE_URL", "REDIS_URL", "POSTGRES_URL", "MYSQL_URL")
    ):
        warnings.append("پایگاه داده درخواست شده اما نحوه اتصال در فایل نمونه پروژه روشن نیست.")
    if req.traffic == "unknown":
        warnings.append("حجم ترافیک نامشخص است؛ تعیین اندازه منابع نیازمند مشاهده مصرف واقعی است.")
    if req.traffic == "high" or req.uptime_critical:
        warnings.append("قبل از انتشار، ظرفیت، محدودیت پلن، افزونگی و شرایط اختلال در پنل واقعی بررسی شوند.")
    if req.workload == "static" and platform in {"python", "php"}:
        warnings.append("برای محتوای صرفاً ایستا شاید سرویس استاتیک مناسب‌تر باشد؛ پلتفرم را قبل از خرید بررسی کنید.")
    if req.workload == "unknown":
        warnings.append("نوع اجرای برنامه هنوز معلوم نیست؛ تعیین کنید وب‌سرویس، محتوای ایستا یا worker است.")
    if req.workload == "worker":
        blockers.append("مسیر انتشار موجود برای وب‌سرویس طراحی شده؛ سازگاری worker و دستور اجرا باید جدا تأیید شوند.")

    resource_profile = (
        "نیازمند ظرفیت‌سنجی با بار آزمایشی و داده واقعی CPU/RAM"
        if req.traffic == "high" or req.uptime_critical
        else "شروع با کوچک‌ترین گزینه سازگارِ قابل‌بررسی در حساب و اندازه‌گیری پس از انتشار"
        if req.traffic == "low"
        else "انتخاب موقت بر اساس محدودیت پلن و پایش اولیه CPU/RAM"
    )
    steps = [
        {"id": "inspect", "title": "بررسی فناوری، وابستگی‌ها و پورت سورس",
         "responsible": "assistant", "status": "reviewed" if not blockers else "needs_attention"},
        {"id": "account", "title": "ورود و بررسی دسترسی حساب یا تیم لیارا",
         "responsible": "operator", "status": "required"},
        {"id": "target", "title": (
            "بررسی وجود برنامه فعلی و تطبیق دقیق پلتفرم در حساب لیارا"
            if req.existing_app else
            "تأیید نام برنامه جدید و امکان ایجاد آن در حساب لیارا"
         ), "responsible": "operator", "status": "required"},
        {"id": "billing", "title": "کنترل موجودی، قیمت و شناسه پلن در پنل واقعی",
         "responsible": "operator", "status": "required"},
        {"id": "secrets", "title": "تنظیم متغیرهای محرمانه در محیط امن لیارا",
         "responsible": "operator", "status": "required" if env_names or req.needs_database else "conditional"},
        {"id": "approval", "title": "مرور اثر روی برنامه و تأیید دقیق استقرار",
         "responsible": "operator", "status": "required"},
        {"id": "deployment", "title": "ارسال انتشار فقط پس از فعال‌شدن مجوزهای محیط آزمایشی",
         "responsible": "assistant", "status": "not_started"},
        {"id": "verification", "title": "بررسی نسخه، پاسخ HTTP و سلامت پس از انتشار",
         "responsible": "assistant", "status": "not_started"},
    ]
    if req.custom_domain:
        steps.extend([
            {"id": "dns", "title": "دریافت رکورد معتبر از لیارا و ثبت DNS نزد مالک دامنه",
             "responsible": "operator", "status": "required"},
            {"id": "tls", "title": "بازبینی وضعیت دامنه و گواهی SSL از داده واقعی",
             "responsible": "assistant", "status": "not_started"},
        ])
    return {
        "type": "readiness_assessment",
        "readiness": "blocked" if blockers else "manual_review_required",
        "framework": framework, "platform": platform, "port": candidate_port,
        "traffic": req.traffic, "workload": req.workload,
        "resource_guidance": resource_profile,
        "liara_plan_id": None, "plan_price": None,
        "pricing_status": "NOT_VERIFIED",
        "required_env_names": env_names,
        "blockers": blockers,
        "warnings": list(dict.fromkeys(warnings)),
        "steps": steps,
        "scope": "STATIC_SOURCE_AND_OPERATOR_INPUT_ONLY",
        "execution": "NOT_STARTED",
        "disclaimer": "پیشنهاد منابع تقریبی است؛ پلن، قیمت، سازگاری API و هزینه فقط با اطلاعات حساب واقعی و تأیید کاربر قطعی می‌شود.",
    }
