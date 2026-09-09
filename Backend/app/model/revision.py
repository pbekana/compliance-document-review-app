from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.db.database import Base


class DocumentRevision(Base):
    __tablename__ = "document_revisions"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False
    )

    version = Column(
        Integer,
        nullable=False
    )

    stored_filename = Column(
        String(255),
        nullable=False
    )

    file_path = Column(
        String(500),
        nullable=False
    )

    content_type = Column(
        String(100),
        nullable=False
    )

    file_size = Column(
        Integer,
        nullable=False
    )

    status = Column(
        String(50),
        nullable=False,
        default="pending_review"
    )

    comment = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
