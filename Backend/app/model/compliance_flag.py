from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class ComplianceFlag(Base):
    __tablename__ = "compliance_flags"

    id = Column(Integer, primary_key=True, index=True)

    analysis_id = Column(
        Integer,
        ForeignKey("ai_analysis.id"),
        nullable=False,
    )

    severity = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    passage = Column(Text, nullable=False)
    matched_rule = Column(String(255), nullable=True)
    explanation = Column(Text, nullable=False)
    page = Column(Integer, nullable=True)

    analysis = relationship("AIAnalysis", back_populates="flags")
