"""Focused checks for the disposable Liara Node.js example, no cloud access."""
import io
import json
from pathlib import Path
import shutil
import socket
import subprocess
import os
import time
import tarfile
import urllib.error
import urllib.request
import pytest

from sentinel.scout import inspect_repo
from sentinel.deployer import safe_tree, verify_existing_platform, DeployError

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "node-sentinel-demo"

def test_node_example_matches_liara_platform_and_archive():
    scan = inspect_repo(SAMPLE)
    assert scan["platform"] == "node"
    assert scan["port"] == 8000
    package = json.loads((SAMPLE / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["start"] == "node server.js"
    archive, _, filenames = safe_tree(SAMPLE)
    assert "server.js" in filenames
    assert "package.json" in filenames
    assert "liara.json" in filenames
    assert ".env.example" not in filenames
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        assert all(m.isfile() for m in bundle.getmembers())

def test_exact_node_app_allowed_but_python_blocked():
    class Existing:
        def get_project(self, name):
            return {"project_id":name, "type":"node", "isDeployed":False}
    verify_existing_platform(Existing(), "disposable-node", "node")
    with pytest.raises(DeployError):
        verify_existing_platform(Existing(), "disposable-node", "python")

@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed locally")
@pytest.mark.parametrize("broken,expected", [(False, 200), (True, 500)])
def test_local_node_health(broken, expected):
    # Local-only smoke run, no live Liara traffic or privileged operations.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["SENTINEL_REQUIRE_DEMO_FLAG"] = "true" if broken else "false"
    env.pop("SENTINEL_DEMO_FLAG", None)
    process = subprocess.Popen(
        ["node", "server.js"], cwd=SAMPLE, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        status = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/health" % port, timeout=1) as response:
                    status = response.status
                    break
            except urllib.error.HTTPError as err:
                status = err.code
                break
            except (OSError, TimeoutError):
                time.sleep(0.05)
        assert status == expected
    finally:
        process.terminate()
        process.communicate(timeout=4)
