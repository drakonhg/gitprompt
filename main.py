from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Annotated
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import AsyncClient
from pydantic import TypeAdapter

import schemas
import auth
from slugify import slugify

load_dotenv()

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def health_check():
    return {"status": "healthy", "message": "GitPrompt API is running"}

@app.get("/prompts", response_model=List[schemas.PromptPublic])
async def read_prompts(
    supabase: Annotated[AsyncClient, Depends(auth.get_supabase_client_with_auth)],
    user_id : Annotated[uuid.UUID, Depends(auth.get_current_user_id)]
):
    prompts = await supabase.table("prompts").select("*").eq("user_id", user_id).execute()
    return prompts.data or []

@app.post("/prompts", response_model=schemas.PromptPublic, status_code=201)
async def create_prompt(
    prompt: schemas.PromptCreate,
    user_supabase: Annotated[AsyncClient, Depends(auth.get_supabase_client_with_auth)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)]
):
    new_prompt = {
        "title": prompt.title,
        "title_slug": slugify(prompt.title),
        "description": prompt.description,
        "visibility": prompt.visibility,
        "messages": [message.model_dump() for message in prompt.messages],
        "user_id": user_id,
        "created_at": "now()"
    }

    result = await user_supabase.table("prompts").insert(new_prompt).execute()
    return result.data[0]

@app.get("/prompts/{prompt_slug}", response_model=schemas.PromptPublic)
async def read_prompt(
    prompt_slug: str,
    user_supabase: Annotated[AsyncClient, Depends(auth.get_supabase_client_with_auth)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)]
):
    prompt = await user_supabase.table("prompts").select("*").eq("user_id", user_id).eq("title_slug", prompt_slug).single().execute()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt.data

@app.post("/prompts/{prompt_slug}/fork", response_model=schemas.PromptPublic, status_code=201)
async def fork_prompt(
    prompt_slug: str,
    fork_data: schemas.PromptFork,
    user_supabase: Annotated[AsyncClient, Depends(auth.get_supabase_client_with_auth)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)]
):  
    forked_prompt = await user_supabase.table("prompts").select("*").eq("user_id", user_id).eq("title_slug", prompt_slug).single().execute()
    if not forked_prompt:
        raise HTTPException(status_code=404, detail="Original prompt not found")

    if fork_data.new_messages:
        new_messages = [message.model_dump() for message in fork_data.new_messages]
    else:
        new_messages = [message for message in forked_prompt.data["messages"]]
    
    new_prompt = {
        "title": fork_data.new_title,
        "title_slug": slugify(fork_data.new_title),
        "description": fork_data.new_description if fork_data.new_description else forked_prompt.data["description"],
        "visibility": schemas.Visibility.private,
        "messages": new_messages,
        "forked_from_id": forked_prompt.data["id"],
        "user_id": user_id,
        "created_at": "now()"
    }
    result = await user_supabase.table("prompts").insert(new_prompt).execute()
    return result.data[0]

@app.delete("/prompts/{prompt_slug}", status_code=204)
async def delete_prompt(
    prompt_slug: str,
    user_supabase: Annotated[AsyncClient, Depends(auth.get_supabase_client_with_auth)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)]
):
    result = await user_supabase.table("prompts").delete().eq("user_id", user_id).eq("title_slug", prompt_slug).execute()
    return result


@app.put("/prompts/{prompt_slug}", response_model=schemas.PromptCreateResponse)
async def update_prompt(
    prompt_slug: str,
    prompt: schemas.PromptCreate,
    user_supabase: Annotated[AsyncClient, Depends(auth.get_supabase_client_with_auth)],
    user_id: Annotated[uuid.UUID, Depends(auth.get_current_user_id)]
):  
    new_prompt = {
        "title": prompt.title,
        "title_slug": slugify(prompt.title),
        "description": prompt.description,
        "visibility": prompt.visibility,
        "messages": [message.model_dump() for message in prompt.messages],
        "user_id": user_id,
        "updated_at": "now()"
    }
    result = await user_supabase.table("prompts") \
        .update(new_prompt) \
        .eq("user_id", user_id) \
        .eq("title_slug", prompt_slug) \
        .execute()
    return result.data[0]
