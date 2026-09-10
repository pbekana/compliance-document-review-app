from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.document.router import router as document_router
from app.review_router import router as review_router
from app.core.config import CORS_ORIGINS
from app.db.database import Base, engine
from app.model.ai_analysis import AIAnalysis
from app.model.compliance_flag import ComplianceFlag

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Compliance Document Review App",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(document_router)
app.include_router(review_router)


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "message": "Backend is running successfully"
    }