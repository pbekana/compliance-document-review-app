from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RevisionResponse(BaseModel):
    id: int
    document_id: int
    version: int
    status: str
    comment: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)