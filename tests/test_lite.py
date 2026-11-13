import json
import pytest
from fastapi.testclient import TestClient
from backend import main as api
from backend.lite import schedule
from database.storage import Store
from services import text_model as llm

@pytest.fixture
def client(tmp_path,monkeypatch):
    s=Store(tmp_path/'db');s.add('old','old.txt','课堂笔记','old.txt',[{'number':1,'text':'old data','status':'verified'}])
    monkeypatch.setattr(api,'store',s);monkeypatch.delenv('NOTEPILOT_TOKEN',raising=False)
    with TestClient(api.app) as c:yield c

def test_lite_closed_loop_and_retains_old_data(client,monkeypatch):
    def fake(schema,task,context):
        if schema is llm.Question:return llm.Question(question='条件是什么？',hint='考虑黏性',reference='无黏',evidence='无黏',needs_verification=False)
        return llm.Evaluation(verdict='incorrect',error_type='condition',explanation='遗漏条件',follow_up='损失如何处理？',evidence='无黏',needs_verification=False)
    monkeypatch.setattr(llm,'generate',fake)
    g=client.post('/api/lite/goals',json={'concept':'伯努利','target':'理解条件','source':'无黏','course_id':'fluid'}).json()['id']
    q=client.post('/api/lite/questions',json={'goal_id':g}).json()
    assert 'reference' not in q
    a=client.post('/api/lite/questions/'+q['id']+'/answer',json={'answer':'不知道'}).json()
    assert a['evaluation']['verdict']=='incorrect'
    again=client.post('/api/lite/questions/'+q['id']+'/answer',json={'answer':'重复'}).json()
    assert again['id']==a['id']
    mid=client.post('/api/lite/answers/'+a['id']+'/mistake').json()['id']
    assert client.post('/api/lite/answers/'+a['id']+'/follow-up').status_code==200
    d=client.get('/api/lite/dashboard').json()
    assert d['attempt_count']==1 and len(d['mistakes'])==1 and d['tasks'][0]['interval_days']==0
    assert api.store.pages()[0]['text']=='old data'
    assert client.put('/api/lite/mistakes/'+mid,json={'concept':'伯努利','question':'条件','answer':'无黏','source':'无黏'}).status_code==200
    assert client.post('/api/lite/mistakes/'+mid+'/analyze').status_code==200
    assert client.delete('/api/lite/mistakes/'+mid).status_code==200
    assert not client.get('/api/lite/dashboard').json()['mistakes']

def test_auth_protects_all_lite_routes(client,monkeypatch):
    monkeypatch.setenv('NOTEPILOT_TOKEN','secret')
    assert client.get('/api/lite/dashboard').status_code==401
    assert client.post('/api/lite/goals',json={'concept':'x','target':'y'}).status_code==401

def test_rule_requires_history_and_uncertainty_cannot_advance():
    g={'id':'g'}
    def history(n,uncertain=False):return [{'created':'2026-11-13 00:00:00','evaluation':json.dumps({'verdict':'correct','needs_verification':uncertain})} for _ in range(n)]
    assert schedule(g,history(1))['interval_days']==1
    assert schedule(g,history(3))['interval_days']==3
    assert schedule(g,history(5,True))['interval_days']==0

def test_structured_evidence_guard(monkeypatch):
    from io import BytesIO
    monkeypatch.setenv('TEXT_API_KEY','fake')
    payload={'verdict':'correct','error_type':'none','explanation':'正确','follow_up':'继续？','evidence':'编造原文','needs_verification':False}
    monkeypatch.setattr(llm.urllib.request,'urlopen',lambda *a,**k:BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(payload)}}]}).encode()))
    result=llm.generate(llm.Evaluation,'test',{'source':'真实原文'})
    assert result.verdict=='uncertain' and result.needs_verification
    payload['unexpected']='extra'
    with pytest.raises(llm.ModelError):llm.generate(llm.Evaluation,'test',{'source':'真实原文'})

