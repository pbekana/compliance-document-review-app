from fastapi import Header, HTTPException, status

from app.core.config import INTERNAL_SERVICE_TOKEN


def verify_internal_service_token(
    authorization: str | None = Header(default=None),
):
    token = INTERNAL_SERVICE_TOKEN

    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal service token is not configured",
        )

    expected = f"Bearer {token}"

    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token",
        )

    return True
