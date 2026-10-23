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
