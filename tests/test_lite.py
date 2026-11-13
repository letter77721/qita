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
    assert result.verdict=='correct' and result.error_type=='none' and result.needs_verification
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

@pytest.mark.parametrize('verdict',['correct','incorrect'])
def test_binary_grading_independent_of_missing_source(monkeypatch,verdict):
    from io import BytesIO
    monkeypatch.setenv('TEXT_API_KEY','fake')
    payload={'verdict':verdict,'error_type':'none' if verdict=='correct' else 'condition','explanation':'按参考答案评价','follow_up':'为什么？','evidence':'','needs_verification':False}
    monkeypatch.setattr(llm.urllib.request,'urlopen',lambda *a,**k:BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(payload)}}]}).encode()))
    result=llm.generate(llm.Evaluation,'评价',{'source':'','reference':'无黏','answer':'无黏' if verdict=='correct' else '有黏'})
    assert result.verdict==verdict and result.needs_verification
    # Missing textbook evidence still cannot be counted as confirmed mastery.
    assert schedule({'id':'g'},[{'created':'2026-11-13 00:00:00','evaluation':result.model_dump_json()}])['certain_samples']==0

@pytest.mark.parametrize('verdict',['uncertain','partial'])
def test_evaluation_rejects_non_binary_verdict(verdict):
    with pytest.raises(ValueError):
        llm.Evaluation(verdict=verdict,error_type='none',explanation='解析',follow_up='追问',evidence='',needs_verification=True)

def test_material_status_and_selected_goal_after_upload(client):
    import time
    u=client.post('/api/documents',files={'file':('chapter.txt','课程文字资料'.encode('gb18030'),'text/plain')}).json()
    for _ in range(100):
        status=client.get('/api/documents/'+u['document_id']+'/status').json()
        if status['status'] in ('completed','failed'):break
        time.sleep(.02)
    assert status['status']=='completed'
    doc=next(d for d in client.get('/api/lite/dashboard').json()['documents'] if d['id']==u['document_id'])
    assert doc['readable_pages']==1 and doc['status']=='completed'
    g=client.post('/api/lite/goals',json={'concept':'课程','target':'理解','document_id':doc['id']})
    assert g.status_code==200
    assert client.get('/api/documents/'+doc['id']+'/pages/1').json()['text']=='课程文字资料'

def test_failed_upload_visible_without_pages(client):
    import time
    u=client.post('/api/documents',files={'file':('broken.pdf',b'not a pdf','application/pdf')}).json()
    for _ in range(100):
        status=client.get('/api/documents/'+u['document_id']+'/status').json()
        if status['status'] in ('completed','failed'):break
        time.sleep(.02)
    assert status['status']=='failed' and '文字提取失败' in status['error']
    doc=next(d for d in client.get('/api/lite/dashboard').json()['documents'] if d['id']==u['document_id'])
    assert doc['page_count']==0 and doc['readable_pages']==0 and doc['status']=='failed'

def test_course_rename_and_delete_preserves_learning(client):
    c=client.post('/api/courses',json={'name':'课程二'}).json()['id']
    assert client.put('/api/courses/'+c,json={'name':'新课程名'}).status_code==200
    assert next(x for x in client.get('/api/courses').json() if x['id']==c)['name']=='新课程名'
    g=client.post('/api/lite/goals',json={'course_id':c,'concept':'知识点','target':'理解'}).json()['id']
    m=client.post('/api/lite/mistakes',json={'course_id':c,'concept':'知识点','question':'题目'}).json()['id']
    assert client.post('/api/courses/'+c+'/merge',json={'target_id':'fluid'}).status_code==200
    d=client.get('/api/lite/dashboard').json()
    assert any(x['id']==g for x in d['tasks']) and any(x['id']==m for x in d['mistakes'])
    assert not any(x['id']==c for x in client.get('/api/courses').json())
    assert client.post('/api/courses/fluid/merge',json={'target_id':'fluid'}).status_code==400
