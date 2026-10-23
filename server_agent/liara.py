"""Constrained Liara PaaS adapter. See docs/03-liara-api.md."""
from __future__ import annotations
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any
import httpx

PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")
class LiaraError(Exception):
    def __init__(self, code: str, status: int | None = None):
        super().__init__(code)
        self.code, self.status = code, status

def project_name(value: str) -> str:
    if not PROJECT_RE.fullmatch(value):
        raise LiaraError("invalid_project")
    return value

def scrub_project(details: dict[str, Any]) -> dict[str, Any]:
    """Whitelist known non-secret fields; never pass raw env values to UI/LLM."""
    project = details.get("project") if "project" in details else details
    if not isinstance(project, dict):
        raise LiaraError("invalid_project_response")
    fields = ("project_id", "status", "scale", "isDeployed", "planID",
              "type", "zeroDowntime", "hourlyPrice", "defaultSubdomain")
    result = {k: project[k] for k in fields if k in project}
    envs = project.get("envs")
    if isinstance(envs, list):
        result["environment_keys"] = sorted({
            item["key"] for item in envs if isinstance(item, dict)
            and isinstance(item.get("key"), str)
        })
    return result

class LiaraClient:
    def __init__(self, token: str | None = None, transport: httpx.BaseTransport | None = None):
        self.token = token if token is not None else os.getenv("LIARA_API_TOKEN", "")
        if not self.token:
            raise LiaraError("missing_liara_token")
        self.http = httpx.Client(
            base_url="https://api.liara.ir",
            headers={"Authorization": "Bearer " + self.token, "Accept": "application/json"},
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=4),
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )

    def close(self):
        self.http.close()

    def _call(self, method: str, path: str, **kwargs):
        try:
            response = self.http.request(method, path, **kwargs)
            response.raise_for_status()
            if len(response.content) > 2_000_000:
                raise LiaraError("liara_response_too_large")
            if not response.content:
                return {}
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise LiaraError("liara_http_error", exc.response.status_code) from exc
        except (httpx.RequestError, ValueError) as exc:
            raise LiaraError("liara_unavailable_or_invalid_json") from exc

    def projects(self):
        data = self._call("GET", "/v1/projects")
        if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
            raise LiaraError("invalid_projects_response")
        return {"projects": [scrub_project(x) for x in data["projects"] if isinstance(x, dict)]}

    def project(self, name: str):
        return scrub_project(self._call("GET", "/v1/projects/" + project_name(name)))

    def logs(self, name: str, minutes: int = 30):
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        # The string type is defined by the OpenAPI; exact runtime syntax needs live validation.
        return self._call("GET", "/v1/projects/" + project_name(name) + "/logs",
                          params={"since": str(int(since.timestamp()))})

    def events(self, name: str, minutes: int = 30):
        start = int(time.time()) - minutes * 60
        return self._call("GET", "/v1/projects/" + project_name(name) + "/events",
                          params={"start": start, "end": int(time.time())})

    def releases(self, name: str):
        return self._call("GET", "/v1/projects/" + project_name(name) + "/releases",
                          params={"page": 1, "count": 10})

    def metrics(self, name: str):
        return self._call("GET", "/v1/projects/" + project_name(name) + "/metrics/summary")

    def applets(self, name: str):
        return self._call("GET", "/v1/projects/" + project_name(name) + "/applets")

    def create_project(self, name: str, plan_id: str, platform: str):
        if not re.fullmatch(r"[A-Za-z0-9_-]{2,80}", plan_id):
            raise LiaraError("invalid_plan_id")
        if platform not in ("python", "node", "docker"):
            raise LiaraError("invalid_platform")
        return self._call("POST", "/v1/projects", json={
            "name": project_name(name), "planID": plan_id, "platform": platform
        })

    def restart(self, name: str):
        return self._call("POST", "/v1/projects/" + project_name(name) + "/actions/restart")

    def upload_archive(self, name: str, archive: bytes):
        if len(archive) > 5_000_000:
            raise LiaraError("archive_too_large")
        return self._call("POST", "/v2/projects/" + project_name(name) + "/sources",
                          files={"file": ("source.tar.gz", archive, "application/gzip")})

    def release(self, name: str, source_id: str, platform: str, port: int):
        return self._call("POST", "/v2/projects/" + project_name(name) + "/releases",
                          json={"sourceID": source_id, "type": platform, "port": port})

    def snapshot(self, name: str, minutes: int = 30) -> dict:
        name = project_name(name)
        snapshot: dict[str, Any] = {
            "name": name, "mode": "live", "project": self.project(name),
            "logs": [], "events": [], "releases": {}, "metrics": {},
            "applets": {}, "limitations": [], "sources": {},
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        for key, fn in (
            ("logs", lambda: self.logs(name, minutes)),
            ("events", lambda: self.events(name, minutes)),
            ("releases", lambda: self.releases(name)),
            ("metrics", lambda: self.metrics(name)),
            ("applets", lambda: self.applets(name)),
        ):
            try:
                data = fn()
                snapshot[key] = data
                snapshot["sources"][key] = "available"
            except LiaraError as exc:
                snapshot["limitations"].append(key + ": " + exc.code +
                                               ((" (" + str(exc.status) + ")") if exc.status else ""))
                snapshot["sources"][key] = "unavailable"
        return snapshot
