from sentinel.engine import diagnose,mock_snapshot,redact

def test_transient_proposes_restart():
    r=diagnose(mock_snapshot('transient'))
    assert r['hypotheses'][0]['code']=='transient'
    assert r['proposals'][0]['requires_approval'] is True

def test_env_error_does_not_restart():
    r=diagnose(mock_snapshot('env'))
    assert r['hypotheses'][0]['code']=='missing_config'
    assert not r['proposals']

def test_oom_does_not_restart_blindly():
    r=diagnose(mock_snapshot('memory'))
    assert r['hypotheses'][0]['code']=='oom'
    assert not r['proposals']

def test_uncertainty_is_explicit():
    r=diagnose(mock_snapshot('healthy'))
    assert r['hypotheses'][0]['confidence']=='نامشخص'

def test_secret_redaction():
    text='Authorization: bearer abcdefghijklmnop password=123456 TOKEN=foobarABC'
    assert 'abcdefghijklmnop' not in redact(text)
    assert '123456' not in redact(text)
    assert 'foobarABC' not in redact(text)


def test_scout_example():
    from pathlib import Path
    from sentinel.scout import inspect_repo
    x=inspect_repo(Path(__file__).resolve().parents[1]/'examples/fastapi-shop')
    assert x['framework']=='FastAPI'
    assert x['port']==8000
    assert 'DATABASE_URL' in x['required_env_names']
    assert x['can_deploy_automatically'] is False


def test_scout_rejects_no_manifests(tmp_path):
    from sentinel.scout import inspect_repo
    import pytest
    with pytest.raises(ValueError):inspect_repo(tmp_path)


def test_old_crash_log_on_running_app_does_not_trigger_restart():
    sample=mock_snapshot('transient')
    sample['project']['status']='running'
    out=diagnose(sample)
    assert not out['proposals']

def test_live_release_timing_builds_only_low_confidence_correlation():
    snap=mock_snapshot('healthy')
    snap['suspected_recent_change']=False
    snap['logs']=[{'datetime':'2026-10-23T12:05:00Z','message':'HTTP 500 internal server error'}]
    snap['releases']['releases'][0]['createdAt']='2026-10-23T12:00:00Z'
    result=diagnose(snap)
    correlations=[h for h in result['hypotheses'] if h['code']=='release_correlation']
    assert len(correlations)==1
    assert correlations[0]['confidence']=='پایین'
    assert correlations[0]['evidence_ids']

def test_no_temporal_correlation_without_error_log():
    snap=mock_snapshot('healthy')
    snap['suspected_recent_change']=False
    snap['logs']=[{'datetime':'2026-10-23T12:05:00Z','message':'GET /health 200 OK'}]
    snap['releases']['releases'][0]['createdAt']='2026-10-23T12:00:00Z'
    result=diagnose(snap)
    assert not any(h['code']=='release_correlation' for h in result['hypotheses'])
