"""
Resume file watcher: a recruiter/admin can drop a new/updated .docx
directly into storage for a candidate (bypassing the /api/me/resume
upload endpoint, which already triggers ingestion synchronously). This
catches that case on a timer.

Candidate creation/removal is no longer YAML-driven (candidates are
created via signup/invite now), so there is no config-file watcher
anymore -- just this one function, looping every organization's
candidates via the DB.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import Candidate, FileWatchState, Organization
from services.candidate_directory import resume_storage_key
from services.resume_ingestion import ingest_resume
from services.storage import Storage


def _file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def get_watch_state(session: Session, file_path: str, file_kind: str) -> FileWatchState:
    state = session.query(FileWatchState).filter_by(file_path=file_path).one_or_none()
    if state is None:
        state = FileWatchState(file_path=file_path, file_kind=file_kind, last_hash=None)
        session.add(state)
        session.flush()
    return state


def check_resumes(session: Session, storage: Storage) -> list[dict]:
    """For every candidate in every organization, checks whether their
    (org-namespaced) resume file exists and whether its content hash
    has changed since last seen. On change, triggers ingest_resume() --
    which only ever produces status='pending' suggestions, never
    auto-approves anything."""
    from services.candidate_directory import list_all_candidate_resolutions

    results = []

    for org in session.query(Organization).all():
        for slug, resolution in list_all_candidate_resolutions(session, org.id):
            candidate_row = (
                session.query(Candidate).filter_by(organization_id=org.id, slug=slug).one_or_none()
            )
            if candidate_row is None:
                continue

            resume_path = (
                resolution.profile.candidate.base_resume_path
                if resolution.status == "ok"
                else resume_storage_key(org.name, slug)
            )

            if not storage.exists(resume_path):
                results.append(
                    {"organization": org.name, "candidate": slug, "resume_path": resume_path, "status": "resume_file_missing"}
                )
                continue

            content = storage.read(resume_path)
            new_hash = _file_hash(content)
            state = get_watch_state(session, resume_path, "resume")

            if state.last_hash == new_hash:
                results.append(
                    {"organization": org.name, "candidate": slug, "resume_path": resume_path, "status": "unchanged"}
                )
                continue

            run = ingest_resume(
                session,
                candidate=candidate_row,
                resume_file_path=resume_path,
                file_bytes=content,
                file_hash=new_hash,
                triggered_by="file_watcher",
            )

            state.last_hash = new_hash
            state.last_checked_at = datetime.now(timezone.utc)
            session.commit()

            results.append({
                "organization": org.name,
                "candidate": slug,
                "resume_path": resume_path,
                "status": "ingested" if run.status == "completed" else "ingestion_failed",
                "new_skills_suggested": run.new_skills_suggested,
                "error": run.error_message,
            })

    return results


def run_watch_cycle(session: Session, storage: Storage, config_path: str | None = None) -> dict:
    """config_path is accepted (and ignored) for backward compatibility
    with existing callers -- there's no config file to check anymore."""
    resume_results = check_resumes(session, storage)
    return {"resumes": resume_results}
