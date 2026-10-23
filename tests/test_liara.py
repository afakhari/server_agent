import httpx
import pytest
from sentinel.liara import LiaraClient, LiaraError, validate_name


def test_name_validation_rejects_path_injection():
    for name in ['../../etc/passwd', 'demo?x=1', '/v1/projects', 'name with spaces']:
        with pytest.raises(LiaraError):
            validate_name(name)


def test_adapter_uses_official_endpoints_and_strips_env_values():
    requests = []
    def handler(request):
        requests.append((request.method, request.url.path, dict(request.url.params)))
        assert request.headers['Authorization'] == 'Bearer fake-test-token'
        if request.url.path.endswith('/releases'):
            return httpx.Response(200, json={'currentRelease': 'v1', 'releases': []})
        if request.url.path.endswith('/logs'):
            return httpx.Response(200, json=[{'message': 'GET /health 200'}])
        if request.url.path.endswith('/events'):
            return httpx.Response(200, json={'data': []})
        if request.url.path.endswith('/metrics/summary'):
            return httpx.Response(200, json={'cpuUsage': [], 'memoryUsage': []})
        return httpx.Response(200, json={'project': {'status': 'running', 'envs': [{'key': 'API', 'value': 'LEAK'}]}})
    with LiaraClient(token='fake-test-token', transport=httpx.MockTransport(handler)) as client:
        result = client.snapshot('demo-shop')
    assert result['mode'] == 'live'
    assert 'envs' not in result['project']
    assert result['derived_metrics'] == {}
    assert len(requests) == 5
    assert any(x[2].get('since') for x in requests if x[1].endswith('/logs'))
    assert any(x[2].get('page') == '1' for x in requests if x[1].endswith('/releases'))


def test_partial_api_failure_is_reported():
    def handler(request):
        if request.url.path.endswith('/logs'):
            return httpx.Response(503)
        if request.url.path.endswith('/events'):
            return httpx.Response(429)
        if request.url.path.endswith('/releases'):
            return httpx.Response(200, json={'releases': []})
        if request.url.path.endswith('/metrics/summary'):
            return httpx.Response(200, json={})
        return httpx.Response(200, json={'project': {'status': 'running'}})
    with LiaraClient(token='fake', transport=httpx.MockTransport(handler)) as client:
        result = client.snapshot('demo-shop')
    assert len(result['limitations']) == 2


def test_malformed_response_rejected():
    with LiaraClient(token='fake', transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'wrong': []}))) as c:
        with pytest.raises(LiaraError):
            c.list_projects()


def test_domain_read_is_redacted_and_scoped():
    import httpx
    from sentinel.liara import LiaraClient
    def handler(request):
        assert request.url.params.get('project') == 'test-shop'
        return httpx.Response(200, json={'domains':[{
            '_id':'abc12345678', 'name':'shop.example.com',
            'status':'active', 'certificatesStatus':'ready',
            'CNameRecord':'target.example.com', 'verificationCode':'PRIVATE'
        }]})
    with LiaraClient(token='example', transport=httpx.MockTransport(handler)) as client:
        result=client.domains('test-shop')
    assert result['domains'][0]['name']=='shop.example.com'
    assert 'PRIVATE' not in repr(result)

def test_missing_project_shows_which_endpoint_failed_without_secrets():
    def handler(request):
        return httpx.Response(404, text='private-response-should-not-leak')
    with LiaraClient(token='TOKEN_SHOULD_NOT_LEAK', transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LiaraError) as exc:
            client.get_project('wrong-project')
    detail=str(exc.value)
    assert 'Liara HTTP 404' in detail
    assert 'GET /v1/projects/wrong-project' in detail
    assert 'TOKEN_SHOULD_NOT_LEAK' not in detail
    assert 'private-response-should-not-leak' not in detail


def test_list_projects_returns_valid_project_id_names():
    with LiaraClient(token='fake', transport=httpx.MockTransport(
        lambda request: httpx.Response(200,json={'projects':[{
            'project_id':'real-test-app','_id':'internal-id','envs':[{'value':'SECRET'}]
        }]}))) as client:
        result=client.list_projects()
    assert result['projects'][0]['project_id']=='real-test-app'
    assert 'SECRET' not in repr(result)


def test_team_context_applies_to_all_reads_with_other_params(monkeypatch):
    from sentinel.liara import LiaraClient
    import httpx
    urls = []
    def handler(request):
        urls.append(request.url)
        if request.url.path.endswith('/logs'):
            return httpx.Response(200, json=[])
        if request.url.path.endswith('/releases'):
            return httpx.Response(200, json={'releases': []})
        return httpx.Response(200, json={'projects': []})
    monkeypatch.setenv('LIARA_TEAM_ID', '0123456789abcdef01234567')
    with LiaraClient(token='fake', transport=httpx.MockTransport(handler)) as client:
        client.list_projects()
        client.logs('example')
        client.releases('example')
    assert all(u.params.get('teamID') == '0123456789abcdef01234567' for u in urls)
    assert urls[1].params.get('since')
    assert urls[2].params.get('count') == '10'


def test_team_scope_persists_into_direct_multipart_upload(monkeypatch):
    from sentinel.liara import LiaraClient
    import httpx
    calls = []
    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, json={'sourceID': 'example'})
    monkeypatch.setenv('LIARA_TEAM_ID', '0123456789abcdef01234567')
    with LiaraClient(token='fake', transport=httpx.MockTransport(handler)) as client:
        response=client.http.post('/v2/projects/example/sources',
                                  files={'file': ('source.tar.gz', b'test')})
    assert response.status_code == 200
    assert calls[0].params.get('teamID') == '0123456789abcdef01234567'


def test_personal_team_scope_absent_and_input_validation(monkeypatch):
    from sentinel.liara import LiaraClient, LiaraError
    import httpx
    monkeypatch.delenv('LIARA_TEAM_ID', raising=False)
    calls = []
    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, json={'projects': []})
    with LiaraClient(token='fake', transport=httpx.MockTransport(handler)) as client:
        client.list_projects()
    assert 'teamID' not in calls[0].params
    with pytest.raises(LiaraError):
        LiaraClient(token='fake', team_id='../unsafe')
