"""Creates an administrator, or promotes an existing account to administrator.

    python scripts/create_admin.py admin@example.com "Full Name"

The password is asked for without echo. For unattended use, set ADMIN_PASSWORD instead.
This is how the first admin is made; after that, admins manage roles in the web app.
"""

import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.db import get_sessionmaker
from app.core.permissions import Role
from app.services.auth import audit, get_user_by_email, register_user

MIN_PASSWORD_LENGTH = 8


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    email = sys.argv[1]
    full_name = sys.argv[2] if len(sys.argv) > 2 else "Administrator"
    try:
        # The same check the sign-in form applies; an address it rejects could never sign in.
        TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        print(f"{email} is not an email address the sign-in form accepts.")
        return 1

    with get_sessionmaker()() as db:
        user = get_user_by_email(db, email)
        if user is not None:
            before = {"role": user.role, "is_active": user.is_active}
            user.role = Role.ADMIN.value
            user.is_active = True
            audit(
                db,
                "cli:create_admin",
                "USER_UPDATED",
                "app_user",
                str(user.id),
                before=before,
                after={"role": user.role, "is_active": True},
            )
            db.commit()
            print(f"{user.email} is now an administrator.")
            return 0

        password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
            return 1
        user = register_user(
            db,
            email=email,
            password=password,
            full_name=full_name,
            locale="en",
            accept_terms=True,
            role=Role.ADMIN,
        )
        db.commit()
        print(f"Administrator {user.email} created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
