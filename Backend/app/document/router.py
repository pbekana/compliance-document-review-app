import os
from app.auth.service_auth import verify_internal_service_token
from fastapi import Header
from app.model.revision import DocumentRevision
from app.schema.revision import RevisionResponse
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status
)
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse
from pathlib import Path
from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.model.document import Document
from app.model.user import User, UserRole
from app.schema.document import DocumentResponse
from app.utils.storage import (
    generate_stored_filename,
    get_file_path
)


router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors can upload documents"
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, DOCX, and XLSX files are allowed"
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
            detail="Failed to save uploaded file"
        )

    document = Document(
        filename=file.filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        content_type=file.content_type,
        file_size=len(contents),
        status="pending_review",
        advisor_id=current_user.id
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
    status="pending_review"
)

    db.add(revision)
    db.commit()

    return document
@router.get("/{document_id}/file")
async def get_document_file(
    document_id: int,
    _: None = Depends(verify_internal_service_token),
    db: Session = Depends(get_db)
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    file_path = Path(document.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found"
        )

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.filename
    )
@router.post(
    "/{document_id}/revision",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_revision(
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors can upload revisions"
        )

    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if document.advisor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revise your own documents"
        )

    if document.status != "needs_revision":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only documents requiring revision can be revised"
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, DOCX, and XLSX files are allowed"
        )

    from app.model.revision import DocumentRevision
    from app.schema.revision import RevisionResponse

    latest_revision = (
        db.query(DocumentRevision)
        .filter(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.version.desc())
        .first()
    )

    next_version = (
        latest_revision.version + 1
        if latest_revision
        else 2
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
            detail="Failed to save revised file"
        )

    revision = DocumentRevision(
        document_id=document_id,
        version=next_version,
        stored_filename=stored_filename,
        file_path=str(file_path),
        content_type=file.content_type,
        file_size=len(contents),
        status="pending_review"
    )

    document.status = "pending_review"
    document.updated_at = None

    db.add(revision)
    db.commit()
    db.refresh(revision)

    return revision
@router.post(
    "/{document_id}/revision",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_revision(
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.ADVISOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only advisors can upload revisions"
        )

    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if document.advisor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revise your own documents"
        )

    if document.status != "needs_revision":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only documents requiring revision can be revised"
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, DOCX, and XLSX files are allowed"
        )

    latest_revision = (
        db.query(DocumentRevision)
        .filter(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.version.desc())
        .first()
    )

    if not latest_revision:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No existing revision found"
        )

    next_version = latest_revision.version + 1

    stored_filename = generate_stored_filename(file.filename)
    file_path = get_file_path(stored_filename)

    try:
        contents = await file.read()

        with open(file_path, "wb") as buffer:
            buffer.write(contents)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save revised file"
        )

    revision = DocumentRevision(
        document_id=document.id,
        version=next_version,
        stored_filename=stored_filename,
        file_path=str(file_path),
        content_type=file.content_type,
        file_size=len(contents),
        status="pending_review"
    )

    document.status = "pending_review"

    db.add(revision)
    db.commit()
    db.refresh(revision)

    return revision
@router.get(
    "/{document_id}/revisions",
    response_model=list[RevisionResponse]
)
def get_document_revisions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Advisors can only see their own document revisions.
    # Compliance officers can see any document revisions.
    if (
        current_user.role == UserRole.ADVISOR
        and document.advisor_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view revisions of your own documents"
        )

    if current_user.role not in {
        UserRole.ADVISOR,
        UserRole.COMPLIANCE_OFFICER
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view revisions"
        )

    revisions = (
        db.query(DocumentRevision)
        .filter(DocumentRevision.document_id == document_id)
        .order_by(DocumentRevision.version.desc())
        .all()
    )

    return revisions