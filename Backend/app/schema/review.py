from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    documentId: int
    decision: str
    comment: str

    model_config = ConfigDict(from_attributes=True)


class OfficerInfo(BaseModel):
    id: int
    full_name: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class ReviewResponse(BaseModel):
    id: int
    documentId: int
    officerId: int
    officer: OfficerInfo | None = None
    decision: str
    comment: str
    timestamp: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
