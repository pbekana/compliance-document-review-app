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


def create_document(db_session, advisor, *, filename="contract.pdf", status="pending_review"):
    document = Document(
        filename=filename,
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


def test_document_upload_requires_authentication(client):
    response = client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")},
    )
    assert response.status_code in {401, 403}


def test_document_upload_and_shows_in_list(client, db_session):
    advisor = create_user(db_session, email=f"upload-{uuid4().hex}@example.com", role="advisor")
    token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})

    response = client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["filename"] == "contract.pdf"
    assert payload["status"] == "PENDING_REVIEW"

    list_response = client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert list_response.json()["documents"][0]["id"] == payload["id"]


def test_document_upload_rejects_invalid_file_type(client, db_session):
    advisor = create_user(db_session, email=f"invalid-type-{uuid4().hex}@example.com", role="advisor")
    token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})

    response = client.post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "Only PDF, DOCX, and XLSX files are allowed" in response.json()["detail"]


def test_document_details_and_download_are_available_to_owner(client, db_session):
    advisor = create_user(db_session, email=f"details-{uuid4().hex}@example.com", role="advisor")
    token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})

    upload_response = client.post(
        "/api/v1/documents",
        files={"file": ("contract.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    document_id = upload_response.json()["id"]

    detail_response = client.get(
        f"/api/v1/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == document_id

    download_response = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert download_response.status_code == 200
    assert download_response.content.startswith(b"%PDF")


def test_document_access_is_restricted_to_owner(client, db_session):
    advisor_one = create_user(db_session, email=f"owner-{uuid4().hex}@example.com", role="advisor")
    advisor_two = create_user(db_session, email=f"other-{uuid4().hex}@example.com", role="advisor")
    document = create_document(db_session, advisor_one)

    other_token = create_access_token({"sub": str(advisor_two.id), "role": advisor_two.role.value})
    response = client.get(f"/api/v1/documents/{document.id}", headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 403

    download_response = client.get(
        f"/api/v1/documents/{document.id}/download",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert download_response.status_code == 403


def test_missing_document_returns_not_found(client, db_session):
    advisor = create_user(db_session, email=f"missing-doc-{uuid4().hex}@example.com", role="advisor")
    token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})

    response = client.get("/api/v1/documents/999999", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404

    file_response = client.get("/api/v1/documents/999999/file", headers={"Authorization": "Bearer test-internal-token"})
    assert file_response.status_code == 404
