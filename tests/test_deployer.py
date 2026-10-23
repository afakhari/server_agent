import io
import os
from pathlib import Path
import tarfile
import pytest
from sentinel.deployer import safe_tree, DeployError, make_plan, claim_plan


def test_safe_archive_excludes_secrets_and_node_modules(tmp_path):
    (tmp_path / 'main.py').write_text('print("ok")')
    (tmp_path / '.env').write_text('API=secret')
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'x.js').write_text('bad')
    data, digest, paths = safe_tree(tmp_path)
    assert paths == ['main.py']
    assert safe_tree(tmp_path)[1] == digest
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        assert archive.getnames() == ['main.py']


def test_safe_archive_excludes_symlinks_without_os_privileges(tmp_path, monkeypatch):
    """Security guard works even where creating symlinks needs admin rights."""
    (tmp_path / 'main.py').write_text('print("ok")')
    fake_symlink = tmp_path / 'escape.py'
    fake_symlink.write_text('print("should not be archived")')
    original_is_symlink = Path.is_symlink

    def is_symlink(path):
        return path == fake_symlink or original_is_symlink(path)

    monkeypatch.setattr(Path, 'is_symlink', is_symlink)
    data, _, paths = safe_tree(tmp_path)
    assert paths == ['main.py']
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        assert archive.getnames() == ['main.py']


def test_safe_archive_excludes_real_symlinks_where_supported(tmp_path):
    """Also test a real link on platforms/accounts that permit creating one."""
    (tmp_path / 'main.py').write_text('print("ok")')
    link = tmp_path / 'escape.py'
    try:
        link.symlink_to(tmp_path / 'main.py')
    except OSError as exc:
        if os.name == 'nt' and getattr(exc, 'winerror', None) == 1314:
            pytest.skip('Windows account lacks symlink creation privilege; simulated guard is tested separately')
        raise
    data, _, paths = safe_tree(tmp_path)
    assert paths == ['main.py']
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


def test_existing_app_upload_skips_project_creation(monkeypatch):
    from sentinel import deployer
    import httpx
    calls = []
    def handler(request):
        calls.append((request.method,request.url.path))
        if request.method == 'GET' and request.url.path.endswith('/v1/projects/sandbox'):
            return httpx.Response(200,json={'project':{
                'project_id':'sandbox','type':'python','isDeployed':False}})
        if request.method == 'POST' and request.url.path.endswith('/v2/projects/sandbox/sources'):
            return httpx.Response(200,json={'sourceID':'source-one'})
        if request.method == 'POST' and request.url.path.endswith('/v2/projects/sandbox/releases'):
            return httpx.Response(200,json={'releaseID':'release-one'})
        return httpx.Response(409,json={'error':'unexpected request'})
    transport=httpx.MockTransport(handler)
    class Fake:
        def __enter__(self):
            from sentinel.liara import LiaraClient
            self.client=LiaraClient(token='fake',transport=transport)
            return self.client
        def __exit__(self,*args): self.client.close()
    monkeypatch.setattr(deployer,'LiaraClient',Fake)
    result=deployer.perform_deploy('sandbox','existing','python',8000,b'test-tar-data')
    assert result['execution']=='SUBMITTED'
    assert result['verification']=='NOT_VERIFIED'
    assert not any(method=='POST' and path=='/v1/projects' for method,path in calls)
    assert ('POST','/v2/projects/sandbox/releases') in calls


def test_existing_app_wrong_platform_blocks_upload(monkeypatch):
    from sentinel import deployer
    import httpx
    calls=[]
    def handler(request):
        calls.append((request.method,request.url.path))
        return httpx.Response(200,json={'project':{
            'project_id':'sandbox','type':'node','isDeployed':False}})
    transport=httpx.MockTransport(handler)
    class Fake:
        def __enter__(self):
            from sentinel.liara import LiaraClient
            self.client=LiaraClient(token='fake',transport=transport)
            return self.client
        def __exit__(self,*args): self.client.close()
    monkeypatch.setattr(deployer,'LiaraClient',Fake)
    with pytest.raises(DeployError):
        deployer.perform_deploy('sandbox','existing','python',8000,b'test')
    assert calls==[('GET','/v1/projects/sandbox')]

def test_case_only_platform_difference_accepted(monkeypatch):
    from sentinel import deployer
    import httpx
    calls=[]
    def handler(request):
        calls.append((request.method,request.url.path))
        if request.method=='GET':
            return httpx.Response(200,json={'project':{
                'project_id':'sandbox','type':'Python','isDeployed':False}})
        if request.url.path.endswith('/sources'):
            return httpx.Response(200,json={'sourceID':'source'})
        if request.url.path.endswith('/releases'):
            return httpx.Response(200,json={'releaseID':'release'})
        return httpx.Response(409)
    transport=httpx.MockTransport(handler)
    class Fake:
        def __enter__(self):
            from sentinel.liara import LiaraClient
            self.client=LiaraClient(token='fake',transport=transport)
            return self.client
        def __exit__(self,*args): self.client.close()
    monkeypatch.setattr(deployer,'LiaraClient',Fake)
    result=deployer.perform_deploy('sandbox','existing','python',8000,b'archive')
    assert result['execution']=='SUBMITTED'
    assert not any(m=='POST' and p=='/v1/projects' for m,p in calls)


def test_actual_platform_mismatch_explained_and_blocks_write(monkeypatch):
    from sentinel import deployer
    import httpx
    calls=[]
    def handler(request):
        calls.append((request.method,request.url.path))
        return httpx.Response(200,json={'project':{
            'project_id':'sandbox','type':'node','isDeployed':False}})
    transport=httpx.MockTransport(handler)
    class Fake:
        def __enter__(self):
            from sentinel.liara import LiaraClient
            self.client=LiaraClient(token='fake',transport=transport)
            return self.client
        def __exit__(self,*args): self.client.close()
    monkeypatch.setattr(deployer,'LiaraClient',Fake)
    with pytest.raises(DeployError,match='node') as exc:
        deployer.perform_deploy('sandbox','existing','python',8000,b'archive')
    assert 'python' in str(exc.value)
    assert calls==[('GET','/v1/projects/sandbox')]


def test_missing_platform_metadata_blocks_write():
    from sentinel.deployer import verify_existing_platform
    class Fake:
        def get_project(self,name): return {'project_id':name}
    with pytest.raises(DeployError,match='نامشخص'):
        verify_existing_platform(Fake(),'sandbox','python')
