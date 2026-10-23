"""Deterministic evidence-backed incident analysis. LLM has no write privileges."""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Any

_PATTERNS = (
    (re.compile(r"(?i)(bearer\s+)[\w.+/=-]{8,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:password|secret|token|api[_-]?key)\s*[=:]\s*)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(postgres(?:ql)?|redis|mysql)://[^\s@]+@"), r"\1://[REDACTED]@"),
    (re.compile(r"(?i)(DATABASE_URL|REDIS_URL)\s*=\s*[^\s]+"), r"\1=[REDACTED]"),
)
def redact(value: Any, limit: int = 500) -> str:
    text = str(value)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:limit]

def demo_snapshot(scenario: str = "transient") -> dict:
    cases = {
        "transient": ("crashed", ["ERROR worker crashed: transient error after a failed request",
                                 "HTTP 500 internal server error"], False),
        "env": ("crashed", ["KeyError: DATABASE_URL - missing environment variable",
                            "HTTP 500 internal server error"], True),
        "memory": ("running", ["OOMKilled: out of memory; process terminated"], False),
        "dependency": ("running", ["ECONNREFUSED: connection to database failed"], False),
        "release": ("crashed", ["HTTP 500 internal server error"], True),
        "healthy": ("running", ["GET /health HTTP 200"], False),
    }
    if scenario not in cases:
        raise ValueError("invalid_scenario")
    status, lines, recent = cases[scenario]
    return {
        "mode": "demo", "name": "demo-shop", "project": {
            "status": status, "isDeployed": True, "scale": 1,
            "environment_keys": ["APP_ENV"],
        },
        "logs": [{"type": "stderr", "datetime": "2026-10-23T12:00:00Z", "message": x} for x in lines],
        "events": {"data": []}, "applets": {"applets": []},
        "releases": {"currentRelease": "rel-v3",
                     "releases": [{"_id": "rel-v3", "state": "ready", "gitInfo": {"commit": "demo-v3"}},
                                  {"_id": "rel-v2", "state": "ready"}]},
        "metrics": {}, "sources": {"logs": "synthetic", "events": "synthetic",
                                    "releases": "synthetic", "metrics": "synthetic"},
        "limitations": ["تمام شواهد این سناریو ساختگی‌اند؛ هیچ اتصال یا اقدام واقعی به لیارا انجام نشده است."],
        "recent_change": recent, "scenario": scenario,
        "observed_at": datetime.now(timezone.utc).isoformat()
    }

