from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ComplianceFlagSchema(BaseModel):
    severity: str
    title: str
    passage: str
    matchedRule: str | None = None
    explanation: str
    page: int | None = None

    model_config = ConfigDict(from_attributes=True)


class AIAnalysisResponse(BaseModel):
    summary: str
    flags: list[ComplianceFlagSchema]
    generatedAt: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
