import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.service_auth import verify_internal_service_token
from app.core.config import AI_SERVICE_URL, INTERNAL_SERVICE_TOKEN
from app.db.database import get_db
from app.model.ai_analysis import AIAnalysis
from app.model.compliance_flag import ComplianceFlag
from app.model.document import Document
from app.model.revision import DocumentRevision
from app.model.user import User, UserRole
from app.schema.ai_analysis import AIAnalysisResponse
from app.schema.document import DocumentListResponse, DocumentResponse
from app.schema.revision import RevisionResponse
from app.utils.storage import generate_stored_filename, get_file_path


router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
)


ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def normalize_status(value: str | None) -> str:
    if not value:
        return "PENDING_REVIEW"
    v = str(value).strip().upper().replace("-", "_")
    mapping = {
        "PENDING_REVIEW": "PENDING_REVIEW",
        "APPROVED": "APPROVED",
        "REJECTED": "REJECTED",
        "NEEDS_REVISION": "NEEDS_REVISION",
        "REQUEST_REVISION": "NEEDS_REVISION",
        "PENDING": "PENDING_REVIEW",
    }
    return mapping.get(v, v)


def serialize_revision(revision: DocumentRevision) -> dict:
    return {
        "id": revision.id,
        "documentId": revision.document_id,
        "version": revision.version,
        "status": normalize_status(revision.status),
        "comment": revision.comment,
        "createdAt": revision.created_at,
    }


def serialize_ai_flag(flag: ComplianceFlag) -> dict:
    return {
        "severity": (flag.severity or "LOW").upper(),
        "title": flag.title,
        "passage": flag.passage,
        "matchedRule": flag.matched_rule,
        "explanation": flag.explanation,
        "page": flag.page,
    }


def serialize_ai_analysis(analysis: AIAnalysis) -> dict:
    return {
        "summary": analysis.summary,
        "flags": [serialize_ai_flag(flag) for flag in analysis.flags],
        "generatedAt": analysis.generated_at.isoformat() if analysis.generated_at else None,
    }


def serialize_document(document: Document, db: Session) -> dict:
    advisor = db.query(User).filter(User.id == document.advisor_id).first()
    revisions = (
        db.query(DocumentRevision)
        .filter(DocumentRevision.document_id == document.id)
        .order_by(DocumentRevision.version.desc())
        .all()
    )
    latest_version = revisions[0].version if revisions else 1
    latest_analysis = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.document_id == document.id)
        .order_by(AIAnalysis.generated_at.desc())
        .first()
    )

    payload = {
        "id": document.id,
        "name": document.filename,
        "filename": document.filename,
        "fileType": document.content_type,
        "fileSize": document.file_size,
        "version": latest_version,
        "submittedDate": document.created_at,
        "updatedDate": document.updated_at or document.created_at,
        "status": normalize_status(document.status),
        "advisorId": document.advisor_id,
        "advisorName": advisor.full_name if advisor else None,
        "revisions": [serialize_revision(item) for item in revisions],
    }
    if latest_analysis:
        payload["aiAnalysis"] = serialize_ai_analysis(latest_analysis)
    return payload


def get_document_for_access(document_id: int, current_user: User, db: Session) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if current_user.role == UserRole.ADVISOR and document.advisor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own documents",
        )

    return document


def load_ai_service_response(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service returned an invalid response",
        )

    summary = payload.get("summary")
    flags = payload.get("flags")
    if summary is None or flags is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service response is missing required fields",
        )
    if not isinstance(flags, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service response has invalid flag data",
        )

    normalized_flags = []
    for flag in flags:
        if not isinstance(flag, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service returned an invalid flag payload",
            )
        normalized_flags.append({
            "severity": str(flag.get("severity", "LOW")).upper(),
            "title": str(flag.get("title", "Untitled finding")),
            "passage": str(flag.get("passage", "")),
            "matchedRule": flag.get("matchedRule") or flag.get("matched_rule") or flag.get("rule"),
            "explanation": str(flag.get("explanation", "")),
            "page": flag.get("page"),
        })

    generated_at_raw = payload.get("generatedAt") or payload.get("generated_at")
    generated_at = None
    if generated_at_raw:
        try:
            generated_at = datetime.fromisoformat(str(generated_at_raw).replace("Z", "+00:00"))
        except ValueError:
            generated_at = datetime.utcnow()

    return {
        "summary": str(summary),
        "flags": normalized_flags,
        "generatedAt": generated_at,
    }