def analyze(snapshot: dict) -> dict:
    """Only cite extracted evidence; no synthetic metrics percentages."""
    evidence: list[dict] = []
    def add(kind: str, text: str, source: str, observed: str | None = None):
        if len(evidence) >= 60:
            return
        evidence.append({"id": "EV-" + str(len(evidence) + 1).zfill(3),
                         "kind": kind, "text": redact(text), "source": source,
                         "observed_at": observed or snapshot.get("observed_at")})
    p = snapshot.get("project", {})
    add("status", "status=" + str(p.get("status", "unknown")) +
        "; isDeployed=" + str(p.get("isDeployed", "unknown")), "liara.project")
    logs = snapshot.get("logs", [])
    if isinstance(logs, list):
        for line in logs[-30:]:
            if isinstance(line, dict):
                add("log", line.get("message", ""), "liara.logs", line.get("datetime"))
    releases = snapshot.get("releases", {})
    if isinstance(releases, dict):
        for item in releases.get("releases", [])[:4]:
            if isinstance(item, dict):
                git = item.get("gitInfo") or {}
                add("release", "release=" + str(item.get("_id")) +
                    "; state=" + str(item.get("state")) +
                    "; commit=" + str(git.get("commit") if isinstance(git, dict) else "unknown") +
                    "; createdAt=" + str(item.get("createdAt", "unknown")),
                    "liara.releases")
    events = snapshot.get("events", {})
    if isinstance(events, dict):
        for entry in events.get("data", [])[:3]:
            add("event", entry, "liara.events")
    # Summary reports can contain heterogeneous unknown units. Preserve availability only.
    if snapshot.get("sources", {}).get("metrics") in ("available", "synthetic"):
        add("metric", "گزارش متریک دریافت شد؛ واحد و آستانه بدون قرارداد معتبر نامشخص است.",
            "liara.metrics")
    logs_ev = [e for e in evidence if e["kind"] == "log"]
    logtext = "\n".join(e["text"].lower() for e in logs_ev)
    log_ids = [e["id"] for e in logs_ev]
    status_ids = [e["id"] for e in evidence if e["kind"] == "status"]
    release_ids = [e["id"] for e in evidence if e["kind"] == "release"]
    hypotheses = []
    def add_h(code, title, confidence, reason, ids, next_check, action="none"):
        hypotheses.append({
            "code": code, "title": title, "confidence": confidence, "reason": reason,
            "supporting_evidence_ids": list(dict.fromkeys(ids)),
            "contradicting_evidence_ids": [],
            "next_readonly_check": next_check, "action": action
        })
    if re.search(r"keyerror|missing (?:env|environment)|undefined environment|configurationerror", logtext):
        add_h("missing_env", "پیکربندی محیطی ناقص", "high",
              "در لاگ خطای مستقیم پیکربندی دیده شده است؛ وجود کلیدها بررسی شود.",
              log_ids, "compare_env_key_names")
    if re.search(r"oomkilled|out of memory|memoryerror|heap out of memory", logtext):
        add_h("out_of_memory", "فشار حافظه یا نشت حافظه", "high",
              "لاگ یک خطای حافظه را ثبت کرده؛ مقدار RAM بدون تطبیق واحد اثبات نشده است.",
              log_ids, "review_memory_series")
    if re.search(r"econnrefused|connection refused|connect etimedout|could not connect", logtext):
        add_h("dependency", "اختلال در اتصال به وابستگی", "medium",
              "اتصال ناموفق به سرویس وابسته گزارش شده است.",
              log_ids, "check_dependency_health")
    if re.search(r"transient error|worker crashed|temporary failure", logtext) and not hypotheses:
        add_h("transient", "خرابی احتمالی پردازش", "medium",
              "خرابی فرایند ثبت شده؛ ری‌استارت فقط بازیابی موقت احتمالی است.",
              log_ids + status_ids, "check_repeated_crashes", "restart")
    if re.search(r"http 500|internal server error|status=500", logtext) and not hypotheses:
        add_h("http500", "خطای HTTP 500 با علت نامعلوم", "low",
              "خطا دیده شده ولی منشأ آن هنوز از داده‌های فعلی روشن نیست.",
              log_ids, "read_application_stacktrace")
    # Real temporal correlation is evidence, never automatic proof of causality.
    if not snapshot.get("recent_change") and isinstance(releases, dict):
        def parse_time(value):
            if not isinstance(value, str):
                return None
            try:
                v = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return v if v.tzinfo else None
            except ValueError:
                return None
        release_times = [parse_time(x.get("createdAt")) for x in releases.get("releases", [])[:3]
                         if isinstance(x, dict)]
        log_times = [parse_time(x.get("datetime")) for x in logs[-30:]
                     if isinstance(x, dict)] if isinstance(logs, list) else []
        snapshot = dict(snapshot)
        snapshot["recent_change"] = any(
            r and l and 0 <= (l - r).total_seconds() <= 1800
            for r in release_times for l in log_times
        )
    if snapshot.get("recent_change") and release_ids:
        add_h("release_correlation", "هم‌زمانی با انتشار اخیر", "low",
              "نزدیکی زمانی انتشار و خطا به‌تنهایی رابطه علّی را اثبات نمی‌کند.",
              release_ids + log_ids, "compare_release_and_error_timestamps")
    if not hypotheses:
        add_h("insufficient", "شواهد کافی وجود ندارد", "unknown",
              "برای تشخیص علت به داده بیشتری نیاز است.", status_ids, "collect_more_evidence")
    hypotheses.sort(key=lambda h: {"high": 0, "medium": 1, "low": 2, "unknown": 3}[h["confidence"]])
    top = hypotheses[0]
    unhealthy = str(p.get("status", "")).lower() in {"crashed", "error", "unhealthy", "failed", "stopped"}
    proposals = []
    if top["action"] == "restart" and unhealthy:
        proposals.append({
            "action": "restart", "title": "ری‌استارت کنترل‌شده سرویس",
            "risk": "اختلال کوتاه، احتمال تکرار خرابی", "requires_approval": True,
            "reason": top["reason"], "evidence_ids": top["supporting_evidence_ids"]
        })
    recommendations = {
        "missing_env": "نام کلیدهای محیطی را بررسی کنید؛ مقادیر محرمانه نباید نمایش داده شوند.",
        "out_of_memory": "مصرف حافظه و رفتار برنامه را تحلیل کنید؛ ارتقای پلن بدون شواهد توصیه نمی‌شود.",
        "dependency": "سلامت پایگاه داده، شبکه و زمان‌انتظار اتصال را بررسی کنید.",
        "transient": "ری‌استارت آزمایشی فقط با تأیید و ارزیابی سلامت بعد از اجرا.",
        "http500": "stacktrace و وضعیت release را برای تشخیص علت دقیق‌تر بررسی کنید.",
        "insufficient": "گردآوری لاگ و اطلاعات رخداد یا آزمون سلامت لازم است.",
        "release_correlation": "مقایسه وضعیت قبل و بعد انتشار و تست مستقیم لازم است.",
    }
    return {
        "mode": snapshot.get("mode"), "project": snapshot.get("name"),
        "observed_at": snapshot.get("observed_at"), "hypotheses": hypotheses,
        "evidence": evidence, "proposals": proposals,
        "limitations": snapshot.get("limitations", []),
        "sources": snapshot.get("sources", {}),
        "verdict": "needs_more_data" if top["confidence"] == "unknown" else "evidence_found",
        "recommendation": recommendations.get(top["code"], "بررسی بیشتر لازم است."),
    }
