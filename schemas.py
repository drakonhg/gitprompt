from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime


class Role(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class Visibility(str, Enum):
    public = "public"
    private = "private"


class Message(BaseModel):
    role: Role
    content: str


class ForkInfo(BaseModel):
    forked_from_username: str | None = None
    forked_from_prompt_title: str | None = None


class PromptBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str = Field(min_length=3, max_length=60)
    description: str = Field(default="", max_length=1000)
    visibility: Visibility
    messages: List[Message]


class PromptCreate(PromptBase):
    pass


class PromptPublic(PromptBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title_slug: str
    created_at: datetime
    updated_at: datetime | None = None
    forked_from_id: uuid.UUID | None = None


class PromptFork(BaseModel):
    new_title: str = Field(min_length=3, max_length=60)
    new_messages: List[Message] | None = None
    new_description: str | None = None


class PromptCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class PromptPublicById(PromptBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title_slug: str
    created_at: datetime
    updated_at: datetime | None = None
    forked_from: ForkInfo | None = None
