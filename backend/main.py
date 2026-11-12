"""Single-user local API. Run one worker: the durable queue has one consumer."""
import base64
import hashlib
import json
import os
import threading
import uuid
import hmac
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, Cookie, Response, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database.storage import ROOT, Store
from agents.parser_agent import parse
from agents.knowledge_agent import organize
from agents.conflict_agent import LABELS
from workflows.graph import run
from services.ocr_service import configured, recognize, VisionError, settings as vision_settings
from services.retrieval import search

load_dotenv(ROOT / '.env')
data_root = Path(os.environ['NOTEPILOT_DATA_DIR']) if os.getenv('NOTEPILOT_DATA_DIR') else ROOT / 'data'
store = Store(os.getenv('NOTEPILOT_DB') or data_root / 'notepilot.db')
pool = ThreadPoolExecutor(max_workers=2)
lock = threading.Lock()


def initialize():
    with store.connect() as c:
        cols = {r['name'] for r in c.execute('PRAGMA table_info(documents)')}
        if 'course_id' not in cols:
            c.execute("ALTER TABLE documents ADD COLUMN course_id TEXT DEFAULT 'fluid'")
        c.executescript('''
        CREATE TABLE IF NOT EXISTS courses(id TEXT PRIMARY KEY,name TEXT NOT NULL,exam_date TEXT);
        INSERT OR IGNORE INTO courses VALUES('fluid','流体力学',NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,document_id TEXT,status TEXT,stage TEXT,error TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS practice(id INTEGER PRIMARY KEY,course_id TEXT,concept TEXT,correct INTEGER,answer TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        c.execute("UPDATE jobs SET status='failed',error='服务重启使任务中断，请重试',stage='任务中断' WHERE status IN ('queued','running')")


def valid_session(value):
    try:
        expires,signature=value.split('.')
        expected=hmac.new(os.environ['NOTEPILOT_TOKEN'].encode(),expires.encode(),hashlib.sha256).hexdigest()
        return int(expires)>time.time() and hmac.compare_digest(expected,signature)
    except (ValueError,KeyError,AttributeError,TypeError): return False


def auth(authorization: str = Header(default=''),np_session: str = Cookie(default='')):
    token = os.getenv('NOTEPILOT_TOKEN','')
    if token and not hmac.compare_digest(authorization.encode(),('Bearer '+token).encode()) and not valid_session(np_session):
        raise HTTPException(401,'访问口令不正确')


@asynccontextmanager
async def lifespan(app):
    if os.getenv('NOTEPILOT_ENV') == 'production' and not os.getenv('NOTEPILOT_TOKEN'):
        raise RuntimeError('Production requires NOTEPILOT_TOKEN')
    initialize()
    yield


app = FastAPI(title='NotePilot 2.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:8081','http://127.0.0.1:8081'],allow_methods=['*'],allow_headers=['*'],allow_credentials=True)


class Login(BaseModel):
    token:str=Field(min_length=1,max_length=1000)


@app.post('/api/auth/login')
def login(body:Login,response:Response,request:Request):
    secret=os.getenv('NOTEPILOT_TOKEN','')
    if not secret or not hmac.compare_digest(body.token.encode(),secret.encode()): raise HTTPException(401,'登录口令不正确')
    expires=str(int(time.time())+86400)
    signature=hmac.new(secret.encode(),expires.encode(),hashlib.sha256).hexdigest()
    response.set_cookie('np_session',expires+'.'+signature,max_age=86400,httponly=True,
                        secure=request.url.scheme=='https' or os.getenv('NOTEPILOT_ENV')=='production',samesite='strict',path='/')
    response.headers['Cache-Control']='no-store'
    return {'signed_in':True}


@app.get('/api/auth/session')
def session(np_session:str=Cookie(default='')):
    return {'signed_in':valid_session(np_session)}


@app.post('/api/auth/logout')
def logout(response:Response):
    response.delete_cookie('np_session',path='/',samesite='strict')
    return {'signed_in':False}


def execute(sql,args=()):
    with store.connect() as c: c.execute(sql,args)


def course_pages(course):
    return [p for p in store.pages() if p['course_id']==course]


def get_page(doc_id,number):
    matches=[p for p in store.pages() if p['document_id']==doc_id and p['number']==number]
    if not matches: raise HTTPException(404,'资料页不存在')
    return matches[0]


def clean(p):
    return {k:v for k,v in p.items() if k!='path'} if p else None


def png(p):
    import fitz
    path=Path(p['path'])
    if path.suffix=='.pdf':
        with fitz.open(path) as doc: return doc[p['number']-1].get_pixmap(dpi=110).tobytes('png'),'image/png'
    return path.read_bytes(),'image/png' if path.suffix=='.png' else 'image/jpeg'


def process(job_id,doc_id,ocr):
    try:
        execute("UPDATE jobs SET status='running',stage='读取原始资料' WHERE id=?",(job_id,))
        doc=next(d for d in store.documents() if d['id']==doc_id)
        parsed=parse(Path(doc['path']).read_bytes(),doc['name'])
        with store.connect() as c:
            # Retry never overwrites existing human corrections.
            c.executemany('INSERT OR IGNORE INTO pages VALUES(?,?,?,?,?)',[(doc_id,p['number'],p['text'],p['text'],p['status']) for p in parsed])
        for p in [p for p in store.pages() if p['document_id']==doc_id]:
            if ocr and configured() and p['status']=='needs_ocr':
                execute('UPDATE jobs SET stage=? WHERE id=?',(f"视觉识别 · 第 {p['number']} 页",job_id))
                data,mime=png(p); text=recognize(data,mime)
                execute("UPDATE pages SET text=?,original=?,status='ocr_unverified' WHERE document_id=? AND number=? AND status='needs_ocr'",(text,text,doc_id,p['number']))
        execute("UPDATE jobs SET stage='知识关联与证据诊断' WHERE id=?",(job_id,))
        run(course_pages(doc['course_id']))
        execute("UPDATE jobs SET status='completed',stage='处理完成' WHERE id=?",(job_id,))
    except VisionError as e:
        execute("UPDATE jobs SET status='failed',stage='视觉识别失败',error=? WHERE id=?",(str(e),job_id))
    except Exception:
        execute("UPDATE jobs SET status='failed',stage='处理失败',error='解析或模型调用失败，请检查文件与后端配置后重试。' WHERE id=?",(job_id,))


def enqueue(doc_id,ocr):
    with lock:
        existing=store.rows("SELECT id FROM jobs WHERE document_id=? AND status IN ('queued','running')",(doc_id,))
        if existing: return existing[0]['id']
        id=uuid.uuid4().hex
        execute("INSERT INTO jobs(id,document_id,status,stage) VALUES(?,?,'queued','等待处理')",(id,doc_id))
        pool.submit(process,id,doc_id,ocr)
        return id


@app.get('/api/health')
def health(): return {'status':'ok','version':'2.0'}


@app.get('/api/vision/status',dependencies=[Depends(auth)])
def vision_status():
    base,model=vision_settings()
    return {'configured':configured(),'model':model,'base_url':base,'scope':'图片与扫描页转录；知识诊断和追问仍使用现有规则'}


class Course(BaseModel):
    name: str = Field(min_length=1,max_length=60)
    exam_date: date | None = None


@app.post('/api/courses',dependencies=[Depends(auth)])
def add_course(body:Course):
    id=uuid.uuid4().hex
    execute('INSERT INTO courses VALUES(?,?,?)',(id,body.name,str(body.exam_date) if body.exam_date else None))
    return {'id':id}


@app.put('/api/courses/{id}',dependencies=[Depends(auth)])
def update_course(id:str,body:Course):
    execute('UPDATE courses SET name=?,exam_date=? WHERE id=?',(body.name,str(body.exam_date) if body.exam_date else None,id))
    return {'ok':True}


def schedule(course,chunks,issues):
    today=datetime.now(timezone(timedelta(hours=8))).date()
    history=store.rows('SELECT * FROM practice WHERE course_id=? ORDER BY id',(course['id'],))
    result=[]
    for concept in sorted({c['concept'] for c in chunks}):
        recent=[a for a in history if a['concept']==concept][-5:]
        score=sum(a['correct'] for a in recent)/len(recent) if recent else None
        has_gap=any(i['concept']==concept and not i.get('review') for i in issues)
        days=0 if not recent or not recent[-1]['correct'] or has_gap else (3 if len(recent)>=3 and score>=.8 else 1)
        base=datetime.fromisoformat(recent[-1]['created']).replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).date() if recent else today
        due=base+timedelta(days=days)
        if course['exam_date']: due=min(due,date.fromisoformat(course['exam_date'])-timedelta(days=1))
        result.append({'concept':concept,'score':score,'count':len(recent),'due':str(due),'priority':3 if has_gap else 2 if days==0 else 1,
                       'reason':'有待核实证据' if has_gap else '先做一次自测' if not recent else '最近答错，优先巩固' if days==0 else '按近期表现间隔复习'})
    return sorted(result,key=lambda t:(t['due'],-t['priority']))


@app.get('/api/workspace',dependencies=[Depends(auth)])
def workspace(course_id:str='fluid'):
    courses=store.rows('SELECT * FROM courses ORDER BY rowid')
    course=next((c for c in courses if c['id']==course_id),None)
    if not course: raise HTTPException(404,'课程不存在')
    jobs=store.rows('SELECT j.* FROM jobs j JOIN documents d ON d.id=j.document_id WHERE d.course_id=? ORDER BY j.created DESC LIMIT 15',(course_id,))
    pages=course_pages(course_id); state=run(pages)
    reviews={r['issue_id']:r for r in store.rows('SELECT * FROM reviews')}
    issues=[{**i,'label':LABELS[i['issue_type']],'source_a':clean(i['source_a']),'source_b':clean(i['source_b']),'review':reviews.get(i['id'])} for i in state['issues']]
    docs=[clean(d) for d in store.documents() if d['course_id']==course_id]
    for d in docs: d['page_count']=sum(p['document_id']==d['id'] for p in pages)
    return {'courses':courses,'course':course,'documents':docs,'issues':issues,
            'concepts':sorted({c['concept'] for c in state['chunks']}),'tasks':schedule(course,state['chunks'],issues),
            'jobs':jobs,
            'attempt_count':len(store.rows('SELECT id FROM practice WHERE course_id=?',(course_id,))),
            'vision_configured':configured(),'engine':state['engine']}


@app.post('/api/documents',dependencies=[Depends(auth)],status_code=202)
async def upload(file:UploadFile=File(...),course_id:str=Form('fluid'),kind:str=Form('课堂笔记'),allow_ocr:bool=Form(False)):
    if not store.rows('SELECT id FROM courses WHERE id=?',(course_id,)): raise HTTPException(404,'课程不存在')
    name=Path((file.filename or '资料').replace('\\','/')).name
    suffix=Path(name).suffix.lower()
    if suffix not in ('.pdf','.txt','.md','.png','.jpg','.jpeg'): raise HTTPException(400,'仅支持 PDF、图片和文本')
    data=await file.read(20*1024*1024+1)
    if not data or len(data)>20*1024*1024: raise HTTPException(400,'文件为空或超过 20 MB')
    id=hashlib.sha256(course_id.encode()+data).hexdigest()
    folder=(Path(os.environ['NOTEPILOT_DATA_DIR']) if os.getenv('NOTEPILOT_DATA_DIR') else ROOT/'data')/'uploads'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/(id+suffix)
    with lock:
        if not store.rows('SELECT id FROM documents WHERE id=?',(id,)):
            path.write_bytes(data)
            store.add(id,name,kind,path,[])
            execute('UPDATE documents SET course_id=? WHERE id=?',(course_id,id))
    return {'document_id':id,'job_id':enqueue(id,allow_ocr)}


class Retry(BaseModel):
    allow_ocr:bool=False


class MergeCourse(BaseModel):
    target_id:str


@app.post('/api/courses/{id}/merge',dependencies=[Depends(auth)])
def merge_course(id:str,body:MergeCourse):
    if id==body.target_id: raise HTTPException(400,'不能合并到同一课程')
    with lock,store.connect() as c:
        if not c.execute('SELECT 1 FROM courses WHERE id=?',(id,)).fetchone() or not c.execute('SELECT 1 FROM courses WHERE id=?',(body.target_id,)).fetchone():
            raise HTTPException(404,'课程不存在')
        if c.execute("SELECT 1 FROM jobs j JOIN documents d ON d.id=j.document_id WHERE d.course_id=? AND j.status IN ('queued','running')",(id,)).fetchone():
            raise HTTPException(409,'请等待该课程处理完成再合并')
        c.execute('UPDATE documents SET course_id=? WHERE course_id=?',(body.target_id,id))
        c.execute('UPDATE practice SET course_id=? WHERE course_id=?',(body.target_id,id))
        c.execute('DELETE FROM courses WHERE id=?',(id,))
    return {'ok':True,'course_id':body.target_id}


@app.post('/api/documents/{id}/process',dependencies=[Depends(auth)])
def retry(id:str,body:Retry):
    if not store.rows('SELECT id FROM documents WHERE id=?',(id,)): raise HTTPException(404,'资料不存在')
    return {'job_id':enqueue(id,body.allow_ocr)}


@app.get('/api/documents/{id}/pages/{number}',dependencies=[Depends(auth)])
def page_detail(id:str,number:int):
    p=get_page(id,number); result=clean(p)
    if Path(p['path']).suffix.lower() not in ('.txt','.md'):
        data,mime=png(p); result['preview']=f'data:{mime};base64,'+base64.b64encode(data).decode()
    return result


class Correction(BaseModel):
    text:str=Field(min_length=1,max_length=100000)


@app.put('/api/documents/{id}/pages/{number}',dependencies=[Depends(auth)])
def correct(id:str,number:int,body:Correction):
    get_page(id,number); store.correct(id,number,body.text)
    return {'ok':True}


@app.get('/api/search',dependencies=[Depends(auth)])
def lookup(q:str,course_id:str='fluid'):
    return [clean(p) for p in search(course_pages(course_id),q)]


class Review(BaseModel):
    decision:str=Field(min_length=1,max_length=100)
    note:str=Field(default='',max_length=2000)


@app.post('/api/issues/{id}/review',dependencies=[Depends(auth)])
def review(id:str,body:Review):
    store.review(id,body.decision,body.note); return {'ok':True}


def question_for(course_id,concept):
    chunks=[c for c in organize(course_pages(course_id)) if c['concept']==concept]
    if not chunks: raise HTTPException(404,'没有这个知识点的原文证据')
    history=store.rows('SELECT * FROM practice WHERE course_id=? AND concept=? ORDER BY id',(course_id,concept))
    depth=2 if len(history)>=2 and all(h['correct'] for h in history[-2:]) else 1
    # Source reconstruction is intentionally conservative: correct answer is the actual quote.
    source=max(chunks,key=lambda c:len(c['quote']))
    question_id=hashlib.sha256((source['quote']+str(depth)).encode()).hexdigest()[:16]
    prompt=(f'结合原文，{concept}记载了哪些条件或定义？先回想，再展开证据。' if depth==1 else
            f'进一步思考：这段{concept}结论依赖哪些前提？换一份资料时，应先核对什么？请用原文说明。')
    return {'id':question_id,'concept':concept,'depth':depth,'prompt':prompt,'source':clean(source),
            'answer':source['quote'],'mode':'基于原文的主动回忆 · 自评，不自动裁决开放回答'}


@app.get('/api/coach',dependencies=[Depends(auth)])
def coach(course_id:str='fluid',concept:str=''):
    ws=workspace(course_id)
    if not ws['tasks']: raise HTTPException(404,'上传资料后才能生成有出处的追问')
    return question_for(course_id,concept or ws['tasks'][0]['concept'])


class Feedback(BaseModel):
    course_id:str
    concept:str
    question_id:str
    answer:str=Field(default='',max_length=5000)
    rating:str


@app.post('/api/coach/feedback',dependencies=[Depends(auth)])
def feedback(body:Feedback):
    q=question_for(body.course_id,body.concept)
    if q['id']!=body.question_id: raise HTTPException(409,'资料或问题已变化，请刷新后作答')
    if body.rating not in ('remembered','again'): raise HTTPException(400,'反馈无效')
    execute('INSERT INTO practice(course_id,concept,correct,answer) VALUES(?,?,?,?)',(body.course_id,body.concept,int(body.rating=='remembered'),body.answer))
    return {'message':'已记录自评并更新复习计划','next':question_for(body.course_id,body.concept)}


@app.get('/api/export',dependencies=[Depends(auth)])
def export():
    return {table:store.rows('SELECT * FROM '+table) for table in ('courses','documents','pages','reviews','practice','attempts','jobs')}


@app.delete('/api/documents/{id}',dependencies=[Depends(auth)])
def delete_document(id:str):
    with lock:
        if store.rows("SELECT id FROM jobs WHERE document_id=? AND status IN ('running','queued')",(id,)): raise HTTPException(409,'请等待处理结束后删除')
        records=store.rows('SELECT path FROM documents WHERE id=?',(id,))
        if not records: raise HTTPException(404,'资料不存在')
        with store.connect() as c:
            c.execute('DELETE FROM pages WHERE document_id=?',(id,)); c.execute('DELETE FROM jobs WHERE document_id=?',(id,)); c.execute('DELETE FROM documents WHERE id=?',(id,))
            c.execute('DELETE FROM reviews')
        # Only delete canonical files from the managed upload directory.
        path=Path(records[0]['path']).resolve()
        root=((Path(os.environ['NOTEPILOT_DATA_DIR']) if os.getenv('NOTEPILOT_DATA_DIR') else ROOT/'data')/'uploads').resolve()
        if path.parent==root: path.unlink(missing_ok=True)
    return {'ok':True}


from backend.demo import router as demo_router
app.include_router(demo_router)

web=ROOT/'mobile/dist'
if web.exists(): app.mount('/',StaticFiles(directory=web,html=True),name='mobile-web')
