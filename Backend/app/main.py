from fastapi import FastAPI
from app.auth.router import router as auth_router
from app.document.router import router as document_router
from app.db.database import Base, engine
from app.model.user import User

Base.metadata.create_all(bind=engine)

app = FastAPI(
title="Compliance Document Review App",
version="1.0.0"
)
app.include_router(auth_router)
@app.get("/health")
def health_check():
   return {
   "status": "healthy",
   "message": "Backend is running successfully"
   }
app.include_router(auth_router)
app.include_router(document_router)
