"""Conservative source-file secret guard used before an archive is created.

Do not treat this as comprehensive DLP: review the source before allowing writes.
"""
from __future__ import annotations
import re

_PROTECTED_NAME = re.compile(
    r"(?:^|/)(?:credentials?|secrets?|service[-_]?account|private[-_]?config|"
    r"production[-_]?config|auth[-_]?settings)\.(?:json|ini|yaml|yml|toml|txt)$",
    flags=re.IGNORECASE,
)
_AUTH_IN_URL = re.compile(
    r"(?i)\b(?:postgres(?:ql)?|mysql|redis|mongodb(?:\+srv)?|amqp|https?)"
    r"://[^\s/@]{1,100}:[^\s/@]{1,160}@[^\s]+"
)
_DIRECT_TOKEN = re.compile(
    r"(?i)(?:\bBearer\s+[A-Za-z0-9._~+/=-]{16,}|"
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{16,}|sk-[A-Za-z0-9_-]{16,}|"
    r"AKIA[0-9A-Z]{16})\b)"
)
_ASSIGNMENT = re.compile(
    r"""(?im)(?<![\w.])(?:["']?)(?:password|passwd|api[_-]?key|access[_-]?token|
        secret[_-]?key|aws_secret_access_key|database_url|redis_url|
        private[_-]?key|liara_api_token|authorization)(?:["']?)
        \s*[:=]\s*(?:["'])?([^\s,;'"{}]{6,200})""",
    re.VERBOSE,
)
_SAFE_EXAMPLES = (
    "example", "placeholder", "your_", "replace_", "changeme",
    "change-me", "dummy", "test-", "fake-", "redacted", "not-set",
)
_SAFE_REFERENCES = (
    "os.", "environ.", "process.", "import.", "env(", "getenv(", "$",
    "secrets.", "settings.", "config.", "none", "null", "undefined",
)


def suspicious_source(relative_path: str, data: bytes) -> str | None:
    """Return a nonsecret reason for blocking upload, or None."""
    path = relative_path.replace("\\", "/")
    if _PROTECTED_NAME.search(path):
        return "نام فایل نشانه تنظیمات محرمانه یا اعتبارنامه است"
    if len(data) > 8 * 1024 * 1024:
        return "فایل بیش از سقف بررسی محرمانگی است"
    value = data.decode("utf-8", errors="replace")
    if "-----BEGIN PRIVATE KEY-----" in value or "-----BEGIN OPENSSH PRIVATE KEY-----" in value:
        return "کلید خصوصی در محتوا موجود است"
    if _AUTH_IN_URL.search(value):
        return "رشته اتصال دارای نام کاربری و رمز است"
    if _DIRECT_TOKEN.search(value):
        return "الگوی اعتبارنامه یا توکن در فایل دیده شد"
    for match in _ASSIGNMENT.finditer(value):
        literal = match.group(1).strip().lower()
        if any(literal.startswith(prefix) for prefix in _SAFE_EXAMPLES + _SAFE_REFERENCES):
            continue
        if literal in {"password", "secret", "token", "true", "false", "unset"}:
            continue
        return "مقدار احتمالی رمز یا اعتبارنامه به‌صورت ثابت در فایل دیده شد"
    return None
