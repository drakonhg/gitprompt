import os
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import AsyncClient, acreate_client
from dotenv import load_dotenv
from typing import Annotated

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
bearer_scheme = HTTPBearer()


async def get_supabase_client() -> AsyncClient:
    return await acreate_client(SUPABASE_URL, SUPABASE_KEY)


async def get_supabase_client_with_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> AsyncClient:
    client = await acreate_client(SUPABASE_URL, SUPABASE_KEY)
    client.postgrest.auth(credentials.credentials)
    return client


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    supabase: Annotated[AsyncClient, Depends(get_supabase_client)]
) -> UUID:

    token = credentials.credentials
    try:
        user_response = await supabase.auth.get_user(token)
        user_id = user_response.user.id
        return user_id
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
