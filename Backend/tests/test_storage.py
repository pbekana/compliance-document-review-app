from types import SimpleNamespace

from app.utils import storage


class FakeDownloadResponse:
    def __init__(self, contents):
        self.contents = contents

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.contents


def test_local_storage_writes_to_upload_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp_path)

    stored = storage.store_document(b"document", "contract.pdf", "application/pdf")

    assert stored["cloudinary_public_id"] is None
    assert stored["file_path"] == str(tmp_path / stored["stored_filename"])
    assert (tmp_path / stored["stored_filename"]).read_bytes() == b"document"


def test_cloudinary_storage_uses_authenticated_raw_upload(monkeypatch):
    calls = []

    monkeypatch.setattr(storage, "STORAGE_BACKEND", "cloudinary")
    monkeypatch.setattr(storage, "CLOUDINARY_CLOUD_NAME", "cloud")
    monkeypatch.setattr(storage, "CLOUDINARY_API_KEY", "key")
    monkeypatch.setattr(storage, "CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setattr(
        storage.cloudinary.uploader,
        "upload",
        lambda contents, **options: calls.append((contents, options)) or {"public_id": "documents/abc"},
    )

    stored = storage.store_document(b"document", "contract.pdf", "application/pdf")

    assert stored["cloudinary_public_id"] == "documents/abc"
    assert stored["file_path"] == ""
    assert calls[0][0] == b"document"
    assert calls[0][1]["resource_type"] == "raw"
    assert calls[0][1]["type"] == "authenticated"


def test_cloudinary_retrieval_downloads_private_asset_to_temporary_file(monkeypatch, tmp_path):
    calls = []
    document = SimpleNamespace(
        cloudinary_public_id="documents/abc",
        filename="contract.pdf",
        file_path="",
    )

    monkeypatch.setattr(storage, "CLOUDINARY_CLOUD_NAME", "cloud")
    monkeypatch.setattr(storage, "CLOUDINARY_API_KEY", "key")
    monkeypatch.setattr(storage, "CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setattr(
        storage,
        "private_download_url",
        lambda public_id, **options: calls.append((public_id, options)) or "https://private.example/file",
    )
    monkeypatch.setattr(
        storage.urllib.request,
        "urlopen",
        lambda url, timeout: FakeDownloadResponse(b"document"),
    )

    temporary_path = storage.materialize_document(document)

    assert temporary_path.read_bytes() == b"document"
    assert calls[0][0] == "documents/abc"
    assert calls[0][1]["type"] == "authenticated"
    assert calls[0][1]["resource_type"] == "raw"
    temporary_path.unlink()