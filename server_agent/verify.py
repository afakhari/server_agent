"""Independent verification; no arbitrary user-controlled URL requests."""
from __future__ import annotations
import ipaddress
import os
import socket
from urllib.parse import urlparse
import httpx

def safe_probe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("invalid_health_url")
    # Only exact operator-configured hostnames may be probed; redirects are disabled.
    allow = {v.strip().lower() for v in os.getenv("LIARA_ALLOWED_HEALTH_HOSTS", "").split(",") if v.strip()}
    if parsed.hostname.lower() not in allow:
        raise ValueError("health_host_not_allowlisted")
    if parsed.port not in (None, 443):
        raise ValueError("health_port_not_allowed")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("health_dns_unavailable") from exc
    if not addresses:
        raise ValueError("health_dns_unavailable")
    for entry in addresses:
        address = ipaddress.ip_address(entry[4][0])
        if not address.is_global:
            raise ValueError("health_ip_not_public")
    return url

def probe(url: str) -> dict:
    safe_probe_url(url)
    try:
        # Operator-configured and validated URL only; no redirects or proxy env.
        with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", url) as response:
                status = response.status_code
        return {"status_code": status, "healthy": 200 <= status < 300}
    except httpx.RequestError:
        return {"healthy": None, "error": "health_probe_unavailable"}
