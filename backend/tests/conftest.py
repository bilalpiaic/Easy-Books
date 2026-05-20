"""Shared pytest fixtures."""
import pytest


@pytest.fixture(autouse=True)
def _clear_login_throttle():
    """Login throttle is process-global; reset before every test so tests
    don't poison each other's IP counters."""
    from routers.auth import _login_attempts
    _login_attempts.clear()
    yield
    _login_attempts.clear()
