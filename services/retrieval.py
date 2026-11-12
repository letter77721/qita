def search(pages, query):
    terms = query.lower().split()
    if not terms:
        return []
    results = []
    for p in pages:
        for line in p['text'].splitlines():
            score = sum(t in line.lower() for t in terms)
            if score:
                results.append({**p, 'quote':line, 'score':score})
    return sorted(results, key=lambda r:r['score'], reverse=True)[:30]
