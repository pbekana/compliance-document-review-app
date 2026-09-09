from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewCreate(BaseModel):
    document_id: int
    decision: str
    comment: str


class ReviewResponse(BaseModel):
    id: int
    document_id: int
    officer_id: int
    decision: str
    comment: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
