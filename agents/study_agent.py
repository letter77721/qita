from datetime import datetime, timedelta, timezone

QUESTIONS = {
 '伯努利方程': ('经典理想流体伯努利方程需要哪些条件？', ['稳态、不可压、无黏，沿流线应用','所有流动均适用','只要求流速很小'],0),
 '雷诺数': ('雷诺数 Re=ρvL/μ 中 L 是什么？',['总是管道长度','按问题选取的特征长度','流体密度'],1),
 '牛顿黏性定律': ('牛顿黏性定律描述什么？',['所有流体的恒定黏度','牛顿流体剪应力与速度梯度成正比','压强与高度成正比'],1),
}


def plan(concepts, attempts):
    today = datetime.now(timezone(timedelta(hours=8))).date()
    tasks = []
    for concept in sorted(set(concepts)):
        history = [a for a in attempts if a['concept']==concept]
        recent = history[-5:]
        score = sum(a['correct'] for a in recent)/len(recent) if recent else None
        interval = 0 if not recent or not recent[-1]['correct'] else (1 if len(recent)<3 or score<0.8 else 3)
        base = datetime.fromisoformat(history[-1]['created']).replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).date() if history else today
        tasks.append({'知识点':concept,'最近正确率':f'{score:.0%}' if score is not None else '未测验',
                      '答题次数':len(history),'复习日期':str(base+timedelta(days=interval)),
                      '建议':'先核对原文，再完成测验' if interval==0 else '间隔复习，结合多次表现调整'})
    return tasks
