import base64
import json
import os
import urllib.request
import urllib.error
import threading
from io import BytesIO
from urllib.parse import urlparse

GLM_BASE = 'https://open.bigmodel.cn/api/paas/v4'
GLM_MODEL = 'glm-4.6v-flash'
_slots = threading.Semaphore(1)


class VisionError(ValueError):
    """Safe user-visible error; never contains provider payload or credentials."""


def settings():
    return (os.getenv('VISION_BASE_URL') or GLM_BASE, os.getenv('VISION_MODEL') or GLM_MODEL)


def configured():
    return bool(os.getenv('VISION_API_KEY','').strip())


def prepare(data):
    from PIL import Image, ImageOps
    with Image.open(BytesIO(data)) as im:
        image=ImageOps.exif_transpose(im).convert('RGB')
        image.thumbnail((4000,4000))
        for quality in (95,85,75):
            out=BytesIO(); image.save(out,format='JPEG',quality=quality)
            if out.tell()<5*1024*1024: return out.getvalue()
    raise VisionError('图片仍过大，请裁剪或缩小后再识别。')


def recognize(data, mime):
    if not configured():
        raise VisionError('尚未配置 VISION_API_KEY，请在后端环境变量中填写智谱 API Key。')
    base,model=settings()
    is_glm=urlparse(base).hostname=='open.bigmodel.cn'
    if is_glm:
        data=prepare(data); mime='image/jpeg'
    payload = {'model': model, 'temperature': 0.1,'max_tokens':8192,'stream':False,
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': '仅转录图中的文字、公式和标题，保留条件和符号。公式用 LaTeX。无法辨认处写 [不确定]，不要补全或推断内容。'},
            {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,' + base64.b64encode(data).decode()}}
        ]}]}
    if is_glm:
        payload['thinking']={'type':'disabled'}
    req = urllib.request.Request(base.rstrip('/') + '/chat/completions',
        data=json.dumps(payload).encode(), headers={'Content-Type':'application/json',
        'Authorization':'Bearer ' + os.environ['VISION_API_KEY']})
    try:
        with _slots, urllib.request.urlopen(req, timeout=120) as response:
            result=json.load(response)
        choice=result['choices'][0]
        if choice.get('finish_reason')=='length': raise VisionError('识别结果超出长度限制，请把页面拆成较小区域后重试。')
        content=choice['message']['content']
    except urllib.error.HTTPError as e:
        message={401:'模型密钥无效，请检查 VISION_API_KEY。',403:'该账号无权调用配置的视觉模型，请检查智谱控制台。',
                 429:'视觉模型触发限流，请稍后手动重试。'}
        raise VisionError(message.get(e.code,'视觉服务拒绝请求，请检查模型名称、权限和图片格式。')) from None
    except (urllib.error.URLError,TimeoutError):
        raise VisionError('视觉服务连接失败或超时，请稍后重试。') from None
    except (KeyError,IndexError,TypeError,json.JSONDecodeError):
        raise VisionError('视觉服务返回了无法解析的结果。') from None
    if not isinstance(content, str) or not content.strip():
        raise VisionError('视觉模型没有返回可用文本')
    return content
