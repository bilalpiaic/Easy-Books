"""FRONTEND_ORIGIN parsing — CORS twins and email-link first origin."""
from services.frontend_origin import frontend_public_origin, parse_frontend_origins


def test_default_includes_localhost_and_loopback():
    origins = parse_frontend_origins("")
    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3000" in origins
    assert frontend_public_origin("") == "http://localhost:3000"


def test_localhost_gains_loopback_twin():
    origins = parse_frontend_origins("http://localhost:3000")
    assert origins[0] == "http://localhost:3000"
    assert "http://127.0.0.1:3000" in origins


def test_loopback_gains_localhost_twin():
    origins = parse_frontend_origins("http://127.0.0.1:3000")
    assert origins[0] == "http://127.0.0.1:3000"
    assert "http://localhost:3000" in origins


def test_comma_list_strips_and_uses_first_for_emails():
    raw = " https://app.example.com/ , http://localhost:3000 "
    origins = parse_frontend_origins(raw)
    assert origins[0] == "https://app.example.com"
    assert frontend_public_origin(raw) == "https://app.example.com"
    # production origin is not twinned with localhost
    assert "https://127.0.0.1" not in "".join(origins)


def test_production_origin_keeps_https_first():
    origins = parse_frontend_origins("https://books.example.com")
    assert origins[0] == "https://books.example.com"
    assert "capacitor://localhost" in origins
    assert "https://localhost" in origins
