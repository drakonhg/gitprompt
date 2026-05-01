"""Data-access helpers for prompts (CRUD, fork) and API keys (issue, hash, lookup, regenerate)."""

import uuid
import math
import logging
import secrets
import hashlib
import hmac
from typing import List
from datetime import datetime

from slugify import slugify
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

import schemas
from models import Prompt, APIKey

logger = logging.getLogger(__name__)


async def get_prompts_by_user_id(
    db: AsyncSession, 
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 12,
) -> dict:
    count_query = select(func.count(Prompt.id)).where(Prompt.user_id == user_id)
    total_items_result = await db.execute(count_query)
    total_prompts = total_items_result.scalar_one()

    if total_prompts == 0:
        logger.info("No prompts found for user_id=%s", user_id)
        return {
            "total_prompts": 0, "total_pages": 0, "current_page": page,
            "page_size": page_size, "prompts": []
        }

    offset = (page - 1) * page_size
    total_pages = math.ceil(total_prompts / page_size)


    result = await db.execute(
        select(Prompt)
        .where(Prompt.user_id == user_id)
        .order_by(Prompt.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    prompts = result.scalars().all()
    logger.info(
        "Fetched %d prompts (page %d/%d) for user_id=%s",
        len(prompts), page, total_pages, user_id,
    )
    return {
        "total_prompts": total_prompts,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "prompts": prompts
    }


async def get_prompt_by_slug(
    db: AsyncSession, user_id: uuid.UUID, slug: str
) -> Prompt | None:
    result = await db.execute(
        select(Prompt)
        .where(Prompt.user_id == user_id, Prompt.title_slug == slug)
        .options(joinedload(Prompt.forked_from))
    )
    prompt = result.scalars().first()
    if prompt is None:
        logger.warning("Prompt not found: user_id=%s slug=%s", user_id, slug)
    else:
        logger.info("Fetched prompt id=%s slug=%s user_id=%s", prompt.id, slug, user_id)
    return prompt


async def create_prompt(
    db: AsyncSession, user_id: uuid.UUID, prompt: schemas.PromptCreate
) -> Prompt:
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
    logger.info(
        "Created prompt id=%s slug=%s user_id=%s",
        new_prompt.id, new_prompt.title_slug, user_id,
    )
    return new_prompt


async def update_prompt(
    db: AsyncSession, existing_prompt: Prompt, prompt: schemas.PromptCreate
) -> Prompt:
    existing_prompt.title = prompt.title
    existing_prompt.title_slug = slugify(prompt.title)
    existing_prompt.description = prompt.description
    existing_prompt.visibility = prompt.visibility.value
    existing_prompt.messages = [message.model_dump() for message in prompt.messages]
    await db.flush()
    await db.refresh(existing_prompt)
    logger.info(
        "Updated prompt id=%s slug=%s user_id=%s",
        existing_prompt.id, existing_prompt.title_slug, existing_prompt.user_id,
    )
    return existing_prompt


async def delete_prompt(db: AsyncSession, prompt: Prompt) -> None:
    logger.info(
        "Deleting prompt id=%s slug=%s user_id=%s",
        prompt.id, prompt.title_slug, prompt.user_id,
    )
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
        description=new_description
        if new_description is not None
        else source_prompt.description,
        visibility=schemas.Visibility.private.value,
        messages=[msg.model_dump() for msg in new_messages]
        if new_messages
        else list(source_prompt.messages),
        forked_from_id=source_prompt.id,
    )
    db.add(forked_prompt)
    await db.flush()
    await db.refresh(forked_prompt)
    logger.info(
        "Forked prompt id=%s slug=%s user_id=%s from source_id=%s",
        forked_prompt.id, forked_prompt.title_slug, user_id, source_prompt.id,
    )
    return forked_prompt


def _generate_api_key() -> tuple[str, str, str, str]:
    """Generate a secure API key with salt and hash.

    Returns:
        tuple: (full_api_key, key_prefix, key_hash, salt)
    """
    # Generate a random 60-character key (64 total - 4 for "gpk-" prefix)
    random_part = secrets.token_urlsafe(60)[:60]

    # Create 64-character API key starting with "gpk-"
    full_api_key = f"gpk-{random_part}"

    # Store last 5 characters for display formatting (renamed from key_suffix to key_prefix)
    key_prefix = full_api_key[-5:]

    # Generate salt
    salt = secrets.token_hex(16)

    # Create hash of the key + salt
    key_hash = hashlib.sha256((full_api_key + salt).encode()).hexdigest()

    return full_api_key, key_prefix, key_hash, salt


async def create_api_key(
    db: AsyncSession, user_id: uuid.UUID, name: str
) -> tuple[APIKey, str]:
    """Create a new API key for the user.

    Returns:
        tuple: (api_key_model, plain_api_key)
    """
    plain_key, key_prefix, key_hash, salt = _generate_api_key()

    api_key = APIKey(
        user_id=user_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        salt=salt,
    )

    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    logger.info(
        "Created API key id=%s name=%s user_id=%s",
        api_key.id, name, user_id,
    )
    return api_key, plain_key


async def get_api_key_by_key(db: AsyncSession, api_key: str) -> APIKey | None:
    """Get API key by the plain API key string.

    This function securely validates an API key by:
    1. Fetching all API keys (we need to check each one due to salted hashing)
    2. For each key, computing hash(api_key + salt) and comparing to stored hash
    3. Updating last_used_at timestamp on successful match
    """
    # Fetch all API keys - we need to check each one since we don't know
    # which user the key belongs to without trying the salted hash
    result = await db.execute(select(APIKey))
    api_keys = result.scalars().all()
    for key_record in api_keys:
        # Hash the provided key with the stored salt
        test_hash = hashlib.sha256((api_key + key_record.salt).encode()).hexdigest()
        # Use constant-time comparison to prevent timing attacks
        if hmac.compare_digest(test_hash, key_record.key_hash):
            # Update last_used_at timestamp for security monitoring
            await update_api_key_last_used(db, key_record.id)
            logger.info(
                "API key matched id=%s user_id=%s",
                key_record.id, key_record.user_id,
            )
            return key_record

    logger.warning("API key lookup failed: no matching key for provided credential")
    return None


async def update_api_key_last_used(db: AsyncSession, api_key_id: uuid.UUID) -> None:
    """Update the last_used_at timestamp for an API key."""

    await db.execute(
        update(APIKey)
        .where(APIKey.id == api_key_id)
        .values(last_used_at=datetime.utcnow())
    )
    logger.info("Updated last_used_at for API key id=%s", api_key_id)


async def get_api_keys_by_user_id(
    db: AsyncSession, user_id: uuid.UUID
) -> List[APIKey]:
    """Get all API keys for a user."""
    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == user_id)
        .order_by(APIKey.created_at.desc())
    )
    api_keys = result.scalars().all()
    logger.info("Fetched %d API keys for user_id=%s", len(api_keys), user_id)
    return api_keys


