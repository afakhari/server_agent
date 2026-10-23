import io
from pathlib import Path
import tarfile
import pytest
from sentinel.deployer import safe_tree, DeployError, make_plan, claim_plan


def test_safe_archive_excludes_secrets_symlinks_and_node_modules(tmp_path):
    (tmp_path / 'main.py').write_text('print("ok")')
    (tmp_path / '.env').write_text('API=secret')
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'x.js').write_text('bad')
    (tmp_path / 'escape.py').symlink_to(tmp_path / 'main.py')
    data, digest, paths = safe_tree(tmp_path)
    assert paths == ['main.py']
    assert safe_tree(tmp_path)[1] == digest
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        assert archive.getnames() == ['main.py']


def test_archive_rejects_private_key(tmp_path):
    (tmp_path / 'key.py').write_text('-----BEGIN PRIVATE KEY-----\nSECRET')
    with pytest.raises(DeployError):
        safe_tree(tmp_path)


def test_plan_and_single_use(monkeypatch, tmp_path):
    root = tmp_path / 'workspace'
    app = root / 'sample'
    app.mkdir(parents=True)
    (app / 'liara.json').write_text('{"port":8000}')
    (app / 'requirements.txt').write_text('fastapi==0.128')
    (app / 'main.py').write_text('print("hello")')
    monkeypatch.setenv('SENTINEL_WORKSPACE', str(root))
    plan = make_plan('actor', 'testing', 'sample', 'plan-verified-by-operator', 'python', 8000)
    assert plan['requires_approval']
    assert claim_plan('actor', plan['proposal_id'], 'testing')[0] == 'testing'
    with pytest.raises(DeployError):
        claim_plan('actor', plan['proposal_id'], 'testing')


def test_changes_invalidate_deploy_approval(monkeypatch, tmp_path):
    root = tmp_path / 'workspace'
    app = root / 'sample'
    app.mkdir(parents=True)
    (app / 'requirements.txt').write_text('fastapi')
    (app / 'main.py').write_text('old')
    monkeypatch.setenv('SENTINEL_WORKSPACE', str(root))
    plan = make_plan('actor', 'testing', 'sample', 'plan-id', 'python', 8080)
    (app / 'main.py').write_text('new')
    with pytest.raises(DeployError):
        claim_plan('actor', plan['proposal_id'], 'testing')
