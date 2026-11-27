"""Firm accounts, seats, API keys and the platform admin screens (F9, D30)."""

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

FirmRole = Literal["ADMIN", "MEMBER"]
FirmName = Annotated[str, Field(min_length=2, max_length=200)]
Disclaimer = Annotated[str, Field(max_length=1000)]


class FirmSummary(BaseModel):
    id: uuid.UUID
    name: str
    role: FirmRole


class MemberOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: FirmRole
    since: dt.datetime


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    rate_limit_per_minute: int
    created_at: dt.datetime
    last_used_at: dt.datetime | None
    revoked_at: dt.datetime | None


class ApiKeyCreated(ApiKeyOut):
    # Shown once, at creation. Only a hash is kept.
    key: str


class UsageRow(BaseModel):
    date: dt.date
    key: str
    endpoint: str
    calls: int


class FirmDetail(BaseModel):
    id: uuid.UUID
    name: str
    role: FirmRole
    seat_limit: int
    report_disclaimer: str | None
    has_logo: bool
    members: list[MemberOut]
    # Only for the firm's admins; empty for members.
    api_keys: list[ApiKeyOut]
    usage: list[UsageRow]
    # Weeks with a published note, newest first, for the weekly report.
    report_weeks: list[dt.date]


class FirmUpdateIn(BaseModel):
    report_disclaimer: Disclaimer | None = None


class SeatIn(BaseModel):
    email: EmailStr
    role: FirmRole = "MEMBER"


class SeatRoleIn(BaseModel):
    role: FirmRole


class ApiKeyIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]


class LogoIn(BaseModel):
    # The image, base64-encoded. PNG or JPEG; the size limit is FIRM_LOGO_MAX_BYTES.
    content_base64: Annotated[str, Field(min_length=8, max_length=600_000)]


class AdminFirmOut(BaseModel):
    id: uuid.UUID
    name: str
    seat_limit: int
    seats_used: int
    is_active: bool
    created_at: dt.datetime


class AdminFirmIn(BaseModel):
    name: FirmName
    seat_limit: Annotated[int, Field(ge=1, le=500)] = 5
    admin_email: EmailStr
    report_disclaimer: Disclaimer | None = None


class AdminFirmUpdateIn(BaseModel):
    name: FirmName | None = None
    seat_limit: Annotated[int, Field(ge=1, le=500)] | None = None
    is_active: bool | None = None
