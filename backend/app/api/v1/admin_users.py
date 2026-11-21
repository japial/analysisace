"""User and role management. Every route needs the USERS_MANAGE permission."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import Db, require_permission
from app.core.permissions import ROLE_PERMISSIONS, Permission, Role
from app.models import User
from app.schemas.auth import RoleOut, RolesOut, UserAdminUpdateIn, UserOut
from app.schemas.common import Page
from app.services import user_admin

router = APIRouter(prefix="/admin", tags=["admin"])

UserManager = Annotated[User, Depends(require_permission(Permission.USERS_MANAGE))]


@router.get("/users")
def list_users(
    _: UserManager,
    db: Db,
    q: Annotated[str | None, Query(max_length=100, description="Email or name contains")] = None,
    role: Role | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[UserOut]:
    rows, total = user_admin.list_users(db, q=q, role=role, limit=limit, offset=offset)
    return Page[UserOut](
        items=[UserOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.patch("/users/{user_id}")
def update_user(user_id: uuid.UUID, body: UserAdminUpdateIn, actor: UserManager, db: Db) -> UserOut:
    user = user_admin.update_user(db, actor, user_id, role=body.role, is_active=body.is_active)
    db.commit()
    return UserOut.model_validate(user)


@router.get("/roles")
def list_roles(_: UserManager) -> RolesOut:
    """The fixed roles and the permissions each one carries."""
    return RolesOut(
        roles=[RoleOut(role=role, permissions=sorted(ROLE_PERMISSIONS[role])) for role in Role],
        permissions=list(Permission),
    )
