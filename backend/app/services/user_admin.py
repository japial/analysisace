"""User and role management for administrators (permission USERS_MANAGE).

Every change is written to the audit log (PRD section 13).
"""

import uuid

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.core.permissions import Role
from app.models import User
from app.services.auth import AuthError, audit, count_active_admins, revoke_all_sessions


def list_users(
    db: Session,
    *,
    q: str | None = None,
    role: Role | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[User], int]:
    filters: list[ColumnElement[bool]] = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
    if role is not None:
        filters.append(User.role == role.value)
    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    rows = db.scalars(
        select(User)
        .where(*filters)
        .order_by(User.created_at.desc(), User.email)
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total


def update_user(
    db: Session,
    actor: User,
    user_id: uuid.UUID,
    *,
    role: Role | None = None,
    is_active: bool | None = None,
) -> User:
    """Change a user's role or active state.

    Refused when it would lock the platform out: an admin cannot change their own role or
    state, and the last active admin cannot be demoted or deactivated.
    """
    user = db.get(User, user_id)
    if user is None:
        raise AuthError("USER_NOT_FOUND", 404)
    if user.id == actor.id:
        raise AuthError("CANNOT_CHANGE_SELF", 409)

    before = {"role": user.role, "is_active": user.is_active}
    new_role = role.value if role is not None else user.role
    new_active = is_active if is_active is not None else user.is_active

    loses_admin = (
        user.role == Role.ADMIN.value
        and user.is_active
        and (new_role != Role.ADMIN.value or not new_active)
    )
    if loses_admin and count_active_admins(db) <= 1:
        raise AuthError("LAST_ADMIN", 409)

    user.role = new_role
    user.is_active = new_active
    after = {"role": user.role, "is_active": user.is_active}
    if after == before:
        return user

    if not user.is_active:
        # A deactivated user is signed out everywhere at once.
        revoke_all_sessions(db, user.id)
    audit(db, str(actor.id), "USER_UPDATED", "app_user", str(user.id), before=before, after=after)
    db.flush()
    return user
