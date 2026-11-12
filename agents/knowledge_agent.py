CONCEPTS = {
    '伯努利方程': ['伯努利', 'Bernoulli'],
    '雷诺数': ['雷诺', 'Reynolds', 'Re='],
    '沿程阻力': ['沿程', 'Darcy'],
    '局部阻力': ['局部阻力', '局部损失'],
    '牛顿黏性定律': ['牛顿黏', '牛顿粘', '黏性定律', '粘性定律'],
    '机械能方程': ['机械能方程'],
}


def organize(pages):
    result = []
    for p in pages:
        for paragraph in p['text'].splitlines():
            if not paragraph.strip():
                continue
            for concept, aliases in CONCEPTS.items():
                if any(a.lower() in paragraph.lower().replace(' ', '') for a in aliases):
                    result.append({**p,'concept':concept,'quote':paragraph.strip()})
    return result
