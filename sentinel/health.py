"""Independent, conservative HTTP health checking; no user-defined destinations."""
import ipaddress
import json
import os
import socket
from urllib.parse import urlsplit
import httpx


def verified_url_for(project: str) -> str | None:
    try:
        mapping = json.loads(os.environ.get('SENTINEL_HEALTH_URLS', '{}'))
    except ValueError:
        return None
    if not isinstance(mapping, dict):
        return None
    target = mapping.get(project)
    if not isinstance(target, str):
        return None
    url = urlsplit(target)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.port not in (None, 443):
        return None
    if url.fragment or url.query or url.hostname.lower() in {'localhost'} or '.' not in url.hostname:
        return None
    try:
        resolved = socket.getaddrinfo(url.hostname, 443, type=socket.SOCK_STREAM)
        if not resolved:
            return None
        for item in resolved:
            ip = ipaddress.ip_address(item[4][0])
            if not ip.is_global:
                return None
    except (OSError, ValueError):
        return None
    return target


def verify_http(project: str) -> dict:
    url = verified_url_for(project)
    if not url:
        return {'status': 'INCONCLUSIVE', 'reason': 'نشانی HTTPS تأییدشده برای این پروژه موجود نیست؛ سلامت قابل اثبات نیست.'}
    try:
        # No redirects, bounded response, no credentials or cookies. DNS rebinding requires
        # stronger egress pinning in production; live-write mode is explicitly test-only.
        with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            with client.stream('GET', url, headers={'Accept': 'text/plain'}) as response:
                status = response.status_code
                # Do not consume or retain potentially sensitive response bodies.
        return {'status': 'HEALTHY_NOW' if status == 200 else 'FAILED', 'http_status': status,
                'reason': 'یک پاسخ HTTP 200 مستقل دریافت شد؛ به‌تنهایی اثبات بازیابی پایدار نیست' if status == 200 else 'پروب مستقل پاسخ سالم دریافت نکرد'}
    except httpx.HTTPError:
        return {'status': 'INCONCLUSIVE', 'reason': 'پروب سلامت مستقل به نتیجه نرسید'}
