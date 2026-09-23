from urllib.error import HTTPError, URLError
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


def create_document(db_session, advisor):
    document = Document(
        filename="contract.pdf",
        stored_filename=f"{uuid4().hex}.pdf",
        file_path=f"/tmp/{uuid4().hex}.pdf",
        cloudinary_public_id=None,
        content_type="application/pdf",
        file_size=123,
        status="pending_review",
        advisor_id=advisor.id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_analyze_document_requires_authentication(client):
    response = client.post("/api/v1/documents/999/analyze")
    assert response.status_code in {401, 403}


def test_analyze_document_rejects_unauthorized_access(client, db_session, monkeypatch):
    advisor = create_user(
        db_session,
        email=f"ai-owner-{uuid4().hex}@example.com",
        role="advisor",
    )
    other = create_user(
        db_session,
        email=f"ai-other-{uuid4().hex}@example.com",
        role="advisor",
    )
    document = create_document(db_session, advisor)
    token = create_access_token({"sub": str(other.id), "role": other.role.value})

    monkeypatch.setattr(
        "app.document.router.call_data_engineering_for_document",
        lambda document_id: "sample text",
    )
    monkeypatch.setattr(
        "app.document.router.call_ai_service_for_document",
        lambda document_id, extracted_text: {"summary": "ok", "flags": []},
    )
    monkeypatch.setattr(
        "app.document.router.load_ai_service_response",
        lambda payload: {"summary": "ok", "flags": [], "generatedAt": None},
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_ai_service_unavailable_is_handled_gracefully(client, db_session, monkeypatch):
    advisor = create_user(
        db_session,
        email=f"ai-down-{uuid4().hex}@example.com",
        role="advisor",
    )
    document = create_document(db_session, advisor)
    token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})

    monkeypatch.setattr(
        "app.document.router.call_data_engineering_for_document",
        lambda document_id: "sample text",
    )
    monkeypatch.setattr(
        "app.document.router.urllib.request.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(URLError("AI service unavailable")),
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503


def test_ai_service_422_is_handled(client, db_session, monkeypatch):
    advisor = create_user(
        db_session,
        email=f"ai-422-{uuid4().hex}@example.com",
        role="advisor",
    )
    document = create_document(db_session, advisor)
    token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})

    monkeypatch.setattr(
        "app.document.router.call_data_engineering_for_document",
        lambda document_id: "sample text",
    )

    def raise_http_422(request, timeout):
        error = HTTPError(
            request.full_url,
            422,
            "Bad request",
            hdrs=None,
            fp=None,
        )
        try:
            raise error
        finally:
            error.close()

    monkeypatch.setattr(
        "app.document.router.urllib.request.urlopen",
        raise_http_422,
    )

    response = client.post(
        f"/api/v1/documents/{document.id}/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 502


def test_successful_ai_analysis_is_persisted_and_retrieved(client, db_session, monkeypatch):
    advisor = create_user(
        db_session,
        email=f"ai-success-{uuid4().hex}@example.com",
        role="advisor",
    )
    document = create_document(db_session, advisor)
    token = create_access_token({"sub": str(advisor.id), "role": advisor.role.value})

    monkeypatch.setattr(
        "app.document.router.call_data_engineering_for_document",
        lambda document_id: "sample text",
    )
    monkeypatch.setattr(
        "app.document.router.call_ai_service_for_document",
        lambda document_id, extracted_text: {
            "summary": "Review required",
            "flags": [
                {
                    "severity": "HIGH",
                    "title": "Missing clause",
                    "passage": "clause",
                    "matchedRule": "rule-1",
                    "explanation": "Required",
                    "page": 2,
                }
            ],
        },
    )
    monkeypatch.setattr(
        "app.document.router.load_ai_service_response",
        lambda payload: {
            "summary": "Review required",
            "flags": [
                {
                    "severity": "HIGH",
                    "title": "Missing clause",
                    "passage": "clause",
                    "matchedRule": "rule-1",
                    "explanation": "Required",
                    "page": 2,
                }
            ],
            "generatedAt": None,
        },
    )

    analyze_response = client.post(
        f"/api/v1/documents/{document.id}/analyze",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert analyze_response.status_code == 200
    payload = analyze_response.json()
    assert payload["summary"] == "Review required"

    fetched = client.get(
        f"/api/v1/documents/{document.id}/analysis",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["summary"] == "Review required"
