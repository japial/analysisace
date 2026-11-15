"""Shared FastAPI dependencies: database session, signed-in user, permission checks."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.core.permissions import Permission, has_permission
from app.models import User, UserSession
from app.services.auth import AuthError, resolve_session

Db = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]

_bearer = HTTPBearer(auto_error=False, description="Session token from POST /auth/login")


@dataclass(frozen=True)
class Identity:
    user: User
    session: UserSession


def get_identity(
    db: Db, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> Identity:
    if credentials is None:
        raise AuthError("NOT_AUTHENTICATED", 401)
    resolved = resolve_session(db, credentials.credentials)
    if resolved is None:
        raise AuthError("NOT_AUTHENTICATED", 401)
    session, user = resolved
    return Identity(user=user, session=session)


CurrentIdentity = Annotated[Identity, Depends(get_identity)]


def get_current_user(identity: CurrentIdentity) -> User:
    return identity.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: Permission) -> Callable[[User], User]:
    """Dependency factory: the signed-in user must hold `permission`."""

    def dependency(user: CurrentUser) -> User:
        if not has_permission(user.role, permission):
            raise AuthError("FORBIDDEN", 403)
        return user

    return dependency
