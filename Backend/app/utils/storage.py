from pathlib import Path
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def generate_stored_filename(original_filename: str) -> str:
    extension = Path(original_filename).suffix.lower()

    return f"{uuid4().hex}{extension}"


def get_file_path(stored_filename: str) -> Path:
    return UPLOAD_DIR / stored_filename