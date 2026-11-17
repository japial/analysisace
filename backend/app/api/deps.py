"""Shared FastAPI dependencies: database session, signed-in user, permission checks."""

import uuid
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
from app.models.enums import HouseholdRole
from app.services import households
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


def household_access(role: HouseholdRole) -> Callable[..., households.Access]:
    """Dependency factory for routes under /households/{household_id}.

    The signed-in user must be a member of that household with at least `role` (FR24.2).
    A household the user is not in answers 404, exactly like one that does not exist.
    """

    def dependency(household_id: uuid.UUID, user: CurrentUser, db: Db) -> households.Access:
        access = households.get_access(db, user, household_id)
        households.require_role(access, role)
        return access

    return dependency


Viewer = Annotated[households.Access, Depends(household_access(HouseholdRole.VIEWER))]
Editor = Annotated[households.Access, Depends(household_access(HouseholdRole.EDITOR))]
Owner = Annotated[households.Access, Depends(household_access(HouseholdRole.OWNER))]