def persist_ai_analysis(document: Document, db: Session, ai_payload: dict) -> AIAnalysis:
    analysis = AIAnalysis(
        document_id=document.id,
        summary=ai_payload["summary"],
        generated_at=ai_payload["generatedAt"],
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    for flag in ai_payload["flags"]:
        db.add(ComplianceFlag(
            analysis_id=analysis.id,
            severity=flag["severity"],
            title=flag["title"],
            passage=flag["passage"],
            matched_rule=flag["matchedRule"],
            explanation=flag["explanation"],
            page=flag["page"],
        ))
    db.commit()
    return analysis


def call_ai_service_for_document(document_id: int) -> dict:
    if not AI_SERVICE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service URL is not configured",
        )

    ai_url = f"{AI_SERVICE_URL.rstrip('/')}/ai/analyze/{document_id}"
    headers = {
        "Content-Type": "application/json",
    }
    if INTERNAL_SERVICE_TOKEN:
        headers["Authorization"] = f"Bearer {INTERNAL_SERVICE_TOKEN}"
        headers["X-Internal-Service-Token"] = INTERNAL_SERVICE_TOKEN

    request = urllib.request.Request(
        ai_url,
        data=json.dumps({}).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            if not response_body:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI service returned an empty response",
                )
            return json.loads(response_body)
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service rejected the request",
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is unavailable",
        ) from exc


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors can upload documents",
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, DOCX, and XLSX files are allowed",
        )

    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A file name is required",
        )

    stored_filename = generate_stored_filename(file.filename)
    file_path = get_file_path(stored_filename)

    try:
        contents = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file",
        )

    document = Document(
        filename=file.filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        content_type=file.content_type,
        file_size=len(contents),
        status="pending_review",
        advisor_id=current_user.id,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    revision = DocumentRevision(
        document_id=document.id,
        version=1,
        stored_filename=stored_filename,
        file_path=str(file_path),
        content_type=file.content_type,
        file_size=len(contents),
        status="pending_review",
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)

    frontend_payload = serialize_document(document, db)
    return frontend_payload


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def upload_document_legacy(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await upload_document(file=file, current_user=current_user, db=db)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    advisorId: int | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if page < 1:
        page = 1
    if limit < 1:
        limit = 10

    if current_user.role == UserRole.ADVISOR:
        advisorId = current_user.id

    query = db.query(Document)

    if advisorId is not None:
        query = query.filter(Document.advisor_id == advisorId)
    if status:
        normalized_status = normalize_status(status)
        query = query.filter(Document.status == normalized_status.lower().replace("_", "_"))
    if search:
        query = query.filter(Document.filename.ilike(f"%{search}%"))

    total = query.count()
    documents = query.order_by(Document.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    items = [serialize_document(doc, db) for doc in documents]

    return {
        "documents": items,
        "total": total,
        "page": page,
        "totalPages": (total + limit - 1) // limit if total else 0,
    }


@router.get("/{id}")
def get_document_detail(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if current_user.role == UserRole.ADVISOR and document.advisor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own documents",
        )

    return serialize_document(document, db)


@router.get("/{id}/download")
def download_document(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if current_user.role == UserRole.ADVISOR and document.advisor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only download your own documents",
        )

    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.filename,
    )


@router.get("/{document_id}/file")
def get_document_file_internal(
    document_id: int,
    _: bool = Depends(verify_internal_service_token),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.filename,
    )


@router.post(
    "/{document_id}/revision",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_revision(
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors can upload revisions",
        )

    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.advisor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revise your own documents",
        )
    if document.status != "needs_revision":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only documents requiring revision can be revised",
        )
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, DOCX, and XLSX files are allowed",
        )

    latest_revision = (
        db.query(DocumentRevision)
        .filter(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.version.desc())
        .first()
    )
    next_version = (latest_revision.version + 1) if latest_revision else 1

    stored_filename = generate_stored_filename(file.filename)
    file_path = get_file_path(stored_filename)

    try:
        contents = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save revised file",
        )

    revision = DocumentRevision(
        document_id=document_id,
        version=next_version,
        stored_filename=stored_filename,
        file_path=str(file_path),
        content_type=file.content_type,
        file_size=len(contents),
        status="pending_review",
    )

    document.status = "pending_review"
    document.updated_at = None

    db.add(revision)
    db.commit()
    db.refresh(revision)

    return {
        "id": revision.id,
        "documentId": revision.document_id,
        "version": revision.version,
        "status": normalize_status(revision.status),
        "comment": revision.comment,
        "createdAt": revision.created_at,
    }


@router.get(
    "/{document_id}/revisions",
    response_model=list[RevisionResponse],
)
def get_document_revisions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if current_user.role == UserRole.ADVISOR and document.advisor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view revisions of your own documents",
        )

    revisions = (
        db.query(DocumentRevision)
        .filter(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.version.desc())
        .all()
    )

    return [
        {
            "id": item.id,
            "documentId": item.document_id,
            "version": item.version,
            "status": normalize_status(item.status),
            "comment": item.comment,
            "createdAt": item.created_at,
        }
        for item in revisions
    ]


@router.post(
    "/{document_id}/analyze",
    response_model=AIAnalysisResponse,
)
def analyze_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_document_for_access(document_id, current_user, db)

    ai_payload = call_ai_service_for_document(document_id)
    normalized_payload = load_ai_service_response(ai_payload)
    normalized_payload["generatedAt"] = normalized_payload["generatedAt"] or datetime.utcnow()

    existing_analysis = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.document_id == document_id)
        .order_by(AIAnalysis.generated_at.desc())
        .first()
    )
    if existing_analysis:
        db.delete(existing_analysis)
        db.commit()

    saved_analysis = persist_ai_analysis(document, db, normalized_payload)
    return {
        "summary": saved_analysis.summary,
        "flags": [
            {
                "severity": flag.severity,
                "title": flag.title,
                "passage": flag.passage,
                "matchedRule": flag.matched_rule,
                "explanation": flag.explanation,
                "page": flag.page,
            }
            for flag in saved_analysis.flags
        ],
        "generatedAt": saved_analysis.generated_at,
    }


@router.get(
    "/{document_id}/analysis",
    response_model=AIAnalysisResponse,
)
def get_document_analysis(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = get_document_for_access(document_id, current_user, db)

    analysis = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.document_id == document.id)
        .order_by(AIAnalysis.generated_at.desc())
        .first()
    )
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI analysis not found for this document",
        )

    return {
        "summary": analysis.summary,
        "flags": [
            {
                "severity": flag.severity,
                "title": flag.title,
                "passage": flag.passage,
                "matchedRule": flag.matched_rule,
                "explanation": flag.explanation,
                "page": flag.page,
            }
            for flag in analysis.flags
        ],
        "generatedAt": analysis.generated_at,
    }