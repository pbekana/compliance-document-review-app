import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
PORT = int(os.getenv("PORT", "8000"))
DATA_ENGINEERING_URL = os.getenv("DATA_ENGINEERING_URL")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN")
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGIN","").split(",")
    if origin.strip()
]

