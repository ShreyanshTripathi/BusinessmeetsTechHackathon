from shiftloop.llm.client import make_client


def test_no_credentials_means_offline(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "SHIFTLOOP_OFFLINE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", "/nonexistent")
    assert make_client() is None


def test_api_key_gives_a_client(monkeypatch):
    monkeypatch.delenv("SHIFTLOOP_OFFLINE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert make_client() is not None
