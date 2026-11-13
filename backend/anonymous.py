"""Anonymous browser workspaces. Owner database is never exposed by public routes."""
import os,hmac,hashlib,secrets,time,threading,re
from pathlib import Path
from contextvars import ContextVar
from collections import defaultdict,deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from database.storage import Store,ROOT

current=ContextVar('anonymous_store',default=None)
visitor=ContextVar('anonymous_id',default=None)
_secret=secrets.token_bytes(32)
_lock=threading.Lock()
_requests=defaultdict(deque)
_model_calls=defaultdict(deque)
_global_calls=deque()
_new_sessions=defaultdict(deque)

class ScopedStore:
    def __init__(self,owner):self.owner=owner
    def __getattr__(self,name):return getattr(current.get() or self.owner,name)

def sign(id):
    key=(os.getenv('NOTEPILOT_TOKEN') or '').encode() or _secret
    return hmac.new(key,id.encode(),hashlib.sha256).hexdigest()

def identity(cookie):
    try:
        id,signature=cookie.split('.')
        if re.fullmatch('[a-f0-9]{32}',id) and hmac.compare_digest(sign(id),signature):return id
    except (ValueError,TypeError):pass
    return secrets.token_hex(16)

def upload_root():
    return current.get().path.parent/'uploads' if current.get() else Path(os.getenv('NOTEPILOT_DATA_DIR') or ROOT/'data')/'uploads'

class AnonymousMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        path=request.scope['path']
        if not path.startswith('/api/open/'):return await call_next(request)
        rest=path[len('/api/open'):]
        if rest.split('/')[1] not in ('lite','courses','documents','workspace','export','search') or rest=='/lite/model-check':
            return JSONResponse({'detail':'接口不存在'},status_code=404)
        ip=hashlib.sha256((request.client.host if request.client else 'unknown').encode()).hexdigest()
        now=time.monotonic()
        model=request.method=='POST' and (rest.startswith('/lite/questions') or rest.endswith('/follow-up') or rest.endswith('/analyze'))
        with _lock:
            for q,seconds in ((_requests[ip],60),(_model_calls[ip],3600),(_global_calls,86400)):
                while q and q[0]<now-seconds:q.popleft()
            if len(_requests[ip])>=120 or (model and (len(_model_calls[ip])>=30 or len(_global_calls)>=200)):
                return JSONResponse({'detail':'体验请求较多，请稍后再试。文本模型每网络每小时最多30次，全站每日最多200次。'},status_code=429)
            _requests[ip].append(now)
            if model:_model_calls[ip].append(now);_global_calls.append(now)
        id=identity(request.cookies.get('np_guest',''))
        if not request.cookies.get('np_guest','').startswith(id+'.'):
            with _lock:
                q=_new_sessions[ip]
                while q and q[0]<now-3600:q.popleft()
                if len(q)>=20:return JSONResponse({'detail':'创建学习空间过于频繁，请保留 Cookie 后稍后再试。'},status_code=429)
                q.append(now)
        root=Path(os.getenv('NOTEPILOT_DATA_DIR') or ROOT/'data')/'anonymous'/id
        guest=Store(root/'notepilot.db')
        token=current.set(guest);who=visitor.set(id)
        try:
            from backend import main
            from backend.lite import initialize
            if not guest.rows("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'"):
                main.initialize()
            initialize(guest)
            request.scope['path']='/api'+rest
            request.scope['raw_path']=request.scope['path'].encode()
            response=await call_next(request)
            response.set_cookie('np_guest',id+'.'+sign(id),max_age=2592000,httponly=True,
                                secure=request.url.scheme=='https' or os.getenv('NOTEPILOT_ENV')=='production',samesite='strict',path='/')
            response.headers['Cache-Control']='no-store'
            return response
        finally:
            current.reset(token);visitor.reset(who)
