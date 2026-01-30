from __future__ import annotations

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class User(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    scopes: list[str] = Field(default_factory=list)

