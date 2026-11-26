"""Per-visitor and per-address limits on sign-up, sign-in, password reset and verification
emails (D28). A small table instead of Redis: the volumes are low, and the database is
already there.

Keys are stored only as SHA-256 hashes, so the table holds no IP or email address. Each
attempt is recorded before the request does its work, so attempts that then fail (a wrong
password, an address already taken) still count.
"""

import datetime as dt
import ipaddress
from functools import lru_cache

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_token, utcnow
from app.models import RateLimitHit


@lru_cache(maxsize=8)
def _networks(spec: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    out = []
    for part in spec.split(","):
        part = part.strip()
        if part:
            out.append(ipaddress.ip_network(part, strict=False))
    return tuple(out)


def _parse_ip(text: str | None) -> str | None:
    if not text:
        return None
    try:
        return str(ipaddress.ip_address(text.strip()))
    except ValueError:
        return None


def client_ip(peer: str | None, forwarded_for: str | None, settings: Settings) -> str:
    """The visitor's address. The browser reaches the API only through the web server, so
    the API sees the web server; the web server passes the visitor on in X-Forwarded-For.
    That header is believed only from TRUSTED_PROXIES, since anyone else could invent it."""
    direct = _parse_ip(peer) or "unknown"
    if direct == "unknown" or not forwarded_for:
        return direct
    address = ipaddress.ip_address(direct)
    if not any(address in net for net in _networks(settings.trusted_proxies)):
        return direct
    first = _parse_ip(forwarded_for.split(",")[0])
    return first or direct


def is_loopback(address: str) -> bool:
    """This machine itself (127.0.0.1, ::1)."""
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def allow(db: Session, bucket: str, key: str, limit: int, window: dt.timedelta) -> bool:
    """Record one attempt for (bucket, key) and say whether it is within the limit. A refused
    attempt is not recorded, so a blocked visitor is free again when the window passes."""
    if limit <= 0:
        return True
    key_hash = hash_token(f"{bucket}:{key.strip().lower()}")
    since = utcnow() - window
    used = db.scalar(
        select(func.count())
        .select_from(RateLimitHit)
        .where(
            RateLimitHit.bucket == bucket,
            RateLimitHit.key_hash == key_hash,
            RateLimitHit.created_at >= since,
        )
    )
    if (used or 0) >= limit:
        return False
    db.add(RateLimitHit(bucket=bucket, key_hash=key_hash, created_at=utcnow()))
    db.flush()
    return True


def purge(db: Session, older_than: dt.timedelta = dt.timedelta(days=1)) -> int:
    """Delete attempts past every window. Run daily by the worker."""
    result = db.execute(
        delete(RateLimitHit)
        .where(RateLimitHit.created_at < utcnow() - older_than)
        .execution_options(synchronize_session=False)
    )
    db.flush()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
