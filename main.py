"""FastAPI application exposing prompt CRUD and account/API-key management endpoints."""

from fastapi import Depends, FastAPI, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from typing import Annotated
import logging
import time
import uuid
import os
from importlib.metadata import version, PackageNotFoundError
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from auth import get_current_user_id, get_current_user_id_readonly
import schemas
from database import get_db, engine
from repository import (
    create_prompt as repo_create_prompt,
    delete_prompt as repo_delete_prompt,
    fork_prompt as repo_fork_prompt,
    get_prompt_by_slug,
    get_prompts_by_user_id,
    update_prompt as repo_update_prompt,
    create_api_key,
    get_api_keys_by_user_id,
    regenerate_api_key,
    delete_api_key,
    get_api_key_by_user_id
)

load_dotenv()


lifespan_logger = logging.getLogger("gitprompt.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код здесь выполняется ОДИН РАЗ ПРИ СТАРТЕ приложения
    lifespan_logger.info("Application startup...")
    # Можно добавить проверку соединения, если нужно
    # conn = await engine.connect()
    # await conn.close()
    yield
    lifespan_logger.info("Application shutdown...")
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

logger = logging.getLogger("gitprompt.requests")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:
        status_code = 500
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s %s %.2fms",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "GitPrompt API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


try:
    _APP_VERSION = version("gitprompt")
except PackageNotFoundError:
    _APP_VERSION = "unknown"


@app.get("/healthz")
async def healthz():
    db_status = "ok"
    db_start = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.exception("healthz db check failed")
        db_status = f"error: {e}"

    db_latency_ms = round((time.perf_counter() - db_start) * 1000, 2)
    healthy = db_status == "ok"
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "error",
            "version": _APP_VERSION,
            "db": db_status,
            "db_latency_ms": db_latency_ms,
        },
    )


def _route_uses_db(route: APIRoute) -> bool:
    seen = set()
    stack = [route.dependant]
    while stack:
        dep = stack.pop()
        if id(dep) in seen:
            continue
        seen.add(id(dep))
        if dep.call is get_db:
            return True
        stack.extend(dep.dependencies)
    return False


@app.get("/api/status")
async def api_status():
    db_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("api/status db check failed")
        db_ok = False

    routes = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is None:
            continue
        methods = sorted(getattr(route, "methods", []) or [])
        db_dependent = isinstance(route, APIRoute) and _route_uses_db(route)
        reachable = db_ok if db_dependent else True
        routes.append({
            "path": path,
            "methods": methods,
            "name": getattr(route, "name", None),
            "db_dependent": db_dependent,
            "reachable": reachable,
        })
    return {
        "status": "ok" if db_ok else "degraded",
        "version": _APP_VERSION,
        "db": "ok" if db_ok else "error",
        "route_count": len(routes),
        "routes": routes,
    }


@app.get("/prompts", response_model=schemas.PaginatedPrompts)
async def read_prompts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id_readonly)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(12, ge=1, le=100, description="Number of prompts per page"),
):
    result = await get_prompts_by_user_id(db, user_id, page, page_size)
    prompts = [schemas.PromptPublic.model_validate(prompt) for prompt in result["prompts"]]
    return schemas.PaginatedPrompts.model_validate({
        "total_prompts": result["total_prompts"],
        "total_pages": result["total_pages"],
        "current_page": result["current_page"],
        "page_size": result["page_size"],
        "prompts": prompts
    }) 


@app.post("/prompts", response_model=schemas.PromptCreateResponse, status_code=201)
async def create_prompt(
    prompt: schemas.PromptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
):
    new_prompt = await repo_create_prompt(db, user_id, prompt)
    return new_prompt


@app.get("/prompts/{prompt_slug}", response_model=schemas.PromptPublicById)
async def read_prompt(
    prompt_slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id_readonly)],
):
    prompt = await get_prompt_by_slug(db, user_id, prompt_slug)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    fork_info = None
    if prompt.forked_from:
        fork_info = schemas.ForkInfo(
            forked_from_username=prompt.forked_from.user.username
            if prompt.forked_from.user
            else None,
            forked_from_prompt_title=prompt.forked_from.title,
        )

    return schemas.PromptPublicById(
        id=prompt.id,
        title=prompt.title,
        description=prompt.description,
        visibility=schemas.Visibility(prompt.visibility),
        messages=[
            schemas.Message.model_validate(message) for message in prompt.messages
        ],
        title_slug=prompt.title_slug,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        forked_from=fork_info,
    )


@app.post(
    "/prompts/{prompt_slug}/fork", response_model=schemas.PromptPublic, status_code=201
)
async def fork_prompt(
    prompt_slug: str,
    fork_data: schemas.PromptFork,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
):
    source_prompt = await get_prompt_by_slug(db, user_id, prompt_slug)
    if not source_prompt:
        raise HTTPException(status_code=404, detail="Original prompt not found")
    new_prompt = await repo_fork_prompt(
        db,
        user_id,
        source_prompt,
        fork_data.new_title,
        fork_data.new_description,
        fork_data.new_messages,
    )
    return schemas.PromptPublic.model_validate(new_prompt)


@app.delete("/prompts/{prompt_slug}")
async def delete_prompt(
    prompt_slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
):
    prompt = await get_prompt_by_slug(db, user_id, prompt_slug)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    await repo_delete_prompt(db, prompt)
    return {"status": "deleted", "prompt_slug": prompt_slug}


@app.put("/prompts/{prompt_slug}", response_model=schemas.PromptCreateResponse)
async def update_prompt(
    prompt_slug: str,
    prompt: schemas.PromptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
):
    existing_prompt = await get_prompt_by_slug(db, user_id, prompt_slug)
    if not existing_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    updated_prompt = await repo_update_prompt(db, existing_prompt, prompt)
    return schemas.PromptCreateResponse.model_validate(updated_prompt)


@app.post("/account/generate-api-key", response_model=schemas.APIKeyCreateResponse, status_code=201)
async def generate_api_key(
    api_key_data: schemas.APIKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
):
    """Generate a new API key for the user."""
    api_key, plain_key = await create_api_key(db, user_id, api_key_data.name)
    return schemas.APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=plain_key,
        key_display=api_key.key_display,
        created_at=api_key.created_at,
    )


@app.get("/account/api-keys", response_model=list[schemas.APIKeyResponse])
async def list_api_keys(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
):
    """List all API keys for the current user."""
    api_keys = await get_api_keys_by_user_id(db, user_id)
    return [
        schemas.APIKeyResponse.model_validate(api_key)
        for api_key in api_keys
    ]


@app.post("/account/api-keys/{key_id}/regenerate", response_model=schemas.APIKeyCreateResponse, status_code=201)
async def regenerate_api_key_endpoint(
    key_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
):
    """Regenerate an API key (delete old, create new with same name)."""
    try:
        api_key, plain_key = await regenerate_api_key(db, key_id, user_id)
        return schemas.APIKeyCreateResponse(
            id=api_key.id,
            name=api_key.name,
            key=plain_key,
            key_prefix=api_key.key_prefix,
            created_at=api_key.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/account/api-keys/{key_id}")
async def delete_api_key_endpoint(
    key_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
):
    """Delete an API key. Requires JWT authentication."""
    # First verify the API key exists and belongs to the user
    api_key = await get_api_key_by_user_id(db, user_id)
    if not api_key or api_key.id != key_id:
        raise HTTPException(
            status_code=404,
            detail="API key not found or doesn't belong to user"
        )

    # Delete the API key
    await delete_api_key(db, key_id)
    return {"status": "deleted", "key_id": str(key_id)}
