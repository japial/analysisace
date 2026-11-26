"""Platform roles and what each may do.

A user has exactly one platform role. Routes check a permission, never a role name, so a
role's reach can change here without touching the routes. Household roles (OWNER, EDITOR,
VIEWER; FR24.2) and firm roles (FR9.3) are separate and arrive with those features.
"""

from enum import StrEnum


class Role(StrEnum):
    USER = "USER"  # every registered person
    ANALYST = "ANALYST"  # staff who review data and publish content
    ADMIN = "ADMIN"  # full control, including users and rule files


class Permission(StrEnum):
    DATA_REVIEW = "DATA_REVIEW"  # data review queue, extracted financials (PRD section 8)
    CONTENT_PUBLISH = "CONTENT_PUBLISH"  # macro notes (FR4.1), shock events (FR5.1)
    SHARIAH_OVERRIDE = "SHARIAH_OVERRIDE"  # board notes and manual overrides (FR1.6)
    CONFIG_MANAGE = "CONFIG_MANAGE"  # approve rule file versions, bank flags
    USERS_MANAGE = "USERS_MANAGE"  # list users, change roles, deactivate accounts
    AUDIT_VIEW = "AUDIT_VIEW"  # read the audit log
    FIRMS_MANAGE = "FIRMS_MANAGE"  # create firms, set seat limits (FR9.3)


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.USER: frozenset(),
    Role.ANALYST: frozenset({Permission.DATA_REVIEW, Permission.CONTENT_PUBLISH}),
    Role.ADMIN: frozenset(Permission),
}


def permissions_for(role: Role | str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[Role(role)]


def has_permission(role: Role | str, permission: Permission) -> bool:
    return permission in permissions_for(role)
