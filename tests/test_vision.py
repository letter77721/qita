import json
from io import BytesIO
import urllib.error
import pytest
from PIL import Image
from services import ocr_service as vision


def image():
    b=BytesIO();Image.new('RGB',(32,32),'white').save(b,format='PNG');return b.getvalue()


def test_glm_payload_and_transcription(monkeypatch):
    monkeypatch.setenv('VISION_API_KEY','test-only-key')
    monkeypatch.delenv('VISION_BASE_URL',raising=False)
    monkeypatch.delenv('VISION_MODEL',raising=False)
    def fake(req,timeout):
        body=json.loads(req.data)
        assert req.full_url==vision.GLM_BASE+'/chat/completions'
        assert body['model']=='glm-4.6v-flash' and body['thinking']['type']=='disabled'
        assert body['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
        return BytesIO(json.dumps({'choices':[{'message':{'content':'雷诺数 Re=ρvL/μ'},'finish_reason':'stop'}]}).encode())
    monkeypatch.setattr(vision.urllib.request,'urlopen',fake)
    assert vision.recognize(image(),'image/png')=='雷诺数 Re=ρvL/μ'


def test_limited_request_reports_safe_error(monkeypatch):
    monkeypatch.setenv('VISION_API_KEY','test-only-key')
    def fake(*a,**k): raise urllib.error.HTTPError('https://example',429,'secret raw response',{},None)
    monkeypatch.setattr(vision.urllib.request,'urlopen',fake)
    with pytest.raises(vision.VisionError,match='限流'): vision.recognize(image(),'image/png')


def test_no_credentials_no_model_call(monkeypatch):
    monkeypatch.delenv('VISION_API_KEY',raising=False)
    assert not vision.configured()
    with pytest.raises(vision.VisionError,match='VISION_API_KEY'): vision.recognize(b'','image/png')
