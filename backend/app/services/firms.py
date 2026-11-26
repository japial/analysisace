"""Firm accounts (F9): seats and roles (FR9.3), API keys with limits and usage logs (FR9.2),
CSV exports (FR9.2) and the logo for the white-label weekly report (FR9.1). D30.

Everything is behind FIRM_FEATURES_ENABLED, off until the BSEC question is settled
(TODO(owner): Q4). Functions flush; the route commits. Audit entries hold ids only.
"""

import csv
import datetime as dt
import io
import uuid
from dataclasses import dataclass
from typing import Any

from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_token, new_token, utcnow
from app.models import ApiKey, ApiUsage, Firm, FirmSeat, Score, User
from app.services import ratelimit, screening
from app.services.auth import AuthError, audit, get_user_by_email
from app.services.storage import DocumentStorage
from app.services.valuation import today_dhaka

FIRM_ROLES = ("ADMIN", "MEMBER")
KEY_PREFIX = "aace_"
LOGO_MAX_SIDE = 600


def require_enabled(settings: Settings) -> None:
    """Every firm route asks this first: while the switch is off, firms do not exist."""
    if not settings.firm_features_enabled:
        raise AuthError("NOT_FOUND", 404)


# --- firms and seats (FR9.3) ------------------------------------------------------------


@dataclass(frozen=True)
class Membership:
    firm: Firm
    seat: FirmSeat

    @property
    def is_admin(self) -> bool:
        return self.seat.role == "ADMIN"


def memberships(db: Session, user: User) -> list[Membership]:
    rows = db.execute(
        select(Firm, FirmSeat)
        .join(FirmSeat, FirmSeat.firm_id == Firm.id)
        .where(FirmSeat.user_id == user.id, Firm.is_active.is_(True))
        .order_by(Firm.name)
    ).all()
    return [Membership(firm, seat) for firm, seat in rows]


def membership(db: Session, user: User, firm_id: uuid.UUID, *, admin: bool = False) -> Membership:
    """The person's seat in this firm. Someone without one gets 404, so a firm's existence
    is not revealed; a member asking for an admin action gets 403."""
    for found in memberships(db, user):
        if found.firm.id == firm_id:
            if admin and not found.is_admin:
                raise AuthError("FIRM_ADMIN_REQUIRED", 403)
            return found
    raise AuthError("NOT_FOUND", 404)


def seats(db: Session, firm_id: uuid.UUID) -> list[tuple[FirmSeat, User]]:
    return [
        (seat, user)
        for seat, user in db.execute(
            select(FirmSeat, User)
            .join(User, User.id == FirmSeat.user_id)
            .where(FirmSeat.firm_id == firm_id)
            .order_by(FirmSeat.created_at)
        ).all()
    ]


def _admin_count(db: Session, firm_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(FirmSeat)
            .where(FirmSeat.firm_id == firm_id, FirmSeat.role == "ADMIN")
        )
        or 0
    )


def add_seat(db: Session, actor: User, firm: Firm, email: str, role: str) -> FirmSeat:
    if role not in FIRM_ROLES:
        raise AuthError("VALIDATION", 422)
    user = get_user_by_email(db, email)
    # The same answer for an unknown address and an inactive account.
    if user is None or not user.is_active:
        raise AuthError("USER_NOT_FOUND", 404)
    if db.scalar(
        select(FirmSeat.id).where(FirmSeat.firm_id == firm.id, FirmSeat.user_id == user.id)
    ):
        raise AuthError("DUPLICATE", 409)
    used = db.scalar(select(func.count()).select_from(FirmSeat).where(FirmSeat.firm_id == firm.id))
    if (used or 0) >= firm.seat_limit:
        raise AuthError("SEAT_LIMIT_REACHED", 409)
    seat = FirmSeat(firm_id=firm.id, user_id=user.id, role=role)
    db.add(seat)
    db.flush()
    audit(
        db,
        str(actor.id),
        "FIRM_SEAT_ADDED",
        "firm",
        str(firm.id),
        after={"user_id": str(user.id), "role": role},
    )
    return seat


