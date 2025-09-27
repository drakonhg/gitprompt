from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated, List
import uuid 
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

import auth
import schemas
from database import get_db
from repository import (
    create_prompt as repo_create_prompt,
    delete_prompt as repo_delete_prompt,
    fork_prompt as repo_fork_prompt,
    get_prompt_by_slug,
    get_prompts_by_user_id,
    update_prompt as repo_update_prompt,
)

load_dotenv()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN")],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "GitPrompt API is running"}

@app.get("/prompts", response_model=List[schemas.PromptPublic])
async def read_prompts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)],
):
    prompts = await get_prompts_by_user_id(db, user_id)
    return [schemas.PromptPublic.model_validate(prompt) for prompt in prompts]

@app.post("/prompts", response_model=schemas.PromptCreateResponse, status_code=201)
async def create_prompt(
    prompt: schemas.PromptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)],
):
    print("PROMPT", prompt)
    new_prompt = await repo_create_prompt(db, user_id, prompt)
    print("NEW PROMPT DB RESPONSE", new_prompt)
    return new_prompt

@app.get("/prompts/{prompt_slug}", response_model=schemas.PromptPublicById)
async def read_prompt(
    prompt_slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)],
):
    prompt = await get_prompt_by_slug(db, user_id, prompt_slug)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    fork_info = None
    if prompt.forked_from:
        fork_info = schemas.ForkInfo(
            forked_from_username=prompt.forked_from.user.username if prompt.forked_from.user else None,
            forked_from_prompt_title=prompt.forked_from.title,
        )

    return schemas.PromptPublicById(
        id=prompt.id,
        title=prompt.title,
        description=prompt.description,
        visibility=schemas.Visibility(prompt.visibility),
        messages=[schemas.Message.model_validate(message) for message in prompt.messages],
        title_slug=prompt.title_slug,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        forked_from=fork_info,
    )

@app.post("/prompts/{prompt_slug}/fork", response_model=schemas.PromptPublic, status_code=201)
async def fork_prompt(
    prompt_slug: str,
    fork_data: schemas.PromptFork,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)],
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

@app.delete("/prompts/{prompt_slug}", status_code=204)
async def delete_prompt(
    prompt_slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)],
):
    prompt = await get_prompt_by_slug(db, user_id, prompt_slug)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    await repo_delete_prompt(db, prompt)
    return Response(status_code=204)


@app.put("/prompts/{prompt_slug}", response_model=schemas.PromptCreateResponse)
async def update_prompt(
    prompt_slug: str,
    prompt: schemas.PromptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)],
):
    existing_prompt = await get_prompt_by_slug(db, user_id, prompt_slug)
    if not existing_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    updated_prompt = await repo_update_prompt(db, existing_prompt, prompt)
    return schemas.PromptCreateResponse.model_validate(updated_prompt)
