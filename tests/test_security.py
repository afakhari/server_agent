from sentinel.health import verified_url_for, verify_http
from sentinel.security import actor_digest, authorized


def test_health_default_unknown(monkeypatch):
    monkeypatch.delenv('SENTINEL_HEALTH_URLS', raising=False)
    assert verify_http('project')['status'] == 'INCONCLUSIVE'


def test_health_rejects_private_and_insecure(monkeypatch):
    for url in ['http://example.com/', 'https://localhost/health', 'https://127.0.0.1/', 'https://user@example.com/', 'https://example.com:8080/']:
        monkeypatch.setenv('SENTINEL_HEALTH_URLS', '{"demo":"' + url + '"}')
        assert verified_url_for('demo') is None


def test_access_key_required_for_live(monkeypatch):
    monkeypatch.delenv('SENTINEL_ACCESS_KEY', raising=False)
    assert not authorized('any')
    try:
        actor_digest(None, 'live')
        assert False
    except PermissionError:
        pass


def test_live_approval_actor_is_team_bound(monkeypatch):
    monkeypatch.setenv('SENTINEL_ACCESS_KEY', 'a-long-operator-access-key-over-24-chars')
    monkeypatch.delenv('LIARA_TEAM_ID', raising=False)
    personal=actor_digest('a-long-operator-access-key-over-24-chars','live')
    monkeypatch.setenv('LIARA_TEAM_ID', '0123456789abcdef01234567')
    team=actor_digest('a-long-operator-access-key-over-24-chars','live')
    assert team != personal
    monkeypatch.delenv('LIARA_TEAM_ID', raising=False)
    assert actor_digest('a-long-operator-access-key-over-24-chars','live') == personal
