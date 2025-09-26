import os
from dataclasses import dataclass
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from supabase import AsyncClient, acreate_client
from dotenv import load_dotenv
from typing import Annotated
import hashlib

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
bearer_scheme = HTTPBearer()
api_key_header = APIKeyHeader(name="X-API-Key")


@dataclass
class AuthResult:
    user_id: UUID
    is_api_key: bool


async def get_supabase_client() -> AsyncClient:
    return await acreate_client(SUPABASE_URL, SUPABASE_KEY)


async def get_supabase_client_with_api_key(
    api_key: Annotated[str, Depends(api_key_header)],
    supabase: Annotated[AsyncClient, Depends(get_supabase_client)],
):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "APIKey"},
        )
    
    if not api_key.startswith("gpk_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "APIKey"},
        )
    
    key_prefix = api_key[:7]
    try:
        api_key_result = await supabase.table("api_keys") \
            .select("user_id, key_hash, salt, name") \
            .eq("key_prefix", key_prefix) \
            .eq("is_active", True) \
            .single() \
            .execute()
        if not api_key_result.data:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key not found or inactive")
        
        api_key_record = api_key_result.data
        key_with_salt = f"{api_key}{api_key_record.get('salt')}".encode()
        computed_hash = hashlib.sha256(key_with_salt).hexdigest()
        
        if computed_hash != api_key_record['key_hash']:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "APIKey"},
            )
        
        # FOR THE FUTURE MAYBE ADD EXPIRATION LOGIC
        
        user_id = api_key_record['user_id']
        
        # Update last_used_at
        await supabase.table("api_keys") \
            .update({"last_used_at": "now()"}) \
            .eq("key_prefix", key_prefix) \
            .execute()
        return user_id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication service error",
            headers={"WWW-Authenticate": "APIKey"},
        )


async def get_supabase_client_with_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> AsyncClient:
    client = await acreate_client(SUPABASE_URL, SUPABASE_KEY)
    client.postgrest.auth(credentials.credentials)
    return client


async def get_current_user_from_jwt(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    supabase: Annotated[AsyncClient, Depends(get_supabase_client)]
):
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


async def get_current_user_id(
    user_id_by_jwt: Annotated[UUID | None, Depends(get_current_user_from_jwt)],
    user_id_by_api_key: Annotated[UUID | None, Depends(get_supabase_client_with_api_key)]
):
    return user_id_by_jwt or user_id_by_api_key
