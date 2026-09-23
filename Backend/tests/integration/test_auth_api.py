from uuid import uuid4

from app.auth.security import create_access_token, hash_password
from app.model.user import User, UserRole


def create_user(db_session, *, email, role="advisor", password="StrongPass123!"):
    user = User(
        full_name="Test User",
        email=email,
        password_hash=hash_password(password),
        role=UserRole.ADVISOR if role == "advisor" else UserRole.COMPLIANCE_OFFICER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_signup_success(client, db_session):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Alice Advisor",
            "email": f"alice-{uuid4().hex}@example.com",
            "password": "StrongPassword123!",
            "role": "advisor",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["email"]
    assert payload["token"]


def test_signup_rejects_duplicate_email(client, db_session):
    email = f"dup-{uuid4().hex}@example.com"
    create_user(db_session, email=email, role="advisor")

    response = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "Alice Advisor",
            "email": email,
            "password": "StrongPassword123!",
            "role": "advisor",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email is already registered"


def test_signup_rejects_invalid_payload(client):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "full_name": "A",
            "email": "not-an-email",
            "password": "short",
            "role": "advisor",
        },
    )

    assert response.status_code == 422


def test_login_success(client, db_session):
    email = f"login-{uuid4().hex}@example.com"
    create_user(db_session, email=email, role="advisor")

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == email
    assert payload["token"]


def test_login_rejects_incorrect_password(client, db_session):
    email = f"bad-pass-{uuid4().hex}@example.com"
    create_user(db_session, email=email, role="advisor")

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401


def test_login_rejects_unknown_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "missing-user@example.com",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code in {401, 403}


def test_me_returns_authenticated_user(client, db_session):
    user = create_user(db_session, email=f"me-{uuid4().hex}@example.com", role="advisor")
    token = create_access_token({"sub": str(user.id), "role": user.role.value})

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()["user"]
    assert payload["id"] == user.id
    assert payload["email"] == user.email


def test_me_rejects_invalid_jwt(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert response.status_code in {401, 403}
