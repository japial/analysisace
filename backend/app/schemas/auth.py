"""Request and response models for accounts, sessions and user management."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from app.core.permissions import Permission, Role, permissions_for
from app.services.auth import ConsentPurpose

Locale = Literal["bn", "en"]
# Long enough to resist guessing; the upper bound stops oversized hashing requests.
Password = Annotated[str, Field(min_length=8, max_length=128)]
FullName = Annotated[str, Field(min_length=1, max_length=120)]


class RegisterIn(BaseModel):
    email: EmailStr
    password: Password
    full_name: FullName
    locale: Locale = "bn"
    accept_terms: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]
    client: Literal["web", "mobile"] = "web"


class PasswordResetRequestIn(BaseModel):
    email: EmailStr


class PasswordResetConfirmIn(BaseModel):
    token: Annotated[str, Field(min_length=10, max_length=200)]
    new_password: Password


class ProfileUpdateIn(BaseModel):
    full_name: FullName | None = None
    locale: Locale | None = None


class PasswordChangeIn(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: Password


class ConsentsUpdateIn(BaseModel):
    consents: dict[ConsentPurpose, bool]


class AccountDeleteIn(BaseModel):
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    locale: str
    role: Role
    is_active: bool
    consents: dict[str, Any]
    created_at: datetime
    last_login_at: datetime | None
    email_verified_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def permissions(self) -> list[Permission]:
        return sorted(permissions_for(self.role))


class AuthOut(BaseModel):
    """Returned once at sign-in. The client keeps `token` and sends it as a Bearer header."""

    user: UserOut
    token: str
    expires_at: datetime


class UserAdminUpdateIn(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class RoleOut(BaseModel):
    role: Role
    permissions: list[Permission]


class RolesOut(BaseModel):
    roles: list[RoleOut]
    permissions: list[Permission]


class VerifyEmailConfirmIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
