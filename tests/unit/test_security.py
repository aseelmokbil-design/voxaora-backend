"""Unit tests for security utilities"""
import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_token, create_refresh_token


def test_password_hashing():
    password = "SecurePassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)


def test_wrong_password_fails():
    hashed = hash_password("correct_password")
    assert not verify_password("wrong_password", hashed)


def test_access_token_roundtrip():
    data = {"sub": "user-uuid-123", "role": "customer"}
    token = create_access_token(data)
    decoded = decode_token(token)
    assert decoded["sub"] == "user-uuid-123"
    assert decoded["role"] == "customer"
    assert decoded["type"] == "access"


def test_refresh_token_type():
    data = {"sub": "user-uuid-456"}
    token = create_refresh_token(data)
    decoded = decode_token(token)
    assert decoded["type"] == "refresh"


def test_invalid_token_raises():
    with pytest.raises(ValueError):
        decode_token("not.a.valid.token")
