"""Conservative source-file secret guard used before an archive is created.

Do not treat this as comprehensive DLP: review the source before allowing writes.
"""
from __future__ import annotations
import json
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
        if literal in {"password", "secret", "token", "bearer", "true", "false", "unset"}:
            continue
        return "مقدار احتمالی رمز یا اعتبارنامه به‌صورت ثابت در فایل دیده شد"

    # Structured JSON often stores environment secrets as {key: "...", value: "..."}.
    # A plain line regex cannot safely detect these without examining the keys.
    if path.lower().endswith(".json"):
        try:
            parsed = json.loads(value)
        except (ValueError, UnicodeError):
            return None
        stack = [parsed]
        inspected = 0
        while stack and inspected < 10000:
            node = stack.pop()
            inspected += 1
            if isinstance(node, dict):
                env_key = node.get("key")
                env_value = node.get("value")
                if isinstance(env_key, str) and isinstance(env_value, str):
                    simple = re.sub(r"[^a-z0-9]", "", env_key.lower())
                    if any(x in simple for x in ("password", "secret", "token", "apikey",
                                                "databaseurl", "privatekey", "accesskey")):
                        lowered = env_value.strip().lower()
                        if len(lowered) >= 6 and not any(
                            lowered.startswith(p) for p in _SAFE_EXAMPLES + _SAFE_REFERENCES
                        ):
                            return "مقدار محرمانه در ساختار متغیرهای JSON دیده شد"
                for key, item in node.items():
                    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
                    if isinstance(item, str) and any(
                        token in normalized for token in
                        ("password", "secretkey", "apikey", "accesstoken", "refreshtoken",
                         "databaseurl", "privatekey", "awssecretaccesskey")
                    ):
                        lower = item.strip().lower()
                        if len(lower) >= 6 and not any(
                            lower.startswith(p) for p in _SAFE_EXAMPLES + _SAFE_REFERENCES
                        ):
                            return "فیلد محرمانه با مقدار ثابت در JSON دیده شد"
                    if isinstance(item, (dict, list)):
                        stack.append(item)
            elif isinstance(node, list):
                stack.extend(x for x in node if isinstance(x, (dict, list)))
        if stack:
            return "ساختار JSON برای بررسی امن بیش از حد پیچیده است"
    return None
