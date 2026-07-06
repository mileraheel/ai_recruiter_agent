"""
Applications history + reporting, scoped to the admin's own
organization (same join-through-Candidate pattern used everywhere else
for tenant isolation). This is what survives a page refresh -- unlike
a posted batch's in-memory review screen, everything here reads
straight from the DB rows created by post-and-match/prepare/send.

pipeline_stage and Interview rows are manually updated by the admin for
now -- there's no inbox monitoring yet to detect a recruiter's reply or
an interview invite automatically. The schema is written so that a
future automated version updates these exact same fields/rows rather
than needing a parallel structure.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_current_admin, get_db
from api.schemas import (
    ApplicationDetail,
    ApplicationsReportSummary,
    ApplicationSummary,
    InterviewCreateRequest,
    InterviewResponse,
    InterviewUpdateRequest,
    PaginatedResponse,
    PipelineUpdateRequest,
)
from db.models import AdminUser, Candidate, Email, FollowUp, Interview, Job

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_admin)])

_VALID_STAGES = {"contacted", "client_submitted", "interviewing", "offer", "rejected", "withdrawn"}
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def _to_summary(email: Email, job: Job, candidate: Candidate, interview_count: int, latest_interview_at) -> ApplicationSummary:
    return ApplicationSummary(
        email_id=email.id,
        candidate_slug=candidate.slug,
        candidate_full_name=candidate.full_name,
        job_id=job.id,
        job_title=job.job_title,
        company_name=job.company_name,
        to_email=email.to_email,
        send_status=email.status,
        pipeline_stage=email.pipeline_stage,
        submitted_to_client_at=email.submitted_to_client_at,
        interview_count=interview_count,
        latest_interview_at=latest_interview_at,
        sent_at=email.sent_at,
        created_at=email.created_at,
    )


@router.get("/applications", response_model=PaginatedResponse[ApplicationSummary])
def list_applications(
    candidate_slug: str | None = None,
    pipeline_stage: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    query = (
        db.query(Email, Job, Candidate)
        .join(Candidate, Email.candidate_id == Candidate.id)
        .join(Job, Email.job_id == Job.id)
        .filter(Candidate.organization_id == admin.organization_id)
    )
    if candidate_slug:
        query = query.filter(Candidate.slug == candidate_slug)
    if pipeline_stage:
        query = query.filter(Email.pipeline_stage == pipeline_stage)

    total = query.count()
    page = query.order_by(Email.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for email, job, candidate in page:
        interviews = db.query(Interview).filter_by(email_id=email.id).all()
        latest = max((i.scheduled_at for i in interviews if i.scheduled_at), default=None)
        results.append(_to_summary(email, job, candidate, len(interviews), latest))
    return PaginatedResponse(items=results, total=total, limit=limit, offset=offset)


@router.get("/applications/{email_id}", response_model=ApplicationDetail)
def get_application(email_id: int, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    email = db.query(Email).filter_by(id=email_id).one_or_none()
    if email is None:
        raise HTTPException(status_code=404, detail="Application not found")
    candidate = db.query(Candidate).filter_by(id=email.candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Application not found")
    job = db.query(Job).filter_by(id=email.job_id).one_or_none()

    interviews = db.query(Interview).filter_by(email_id=email.id).order_by(Interview.scheduled_at.asc()).all()
    latest = max((i.scheduled_at for i in interviews if i.scheduled_at), default=None)
    summary = _to_summary(email, job, candidate, len(interviews), latest)

    resume_file_name = email.resume_file_path.rsplit("/", 1)[-1] if email.resume_file_path else None
    return ApplicationDetail(
        **summary.model_dump(),
        subject=email.subject,
        body=email.body,
        resume_file_name=resume_file_name,
        pipeline_notes=email.pipeline_notes,
        interviews=[InterviewResponse.model_validate(i) for i in interviews],
    )


@router.patch("/applications/{email_id}/pipeline", response_model=ApplicationDetail)
def update_pipeline(
    email_id: int,
    payload: PipelineUpdateRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    email = db.query(Email).filter_by(id=email_id).one_or_none()
    if email is None:
        raise HTTPException(status_code=404, detail="Application not found")
    candidate = db.query(Candidate).filter_by(id=email.candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Application not found")

    from services.followup_service import (
        check_resubmission_dedup,
        record_client_submission,
        schedule_client_submission_followup,
    )

    dedup_warning = None
    becoming_client_submitted = (
        payload.pipeline_stage == "client_submitted" and email.pipeline_stage != "client_submitted"
    ) or (payload.mark_submitted_to_client_now and email.pipeline_stage not in ("client_submitted",))

    if becoming_client_submitted and payload.end_client_name:
        existing = check_resubmission_dedup(
            db, candidate.id, admin.organization_id, payload.end_client_name, payload.location
        )
        if existing:
            dedup_warning = (
                f"Heads up: {candidate.full_name} was already submitted to "
                f"'{existing.end_client_name}'"
                + (f" ({existing.location})" if existing.location else "")
                + f" on {existing.submitted_at.date().isoformat()} -- this may be a duplicate "
                f"submission via a different recruiter/vendor. Recorded anyway since the "
                f"submission already happened; review before any further outreach for this client."
            )
        record_client_submission(
            db, candidate.id, email.id, payload.end_client_name, payload.implementation_partner_name, payload.location
        )

    if payload.pipeline_stage is not None:
        if payload.pipeline_stage not in _VALID_STAGES:
            raise HTTPException(status_code=422, detail=f"pipeline_stage must be one of {sorted(_VALID_STAGES)}")
        email.pipeline_stage = payload.pipeline_stage
        if payload.pipeline_stage == "client_submitted" and email.submitted_to_client_at is None:
            email.submitted_to_client_at = datetime.now(timezone.utc)

    if payload.mark_submitted_to_client_now:
        email.submitted_to_client_at = datetime.now(timezone.utc)
        if email.pipeline_stage in (None, "contacted"):
            email.pipeline_stage = "client_submitted"

    if payload.pipeline_notes is not None:
        email.pipeline_notes = payload.pipeline_notes

    db.commit()

    if becoming_client_submitted:
        schedule_client_submission_followup(db, email)

    result = get_application(email_id, db, admin)
    result.dedup_warning = dedup_warning
    return result


@router.post("/applications/{email_id}/interviews", response_model=InterviewResponse)
def add_interview(
    email_id: int,
    payload: InterviewCreateRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    email = db.query(Email).filter_by(id=email_id).one_or_none()
    if email is None:
        raise HTTPException(status_code=404, detail="Application not found")
    candidate = db.query(Candidate).filter_by(id=email.candidate_id).one_or_none()
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Application not found")

    interview = Interview(
        email_id=email_id,
        round_name=payload.round_name,
        scheduled_at=payload.scheduled_at,
        notes=payload.notes,
    )
    db.add(interview)

    # An interview existing at all implies the pipeline reached at
    # least 'interviewing' -- bump it forward automatically unless
    # already further along (offer/rejected/withdrawn), never backward.
    if email.pipeline_stage in (None, "contacted", "client_submitted"):
        email.pipeline_stage = "interviewing"

    db.commit()
    db.refresh(interview)
    return interview


@router.patch("/interviews/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: int,
    payload: InterviewUpdateRequest,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    interview = db.query(Interview).filter_by(id=interview_id).one_or_none()
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    email = db.query(Email).filter_by(id=interview.email_id).one_or_none()
    candidate = db.query(Candidate).filter_by(id=email.candidate_id).one_or_none() if email else None
    if candidate is None or candidate.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Interview not found")

    if payload.round_name is not None:
        interview.round_name = payload.round_name
    if payload.scheduled_at is not None:
        interview.scheduled_at = payload.scheduled_at
    becoming_completed = payload.status == "completed" and interview.status != "completed"
    if payload.status is not None:
        interview.status = payload.status
    if payload.notes is not None:
        interview.notes = payload.notes

    db.commit()
    db.refresh(interview)

    if becoming_completed:
        from services.followup_service import schedule_post_interview_followup

        schedule_post_interview_followup(db, email)

    return interview


@router.get("/followups/due", response_model=list[dict])
def list_due_followups(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    from services.followup_service import get_due_followups

    due = get_due_followups(db, admin.organization_id)
    results = []
    for fu in due:
        email = db.query(Email).filter_by(id=fu.email_id).one_or_none() if fu.email_id else None
        job = db.query(Job).filter_by(id=fu.job_id).one_or_none()
        candidate = db.query(Candidate).filter_by(id=email.candidate_id).one_or_none() if email else None
        results.append({
            "follow_up_id": fu.id,
            "follow_up_type": fu.follow_up_type,
            "next_follow_up_date": fu.next_follow_up_date,
            "email_id": fu.email_id,
            "job_title": job.job_title if job else None,
            "candidate_name": candidate.full_name if candidate else None,
        })
    return results


@router.post("/followups/{follow_up_id}/send")
def send_followup(
    follow_up_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    """Composes the templated follow-up text, updates the ORIGINAL
    application email's body/subject with it, and reuses the existing
    two-step prepare/send infrastructure -- no separate send mechanism.
    Marks the FollowUp row 'sent' regardless of outcome recording, but
    the actual Gmail action still goes through send_prepared_email's
    normal confirm/gating."""
    from core.followup_composer import FOLLOW_UP_COMPOSERS

    fu = db.query(FollowUp).filter_by(id=follow_up_id).one_or_none()
    if fu is None or fu.organization_id != admin.organization_id:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    if fu.status != "scheduled":
        raise HTTPException(status_code=409, detail=f"Follow-up already {fu.status}")

    email = db.query(Email).filter_by(id=fu.email_id).one_or_none()
    job = db.query(Job).filter_by(id=fu.job_id).one_or_none()
    candidate = db.query(Candidate).filter_by(id=email.candidate_id).one_or_none() if email else None
    if not (email and job and candidate):
        raise HTTPException(status_code=422, detail="Missing underlying application data for this follow-up.")

    composer = FOLLOW_UP_COMPOSERS.get(fu.follow_up_type)
    if composer is None:
        raise HTTPException(status_code=500, detail=f"No composer for follow-up type '{fu.follow_up_type}'")

    if fu.follow_up_type == "client_submission":
        body_text = composer(email, job, candidate.full_name, None)
    else:
        body_text = composer(email, job, candidate.full_name)

    # A follow-up is a NEW email in the thread, not a re-send of the
    # original -- create its own Email row (draft) referencing the same
    # job/candidate, then run it through the normal prepare/send gate.
    followup_email = Email(
        candidate_id=candidate.id,
        job_id=job.id,
        job_contact_id=email.job_contact_id,
        to_email=email.to_email,
        from_email=email.from_email,
        subject=f"Re: {job.job_title or 'your opportunity'} -- Follow-up",
        body=body_text,
        status="draft",
    )
    db.add(followup_email)
    fu.follow_up_count += 1
    fu.last_follow_up_sent_at = datetime.now(timezone.utc)
    fu.status = "sent"
    db.commit()
    db.refresh(followup_email)

    return {
        "follow_up_id": fu.id,
        "new_email_id": followup_email.id,
        "message": "Follow-up drafted as a new email -- call /api/applications/emails/{id}/send with confirm=true to actually send it.",
    }


@router.get("/summary", response_model=ApplicationsReportSummary)
def applications_summary(db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    rows = (
        db.query(Email, Candidate)
        .join(Candidate, Email.candidate_id == Candidate.id)
        .filter(Candidate.organization_id == admin.organization_id)
        .all()
    )

    total_prepared = len(rows)
    total_sent = sum(1 for e, _ in rows if e.status in ("sent", "approved"))
    total_client_submitted = sum(1 for e, _ in rows if e.pipeline_stage == "client_submitted")
    total_interviewing = sum(1 for e, _ in rows if e.pipeline_stage == "interviewing")
    total_offers = sum(1 for e, _ in rows if e.pipeline_stage == "offer")
    total_rejected = sum(1 for e, _ in rows if e.pipeline_stage == "rejected")

    by_candidate: dict[str, int] = {}
    for _, candidate in rows:
        by_candidate[candidate.full_name] = by_candidate.get(candidate.full_name, 0) + 1

    return ApplicationsReportSummary(
        total_prepared=total_prepared,
        total_sent=total_sent,
        total_client_submitted=total_client_submitted,
        total_interviewing=total_interviewing,
        total_offers=total_offers,
        total_rejected=total_rejected,
        by_candidate=by_candidate,
    )
