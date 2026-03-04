from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)
    is_super_admin: bool = False


class UpdateUserRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    status: Literal["active", "disabled"] | None = None
    is_super_admin: bool | None = None
    password: str | None = Field(default=None, min_length=1)


class UpdateMeRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=255)


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="")


class UpsertMemberRequest(BaseModel):
    user_id: str
    role: str
