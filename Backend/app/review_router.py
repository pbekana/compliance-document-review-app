from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.model.document import Document
from app.model.review import Review
from app.model.revision import DocumentRevision
from app.model.user import User, UserRole
from app.schema.review import ReviewCreate, ReviewResponse

router = APIRouter(
    prefix="/api/v1/reviews",
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
    db: Session = Depends(get_db),
):
    if current_user.role != UserRole.COMPLIANCE_OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only compliance officers can submit reviews",
        )

    document = db.query(Document).filter(Document.id == review_data.documentId).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    allowed_decisions = {
        "APPROVE": "approved",
        "REJECT": "rejected",
        "REQUEST_REVISION": "needs_revision",
    }

    if review_data.decision not in allowed_decisions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid review decision",
        )

    review = Review(
        document_id=document.id,
        officer_id=current_user.id,
        decision=review_data.decision,
        comment=review_data.comment,
    )

    document.status = allowed_decisions[review_data.decision]
    current_revision = (
        db.query(DocumentRevision)
        .filter(
            DocumentRevision.document_id == document.id,
            DocumentRevision.status == "pending_review",
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

    response = ReviewResponse(
        id=review.id,
        documentId=review.document_id,
        officerId=review.officer_id,
        decision=review.decision,
        comment=review.comment,
        timestamp=review.created_at,
        officer={
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "role": "COMPLIANCE_OFFICER",
        },
    )
    return response


@router.get(
    "/{documentId}",
    response_model=list[ReviewResponse],
)
def get_review_history(
    documentId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == documentId).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if current_user.role == UserRole.ADVISOR and document.advisor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view reviews for your own documents",
        )

    reviews = (
        db.query(Review)
        .filter(Review.document_id == documentId)
        .order_by(Review.created_at.desc())
        .all()
    )

    result = []
    for review in reviews:
        officer = db.query(User).filter(User.id == review.officer_id).first()
        result.append(
            ReviewResponse(
                id=review.id,
                documentId=review.document_id,
                officerId=review.officer_id,
                officer={
                    "id": officer.id,
                    "full_name": officer.full_name,
                    "email": officer.email,
                    "role": "COMPLIANCE_OFFICER",
                } if officer else None,
                decision=review.decision,
                comment=review.comment,
                timestamp=review.created_at,
            )
        )

    return result