def _seat(db: Session, firm_id: uuid.UUID, user_id: uuid.UUID) -> FirmSeat:
    seat = db.scalar(
        select(FirmSeat).where(FirmSeat.firm_id == firm_id, FirmSeat.user_id == user_id)
    )
    if seat is None:
        raise AuthError("NOT_FOUND", 404)
    return seat


def change_role(db: Session, actor: User, firm: Firm, user_id: uuid.UUID, role: str) -> FirmSeat:
    if role not in FIRM_ROLES:
        raise AuthError("VALIDATION", 422)
    seat = _seat(db, firm.id, user_id)
    if seat.role == "ADMIN" and role != "ADMIN" and _admin_count(db, firm.id) <= 1:
        raise AuthError("LAST_FIRM_ADMIN", 409)
    before = seat.role
    seat.role = role
    db.flush()
    audit(
        db,
        str(actor.id),
        "FIRM_ROLE_CHANGED",
        "firm",
        str(firm.id),
        before={"user_id": str(user_id), "role": before},
        after={"role": role},
    )
    return seat


def remove_seat(db: Session, actor: User, firm: Firm, user_id: uuid.UUID) -> None:
    seat = _seat(db, firm.id, user_id)
    if seat.role == "ADMIN" and _admin_count(db, firm.id) <= 1:
        raise AuthError("LAST_FIRM_ADMIN", 409)
    db.delete(seat)
    db.flush()
    audit(
        db,
        str(actor.id),
        "FIRM_SEAT_REMOVED",
        "firm",
        str(firm.id),
        before={"user_id": str(user_id)},
    )


# --- platform administration ------------------------------------------------------------


def create_firm(
    db: Session,
    actor: User,
    *,
    name: str,
    seat_limit: int,
    admin_email: str,
    disclaimer: str | None,
) -> Firm:
    name = name.strip()
    if db.scalar(select(Firm.id).where(func.lower(Firm.name) == name.lower())):
        raise AuthError("DUPLICATE", 409)
    first_admin = get_user_by_email(db, admin_email)
    if first_admin is None or not first_admin.is_active:
        raise AuthError("USER_NOT_FOUND", 404)
    firm = Firm(
        name=name, seat_limit=seat_limit, report_disclaimer=(disclaimer or "").strip() or None
    )
    db.add(firm)
    db.flush()
    db.add(FirmSeat(firm_id=firm.id, user_id=first_admin.id, role="ADMIN"))
    db.flush()
    audit(
        db,
        str(actor.id),
        "FIRM_CREATED",
        "firm",
        str(firm.id),
        after={"seat_limit": seat_limit, "admin_id": str(first_admin.id)},
    )
    return firm


def update_firm(db: Session, actor: User, firm: Firm, changes: dict[str, Any]) -> Firm:
    before = {k: getattr(firm, k) for k in changes}
    if "seat_limit" in changes:
        used = db.scalar(
            select(func.count()).select_from(FirmSeat).where(FirmSeat.firm_id == firm.id)
        )
        if changes["seat_limit"] < (used or 0):
            raise AuthError("SEAT_LIMIT_BELOW_SEATS", 409)
    if "name" in changes:
        name = str(changes["name"]).strip()
        clash = db.scalar(
            select(Firm.id).where(func.lower(Firm.name) == name.lower(), Firm.id != firm.id)
        )
        if clash:
            raise AuthError("DUPLICATE", 409)
        changes["name"] = name
    if "report_disclaimer" in changes:
        changes["report_disclaimer"] = (changes["report_disclaimer"] or "").strip() or None
    for key, value in changes.items():
        setattr(firm, key, value)
    db.flush()
    audit(
        db,
        str(actor.id),
        "FIRM_UPDATED",
        "firm",
        str(firm.id),
        before={k: str(v) for k, v in before.items()},
        after={k: str(v) for k, v in changes.items()},
    )
    return firm


