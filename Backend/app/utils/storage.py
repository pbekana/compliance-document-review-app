import os
import tempfile
import urllib.request
from pathlib import Path
from uuid import uuid4

import cloudinary
import cloudinary.uploader
from cloudinary.utils import private_download_url

from app.core.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
    STORAGE_BACKEND,
)

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def generate_stored_filename(original_filename: str) -> str:
    extension = Path(original_filename).suffix.lower()

    return f"{uuid4().hex}{extension}"


def get_file_path(stored_filename: str) -> Path:
    return UPLOAD_DIR / stored_filename


def is_cloudinary_enabled() -> bool:
    return STORAGE_BACKEND == "cloudinary"


def _configure_cloudinary() -> None:
    if not all((CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET)):
        raise RuntimeError("Cloudinary storage is enabled but credentials are not configured")

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )


def store_document(contents: bytes, original_filename: str, content_type: str) -> dict:
    stored_filename = generate_stored_filename(original_filename)

    if not is_cloudinary_enabled():
        file_path = get_file_path(stored_filename)
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        return {
            "stored_filename": stored_filename,
            "file_path": str(file_path),
            "cloudinary_public_id": None,
        }

    _configure_cloudinary()
    upload_result = cloudinary.uploader.upload(
        contents,
        resource_type="raw",
        type="authenticated",
        folder="documents",
        public_id=Path(stored_filename).stem,
        format=Path(stored_filename).suffix.lstrip("."),
        context={"original_filename": original_filename},
    )
    return {
        "stored_filename": stored_filename,
        "file_path": "",
        "cloudinary_public_id": upload_result["public_id"],
    }


def materialize_document(document) -> Path:
    if not document.cloudinary_public_id:
        file_path = Path(document.file_path)
        if not file_path.exists():
            raise FileNotFoundError(document.file_path)
        return file_path

    _configure_cloudinary()
    extension = Path(document.filename).suffix.lstrip(".")
    download_url = private_download_url(
        document.cloudinary_public_id,
        format=extension or None,
        resource_type="raw",
        type="authenticated",
        attachment=False,
        secure=True,
    )
    temporary_file = tempfile.NamedTemporaryFile(delete=False, suffix=Path(document.filename).suffix)
    try:
        with urllib.request.urlopen(download_url, timeout=90) as response:
            temporary_file.write(response.read())
        temporary_file.close()
    except Exception:
        temporary_file.close()
        os.unlink(temporary_file.name)
        raise
    return Path(temporary_file.name)
