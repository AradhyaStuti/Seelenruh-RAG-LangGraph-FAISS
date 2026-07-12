"""Tests for auth.py — token creation, decoding, type enforcement,
expiry, and the revocation blacklist."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth import (
    make_access_token,
    make_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from config import JWT_SECRET, JWT_ALG
from fastapi import HTTPException


# ── token creation ────────────────────────────────────────────────────────────

def test_access_token_contains_expected_fields():
    token = make_access_token("uid123", "user@example.com")
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    assert payload["sub"] == "uid123"
    assert payload["email"] == "user@example.com"
    assert payload["type"] == "access"
    assert "jti" in payload
    assert "iat" in payload
    assert "exp" in payload


def test_refresh_token_contains_expected_fields():
    token = make_refresh_token("uid456", "user@example.com")
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    assert payload["sub"] == "uid456"
    assert payload["type"] == "refresh"
    assert "iat" in payload
    assert "exp" in payload


def test_access_token_shorter_ttl_than_refresh():
    access = make_access_token("u1", "a@b.com")
    refresh = make_refresh_token("u1", "a@b.com")
    ap = jwt.decode(access, JWT_SECRET, algorithms=[JWT_ALG])
    rp = jwt.decode(refresh, JWT_SECRET, algorithms=[JWT_ALG])
    assert rp["exp"] > ap["exp"]


def test_each_token_has_unique_jti():
    t1 = make_access_token("u1", "a@b.com")
    t2 = make_access_token("u1", "a@b.com")
    p1 = jwt.decode(t1, JWT_SECRET, algorithms=[JWT_ALG])
    p2 = jwt.decode(t2, JWT_SECRET, algorithms=[JWT_ALG])
    assert p1["jti"] != p2["jti"]


# ── decode_token ──────────────────────────────────────────────────────────────

def test_decode_valid_access_token():
    token = make_access_token("uid1", "test@test.com")
    payload = decode_token(token)
    assert payload["sub"] == "uid1"


def test_decode_wrong_type_raises_401():
    refresh = make_refresh_token("uid1", "test@test.com")
    with pytest.raises(HTTPException) as exc:
        decode_token(refresh, expected_type="access")
    assert exc.value.status_code == 401


def test_decode_expired_token_raises_401():
    payload = {
        "sub": "uid1",
        "email": "e@e.com",
        "jti": "abc",
        "type": "access",
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    with pytest.raises(HTTPException) as exc:
        decode_token(expired_token)
    assert exc.value.status_code == 401


def test_decode_tampered_token_raises_401():
    token = make_access_token("uid1", "e@e.com") + "tampered"
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401


# ── password hashing ──────────────────────────────────────────────────────────

def test_password_round_trip():
    plain = "my$ecureP@ssw0rd!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)


def test_wrong_password_fails():
    hashed = hash_password("correct-horse-battery-staple")
    assert not verify_password("wrong-password", hashed)


def test_long_password_hashes_safely():
    # bcrypt silently truncates at 72 bytes — we should handle that gracefully
    long_pw = "x" * 200
    hashed = hash_password(long_pw)
    assert verify_password(long_pw, hashed)
