"""
FastAPI app entrypoint.

Run locally:
    uvicorn api.main:app --reload --port 8000

Background loop: polls candidate.yaml + resumes/ every
WATCH_INTERVAL_SECONDS (default 60) via services/file_watcher.py. Runs
in-process for local mode; the design (a plain async function on a
timer, writing to the same DB the API reads from) means it can move to
a separate worker process/task queue later without changing the
watcher logic itself.
"""
from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    auth, candidates, approval_queue, jobs, resumes,
    candidate_auth, candidate_self, candidate_review, candidate_email_account,
    applications, job_posting, reports, superuser,
    invite, staff_auth, staff, candidate_config,
    candidate_documents, candidate_artifact_review, organization_settings, dashboard,
    push,
)
from db.session import get_session_factory
from services.file_watcher import run_watch_cycle
from services.storage import get_storage

app = FastAPI(title="AI Recruiter Agent API", version="0.1.0")

_allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(approval_queue.router)
app.include_router(jobs.router)
app.include_router(resumes.router)
app.include_router(candidate_auth.router)
app.include_router(candidate_self.router)
app.include_router(candidate_review.router)
app.include_router(candidate_email_account.router)
app.include_router(applications.router)
app.include_router(job_posting.router)
app.include_router(reports.router)
app.include_router(superuser.router)
app.include_router(invite.router)
app.include_router(staff_auth.router)
app.include_router(staff.router)
app.include_router(candidate_config.router)
app.include_router(candidate_documents.router)
app.include_router(candidate_artifact_review.router)
app.include_router(organization_settings.router)
app.include_router(dashboard.router)
app.include_router(push.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


async def _background_watch_loop() -> None:
    interval = int(os.environ.get("WATCH_INTERVAL_SECONDS", "60"))
    SessionFactory = get_session_factory()
    storage = get_storage()
    while True:
        try:
            with SessionFactory() as session:
                run_watch_cycle(session, storage)
        except Exception as e:  # noqa: BLE001 -- the loop must survive one bad cycle
            print(f"[watch loop] error: {e}")
        await asyncio.sleep(interval)


@app.on_event("startup")
async def _start_background_loop() -> None:
    if os.environ.get("DISABLE_WATCH_LOOP") != "1":
        asyncio.create_task(_background_watch_loop())