def test_goal_reads_selected_document_and_preserves_snapshot(client,monkeypatch):
    api.store.add('material','教材.txt','课件','material.txt',[{'number':1,'text':'稳态、不可压、无黏','status':'extracted'}])
    g=client.post('/api/lite/goals',json={'concept':'伯努利','target':'掌握公式与适用条件','document_id':'material'}).json()['id']
    assert api.store.rows('SELECT source FROM lite_goals WHERE id=?',(g,))[0]['source']=='稳态、不可压、无黏'
    api.execute('UPDATE pages SET text=? WHERE document_id=?',('已更改','material'))
    def fake(schema,task,context):
        assert context['source']=='稳态、不可压、无黏'
        return llm.Question(question='条件？',hint='想想密度',reference='不可压',evidence='不可压',needs_verification=False)
    monkeypatch.setattr(llm,'generate',fake)
    assert client.post('/api/lite/questions',json={'goal_id':g}).status_code==200

def test_goal_rejects_other_course_material_and_unreadable_scan(client):
    api.store.add('other','另一课程.txt','课件','other.txt',[{'number':1,'text':'其他资料','status':'extracted'}])
    api.execute('UPDATE documents SET course_id=? WHERE id=?',('other-course','other'))
    payload={'concept':'伯努利','target':'理解基本概念','document_id':'other'}
    assert client.post('/api/lite/goals',json=payload).status_code==404
    api.store.add('scan','扫描.pdf','课件','scan.pdf',[{'number':1,'text':'','status':'needs_review'}])
    payload['document_id']='scan'
    assert client.post('/api/lite/goals',json=payload).status_code==400
    assert not api.store.rows('SELECT * FROM lite_goals')

def test_goal_without_material_reuses_current_course_text(client,monkeypatch):
    g=client.post('/api/lite/goals',json={'concept':'知识点','target':'理解基本概念'}).json()['id']
    def fake(schema,task,context):
        assert context['source']=='old data'
        return llm.Question(question='问题？',hint='提示',reference='old data',evidence='old data',needs_verification=False)
    monkeypatch.setattr(llm,'generate',fake)
    assert client.post('/api/lite/questions',json={'goal_id':g}).status_code==200

def test_choice_and_short_answer_round_trip(client,monkeypatch):
    def fake(schema,task,context):
        if schema is llm.Question:
            kind=context.get('question_type','short_answer')
            return llm.Question(question='条件是什么？',hint='考虑黏性',reference='A. 无黏',evidence='无黏',needs_verification=False,question_type=kind,options=['无黏','强黏性','必须有泵','必须有涡'] if kind=='single_choice' else [])
        assert context['options']==['无黏','强黏性','必须有泵','必须有涡']
        assert context['answer']=='A. 无黏'
        return llm.Evaluation(verdict='correct',error_type='none',explanation='回答正确',follow_up='为什么？',evidence='无黏',needs_verification=False)
    monkeypatch.setattr(llm,'generate',fake)
    g=client.post('/api/lite/goals',json={'concept':'伯努利','target':'理解','source':'无黏'}).json()['id']
    q=client.post('/api/lite/questions',json={'goal_id':g}).json()
    assert q['question_type']=='single_choice' and len(q['options'])==4 and 'reference' not in q
    assert client.post('/api/lite/questions/'+q['id']+'/answer',json={'answer':'Z. 伪造选项'}).status_code==400
    assert client.get('/api/lite/dashboard').json()['attempt_count']==0
    a=client.post('/api/lite/questions/'+q['id']+'/answer',json={'answer':'A. 无黏'}).json()
    assert a['evaluation']['verdict']=='correct'
    mid=client.post('/api/lite/answers/'+a['id']+'/mistake').json()['id']
    mistake=next(m for m in client.get('/api/lite/dashboard').json()['mistakes'] if m['id']==mid)
    assert 'A. 无黏' in mistake['question'] and 'D. 必须有涡' in mistake['question']
    next_q=client.post('/api/lite/questions',json={'goal_id':g}).json()
    assert next_q['question_type']=='short_answer' and next_q['options']==[]

@pytest.mark.parametrize('kind,options',[
    ('single_choice',['A','A','B','C']),('single_choice',['A','B']),
    ('single_choice',['A','B','C',' ']),('short_answer',['A','B','C','D'])])
def test_question_rejects_invalid_options(kind,options):
    with pytest.raises(ValueError):
        llm.Question(question='问题',hint='提示',reference='答案',evidence='',needs_verification=True,question_type=kind,options=options)
