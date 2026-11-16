import json,uuid,re,unicodedata
from difflib import SequenceMatcher
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,HTTPException,Depends
from pydantic import BaseModel,Field
from services import text_model as llm

router=APIRouter(prefix='/api/lite')
def main():
    from backend import main
    return main
def initialize(store):
    with store.connect() as c:c.executescript('''
    CREATE TABLE IF NOT EXISTS lite_summaries(id TEXT PRIMARY KEY,course_id TEXT,payload TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS lite_goals(id TEXT PRIMARY KEY,course_id TEXT,concept TEXT,target TEXT,source TEXT);
    CREATE TABLE IF NOT EXISTS lite_questions(id TEXT PRIMARY KEY,goal_id TEXT,payload TEXT,trace TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS lite_answers(id TEXT PRIMARY KEY,question_id TEXT UNIQUE,goal_id TEXT,answer TEXT,evaluation TEXT,trace TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS lite_mistakes(id TEXT PRIMARY KEY,course_id TEXT,concept TEXT,question TEXT,answer TEXT,source TEXT,analysis TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
def now():return datetime.now(timezone(timedelta(hours=8)))
def schedule(goal,history,exam=None):
    recent=history[-5:];results=[json.loads(h['evaluation']) for h in recent]
    certain=[r for r in results if r['verdict']!='uncertain' and not r['needs_verification']]
    streak=0
    for r in reversed(results):
        if r['verdict']=='correct' and not r['needs_verification']:streak+=1
        else:break
    days=0 if not results or results[-1]['verdict']!='correct' or results[-1]['needs_verification'] else (1 if streak<3 else 3 if streak<5 else 7)
    base=datetime.fromisoformat(recent[-1]['created']).replace(tzinfo=timezone.utc).astimezone(now().tzinfo) if recent else now()
    due=(base+timedelta(days=days)).date()
    if exam:due=min(due,datetime.fromisoformat(exam).date()-timedelta(days=1))
    return {**goal,'due':str(due),'attempts':len(history),'certain_samples':len(certain),'recent_accuracy':sum(r['verdict']=='correct' for r in certain)/len(certain) if certain else None,
            'level':'尚未评估' if not results else '需要巩固' if streak<3 else '近期较稳定，继续验证','interval_days':days}

class Goal(BaseModel):
    course_id:str='fluid'
    concept:str=Field(min_length=1,max_length=100)
    target:str=Field(min_length=1,max_length=1000)
    source:str=Field(default='',max_length=15000)
    document_id:str=Field(default='',max_length=100)
class Practice(BaseModel):
    goal_id:str=''
    course_id:str='fluid'
class Answer(BaseModel):answer:str=Field(min_length=1,max_length=5000)
class Mistake(BaseModel):
    course_id:str='fluid'
    concept:str=Field(min_length=1,max_length=100)
    question:str=Field(min_length=1,max_length=5000)
    answer:str=Field(default='',max_length=5000)
    source:str=Field(default='',max_length=15000)
def row(table,id):
    rows=main().store.rows('SELECT * FROM '+table+' WHERE id=?',(id,))
    if not rows:raise HTTPException(404,'记录不存在')
    return rows[0]
def model(schema,task,context):
    try:return llm.generate(schema,task,context).model_dump()
    except llm.ModelError as e:raise HTTPException(e.status,str(e))
@router.post('/model-check')
def model_check():
    source='合成验收资料：经典伯努利方程沿同一流线使用时，假设稳态、不可压、无黏流动。'
    q=model(llm.Question,'生成一个简短的条件回忆题。',{'source':source,'concept':'伯努利方程'})
    e=model(llm.Evaluation,'核对这个合成测试回答。',{'source':source,'question':q['question'],'reference':q['reference'],'answer':'需要稳态、不可压、无黏，并沿同一流线使用。'})
    return {'test_only':True,'stored':False,'model':llm.configuration()['model'],'question':q,'evaluation':e}

@router.get('/dashboard')
def dashboard(course_id:str='fluid'):
    s=main().store;goals=s.rows('SELECT * FROM lite_goals WHERE course_id=?',(course_id,))
    course=next((c for c in s.rows('SELECT * FROM courses') if c['id']==course_id),None)
    if not course:raise HTTPException(404,'课程不存在')
    answers=s.rows('SELECT a.* FROM lite_answers a JOIN lite_goals g ON g.id=a.goal_id WHERE g.course_id=? ORDER BY a.created,a.rowid',(course_id,))
    tasks=sorted([schedule(g,[a for a in answers if a['goal_id']==g['id']],course['exam_date']) for g in goals],key=lambda g:(g['due'],g['concept']))
    documents=[{**{k:v for k,v in d.items() if k!='path'},'page_count':sum(p['document_id']==d['id'] for p in s.pages())} for d in s.documents() if d['course_id']==course_id]
    for d in documents:
        d['readable_pages']=sum(p['document_id']==d['id'] and bool(p['text'].strip()) and p['status'] in ('verified','extracted') for p in s.pages())
        jobs=s.rows('SELECT status,error FROM jobs WHERE document_id=? ORDER BY created DESC,rowid DESC LIMIT 1',(d['id'],))
        d.update(jobs[0] if jobs else {'status':'completed','error':None})
    return {'courses':s.rows('SELECT * FROM courses'),'course':course,'tasks':tasks,'history':[{**a,'evaluation':json.loads(a['evaluation']),'trace':json.loads(a['trace'])} for a in answers[-30:][::-1]],
            'mistakes':s.rows('SELECT * FROM lite_mistakes WHERE course_id=? ORDER BY created DESC',(course_id,)),
            'model':llm.configuration(),'attempt_count':len(answers),'documents':documents,'summaries':[{**x,'payload':json.loads(x['payload'])} for x in s.rows('SELECT * FROM lite_summaries WHERE course_id=? ORDER BY created DESC,rowid DESC LIMIT 5',(course_id,))]}
@router.post('/goals')
def add_goal(body:Goal):
    if not main().store.rows('SELECT id FROM courses WHERE id=?',(body.course_id,)):raise HTTPException(404,'课程不存在')
    source=body.source
    if body.document_id:
        if not main().store.rows('SELECT id FROM documents WHERE id=? AND course_id=?',(body.document_id,body.course_id)):
            raise HTTPException(404,'该课程中没有这份资料')
        source='\n'.join(p['text'] for p in main().course_pages(body.course_id) if p['document_id']==body.document_id and p['status'] in ('verified','extracted') and p['text'].strip())[:15000]
        if not source.strip():raise HTTPException(400,'这份资料暂无可提取文字，请等待处理完成或换用文字版 PDF / TXT / MD')
    id=uuid.uuid4().hex;main().execute('INSERT INTO lite_goals VALUES(?,?,?,?,?)',(id,body.course_id,body.concept,body.target,source));return {'id':id}
def fresh_question(context):
    recent=main().store.rows('SELECT payload FROM lite_questions WHERE goal_id=? ORDER BY created DESC,rowid DESC LIMIT 20',(context.pop('_goal_id'),))
    seen=[json.loads(r['payload'])['question'] for r in recent]
    context['recent_questions']=seen
    def normalize(text):return re.sub(r'[^\w]','',unicodedata.normalize('NFKC',text).lower())
    for attempt in range(2):
        result=model(llm.Question,'Tutor：生成一道新的练习题及提示与参考答案。必须避开 recent_questions 已考过的问题，不能仅改写题干、交换选项或更换题型。依照 focus 改变考查角度，如条件、反例、比较、情境应用；资料不足以支持新题时不要编造事实。',context)
        key=normalize(result['question'])
        if not any(key==normalize(q) or SequenceMatcher(None,key,normalize(q)).ratio()>.92 for q in seen):return result
        context['recent_questions']=[result['question']]+seen
        context['retry_instruction']='上一题重复，请换一个尚未考查的知识角度。'
    raise HTTPException(409,'模型连续生成了重复题，本次未计入练习。请再试一次，或补充资料、切换知识点。')

@router.post('/questions')
def question(body:Practice):
    goal_id=body.goal_id
    if not goal_id:
        tasks=dashboard(body.course_id)['tasks']
        if not tasks:raise HTTPException(400,'先创建学习目标')
        goal_id=tasks[0]['id']
    g=row('lite_goals',goal_id);history=main().store.rows('SELECT evaluation FROM lite_answers WHERE goal_id=? ORDER BY created DESC LIMIT 5',(g['id'],))
    # Include existing textual PDF/notes when no material was pasted into the goal.
    source=g['source'] or '\n'.join(p['text'] for p in main().course_pages(g['course_id']) if p['status'] in ('verified','extracted'))[:15000]
    count=main().store.rows('SELECT COUNT(*) AS n FROM lite_questions WHERE goal_id=?',(g['id'],))[0]['n']
    question_type='single_choice' if count%2==0 else 'short_answer'
    focus=['基本概念辨析','适用条件与边界','反例与常见误解','实际情境应用','概念或方法比较','综合推理与迁移'][count%6]
    result=fresh_question({'_goal_id':g['id'],'concept':g['concept'],'target':g['target'],'history':history,'source':source,'question_type':question_type,'focus':focus,'question_number':count+1})
    trace=[{'agent':'Planner','decision':'用户选择知识点；按到期时间推荐任务'},{'agent':'Tutor','model':llm.configuration()['model'],'status':'validated_json'}]
    id=uuid.uuid4().hex
    # Snapshot evidence to keep grading stable if a goal later changes.
    main().execute('INSERT INTO lite_questions(id,goal_id,payload,trace) VALUES(?,?,?,?)',(id,g['id'],json.dumps({**result,'source':source},ensure_ascii=False),json.dumps(trace)))
    return {'id':id,'goal_id':g['id'],**{k:v for k,v in result.items() if k!='reference'},'trace':trace}

@router.post('/answers/{id}/follow-up')
def follow_up(id:str):
    a=row('lite_answers',id);q=row('lite_questions',a['question_id']);payload=json.loads(q['payload']);evaluation=json.loads(a['evaluation'])
    result=fresh_question({'_goal_id':q['goal_id'],'previous_question':payload['question'],'previous_answer':a['answer'],'feedback':evaluation,'source':payload['source'],'question_type':'short_answer','focus':'围绕上一次错因的新情境应用'})
    qid=uuid.uuid4().hex;trace=[{'agent':'Planner','decision':'依据上一次错因追问'},{'agent':'Tutor','model':llm.configuration()['model'],'status':'validated_json'}]
    main().execute('INSERT INTO lite_questions(id,goal_id,payload,trace) VALUES(?,?,?,?)',(qid,q['goal_id'],json.dumps({**result,'source':payload['source']},ensure_ascii=False),json.dumps(trace)))
    return {'id':qid,'goal_id':q['goal_id'],**{k:v for k,v in result.items() if k!='reference'},'trace':trace}
@router.post('/questions/{id}/answer')
def answer(id:str,body:Answer):
    q=row('lite_questions',id);existing=main().store.rows('SELECT * FROM lite_answers WHERE question_id=?',(id,))
    if existing:return {'id':existing[0]['id'],'evaluation':json.loads(existing[0]['evaluation']),'trace':json.loads(existing[0]['trace'])}
    payload=json.loads(q['payload'])
    if payload.get('question_type')=='single_choice':
        allowed=[chr(65+i)+'. '+o for i,o in enumerate(payload['options'])]
        if body.answer not in allowed:raise HTTPException(400,'请选择题目提供的一个选项')
    result=model(llm.Evaluation,'Evaluator：按本题参考答案与教材核对回答，只判正确 correct 或错误 incorrect，解释原因并给出一个有针对性的追问。教材证据不足单独标记 needs_verification，不改变答题对错。',{'question':payload['question'],'options':payload.get('options',[]),'reference':payload['reference'],'answer':body.answer,'source':payload['source']})
    trace=json.loads(q['trace'])+[{'agent':'Evaluator','model':llm.configuration()['model'],'status':'validated_json'},{'agent':'Scheduler','rule':'最近5次；不确定不计正确率；连续正确3次才延长间隔'}]
    aid=uuid.uuid4().hex
    with main().store.connect() as c:
        c.execute('INSERT OR IGNORE INTO lite_answers(id,question_id,goal_id,answer,evaluation,trace) VALUES(?,?,?,?,?,?)',(aid,id,q['goal_id'],body.answer,json.dumps(result,ensure_ascii=False),json.dumps(trace)))
    saved=main().store.rows('SELECT * FROM lite_answers WHERE question_id=?',(id,))[0]
    return {'id':saved['id'],'evaluation':json.loads(saved['evaluation']),'trace':json.loads(saved['trace']),'reference':payload['reference']}
@router.post('/answers/{id}/mistake')
def save_answer(id:str):
    a=row('lite_answers',id);q=row('lite_questions',a['question_id']);g=row('lite_goals',q['goal_id']);p=json.loads(q['payload'])
    mid='answer-'+id
    text=p['question']+'\n'+'\n'.join(chr(65+i)+'. '+o for i,o in enumerate(p['options'])) if p.get('options') else p['question']
    main().execute('INSERT OR IGNORE INTO lite_mistakes(id,course_id,concept,question,answer,source,analysis) VALUES(?,?,?,?,?,?,?)',(mid,g['course_id'],g['concept'],text,a['answer'],p['source'],a['evaluation']))
    return {'id':mid}
@router.post('/mistakes')
def add_mistake(body:Mistake):
    if not main().store.rows('SELECT id FROM courses WHERE id=?',(body.course_id,)):raise HTTPException(404,'课程不存在')
    id=uuid.uuid4().hex;main().execute('INSERT INTO lite_mistakes(id,course_id,concept,question,answer,source,analysis) VALUES(?,?,?,?,?,?,?)',(id,body.course_id,body.concept,body.question,body.answer,body.source,''));return {'id':id}
@router.put('/mistakes/{id}')
def edit_mistake(id:str,body:Mistake):
    row('lite_mistakes',id);main().execute('UPDATE lite_mistakes SET concept=?,question=?,answer=?,source=?,analysis=? WHERE id=?',(body.concept,body.question,body.answer,body.source,'',id));return {'ok':True}
@router.delete('/mistakes/{id}')
def delete_mistake(id:str):
    row('lite_mistakes',id);main().execute('DELETE FROM lite_mistakes WHERE id=?',(id,));return {'ok':True}
@router.post('/mistakes/{id}/analyze')
def analyze_mistake(id:str):
    m=row('lite_mistakes',id);result=model(llm.Evaluation,'分析用户手动录入错题的错因与不确定性。',{'question':m['question'],'answer':m['answer'],'source':m['source']})
    main().execute('UPDATE lite_mistakes SET analysis=? WHERE id=?',(json.dumps(result,ensure_ascii=False),id));return result

class SummaryRequest(BaseModel):
    course_id:str='fluid'

@router.post('/summaries')
def summarize(body:SummaryRequest):
    courses=main().store.rows('SELECT * FROM courses WHERE id=?',(body.course_id,))
    if not courses:raise HTTPException(404,'课程不存在')
    goals=main().store.rows('SELECT concept,target,source FROM lite_goals WHERE course_id=?',(body.course_id,))
    texts=[p['text'] for p in main().course_pages(body.course_id) if p['status'] in ('verified','extracted') and p['text'].strip()]
    texts += [g['source'] for g in goals if g['source']]
    if not texts and not goals:raise HTTPException(400,'请先上传课程资料或创建学习目标，再总结知识点')
    source='\n'.join(texts)[:15000]
    result=model(llm.KnowledgeSummary,'总结本课程的核心知识点、重要公式及适用条件、常见易错点。优先依据资料；无教材时围绕学习目标提供通用总结。不要出题或反问。每项简明清楚，公式用 LaTeX。',{'course':courses[0]['name'],'goals':[{'concept':g['concept'],'target':g['target']} for g in goals],'source':source})
    id=uuid.uuid4().hex
    main().execute('INSERT INTO lite_summaries(id,course_id,payload) VALUES(?,?,?)',(id,body.course_id,json.dumps(result,ensure_ascii=False)))
    return {'id':id,'payload':result}
