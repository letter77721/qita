import time
from fastapi.testclient import TestClient
from backend import main as api
from database.storage import Store


def test_login_restores_cookie_session_and_logout(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'store',Store(tmp_path/'db'))
    monkeypatch.setenv('NOTEPILOT_TOKEN','test-secret')
    with TestClient(api.app,base_url='https://testserver') as c:
        assert c.get('/api/auth/session').json()=={'signed_in':False}
        assert c.post('/api/auth/login',json={'token':'错误口令'}).status_code==401
        r=c.post('/api/auth/login',json={'token':'test-secret'})
        assert r.status_code==200
        cookie=r.headers['set-cookie'].lower()
        assert 'httponly' in cookie and 'secure' in cookie and 'samesite=strict' in cookie
        assert 'test-secret' not in cookie
        assert c.get('/api/auth/session').json()['signed_in']
        assert c.get('/api/workspace').status_code==200
        c.post('/api/auth/logout')
        assert not c.get('/api/auth/session').json()['signed_in']
        assert c.get('/api/workspace').status_code==401
        c.cookies.set('np_session','9999999999.forged')
        assert c.get('/api/workspace').status_code==401


def test_pdf_upload_after_login_preserves_all_pages(tmp_path,monkeypatch):
    import fitz
    monkeypatch.setattr(api,'store',Store(tmp_path/'db'))
    monkeypatch.setattr(api,'ROOT',tmp_path)
    monkeypatch.setenv('NOTEPILOT_TOKEN','test-secret')
    with fitz.open() as pdf:
        pdf.new_page().insert_text((72,72),'Reynolds Re=rho*v*L/mu')
        pdf.new_page().insert_text((72,72),'Bernoulli equation')
        data=pdf.tobytes()
    with TestClient(api.app,base_url='https://testserver') as c:
        c.post('/api/auth/login',json={'token':'test-secret'})
        r=c.post('/api/documents',files={'file':('lecture.pdf',data,'application/pdf')},data={'kind':'课程课件'})
        assert r.status_code==202
        id=r.json()['document_id']
        for _ in range(100):
            ws=c.get('/api/workspace').json()
            if ws['jobs'][0]['status'] in ('completed','failed'): break
            time.sleep(.02)
        assert ws['jobs'][0]['status']=='completed'
        assert ws['documents'][0]['page_count']==2
        assert 'Bernoulli' in c.get(f'/api/documents/{id}/pages/2').json()['text']
