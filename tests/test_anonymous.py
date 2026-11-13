import time
from fastapi.testclient import TestClient
from backend import main as api
from backend.anonymous import ScopedStore
from database.storage import Store

def test_anonymous_browser_isolation_upload_and_private_guard(tmp_path,monkeypatch):
    monkeypatch.setenv('NOTEPILOT_DATA_DIR',str(tmp_path))
    owner=Store(tmp_path/'owner.db');monkeypatch.setattr(api,'store',ScopedStore(owner))
    monkeypatch.setenv('NOTEPILOT_TOKEN','owner-secret')
    with TestClient(api.app) as a, TestClient(api.app) as b:
        assert a.get('/api/open/lite/dashboard').status_code==200
        assert b.get('/api/open/lite/dashboard').status_code==200
        goal=a.post('/api/open/lite/goals',json={'concept':'私人知识点','target':'理解','source':'材料'}).json()['id']
        assert len(a.get('/api/open/lite/dashboard').json()['tasks'])==1
        assert not b.get('/api/open/lite/dashboard').json()['tasks']
        assert b.post('/api/open/lite/questions',json={'goal_id':goal}).status_code==404
        assert a.get('/api/lite/dashboard').status_code==401
        assert a.post('/api/open/auth/login',json={'token':'owner-secret'}).status_code==404
        assert a.post('/api/open/lite/model-check',json={}).status_code==404
        upload=a.post('/api/open/documents',files={'file':('note.txt',b'textbook source','text/plain')}).json()
        for _ in range(100):
            ws=a.get('/api/open/workspace').json()
            if ws['jobs'][0]['status'] in ('completed','failed'):break
            time.sleep(.03)
        assert ws['jobs'][0]['status']=='completed'
        id=upload['document_id']
        assert a.get('/api/open/documents/'+id+'/pages/1').status_code==200
        assert b.get('/api/open/documents/'+id+'/pages/1').status_code==404
        assert not owner.documents()
        cookie=a.cookies.get('np_guest');a.cookies.clear();a.cookies.set('np_guest',cookie)
        assert len(a.get('/api/open/lite/dashboard').json()['tasks'])==1
