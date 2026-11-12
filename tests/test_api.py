import time
import pytest
from fastapi.testclient import TestClient
from database.storage import Store
from backend import main as api

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'store',Store(tmp_path/'test.db'))
    monkeypatch.setattr(api,'ROOT',tmp_path)
    monkeypatch.delenv('NOTEPILOT_TOKEN',raising=False)
    with TestClient(api.app) as c: yield c

def upload(client,text,name='notes.txt'):
    r=client.post('/api/documents',files={'file':(name,text.encode(),'text/plain')})
    assert r.status_code==202,r.text
    id=r.json()['document_id']
    for _ in range(150):
        ws=client.get('/api/workspace').json()
        job=next(j for j in ws['jobs'] if j['id']==r.json()['job_id'])
        if job['status'] in ('completed','failed'): break
        time.sleep(.02)
    assert job['status']=='completed',job
    return id

def test_upload_evidence_review_coach(client):
    a=upload(client,'伯努利方程沿流线。')
    upload(client,'伯努利方程稳态、无黏条件下沿流线。','slides.txt')
    issue=client.get('/api/workspace').json()['issues'][0]
    assert issue['issue_type']=='missing_condition'
    assert 'path' not in issue['source_a']
    assert issue['source_a']['number']==1
    assert client.post('/api/issues/'+issue['id']+'/review',json={'decision':'确认需补充'}).status_code==200
    question=client.get('/api/coach').json()
    assert question['answer']=='伯努利方程稳态、无黏条件下沿流线。'
    for _ in range(2):
        question=client.get('/api/coach').json()
        assert client.post('/api/coach/feedback',json={'course_id':'fluid','concept':question['concept'],'question_id':question['id'],'answer':'稳态、无黏','rating':'remembered'}).status_code==200
    assert client.get('/api/coach').json()['depth']==2
    assert client.get('/api/workspace').json()['attempt_count']==2
    assert client.get(f'/api/documents/{a}/pages/1').json()['original']=='伯努利方程沿流线。'
    assert client.put(f'/api/documents/{a}/pages/1',json={'text':'伯努利方程稳态、无黏条件下沿流线。'}).status_code==200
    assert not client.get('/api/workspace').json()['issues']
    assert client.get('/api/search',params={'q':'伯努利'}).json()
    assert client.delete('/api/documents/'+a).status_code==200
    assert client.get(f'/api/documents/{a}/pages/1').status_code==404

def test_course_isolation_exam_and_auth(client,monkeypatch):
    upload(client,'雷诺数 Re=ρvL/μ')
    course=client.post('/api/courses',json={'name':'理论力学'}).json()['id']
    ws=client.get('/api/workspace',params={'course_id':course}).json()
    assert not ws['documents'] and not ws['concepts']
    assert client.put('/api/courses/fluid',json={'name':'流体力学','exam_date':'2026-11-27'}).status_code==200
    assert client.put('/api/courses/fluid',json={'name':'流体力学','exam_date':'oops'}).status_code==422
    monkeypatch.setenv('NOTEPILOT_TOKEN','secret')
    assert client.get('/api/workspace').status_code==401
    assert client.get('/api/workspace',headers={'Authorization':'Bearer secret'}).status_code==200

def test_reject_invalid_upload(client):
    assert client.post('/api/documents',files={'file':('run.exe',b'x')}).status_code==400
    assert client.post('/api/documents',data={'course_id':'missing'},files={'file':('a.txt',b'x')}).status_code==404

def test_upload_uses_persistent_disk(client,tmp_path,monkeypatch):
    disk=tmp_path/'persistent'
    monkeypatch.setenv('NOTEPILOT_DATA_DIR',str(disk))
    id=upload(client,'雷诺数 Re=ρvL/μ')
    record=api.store.rows('SELECT path FROM documents WHERE id=?',(id,))[0]
    from pathlib import Path
    path=Path(record['path'])
    assert path.parent==disk/'uploads' and path.exists()
    assert client.delete('/api/documents/'+id).status_code==200
    assert not path.exists()
