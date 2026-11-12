from fastapi.testclient import TestClient
from backend import main as api
from database.storage import Store

def test_demo_is_public_and_private_data_stays_protected(tmp_path,monkeypatch):
    db=Store(tmp_path/'test.db')
    monkeypatch.setattr(api,'store',db)
    monkeypatch.setenv('NOTEPILOT_TOKEN','private-test')
    db.add('secret','private-note.txt','私人笔记','/private', [{'number':1,'text':'私人内容','status':'verified'}])
    with TestClient(api.app) as client:
        response=client.get('/api/demo/workspace')
        assert response.status_code==200
        ws=response.json()
        assert ws['demo'] and len(ws['documents'])==2 and ws['issues']
        assert 'private-note' not in response.text and '私人内容' not in response.text
        assert client.get('/api/workspace').status_code==401
        assert client.get('/api/demo/documents/secret/pages/1').status_code==404
        assert client.post('/api/demo/documents',files={'file':('a.txt',b'x')}).status_code in (404,405)
        assert client.get('/api/demo/search?q=伯努利').json()
        q=client.get('/api/demo/coach?depth=2').json()
        assert q['depth']==2 and '合成资料' in q['mode']
        assert client.get('/api/demo/documents/demo-slides/pages/1').status_code==200
