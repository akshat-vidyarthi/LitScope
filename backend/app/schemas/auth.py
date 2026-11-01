import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class UserRegister(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_.-]+$', description="Unique username (letters, numbers, underscores, dots, hyphens)")
    password: str = Field(..., min_length=6, description="Password (at least 6 characters)")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name or display name")
    email: Optional[str] = Field(None, max_length=255, description="Optional email address")

    @model_validator(mode="after")
    def ensure_username(self):
        if not self.username and not self.email:
            raise ValueError("Either username or email must be provided.")
        if not self.username and self.email:
            derived = self.email.split('@')[0]
            clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', derived)
            self.username = clean[:50]
        return self


class UserLogin(BaseModel):
    username: Optional[str] = Field(None, description="Registered username")
    email: Optional[str] = Field(None, description="Registered email (alternative)")
    password: str = Field(..., description="Password")

    @model_validator(mode="after")
    def ensure_ident(self):
        if not self.username and not self.email:
            raise ValueError("Either username or email must be provided.")
        if not self.username and self.email:
            self.username = self.email
        return self


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserSearchResult(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
