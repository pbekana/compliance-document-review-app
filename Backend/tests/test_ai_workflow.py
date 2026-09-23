import json
from types import SimpleNamespace
from urllib.error import URLError

import pytest
from fastapi import HTTPException

from app.auth.service_auth import verify_internal_service_token
from app.document import router
from app.model.ai_analysis import AIAnalysis
from app.model.compliance_flag import ComplianceFlag


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


class RecordingDb:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)

    def commit(self):
        return None

    def refresh(self, item):
        item.id = 1


class EmptyAnalysisDb:
    def query(self, model):
        return self

    def filter(self, condition):
        return self

    def order_by(self, condition):
        return self

    def first(self):
        return None

    def all(self):
        return []


class ReplacementAnalysisDb(EmptyAnalysisDb):
    def __init__(self, analyses):
        self.analyses = analyses
        self.deleted = []
        self.commits = 0

    def all(self):
        return self.analyses

    def delete(self, analysis):
        self.deleted.append(analysis)

    def commit(self):
        self.commits += 1


def test_analyze_document_retrieves_text_calls_ai_and_persists(monkeypatch):
    document = SimpleNamespace(id=1)
    saved_analysis = SimpleNamespace(
        summary="Compliant",
        flags=[],
        generated_at=None,
    )
    calls = []

    monkeypatch.setattr(router, "get_document_for_access", lambda document_id, user, db: document)
    monkeypatch.setattr(
        router,
        "call_data_engineering_for_document",
        lambda document_id: calls.append(("extract", document_id)) or "extracted contract text",
    )
    monkeypatch.setattr(
        router,
        "call_ai_service_for_document",
        lambda document_id, extracted_text: calls.append(("ai", document_id, extracted_text)) or {"summary": "ok"},
    )
    monkeypatch.setattr(
        router,
        "load_ai_service_response",
        lambda payload: {
            "summary": "ok",
            "flags": [],
            "generatedAt": None,
        },
    )
    monkeypatch.setattr(router, "persist_ai_analysis", lambda document, db, payload: saved_analysis)

    response = router.analyze_document(1, SimpleNamespace(), EmptyAnalysisDb())

    assert calls == [("extract", 1), ("ai", 1, "extracted contract text")]
    assert response["summary"] == "Compliant"


def test_data_engineering_response_is_sent_as_exact_ai_payload(monkeypatch):
    requests = []
    responses = [
        FakeResponse({"document_id": 1, "extracted_text": "text from DE"}),
        FakeResponse({"summary": "ok", "flags": []}),
    ]

    def fake_urlopen(request, timeout):
        requests.append(request)
        return responses.pop(0)

    monkeypatch.setattr(router, "DATA_ENGINEERING_URL", "http://data-engineering:8002")
    monkeypatch.setattr(router, "AI_SERVICE_URL", "http://ai:8001")
    monkeypatch.setattr(router, "INTERNAL_SERVICE_TOKEN", "test-token")
    monkeypatch.setattr(router.urllib.request, "urlopen", fake_urlopen)

    extracted_text = router.call_data_engineering_for_document(1)
    router.call_ai_service_for_document(1, extracted_text)

    assert requests[0].full_url == "http://data-engineering:8002/documents/1/extracted-text"
    assert requests[0].method == "GET"
    assert requests[1].full_url == "http://ai:8001/ai/analyze/1"
    assert requests[1].method == "POST"
    assert json.loads(requests[1].data) == {
        "document_id": "1",
        "extracted_text": "text from DE",
    }


def test_data_engineering_rejects_mismatched_document_id(monkeypatch):
    monkeypatch.setattr(router, "DATA_ENGINEERING_URL", "http://data-engineering:8002")
    monkeypatch.setattr(
        router.urllib.request,
        "urlopen",
        lambda request, timeout: FakeResponse({"document_id": 2, "extracted_text": "wrong text"}),
    )

    with pytest.raises(HTTPException) as error:
        router.call_data_engineering_for_document(1)

    assert error.value.status_code == 502


