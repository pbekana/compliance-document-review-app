from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.auth.dependencies import get_current_user
from app.auth.security import ALGORITHM, SECRET_KEY, create_access_token, hash_password, verify_password
from app.model.user import User, UserRole


def test_password_hashing_and_verification():
    raw_password = "StrongPass123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_invalid_passwords_and_long_passwords():
    hashed = hash_password("valid-password")
    assert verify_password("invalid-password", hashed) is False

    with pytest.raises(ValueError):
        hash_password("a" * 1000)


def test_valid_jwt_is_accepted(db_session):
    user = User(
        full_name="Test User",
        email="valid-jwt@example.com",
        password_hash=hash_password("TestPassword123!"),
        role=UserRole.ADVISOR,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    current_user = get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db_session)

    assert current_user.id == user.id


def test_invalid_jwt_is_rejected(db_session):
    with pytest.raises(HTTPException):
        get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-real-token"), db_session)


def test_expired_jwt_is_rejected(db_session):
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException):
        get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired), db_session)


def test_missing_or_unknown_user_is_rejected(db_session):
    missing_user_token = create_access_token({"sub": "999999", "role": "advisor"})

    with pytest.raises(HTTPException):
        get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=missing_user_token), db_session)

    invalid_user_token = create_access_token({"sub": "abc", "role": "advisor"})
    with pytest.raises(HTTPException):
        get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=invalid_user_token), db_session)
