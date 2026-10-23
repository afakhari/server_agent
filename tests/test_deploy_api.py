from fastapi.testclient import TestClient
from app import app


def test_deploy_denied_without_live_credentials():
    client=TestClient(app)
    response=client.post('/api/deploy/plan', json={'project':'test-project','path':'sample','plan_id':'plan-x','platform':'python','port':8000})
    assert response.status_code==403
    response=client.post('/api/deploy/execute', json={'proposal_id':'a'*30,'confirm_project':'test-project'})
    assert response.status_code==403


def test_no_deploy_button_executes_without_preview():
    html=TestClient(app).get('/').text
    assert 'پیش‌نمایش انتشار' in html
    assert 'confirmDeploy' in html
