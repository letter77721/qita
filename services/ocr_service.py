import base64
import json
import os
import urllib.request


def configured():
    return all(os.getenv(k) for k in ('VISION_BASE_URL','VISION_API_KEY','VISION_MODEL'))


def recognize(data, mime):
    if not configured():
        raise ValueError('请配置 .env 中的视觉模型，或手动录入并核验文字。')
    payload = {'model': os.environ['VISION_MODEL'], 'temperature': 0,
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': '仅转录图中的文字、公式和标题，保留条件和符号。公式用 LaTeX。无法辨认处写 [不确定]，不要补全或推断内容。'},
            {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,' + base64.b64encode(data).decode()}}
        ]}]}
    req = urllib.request.Request(os.environ['VISION_BASE_URL'].rstrip('/') + '/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type':'application/json',
        'Authorization':'Bearer ' + os.environ['VISION_API_KEY']})
    with urllib.request.urlopen(req, timeout=90) as response:
        content = json.load(response)['choices'][0]['message']['content']
    if not isinstance(content, str) or not content.strip():
        raise ValueError('视觉模型没有返回可用文本')
    return content
