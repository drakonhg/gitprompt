import uuid
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import schemas

async def get_prompts_by_user_id(db: AsyncSession, user_id: uuid.UUID):
    result = await db.execute(
        text("SELECT id, name, forked_from_id, created_at, updated_at, visibility, messages FROM prompts WHERE user_id = :user_id"),
        {"user_id": user_id}
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]

async def get_prompt_by_name(db: AsyncSession, user_id: uuid.UUID, name: str):
    result = await db.execute(
        text("SELECT id, name, forked_from_id, created_at, updated_at, visibility, messages FROM prompts WHERE user_id = :user_id AND name = :name"),
        {"user_id": user_id, "name": name}
    )
    row = result.fetchone()
    return dict(row._mapping) if row else None

async def create_prompt(db: AsyncSession, user_id: uuid.UUID, prompt: schemas.PromptCreate):
    result = await db.execute(
        text("""
            INSERT INTO prompts (user_id, name, visibility, messages)
            VALUES (:user_id, :name, :visibility, :messages)
            RETURNING id, name, forked_from_id, created_at, updated_at, visibility, messages
        """),
        {
            "user_id": user_id,
            "name": prompt.name,
            "visibility": prompt.visibility,
            "messages": json.dumps([m.dict() for m in prompt.messages])
        }
    )
    row = result.fetchone()
    await db.commit()
    return dict(row._mapping)

async def fork_prompt(db: AsyncSession, user_id: uuid.UUID, original_prompt_name: str, new_prompt_name: str):
    async with db.begin():
        result = await db.execute(
            text("SELECT id, messages FROM prompts WHERE user_id = :user_id AND name = :name"),
            {"user_id": user_id, "name": original_prompt_name}
        )
        original_prompt = result.fetchone()

        if not original_prompt:
            return None

        result = await db.execute(
            text("""
                INSERT INTO prompts (user_id, name, visibility, messages, forked_from_id)
                VALUES (:user_id, :name, :visibility, :messages, :forked_from_id)
                RETURNING id, name, forked_from_id, created_at, updated_at, visibility, messages
            """),
            {
                "user_id": user_id,
                "name": new_prompt_name,
                "visibility": 'private',
                "messages": original_prompt._mapping["messages"],
                "forked_from_id": original_prompt._mapping["id"]
            }
        )
        row = result.fetchone()
        await db.commit()
        return dict(row._mapping)