def list_firms(db: Session) -> list[tuple[Firm, int]]:
    counts = dict(
        db.execute(select(FirmSeat.firm_id, func.count()).group_by(FirmSeat.firm_id)).all()
    )
    return [(f, int(counts.get(f.id, 0))) for f in db.scalars(select(Firm).order_by(Firm.name))]


def get_firm(db: Session, firm_id: uuid.UUID) -> Firm:
    firm = db.get(Firm, firm_id)
    if firm is None:
        raise AuthError("NOT_FOUND", 404)
    return firm


# --- logo (FR9.1) -----------------------------------------------------------------------


def set_logo(
    db: Session, actor: User, firm: Firm, storage: DocumentStorage, data: bytes, max_bytes: int
) -> None:
    """Accept a PNG or JPEG, shrink it to fit 600 px, and store it re-encoded as PNG. Re-encoding
    drops anything else the file carried."""
    if len(data) > max_bytes:
        raise AuthError("LOGO_TOO_LARGE", 413)
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("PNG", "JPEG"):
                raise AuthError("LOGO_INVALID", 422)
            image.load()
            clean = image.convert("RGBA")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise AuthError("LOGO_INVALID", 422) from None
    clean.thumbnail((LOGO_MAX_SIDE, LOGO_MAX_SIDE))
    out = io.BytesIO()
    clean.save(out, format="PNG", optimize=True)
    old = firm.logo_ref
    firm.logo_ref = storage.put(out.getvalue())
    if old:
        storage.delete(old)
    db.flush()
    audit(db, str(actor.id), "FIRM_LOGO_SET", "firm", str(firm.id))


def remove_logo(db: Session, actor: User, firm: Firm, storage: DocumentStorage) -> None:
    if firm.logo_ref:
        storage.delete(firm.logo_ref)
        firm.logo_ref = None
        db.flush()
        audit(db, str(actor.id), "FIRM_LOGO_REMOVED", "firm", str(firm.id))


def logo(firm: Firm, storage: DocumentStorage) -> bytes | None:
    return storage.get(firm.logo_ref) if firm.logo_ref else None


# --- API keys (FR9.2) -------------------------------------------------------------------


def create_key(
    db: Session, actor: User, firm: Firm, name: str, per_minute: int
) -> tuple[ApiKey, str]:
    """A new key. The full key is returned once; only its hash and first characters are kept."""
    secret = f"{KEY_PREFIX}{new_token()}"
    row = ApiKey(
        firm_id=firm.id,
        name=name.strip(),
        prefix=secret[:12],
        key_hash=hash_token(secret),
        rate_limit_per_minute=per_minute,
    )
    db.add(row)
    db.flush()
    audit(
        db,
        str(actor.id),
        "API_KEY_CREATED",
        "api_key",
        str(row.id),
        after={"firm_id": str(firm.id)},
    )
    return row, secret


def list_keys(db: Session, firm_id: uuid.UUID) -> list[ApiKey]:
    return list(
        db.scalars(select(ApiKey).where(ApiKey.firm_id == firm_id).order_by(ApiKey.created_at))
    )


def revoke_key(db: Session, actor: User, firm: Firm, key_id: uuid.UUID) -> ApiKey:
    row = db.get(ApiKey, key_id)
    if row is None or row.firm_id != firm.id:
        raise AuthError("NOT_FOUND", 404)
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        db.flush()
        audit(db, str(actor.id), "API_KEY_REVOKED", "api_key", str(row.id))
    return row


def authenticate_key(db: Session, secret: str | None) -> tuple[ApiKey, Firm]:
    """The key and firm behind an X-API-Key header. Unknown, revoked and inactive all look the
    same to the caller."""
    if not secret or not secret.startswith(KEY_PREFIX):
        raise AuthError("API_KEY_INVALID", 401)
    row = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_token(secret)))
    firm = db.get(Firm, row.firm_id) if row else None
    if row is None or row.revoked_at is not None or firm is None or not firm.is_active:
        raise AuthError("API_KEY_INVALID", 401)
    return row, firm


