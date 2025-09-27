import uuid
from typing import Sequence

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

import schemas
from models import Prompt


async def get_prompts_by_user_id(db: AsyncSession, user_id: uuid.UUID) -> Sequence[Prompt]:
    result = await db.execute(
        select(Prompt)
        .where(Prompt.user_id == user_id)
        .options(joinedload(Prompt.forked_from))
        .order_by(Prompt.created_at.desc())
    )
    return result.scalars().all()


async def get_prompt_by_slug(db: AsyncSession, user_id: uuid.UUID, slug: str) -> Prompt | None:
    result = await db.execute(
        select(Prompt)
        .where(Prompt.user_id == user_id, Prompt.title_slug == slug)
        .options(joinedload(Prompt.forked_from))
    )
    return result.scalars().first()


async def create_prompt(db: AsyncSession, user_id: uuid.UUID, prompt: schemas.PromptCreate) -> Prompt:
    print("PROMPT", prompt)
    new_prompt = Prompt(
        user_id=user_id,
        title=prompt.title,
        title_slug=slugify(prompt.title),
        description=prompt.description,
        visibility=prompt.visibility.value,
        messages=[message.model_dump() for message in prompt.messages],
    )
    db.add(new_prompt)
    await db.flush()
    await db.refresh(new_prompt)
    print("NEW PROMPT", new_prompt)
    return new_prompt


async def update_prompt(db: AsyncSession, existing_prompt: Prompt, prompt: schemas.PromptCreate) -> Prompt:
    existing_prompt.title = prompt.title
    existing_prompt.title_slug = slugify(prompt.title)
    existing_prompt.description = prompt.description
    existing_prompt.visibility = prompt.visibility.value
    existing_prompt.messages = [message.model_dump() for message in prompt.messages]
    await db.refresh(existing_prompt)
    return existing_prompt


async def delete_prompt(db: AsyncSession, prompt: Prompt) -> None:
    await db.delete(prompt)


async def fork_prompt(
    db: AsyncSession,
    user_id: uuid.UUID,
    source_prompt: Prompt,
    new_title: str,
    new_description: str | None,
    new_messages: list[schemas.Message] | None,
) -> Prompt:
    forked_prompt = Prompt(
        user_id=user_id,
        title=new_title,
        title_slug=slugify(new_title),
        description=new_description if new_description is not None else source_prompt.description,
        visibility=schemas.Visibility.private.value,
        messages=[msg.model_dump() for msg in new_messages] if new_messages else list(source_prompt.messages),
        forked_from_id=source_prompt.id,
    )
    db.add(forked_prompt)
    await db.refresh(forked_prompt)
    return forked_prompt
