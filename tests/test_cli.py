"""Focused optional CLI transport checks: local only, no Liara network."""
from pathlib import Path
import os
import pytest
from sentinel import cli
from sentinel.deployer import DeployError


def configure_cli(monkeypatch, tmp_path):
    executable = tmp_path / 'liara'
    executable.write_text('#!/bin/sh\necho "@liara/cli/9.6.0"\n')
    executable.chmod(0o755)
    home = tmp_path / 'private-home'
    home.mkdir(mode=0o700)
    monkeypatch.setenv('SENTINEL_CLI_DEPLOY_ENABLED', 'true')
    monkeypatch.setenv('SENTINEL_CLI_BIN', str(executable))
    monkeypatch.setenv('SENTINEL_CLI_ACCOUNT', 'demo-account')
    monkeypatch.setenv('SENTINEL_CLI_HOME', str(home))
    return home


def test_default_deny(monkeypatch):
    monkeypatch.delenv('SENTINEL_CLI_DEPLOY_ENABLED', raising=False)
    with pytest.raises(DeployError):
        cli.cli_settings()


def test_no_api_token_passed_to_subprocess(monkeypatch, tmp_path):
    home = configure_cli(monkeypatch, tmp_path)
    monkeypatch.setenv('LIARA_API_TOKEN', 'SENSITIVE_HTTP_TOKEN')
    # Verify the subprocess boundary without executing a POSIX shell script
    # on Windows. The test is about environment/argument isolation.
    seen = {}
    def capture(argv, **kwargs):
        seen['argv'] = argv
        seen['env'] = kwargs['env']
        seen['shell'] = kwargs['shell']
        seen['stdin'] = kwargs['stdin']
        return cli.subprocess.CompletedProcess(
            argv, returncode=0, stdout='@liara/cli/9.6.0\\n', stderr=''
        )
    monkeypatch.setattr(cli.subprocess, 'run', capture)
    result = cli.invoke(['--version'], timeout=4)
    assert result.returncode == 0
    assert result.stdout.strip() == '@liara/cli/9.6.0'
    assert seen['argv'] == [str(tmp_path / 'liara'), '--version']
    assert seen['stdin'] == cli.subprocess.DEVNULL
    assert seen['env']['HOME'] == str(home)
    assert 'LIARA_API_TOKEN' not in seen['env']
    assert 'SENSITIVE_HTTP_TOKEN' not in str(seen['argv'])
    assert seen['shell'] is False


@pytest.mark.skipif(os.name != 'posix', reason='Fixture is a POSIX /bin/sh script')
def test_posix_cli_stub_can_be_launched_without_shell(monkeypatch, tmp_path):
    configure_cli(monkeypatch, tmp_path)
    result = cli.invoke(['--version'], timeout=4)
    assert result.returncode == 0
    assert result.stdout.strip() == '@liara/cli/9.6.0'


def test_cli_approval_binds_project_and_content(monkeypatch, tmp_path):
    configure_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, 'preflight', lambda: {'account':'demo-account','email':'demo@example.com','version':'@liara/cli/9.6.0'})
    workspace = tmp_path / 'workspace'
    root = workspace / 'sample'
    root.mkdir(parents=True)
    (root / 'requirements.txt').write_text('fastapi')
    (root / 'main.py').write_text('print("ok")')
    (root / 'liara.json').write_text('{"port":8000}')
    monkeypatch.setenv('SENTINEL_WORKSPACE', str(workspace))
    monkeypatch.setenv('SENTINEL_DB_PATH', str(tmp_path / 'approvals.db'))
    monkeypatch.setattr(cli, '_ensure_existing_test_app', lambda name: None)
    plan = cli.make_cli_plan('actor', 'testing', 'sample', 'python', 8000)
    assert plan['backend'] == 'cli'
    assert plan['pricing_status'] == 'NOT_VERIFIED'
    with pytest.raises(DeployError):
        cli.claim_cli_plan('actor', plan['proposal_id'], 'other')
    (root / 'main.py').write_text('print("changed")')
    with pytest.raises(DeployError):
        cli.claim_cli_plan('actor', plan['proposal_id'], 'testing')
    (root / 'main.py').write_text('print("ok")')
    assert cli.claim_cli_plan('actor', plan['proposal_id'], 'testing')[0] == 'testing'
    with pytest.raises(DeployError):
        cli.claim_cli_plan('actor', plan['proposal_id'], 'testing')


def test_cli_staging_excludes_env_file(monkeypatch, tmp_path):
    configure_cli(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, '_ensure_existing_test_app', lambda name: None)
    from sentinel.deployer import safe_tree
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'main.py').write_text('print("ok")')
    (source / '.env').write_text('PASSWORD=leak')
    archive, _, _ = safe_tree(source)
    seen = {}
    def capture(args, *, timeout, cwd=None):
        seen['args'] = args
        seen['cwd'] = cwd
        seen['main'] = (Path(cwd) / 'main.py').exists()
        seen['secret'] = (Path(cwd) / '.env').exists()
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(cli, 'invoke', capture)
    response = cli.perform_cli_deploy('testing', 'python', 8000, archive)
    assert response['verification'] == 'NOT_VERIFIED'
    assert seen['main'] is True and seen['secret'] is False
    assert '--api-token' not in seen['args']
    assert '--detach' in seen['args']
    assert not Path(seen['cwd']).exists()