def test_ai_response_normalizes_optional_fields_and_fallbacks():
    normalized = router.load_ai_service_response(
        {
            "summary": "Review required",
            "flags": [
                {
                    "passage_excerpt": "excerpt",
                    "matched_rule": "rule text",
                    "severity": "high",
                    "explanation": "Explain this",
                },
                {"matched_rule_id": "rule-2"},
                {},
            ],
        }
    )

    assert normalized["flags"] == [
        {
            "severity": "HIGH",
            "title": "Untitled finding",
            "passage": "excerpt",
            "matchedRule": "rule text",
            "explanation": "Explain this",
            "page": None,
        },
        {
            "severity": "LOW",
            "title": "Untitled finding",
            "passage": "",
            "matchedRule": "rule-2",
            "explanation": "",
            "page": None,
        },
        {
            "severity": "LOW",
            "title": "Untitled finding",
            "passage": "",
            "matchedRule": "Untitled finding",
            "explanation": "",
            "page": None,
        },
    ]


def test_reanalysis_deletes_all_existing_analyses_before_persisting(monkeypatch):
    previous_analysis = SimpleNamespace(id=1)
    legacy_duplicate = SimpleNamespace(id=2)
    db = ReplacementAnalysisDb([previous_analysis, legacy_duplicate])
    document = SimpleNamespace(id=1)
    latest_analysis = SimpleNamespace(summary="latest", flags=[], generated_at=None)

    monkeypatch.setattr(router, "get_document_for_access", lambda document_id, user, db: document)
    monkeypatch.setattr(router, "call_data_engineering_for_document", lambda document_id: "text")
    monkeypatch.setattr(router, "call_ai_service_for_document", lambda document_id, text: {})
    monkeypatch.setattr(
        router,
        "load_ai_service_response",
        lambda payload: {
            "summary": "latest",
            "flags": [],
            "generatedAt": None,
        },
    )
    monkeypatch.setattr(router, "persist_ai_analysis", lambda document, db, payload: latest_analysis)

    response = router.analyze_document(1, SimpleNamespace(), db)

    assert db.deleted == [previous_analysis, legacy_duplicate]
    assert db.commits == 1
    assert response["summary"] == "latest"


def test_internal_file_endpoint_requires_service_token(monkeypatch):
    monkeypatch.setattr("app.auth.service_auth.INTERNAL_SERVICE_TOKEN", "test-token")

    with pytest.raises(HTTPException) as error:
        verify_internal_service_token(None)

    assert error.value.status_code == 401


def test_ai_response_is_persisted():
    db = RecordingDb()
    analysis = router.persist_ai_analysis(
        SimpleNamespace(id=1),
        db,
        {
            "summary": "Review required",
            "generatedAt": None,
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

    assert analysis.summary == "Review required"
    assert any(isinstance(item, AIAnalysis) for item in db.added)
    assert any(isinstance(item, ComplianceFlag) for item in db.added)


def test_data_engineering_unavailable(monkeypatch):
    monkeypatch.setattr(router, "DATA_ENGINEERING_URL", "http://data-engineering:8002")
    monkeypatch.setattr(
        router.urllib.request,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(URLError("down")),
    )

    with pytest.raises(HTTPException) as error:
        router.call_data_engineering_for_document(1)

    assert error.value.status_code == 503


def test_ai_unavailable(monkeypatch):
    monkeypatch.setattr(router, "AI_SERVICE_URL", "http://ai:8001")
    monkeypatch.setattr(
        router.urllib.request,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(URLError("down")),
    )

    with pytest.raises(HTTPException) as error:
        router.call_ai_service_for_document(1, "text")

    assert error.value.status_code == 503


@pytest.mark.parametrize(
    "payload",
    [
        {"document_id": 1},
        {"document_id": 1, "extracted_text": ""},
        {"document_id": 1, "extracted_text": 42},
    ],
)
def test_missing_or_invalid_extracted_text(monkeypatch, payload):
    monkeypatch.setattr(router, "DATA_ENGINEERING_URL", "http://data-engineering:8002")
    monkeypatch.setattr(router.urllib.request, "urlopen", lambda request, timeout: FakeResponse(payload))

    with pytest.raises(HTTPException) as error:
        router.call_data_engineering_for_document(1)

    assert error.value.status_code == 502