def record_call(db: Session, key: ApiKey, endpoint: str) -> None:
    """Rate-limit the key per minute (D28's table), then count the call for the usage log."""
    if not ratelimit.allow(
        db, "api-key", str(key.id), key.rate_limit_per_minute, dt.timedelta(minutes=1)
    ):
        db.commit()
        raise AuthError("RATE_LIMITED", 429)
    day = today_dhaka()
    usage = db.scalar(
        select(ApiUsage).where(
            ApiUsage.api_key_id == key.id, ApiUsage.date == day, ApiUsage.endpoint == endpoint
        )
    )
    if usage is None:
        usage = ApiUsage(api_key_id=key.id, date=day, endpoint=endpoint, calls=0)
        db.add(usage)
    usage.calls += 1
    key.last_used_at = utcnow()
    db.flush()


def usage(db: Session, firm_id: uuid.UUID, days: int = 30) -> list[dict[str, Any]]:
    since = today_dhaka() - dt.timedelta(days=days - 1)
    rows = db.execute(
        select(ApiUsage.date, ApiKey.name, ApiUsage.endpoint, ApiUsage.calls)
        .join(ApiKey, ApiKey.id == ApiUsage.api_key_id)
        .where(ApiKey.firm_id == firm_id, ApiUsage.date >= since)
        .order_by(ApiUsage.date.desc(), ApiKey.name, ApiUsage.endpoint)
    ).all()
    return [{"date": d, "key": n, "endpoint": e, "calls": c} for d, n, e, c in rows]


# --- data shared by the CSV exports and the API (FR9.2) -----------------------------------


def shariah_rows(db: Session) -> tuple[list[dict[str, Any]], dt.datetime | None, set[uuid.UUID]]:
    items, newest, sources = screening.list_items(db)
    return items, newest, sources


def score_rows(db: Session) -> tuple[list[dict[str, Any]], dt.datetime | None]:
    rows = list(
        db.scalars(
            select(Score)
            .where(Score.subject_type == "TICKER", Score.score_type == "RATE_SENSITIVITY")
            .order_by(Score.subject)
        )
    )
    out = [
        {
            "ticker": r.subject,
            "rate_sensitivity_pct": r.value,
            "std_error": r.std_error,
            "confidence": r.confidence,
            "observations": r.n_obs,
            "sample_start": r.sample_start,
            "sample_end": r.sample_end,
            "computed_at": r.computed_at,
        }
        for r in rows
    ]
    return out, max((r.computed_at for r in rows), default=None)


def _csv(columns: list[str], rows: list[dict[str, Any]], trailer: list[str]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if row.get(c) is None else str(row.get(c)) for c in columns])
    for line in trailer:
        writer.writerow([line])
    return out.getvalue()


DISCLAIMER = "Historical analysis for education only. Not investment advice."


def shariah_csv(db: Session) -> str:
    """analysisACE's own screen, never the DSE's licensed constituent list."""
    rows, newest, _ = shariah_rows(db)
    columns = ["ticker", "name", "sector", "status", "method_version", "screened_at", "market_cap"]
    trailer = [
        f"# Screened by analysisACE; as of {newest.isoformat() if newest else '-'}",
        f"# {DISCLAIMER}",
    ]
    return _csv(columns, rows, trailer)


def scores_csv(db: Session) -> str:
    rows, computed = score_rows(db)
    columns = [
        "ticker",
        "rate_sensitivity_pct",
        "std_error",
        "confidence",
        "observations",
        "sample_start",
        "sample_end",
        "computed_at",
    ]
    trailer = [
        "# Typical weekly move per 1-point rise in the 91-day T-bill yield;"
        " history, not a forecast",
        f"# Computed {computed.isoformat() if computed else '-'}",
        f"# {DISCLAIMER}",
    ]
    return _csv(columns, rows, trailer)
