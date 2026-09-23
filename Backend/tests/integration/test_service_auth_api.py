from uuid import uuid4

from app.auth.security import create_access_token, hash_password
from app.model.user import User, UserRole


def create_user(db_session, *, email, role="advisor"):
    user = User(
        full_name="Test User",
        email=email,
        password_hash=hash_password("StrongPass123!"),
        role=UserRole.ADVISOR if role == "advisor" else UserRole.COMPLIANCE_OFFICER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_internal_document_file_requires_service_token(client, db_session):
    advisor = create_user(db_session, email=f"svc-{uuid4().hex}@example.com", role="advisor")
    token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})

    missing = client.get("/api/v1/documents/999999/file")
    assert missing.status_code == 401

    wrong = client.get("/api/v1/documents/999999/file", headers={"Authorization": "Bearer wrong-token"})
    assert wrong.status_code == 401

    normal_user = client.get("/api/v1/documents/999999/file", headers={"Authorization": f"Bearer {token}"})
    assert normal_user.status_code == 401
