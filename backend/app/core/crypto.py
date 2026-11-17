"""Field-level encryption for account numbers and documents (FR23.3).

Fernet (AES-128-CBC with an HMAC) from the `cryptography` package. The key comes from
`DATA_ENCRYPTION_KEY`. In development only, a key is created in `backend/.dev-encryption-key`
on first use so the features work without setup; it is ignored by git.

Key rotation: set `DATA_ENCRYPTION_KEY` to "new,old". New data uses the first key; data
written with any listed key can still be read. Re-encrypt, then drop the old key.
"""

from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import REPO_ROOT, get_settings

DEV_KEY_FILE = REPO_ROOT / "backend" / ".dev-encryption-key"


class EncryptionUnavailable(Exception):
    """No key is configured, or the data cannot be read with the configured keys."""


def _dev_key(path: Path) -> str:
    if not path.exists():
        path.write_text(Fernet.generate_key().decode("ascii"), encoding="ascii")
    return path.read_text(encoding="ascii").strip()


@lru_cache
def _fernet() -> MultiFernet:
    settings = get_settings()
    raw = settings.data_encryption_key
    if not raw:
        if settings.environment != "development":
            raise EncryptionUnavailable("DATA_ENCRYPTION_KEY is not set")
        raw = _dev_key(DEV_KEY_FILE)
    try:
        return MultiFernet([Fernet(key.strip().encode("ascii")) for key in raw.split(",")])
    except ValueError as exc:
        raise EncryptionUnavailable("DATA_ENCRYPTION_KEY is not a valid Fernet key") from exc


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _fernet().decrypt(token)
    except InvalidToken as exc:
        raise EncryptionUnavailable("Stored data cannot be decrypted with the current key") from exc


def encrypt_text(value: str) -> str:
    return encrypt_bytes(value.encode("utf-8")).decode("ascii")


def decrypt_text(token: str) -> str:
    return decrypt_bytes(token.encode("ascii")).decode("utf-8")
