from agents.parser_agent import parse
from agents.knowledge_agent import organize
from agents.conflict_agent import diagnose
from agents.study_agent import plan
from database.storage import Store
from workflows.graph import run


def page(id,text,status='extracted'):
    return dict(document_id=id,number=1,text=text,status=status,name=id,kind='课堂笔记',path='')


def test_parser_and_storage(tmp_path):
    parsed = parse('雷诺数'.encode(),'笔记.txt')
    s = Store(tmp_path/'db.sqlite')
    assert s.add('a','笔记.txt','课堂笔记','a.txt',parsed)
    assert not s.add('a','笔记.txt','课堂笔记','a.txt',parsed)
    s.correct('a',1,'雷诺数 Re=ρvL/μ')
    assert s.pages()[0]['original']=='雷诺数'
    assert s.pages()[0]['status']=='verified'


def test_different_conditions_not_contradiction():
    pages=[page('a','伯努利方程：理想流体适用'),page('b','伯努利方程：实际流体不适用')]
    results=diagnose(organize(pages),pages)
    assert [r['issue_type'] for r in results]==['condition_difference']


def test_missing_and_uncertain():
    pages=[page('a','伯努利方程沿流线'),page('b','伯努利方程稳态、无黏'),page('c','','needs_ocr')]
    assert {i['issue_type'] for i in run(pages)['issues']}=={'missing_condition','uncertain_recognition'}


def test_opposite_same_conditions():
    pages=[page('a','伯努利方程：稳态适用'),page('b','伯努利方程：稳态不适用')]
    assert diagnose(organize(pages),pages)[0]['issue_type']=='contradiction'


def test_study_changes_after_feedback():
    attempts=[dict(concept='雷诺数',correct=1,created='2026-11-11 00:00:00')]*3
    assert plan(['雷诺数'],attempts)[0]['复习日期']=='2026-11-14'
    attempts.append(dict(concept='雷诺数',correct=0,created='2026-11-11 00:00:00'))
    assert plan(['雷诺数'],attempts)[0]['复习日期']=='2026-11-11'
