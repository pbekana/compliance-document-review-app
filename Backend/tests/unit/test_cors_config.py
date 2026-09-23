import os

from app.core import config


def test_cors_origins_are_parsed_into_multiple_entries():
    original = os.environ.get("CORS_ORIGIN")
    os.environ["CORS_ORIGIN"] = (
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,"
        "https://compliance-document-review-frontend.vercel.app"
    )
    try:
        import importlib

        importlib.reload(config)
        assert config.CORS_ORIGINS == [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "https://compliance-document-review-frontend.vercel.app",
        ]
    finally:
        if original is None:
            os.environ.pop("CORS_ORIGIN", None)
        else:
            os.environ["CORS_ORIGIN"] = original
        importlib.reload(config)
