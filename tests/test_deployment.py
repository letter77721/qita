import pytest
from fastapi.testclient import TestClient
from database.storage import Store
from backend import main as api


def test_production_refuses_unprotected_data(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'store',Store(tmp_path/'test.db'))
    monkeypatch.setenv('NOTEPILOT_ENV','production')
    monkeypatch.delenv('NOTEPILOT_TOKEN',raising=False)
    with pytest.raises(RuntimeError,match='NOTEPILOT_TOKEN'):
        with TestClient(api.app): pass


def test_production_health_public_but_records_require_token(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'store',Store(tmp_path/'test.db'))
    monkeypatch.setenv('NOTEPILOT_ENV','production')
    monkeypatch.setenv('NOTEPILOT_TOKEN','test-only-token')
    with TestClient(api.app) as client:
        assert client.get('/api/health').status_code==200
        assert client.get('/api/export').status_code==401
        assert client.get('/api/export',headers={'Authorization':'Bearer test-only-token'}).status_code==200
