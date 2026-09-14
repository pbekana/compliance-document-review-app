import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
PORT = int(os.getenv("PORT", "8000"))
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGIN","").split(",")
    if origin.strip()
]

