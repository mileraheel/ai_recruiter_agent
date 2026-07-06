"""
Storage abstraction: everything that reads/writes resume files, generated
docx/signatures, and uploaded screenshots goes through this interface --
never touches the filesystem directly from routers/services. That's the
whole point: swapping local disk for S3/Azure Blob later means writing
one new class here, not touching call sites across the app.

Selected via STORAGE_BACKEND env var ("local" today; "s3"/"azure_blob"
later would each be a new class implementing the same interface).
"""
from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path


class Storage(ABC):
    @abstractmethod
    def save(self, key: str, content: bytes) -> str:
        """Writes content under `key` (e.g. 'resumes/raheel_ahmed_khan.docx').
        Returns a value the caller can persist to reference this file
        later (local path today; would be an object key/URL for cloud
        backends) -- callers should treat the return value as opaque."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def list(self, prefix: str = "") -> list[str]:
        """Returns keys under `prefix`, relative to the storage root."""


class LocalStorage(Storage):
    """Local-disk backend. root_dir defaults to STORAGE_ROOT env var or
    ./storage relative to the process working directory."""

    def __init__(self, root_dir: str | Path | None = None):
        self.root = Path(root_dir or os.environ.get("STORAGE_ROOT", ".")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Prevent path traversal outside the storage root via a key like
        # "../../etc/passwd" -- resolve and verify containment before any
        # read/write/delete touches the filesystem.
        candidate = (self.root / key).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError(f"Storage key resolves outside storage root: {key!r}")
        return candidate

    def save(self, key: str, content: bytes) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def read(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def list(self, prefix: str = "") -> list[str]:
        base = self._resolve(prefix) if prefix else self.root
        if not base.exists():
            return []
        if base.is_file():
            return [str(base.relative_to(self.root))]
        return [
            str(p.relative_to(self.root))
            for p in base.rglob("*")
            if p.is_file()
        ]


class DatabaseStorage(Storage):
    """Stores file content as rows in the stored_files table instead of
    local disk. This is the correct default once more than one thing
    (or, later, more than one process/pod) needs to read the same
    files: local disk isn't shared across instances, the DB already is.
    Same key scheme as LocalStorage -- nothing calling Storage needs to
    know which backend is active.

    Session-per-call rather than a held-open session, since Storage
    instances get created fresh per request via the get_app_storage
    FastAPI dependency but may also be used from the background watch
    loop, which manages its own longer-lived session lifecycle."""

    def _session_factory(self):
        from db.session import get_session_factory

        return get_session_factory()

    def save(self, key: str, content: bytes) -> str:
        from db.models import StoredFile

        SessionFactory = self._session_factory()
        with SessionFactory() as session:
            row = session.query(StoredFile).filter_by(key=key).one_or_none()
            if row is None:
                row = StoredFile(key=key)
                session.add(row)
            row.content = content
            row.size_bytes = len(content)
            session.commit()
        return key

    def read(self, key: str) -> bytes:
        from db.models import StoredFile

        SessionFactory = self._session_factory()
        with SessionFactory() as session:
            row = session.query(StoredFile).filter_by(key=key).one_or_none()
            if row is None:
                raise FileNotFoundError(f"No stored file for key: {key!r}")
            return row.content

    def exists(self, key: str) -> bool:
        from db.models import StoredFile

        SessionFactory = self._session_factory()
        with SessionFactory() as session:
            return session.query(StoredFile.id).filter_by(key=key).first() is not None

    def delete(self, key: str) -> None:
        from db.models import StoredFile

        SessionFactory = self._session_factory()
        with SessionFactory() as session:
            row = session.query(StoredFile).filter_by(key=key).one_or_none()
            if row is not None:
                session.delete(row)
                session.commit()

    def list(self, prefix: str = "") -> list[str]:
        from db.models import StoredFile

        SessionFactory = self._session_factory()
        with SessionFactory() as session:
            query = session.query(StoredFile.key)
            if prefix:
                query = query.filter(StoredFile.key.like(f"{prefix}%"))
            return [row[0] for row in query.all()]


def get_storage() -> Storage:
    backend = os.environ.get("STORAGE_BACKEND", "local")
    if backend == "local":
        return LocalStorage()
    if backend == "db":
        return DatabaseStorage()
    raise NotImplementedError(
        f"Storage backend '{backend}' is not implemented yet. Implement a new "
        f"Storage subclass in services/storage.py (e.g. S3Storage, "
        f"AzureBlobStorage) and register it here -- no other code should need "
        f"to change, since all callers go through the Storage interface."
    )
