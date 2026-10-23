"""Checks that visitors can use the simulated demo without a credential."""

from fastapi.testclient import TestClient
import app


def test_anonymous_demo_with_server_key(monkeypatch, tmp_path):
    monkeypatch.setenv('SENTINEL_EXPOSURE_MODE', 'local')
    monkeypatch.setenv('SENTINEL_ACCESS_KEY', 'a' * 40)
    monkeypatch.setenv('SENTINEL_DB_PATH', str(tmp_path / 'guest.sqlite3'))
    with TestClient(app.app) as guest:
        response = guest.post('/api/inspect', json={'mode': 'demo', 'scenario': 'transient'})
        assert response.status_code == 200, response.text
        assert guest.cookies.get('sentinel_demo_session')
        proposal = response.json()['proposals'][0]['proposal_id']
        assert guest.post('/api/approve', json={'proposal_id': proposal, 'confirm_project': 'demo-shop'}).status_code == 200
        assert guest.post('/api/inspect', json={'mode': 'live', 'project': 'example'}).status_code == 403
        chat = guest.post('/api/chat/messages', json={'mode': 'demo', 'message': 'سایتم خطای ۵۰۰ دارد'})
        assert chat.status_code == 200, chat.text
        thread_id = chat.json()['thread_id']
        assert guest.get('/api/chat/threads/' + thread_id).status_code == 200
        assert guest.get('/api/audit').json()['events'] == []
        with TestClient(app.app) as other:
            assert other.post('/api/approve', json={'proposal_id': proposal, 'confirm_project': 'demo-shop'}).status_code != 200
            assert other.get('/api/chat/threads/' + thread_id).status_code == 403
            assert other.post('/api/chat/messages', json={
                'mode': 'demo', 'thread_id': thread_id, 'message': 'سلام'
            }).status_code == 403