async def get_api_key_by_user_id(
    db: AsyncSession, user_id: uuid.UUID
) -> APIKey | None:
    """Get the API key for a specific user (assumes one API key per user for now)."""
    result = await db.execute(
        select(APIKey)
        .where(APIKey.user_id == user_id)
        .order_by(APIKey.created_at.desc())
        .limit(1)
    )
    api_key = result.scalars().first()
    if api_key is None:
        logger.warning("No API key found for user_id=%s", user_id)
    else:
        logger.info("Fetched API key id=%s for user_id=%s", api_key.id, user_id)
    return api_key


async def delete_api_key(db: AsyncSession, api_key_id: uuid.UUID) -> None:
    """Delete an API key by ID."""
    await db.execute(
        delete(APIKey)
        .where(APIKey.id == api_key_id)
    )
    logger.info("Deleted API key id=%s", api_key_id)


async def regenerate_api_key(
    db: AsyncSession, api_key_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[APIKey, str]:
    """Regenerate an API key (delete old, create new with same name).

    Args:
        db: Database session
        api_key_id: ID of the API key to regenerate
        user_id: ID of the user (for security check)

    Returns:
        tuple: (new_api_key_model, plain_api_key)

    Raises:
        ValueError: If API key not found or doesn't belong to user
    """
    # First, get the existing API key to verify ownership
    result = await db.execute(
        select(APIKey)
        .where(APIKey.id == api_key_id, APIKey.user_id == user_id)
    )
    existing_key = result.scalars().first()

    if not existing_key:
        logger.warning(
            "Regenerate failed: API key id=%s not found for user_id=%s",
            api_key_id, user_id,
        )
        raise ValueError("API key not found or doesn't belong to user")

    # Store the name for the new key
    key_name = existing_key.name

    logger.info(
        "Regenerating API key id=%s name=%s user_id=%s",
        api_key_id, key_name, user_id,
    )

    # Delete the old key
    await delete_api_key(db, api_key_id)

    # Create new key with same name
    return await create_api_key(db, user_id, key_name)
