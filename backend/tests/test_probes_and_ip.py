"""#427 — sliding window fail-open and client IP parsing."""
from types import SimpleNamespace

from services.client_ip import client_ip
from services.sliding_window import allow, reset_memory


def test_memory_limiter_blocks_after_limit():
    reset_memory()
    mem = {}
    assert allow("t", "a", limit=2, window=60, memory=mem) is True
    assert allow("t", "a", limit=2, window=60, memory=mem) is True
    assert allow("t", "a", limit=2, window=60, memory=mem) is False


def test_redis_errors_fail_open(monkeypatch):
    reset_memory()
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")

    class Boom:
        def pipeline(self):
            raise ConnectionError("down")

    monkeypatch.setattr("services.sliding_window._redis_client", lambda: Boom())
    assert allow("t", "b", limit=1, window=60) is True
    assert allow("t", "b", limit=1, window=60) is True


def test_client_ip_ignores_xff_from_untrusted_peer(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    req = SimpleNamespace(
        client=SimpleNamespace(host="203.0.113.1"),
        headers={"x-forwarded-for": "198.51.100.9"},
    )
    assert client_ip(req) == "203.0.113.1"


def test_client_ip_uses_xff_when_peer_trusted(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "127.0.0.1")
    req = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"x-forwarded-for": "198.51.100.9, 10.0.0.1"},
    )
    assert client_ip(req) == "198.51.100.9"
