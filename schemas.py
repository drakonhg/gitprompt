from enum import Enum
from pydantic import BaseModel, Field
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


class PromptBase(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=1000)
    visibility: Visibility
    messages: List[Message]


class PromptCreate(PromptBase):
    pass


class PromptPublic(PromptBase):
    id: uuid.UUID
    title_slug: str
    created_at: datetime
    updated_at: datetime | None = None
    forked_from_id: uuid.UUID | None = None


class PromptFork(BaseModel):
    new_title: str = Field(min_length=3, max_length=120)
    new_messages: List[Message] | None = None
    new_description: str | None = None


class PromptCreateResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
