from uuid import uuid4

from app.auth.security import create_access_token, hash_password
from app.model.document import Document
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


def create_document(db_session, advisor, status="pending_review"):
    document = Document(
        filename="contract.pdf",
        stored_filename=f"{uuid4().hex}.pdf",
        file_path=f"/tmp/{uuid4().hex}.pdf",
        cloudinary_public_id=None,
        content_type="application/pdf",
        file_size=123,
        status=status,
        advisor_id=advisor.id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_review_flow_requires_compliance_officer(client, db_session):
    advisor = create_user(db_session, email=f"review-advisor-{uuid4().hex}@example.com", role="advisor")
    officer = create_user(db_session, email=f"review-officer-{uuid4().hex}@example.com", role="compliance_officer")
    document = create_document(db_session, advisor)
    advisor_token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})
    officer_token = create_access_token({"sub": str(officer.id), "role": officer.role.value})

    forbidden = client.post(
        "/api/v1/reviews",
        json={"documentId": document.id, "decision": "APPROVE", "comment": "Looks good"},
        headers={"Authorization": f"Bearer {advisor_token}"},
    )
    assert forbidden.status_code == 403

    response = client.post(
        "/api/v1/reviews",
        json={"documentId": document.id, "decision": "APPROVE", "comment": "Looks good"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["documentId"] == document.id
    assert payload["decision"] == "APPROVE"

    history = client.get(f"/api/v1/reviews/{document.id}", headers={"Authorization": f"Bearer {officer_token}"})
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_review_access_is_restricted_by_document_ownership(client, db_session):
    advisor = create_user(db_session, email=f"review-owner-{uuid4().hex}@example.com", role="advisor")
    other = create_user(db_session, email=f"review-other-{uuid4().hex}@example.com", role="advisor")
    officer = create_user(db_session, email=f"review-officer-2-{uuid4().hex}@example.com", role="compliance_officer")
    document = create_document(db_session, advisor)

    other_token = create_access_token({"sub": str(other.id), "role": other.role.value})
    officer_token = create_access_token({"sub": str(officer.id), "role": officer.role.value})

    unauthorized = client.get(f"/api/v1/reviews/{document.id}", headers={"Authorization": f"Bearer {other_token}"})
    assert unauthorized.status_code == 403

    valid = client.get(f"/api/v1/reviews/{document.id}", headers={"Authorization": f"Bearer {officer_token}"})
    assert valid.status_code == 200


def test_revision_history_and_validation_paths(client, db_session):
    advisor = create_user(db_session, email=f"revision-owner-{uuid4().hex}@example.com", role="advisor")
    token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})
    document = create_document(db_session, advisor, status="needs_revision")

    response = client.get(f"/api/v1/documents/{document.id}/revisions", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []

    invalid_document = client.get("/api/v1/documents/999999/revisions", headers={"Authorization": f"Bearer {token}"})
    assert invalid_document.status_code == 404
