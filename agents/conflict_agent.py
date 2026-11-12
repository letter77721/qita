import hashlib
from services.formula_checker import compare, extract

LABELS = {'contradiction':'疑似真正矛盾','condition_difference':'条件差异',
          'missing_condition':'内容缺失','uncertain_recognition':'识别不确定'}
CONDITIONS = ('稳态','不可压','无黏','理想流体','实际流体','牛顿流体')


def diagnose(chunks, pages):
    issues = []
    def add(concept, kind, a, b, explanation):
        key = repr((concept,kind,a['document_id'],a['number'],a.get('quote',a['text']),
                    b and (b['document_id'],b['number'],b.get('quote',b['text']))))
        issues.append({'id':hashlib.sha256(key.encode()).hexdigest()[:20], 'concept':concept,
            'issue_type':kind,'severity':'medium','source_a':a,'source_b':b,
            'explanation':explanation,'suggestion':'请对照原始页面核实并补充适用条件。',
            'requires_human_review':True})
    for p in pages:
        if p['status'] == 'needs_ocr' or '[不确定]' in p['text']:
            add('页面识别', 'uncertain_recognition', p, None, '页面未识别或含无法辨认符号，需要查看原图。')
    for i,a in enumerate(chunks):
        for b in chunks[i+1:]:
            if a['document_id']==b['document_id'] or a['concept']!=b['concept']:
                continue
            ca = {c for c in CONDITIONS if c in a['quote']}
            cb = {c for c in CONDITIONS if c in b['quote']}
            if ca != cb and (ca or cb):
                kind = 'condition_difference' if ca and cb else 'missing_condition'
                add(a['concept'],kind,a,b,'对齐片段记载的条件不同：' +
                    ' / '.join(('、'.join(sorted(ca)) or '未记录条件','、'.join(sorted(cb)) or '未记录条件')) + '。片段缺失不代表整份资料缺失。')
            elif ca and ca == cb:
                fa,fb=extract(a['quote']),extract(b['quote'])
                if fa and fb and compare(fa,fb)=='different':
                    add(a['concept'],'contradiction',a,b,'已记录条件与公式符号相同，但受限代数核验发现表达式不等价。需核对符号定义、单位和原图，不能仅凭此判错。')
                # Deliberately narrow: explicit opposite assertions with identical stated conditions.
                for pos,neg in (('适用','不适用'),('成立','不成立')):
                    def polarity(text):
                        if neg in text: return -1
                        if pos in text: return 1
                        return 0
                    if polarity(a['quote'])*polarity(b['quote']) == -1:
                        add(a['concept'],'contradiction',a,b,'相同已记录条件下出现相反措辞；仍需核实语境、符号与否定范围。')
                        break
    return list({v['id']:v for v in issues}.values())
