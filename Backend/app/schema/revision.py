from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RevisionResponse(BaseModel):
    id: int
    documentId: int
    version: int
    status: str
    comment: str | None = None
    createdAt: datetime | None = None

    model_config = ConfigDict(from_attributes=True)