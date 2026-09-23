from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(String(255), nullable=False)

    stored_filename = Column(String(255), nullable=False)

    file_path = Column(String(500), nullable=False)

    cloudinary_public_id = Column(String(500), nullable=True)

    content_type = Column(String(100), nullable=False)

    file_size = Column(Integer, nullable=False)

    status = Column(String(50), nullable=False, default="pending_review")

    advisor_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    ai_analysis = relationship("AIAnalysis", back_populates="document", uselist=False)
