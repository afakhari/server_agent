"""Static, bounded repo inspection. This module never runs repository code."""
from __future__ import annotations
import json
from pathlib import Path

SAMPLE_FILES = ("main.py", "requirements.txt", "liara.json")
MAX_FILE = 128_000

def scan(root: Path) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("not_a_directory")
    files = {p.name for p in root.iterdir() if p.is_file() and not p.is_symlink()}
    result = {
        "path_name": root.name, "files": sorted(files)[:40],
        "platform": "unknown", "port": None, "env_key_names": [],
        "warnings": [], "deployment_ready": False
    }
    if "requirements.txt" in files or "pyproject.toml" in files:
        result["platform"] = "python"
    if "package.json" in files:
        result["platform"] = "node"
    if "Dockerfile" in files:
        result["warnings"].append("Dockerfile موجود است؛ رفتار ساخت نیاز به بررسی دستی دارد.")
    if "liara.json" in files:
        try:
            conf = json.loads((root / "liara.json").read_text(encoding="utf-8")[:MAX_FILE])
            if isinstance(conf, dict):
                platform = conf.get("platform")
                port = conf.get("port")
                if isinstance(platform, str) and platform in ("python", "node", "docker"):
                    result["platform"] = platform
                if isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535:
                    result["port"] = port
        except (ValueError, OSError, UnicodeError):
            result["warnings"].append("liara.json نامعتبر است.")
    for file in (".env.example", "example.env"):
        if file in files:
            try:
                content = (root / file).read_text(encoding="utf-8")[:MAX_FILE]
                result["env_key_names"] = [
                    line.split("=", 1)[0].strip() for line in content.splitlines()
                    if "=" in line and line.strip() and not line.lstrip().startswith("#")
                ][:40]
            except (OSError, UnicodeError):
                result["warnings"].append("خواندن نام متغیرهای نمونه ممکن نبود.")
    if result["port"] is None:
        result["warnings"].append("پورت سرویس باید پیش از انتشار تأیید شود.")
    result["deployment_ready"] = result["platform"] != "unknown" and result["port"] is not None
    return result

def workspace_path(raw: str, workspace_root: Path) -> Path:
    root = workspace_root.resolve(strict=True)
    p = (root / raw).resolve(strict=True)
    if p != root and root not in p.parents:
        raise ValueError("path_outside_workspace")
    if not p.is_dir():
        raise ValueError("not_a_directory")
    return p

def sample_archive(sample_root: Path) -> bytes:
    """Archive a fixed audited sample, not a user-selected directory."""
    import io
    import tarfile
    data = io.BytesIO()
    root = sample_root.resolve(strict=True)
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        for name in SAMPLE_FILES:
            file = root / name
            if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_FILE:
                raise ValueError("invalid_sample_file")
            archive.add(file, arcname=name, recursive=False)
    return data.getvalue()
