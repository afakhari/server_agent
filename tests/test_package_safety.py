"""Archive secret safety: all cases operate on disposable local temp files."""
import pytest

from sentinel.deployer import DeployError, safe_tree
from sentinel.package_safety import suspicious_source


@pytest.mark.parametrize("name, contents", [
    ("credentials.json", b'{"client_email":"service@example.test"}'),
    ("service-account.json", b'{"test":true}'),
    ("settings.ini", b"password = actual-secret-value123"),
    ("settings.json", b'{"api_key":"real_live_api_key_1234567890123"}'),
    ("config.yaml", b"database_url: postgres://admin:actualpass@db.example:5432/app"),
    ("config.json", b'{"token":"ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"}'),
    ("notes.md", b"Authorization: Bearer abcdefghijklmnop0123456789"),
    ("myapp.py", b'PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----"'),
])
def test_sensitive_source_is_blocked_without_echoing_values(tmp_path, name, contents):
    folder = tmp_path / "app"
    folder.mkdir()
    (folder / "main.py").write_text("print('hello')\n", encoding="utf8")
    (folder / name).write_bytes(contents)
    why = suspicious_source(name, contents)
    assert why
    with pytest.raises(DeployError) as exc:
        safe_tree(folder)
    assert "ایمن نیست" in str(exc.value)
    assert "actual-secret" not in str(exc.value)
    assert "real_live" not in str(exc.value)
    assert "ghp_" not in str(exc.value)


@pytest.mark.parametrize("source", [
    b'import os\nDB = os.getenv("DATABASE_URL")\n',
    b'const api_key = process.env.API_KEY;\n',
    b'API_KEY=YOUR_TEST_API_KEY\n',
    b'# Passwords come from secret stores, never the repository\n',
])
def test_environment_references_do_not_falsely_block(source):
    assert suspicious_source("app.py", source) is None


def test_clean_archive_builds_and_keeps_only_allowed_files(tmp_path):
    folder = tmp_path / "clean"
    folder.mkdir()
    (folder / "main.py").write_text('import os\nPORT = os.getenv("PORT")\n')
    (folder / "requirements.txt").write_text("fastapi>=0.115\n")
    (folder / "liara.json").write_text('{"platform":"python","port":8000}')
    payload, digest, names = safe_tree(folder)
    assert payload
    assert len(digest) == 64
    assert set(names) == {"main.py", "requirements.txt", "liara.json"}


def test_private_env_is_not_accidentally_archived(tmp_path):
    folder = tmp_path / "withoutenv"
    folder.mkdir()
    (folder / "app.py").write_text("print('safe')\n")
    (folder / ".env").write_text("DATABASE_URL=postgres://user:pass@db/internal\n")
    (folder / ".env.production").write_text("PASSWORD=real-secret\n")
    _, _, names = safe_tree(folder)
    assert names == ["app.py"]
