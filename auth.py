import os
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from repository import get_api_key_by_key

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

bearer_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db)
) -> UUID:
    """
    Authentication for write operations - JWT tokens only.
    API keys are rejected for write operations.
    """
    token = credentials.credentials

    # Validate JWT token (write operations require JWT)
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience="authenticated",
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return UUID(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for write operations",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id_readonly(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db)
) -> UUID:
    """
    Authentication for read operations - supports both JWT tokens and API keys.
    Both are passed as Bearer tokens in the Authorization header.

    For JWT tokens: "Authorization: Bearer <jwt_token>"
    For API keys: "Authorization: Bearer <api_key>"
    """
    token = credentials.credentials

    # First, try to decode as JWT token
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience="authenticated",
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return UUID(user_id_str)
    except (JWTError, ValueError):
        # If JWT decoding fails, try as API key
        pass

    # Try to validate as API key (for read-only operations)
    api_key_record = await get_api_key_by_key(db, token)
    if api_key_record:
        return api_key_record.user_id

    # If both methods fail, return 401
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials. Provide either a valid JWT token or API key for read operations.",
        headers={"WWW-Authenticate": "Bearer"},
    )
