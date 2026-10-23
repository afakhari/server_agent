"""Focused mock checks of CLI account identity and source boundary; no network."""
import json
from types import SimpleNamespace
import pytest
from sentinel import cli
from sentinel.deployer import DeployError, safe_tree

def fake_invoke(args, **kwargs):
    if args == ['--version']:
        return SimpleNamespace(returncode=0,stdout='@liara/cli/9.6.0 linux-x64 node-v24')
    return SimpleNamespace(returncode=0,stdout=json.dumps({
        'account':{'name':'sandbox-alias','email':'sandbox@example.com'}, 'team':None}))

def test_strict_cli_account_identity(monkeypatch,tmp_path):
    monkeypatch.setattr(cli,'cli_settings',lambda:('/opt/liara','sandbox-alias',tmp_path))
    monkeypatch.setattr(cli,'invoke',fake_invoke)
    assert cli.preflight()['email']=='sandbox@example.com'
    monkeypatch.setattr(cli,'cli_settings',lambda:('/opt/liara','wrong-alias',tmp_path))
    with pytest.raises(DeployError): cli.preflight()

def test_cli_rejects_team_auth(monkeypatch,tmp_path):
    monkeypatch.setattr(cli,'cli_settings',lambda:('/opt/liara','sandbox-alias',tmp_path))
    def with_team(args,**kwargs):
        result=fake_invoke(args,**kwargs)
        if '--json' in args:
            result.stdout=json.dumps({'account':{'name':'sandbox-alias','email':'sandbox@example.com'},
                                      'team':{'id':'not-allowed'}})
        return result
    monkeypatch.setattr(cli,'invoke',with_team)
    with pytest.raises(DeployError): cli.preflight()

def test_source_cannot_override_cli_team(tmp_path):
    root=tmp_path/'sample'
    root.mkdir()
    (root/'main.py').write_text('print("ok")')
    (root/'liara.json').write_text('{"port":8000,"team-id":"override"}')
    # The packager rejects a source-controlled account/team override before
    # it ever reaches the CLI validation layer.
    with pytest.raises(DeployError): safe_tree(root)
    (root/'liara.json').write_text('{"platform":"python","port":8000}')
    archive,_,_=safe_tree(root)
    cli.validate_cli_archive(archive)

def test_api_identity_must_match_cli_identity(monkeypatch):
    monkeypatch.setattr(cli,'preflight',lambda:{'email':'cli@example.com'})
    class Fake:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def request(self,method,path): return {'user':{'email':'different@example.com'}}
        def get_project(self,name): return {'project_id':'sandbox'}
    monkeypatch.setattr(cli,'LiaraClient',Fake)
    with pytest.raises(DeployError): cli._ensure_existing_test_app('sandbox')

def test_launcher_safe_modes():
    from scripts.run_local import choices
    assert choices('demo',None)==(False,False)
    assert choices('read',None)==(True,False)
    with pytest.raises(ValueError): choices('test-cli',None)
    with pytest.raises(ValueError): choices('test-api','../bad')

def test_direct_script_imports_repo_package(monkeypatch):
    # The Windows CMD form calls the script directly rather than with -m.
    import os
    import subprocess
    import sys
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([
        sys.executable, str(root/'scripts'/'run_local.py'), '--mode', 'read',
        '--team-id', 'TEAM_ID', '--project', 'sentinel-sandbox-01',
    ],cwd=root,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
    assert result.returncode == 2
    output=result.stderr+result.stdout
    assert 'No module named' not in output
    assert 'TEAM_ID' in output
