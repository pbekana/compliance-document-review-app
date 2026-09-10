from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    id: int
    name: str | None = None
    filename: str | None = None
    fileType: str | None = None
    fileSize: int | None = None
    version: int | None = None
    submittedDate: datetime | None = None
    updatedDate: datetime | None = None
    status: str | None = None
    advisorId: int | None = None
    advisorName: str | None = None
    revisions: list[dict] | None = None
    aiAnalysis: dict | None = None
    content_type: str | None = None
    file_size: int | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    page: int
    totalPages: int

    model_config = ConfigDict(from_attributes=True)