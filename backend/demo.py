"""Public synthetic examples. No database, uploads, model calls or private files."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from agents.knowledge_agent import organize
from agents.conflict_agent import diagnose, LABELS
from services.retrieval import search

router=APIRouter(prefix='/api/demo')
COURSE={'id':'fluid','name':'流体力学 · 公开示例','exam_date':None}
PAGES=[
    {'document_id':'demo-notes','name':'课堂笔记（合成示例）.txt','kind':'课堂笔记','number':1,
     'text':'【合成示例，用于演示，非真实课堂记录】\n伯努利方程：沿流线应用。\n雷诺数：$Re=\\frac{\\rho v L}{\\mu}$，L 为特征长度。\n牛顿黏性定律：牛顿流体剪应力与速度梯度成正比。',
     'status':'extracted','course_id':'fluid'},
    {'document_id':'demo-slides','name':'课程课件（合成示例）.txt','kind':'课程课件','number':1,
     'text':'【合成示例，用于演示，非真实课程课件】\n伯努利方程：稳态、不可压、无黏条件下沿流线应用。\n雷诺数：$Re=\\frac{\\rho v L}{\\mu}$，管流常取管道内径为特征长度。\n牛顿黏性定律：牛顿流体剪应力与速度梯度成正比。',
     'status':'extracted','course_id':'fluid'}]
for p in PAGES: p['original']=p['text']


@router.get('/workspace')
def workspace():
    chunks=organize(PAGES)
    issues=[{**i,'label':LABELS[i['issue_type']],'review':None} for i in diagnose(chunks,PAGES)]
    today=str(datetime.now(timezone(timedelta(hours=8))).date())
    concepts=sorted({c['concept'] for c in chunks})
    return {'courses':[COURSE],'course':COURSE,'documents':[
        {'id':p['document_id'],'name':p['name'],'kind':p['kind'],'course_id':'fluid','page_count':1} for p in PAGES],
        'issues':issues,'concepts':concepts,'tasks':[{'concept':c,'score':None,'count':0,'due':today,
        'priority':3 if c=='伯努利方程' else 1,'reason':'示例条件待核实' if c=='伯努利方程' else '示例主动回忆'} for c in concepts],
        'jobs':[],'attempt_count':0,'vision_configured':False,'engine':'公开样例 · 实时规则诊断','demo':True}


@router.get('/documents/{id}/pages/{number}')
def page(id:str,number:int):
    p=next((p for p in PAGES if p['document_id']==id and p['number']==number),None)
    if not p: raise HTTPException(404,'公开样例页不存在')
    return p


@router.get('/search')
def lookup(q:str): return search(PAGES,q)


@router.get('/coach')
def coach(concept:str='',depth:int=1):
    concept=concept or '伯努利方程'
    candidates=[c for c in organize(PAGES) if c['concept']==concept]
    if not candidates: raise HTTPException(404,'样例中没有这个知识点')
    source=max(candidates,key=lambda c:len(c['quote']))
    depth=2 if depth>=2 else 1
    return {'id':f'demo-{concept}-{depth}','concept':concept,'depth':depth,
        'prompt':f'结合示例，{concept}记载了哪些条件或定义？请先回想，再对照原文。' if depth==1 else
                 f'进一步思考：{concept}依赖哪些前提？切换到实际流动或另一份资料时，应该核对什么？',
        'source':source,'answer':source['quote'],'mode':'合成资料演示 · 回答、复核和自评仅在当前页面会话保留；不是模型生成内容'}
