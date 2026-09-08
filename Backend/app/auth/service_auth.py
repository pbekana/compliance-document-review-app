import os

from fastapi import Header, HTTPException, status


INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN")


def verify_internal_service_token(
    authorization: str | None = Header(default=None),
):
    if not INTERNAL_SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal service token is not configured",
        )

    expected = f"Bearer {INTERNAL_SERVICE_TOKEN}"

    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token",
        )

    return True
