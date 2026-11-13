import json
from io import BytesIO
import urllib.error
import pytest
from services import text_model as llm

@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ('DEEPSEEK_API_KEY','DEEPSEEK_URL','DEEPSEEK_MODEL','TEXT_API_KEY','TEXT_BASE_URL','TEXT_MODEL','VISION_API_KEY'):
        monkeypatch.delenv(name,raising=False)

def test_deepseek_overrides_legacy_and_sends_structured_request(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-deepseek')
    monkeypatch.setenv('TEXT_MODEL','glm-4.7-flash')
    monkeypatch.setenv('VISION_API_KEY','test-zhipu')
    result={'question':'条件？','hint':'看教材','reference':'无黏','evidence':'无黏','needs_verification':False}
    def respond(req,**kwargs):
        assert req.full_url=='https://api.deepseek.com/v1/chat/completions'
        assert req.get_header('Authorization')=='Bearer test-deepseek'
        body=json.loads(req.data)
        assert body['model']=='deepseek-flash'
        assert body['response_format']=={'type':'json_object'}
        assert body['thinking']=={'type':'disabled'}
        return BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(result)}}]}).encode())
    monkeypatch.setattr(llm.urllib.request,'urlopen',respond)
    assert llm.generate(llm.Question,'提问',{'source':'无黏'}).needs_verification is False
    assert llm.configuration()=={'provider':'DeepSeek','model':'deepseek-flash','configured':True}

def test_legacy_key_never_sent_to_deepseek(monkeypatch):
    monkeypatch.setenv('TEXT_BASE_URL','https://api.deepseek.com/v1')
    monkeypatch.setenv('VISION_API_KEY','test-zhipu')
    assert not llm.configuration()['configured']
    with pytest.raises(llm.ModelError,match='尚未配置'):llm.generate(llm.Question,'test',{})

def test_dedicated_key_rejects_wrong_endpoint(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-deepseek')
    monkeypatch.setenv('DEEPSEEK_URL','https://example.com/chat/completions')
    with pytest.raises(llm.ModelError,match='官方 HTTPS'):llm.settings()

@pytest.mark.parametrize('status,expected',[(429,'DeepSeek 模型当前限流'),(402,'DeepSeek 账户余额不足')])
def test_deepseek_error_is_safe_and_releases_slot(monkeypatch,status,expected):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-deepseek')
    def fail(*args,**kwargs):
        raise urllib.error.HTTPError('https://api.deepseek.com',status,'error',{},BytesIO(b'{"error":{"code":"rate_limit","message":"private"}}'))
    monkeypatch.setattr(llm.urllib.request,'urlopen',fail)
    with pytest.raises(llm.ModelError,match=expected) as e:llm.generate(llm.Question,'test',{})
    assert 'private' not in str(e.value) and 'test-deepseek' not in str(e.value)
    assert llm._slot.acquire(blocking=False)
    llm._slot.release()

def test_zhipu_fallback_stays_compatible(monkeypatch):
    monkeypatch.setenv('VISION_API_KEY','test-zhipu')
    assert llm.configuration()=={'provider':'GLM','model':'glm-4.7-flash','configured':True}
