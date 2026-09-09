from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.model.document import Document
from app.model.review import Review
from app.model.user import User, UserRole
from app.schema.review import ReviewCreate, ReviewResponse
from app.model.revision import DocumentRevision

router = APIRouter(
    prefix="/reviews",
    tags=["Reviews"]
)


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED
)
def submit_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.COMPLIANCE_OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only compliance officers can submit reviews"
        )

    document = (
        db.query(Document)
        .filter(Document.id == review_data.document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    allowed_decisions = {
        "APPROVE": "approved",
        "REJECT": "rejected",
        "REQUEST_REVISION": "needs_revision"
    }

    if review_data.decision not in allowed_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid review decision"
        )

    review = Review(
        document_id=document.id,
        officer_id=current_user.id,
        decision=review_data.decision,
        comment=review_data.comment
    )

    document.status = allowed_decisions[review_data.decision]
    current_revision = (
    db.query(DocumentRevision)
    .filter(
        DocumentRevision.document_id == document.id,
        DocumentRevision.status == "pending_review"
    )
    .order_by(DocumentRevision.version.desc())
    .first()
)

    if current_revision:
      current_revision.status = allowed_decisions[review_data.decision]
      current_revision.comment = review_data.comment

      db.add(review)
      db.commit()
      db.refresh(review)

    return review


@router.get(
    "/{document_id}",
    response_model=list[ReviewResponse]
)
def get_review_history(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != UserRole.COMPLIANCE_OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only compliance officers can view review history"
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

    reviews = (
        db.query(Review)
        .filter(Review.document_id == document_id)
        .order_by(Review.created_at.desc())
        .all()
    )

    return reviews
