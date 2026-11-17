"""Encrypted document storage behind an interface (FR25.4, FR23.3).

Object storage is not chosen yet (PRD section 11 names S3-compatible storage). Until it
is, files are encrypted and kept on the server's disk. Swap `get_document_storage` for an
S3 implementation of the same protocol; callers do not change.
"""

import uuid
from pathlib import Path
from typing import Protocol

from app.core import crypto
from app.core.config import get_settings


class DocumentStorage(Protocol):
    def put(self, data: bytes) -> str:
        """Store `data` encrypted. Returns the key to read it back with."""
        ...

    def get(self, ref: str) -> bytes: ...

    def delete(self, ref: str) -> None: ...


class LocalEncryptedStorage:
    """One encrypted file per document under a directory. Names are random, never the
    uploaded filename, so nothing about the content shows on disk."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, ref: str) -> Path:
        # A ref is always a UUID we made; anything else could point outside the directory.
        return self.directory / f"{uuid.UUID(ref)}.bin"

    def put(self, data: bytes) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        ref = str(uuid.uuid4())
        self._path(ref).write_bytes(crypto.encrypt_bytes(data))
        return ref

    def get(self, ref: str) -> bytes:
        return crypto.decrypt_bytes(self._path(ref).read_bytes())

    def delete(self, ref: str) -> None:
        self._path(ref).unlink(missing_ok=True)


def get_document_storage() -> DocumentStorage:
    """FastAPI dependency. Tests override it with a temporary directory."""
    return LocalEncryptedStorage(get_settings().document_storage_dir)
