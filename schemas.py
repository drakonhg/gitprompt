from enum import Enum
from pydantic import BaseModel
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
    title: str
    description: str
    visibility: Visibility
    messages: List[Message]

class PromptCreate(PromptBase):
    pass

class PromptPublic(PromptBase):
    id: uuid.UUID
    title_slug: str
    created_at: datetime
    forked_from_id: uuid.UUID | None = None


class PromptFork(BaseModel):
    new_title: str


class PromptCreateResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
