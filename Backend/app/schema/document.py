from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: int
    filename: str
    content_type: str
    file_size: int
    status: str
    advisor_id: int
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)