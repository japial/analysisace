"""Health and metadata endpoints. Not data-derived, so no `as_of`/`sources` envelope."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.app_config import DOMAINS, get_config
from app.core.db import get_db

router = APIRouter(tags=["system"])
logger = logging.getLogger(__name__)


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]


class Meta(BaseModel):
    api_version: str
    config_versions: dict[str, str]


@router.get("/health")
def health(response: Response, db: Annotated[Session, Depends(get_db)]) -> Health:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check could not reach the database")
        response.status_code = 503
        return Health(status="degraded", database="unavailable")
    return Health(status="ok", database="ok")


@router.get("/meta")
def meta() -> Meta:
    """Versions of the rule files this process is running with."""
    return Meta(
        api_version="v1",
        config_versions={domain: get_config(domain).version for domain in DOMAINS},
    )
