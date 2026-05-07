import pytest
from auth import get_password_hash, verify_password, create_access_token
from jose import jwt

def test_password_hashing():
    password = "secret-password"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False

def test_create_access_token():
    data = {"sub": "user@example.com", "tenant_id": 1}
    token = create_access_token(data)
    assert token is not None
    
    # Secret key should match what's in auth.py for testing
    # In a real app, we'd use a config/env variable
    from auth import SECRET_KEY, ALGORITHM
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "user@example.com"
    assert payload["tenant_id"] == 1
    assert "exp" in payload
