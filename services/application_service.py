"""
Core prepare/send logic, extracted so it's callable both from a single
job (api/routers/applications.py) and from the multi-candidate fan-out
flow (api/routers/job_posting.py) without duplicating it.

Two distinct operations, kept separate on purpose:
  - prepare_application_for_job: pure generation (tailor resume, compose
    email, save as a draft Email row). No external call, safe to run
    automatically across every matched candidate when a job is posted.
  - send_prepared_email: the one real external action (Gmail draft or
    actual send). NEVER called automatically as part of posting a job
    -- always requires a separate, explicit confirm step from the admin,
    whether for one email or a batch of them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.email_composer import compose_email
from db.models import Candidate, Email, EmailAccountCredential, Job, JobContact, Organization
from services.candidate_directory import CandidateResolution, resolve_candidate_profile_for_row
from services.crypto import decrypt_secret
from services.gmail_client import build_mime_message, create_draft, send_message
from services.resume_service import ResumeGenerationError, get_or_generate_tailored_resume
from services.storage import Storage


class ApplicationError(Exception):
    """Raised for any failure preparing/sending -- callers map this to
    the right HTTP status per-endpoint, and batch callers catch it
    per-item so one candidate's failure doesn't abort the whole batch."""


@dataclass
class PreparedApplication:
    email_id: int
    to_email: str | None
    subject: str
    body: str
    resume_file_name: str
    resume_human_review_required: bool
    resume_risk_notes: str | None


def prepare_application_for_job(
    db: Session, storage: Storage, job: Job, candidate_row: Candidate, resolution: CandidateResolution | None = None
) -> PreparedApplication:
    resolution = resolution or resolve_candidate_profile_for_row(db, candidate_row)
    if resolution.status != "ok":
        raise ApplicationError(resolution.message or "Candidate is not active.")
    profile = resolution.profile

    if candidate_row.organization_id is not None:
        from services.volume_limits import check_application_volume

        within_volume, volume_reason = check_application_volume(db, candidate_row.organization_id)
        if not within_volume:
            raise ApplicationError(volume_reason)

    recruiter_email = None
    recruiter_name = None
    if job.job_contact_id:
        contact = db.query(JobContact).filter_by(id=job.job_contact_id).one_or_none()
        if contact:
            recruiter_email = contact.recruiter_email
            recruiter_name = contact.recruiter_name

    try:
        resume_version = get_or_generate_tailored_resume(db, storage, job, candidate_row, resolution)
    except ResumeGenerationError as e:
        raise ApplicationError(str(e))

    try:
        composed = compose_email(
            candidate=profile.candidate,
            job_title=job.job_title or resume_version.target_role or "the role",
            job_description_text=job.description_text or "",
            recruiter_name=recruiter_name,
        )
    except ValueError as e:
        # e.g. career_start_date missing on this candidate's approved
        # profile -- a per-candidate data problem, not a reason to fail
        # the whole batch fan-out with an unhandled 500.
        raise ApplicationError(str(e))
    subject = f"Re: {job.job_title}" if job.job_title else "Application"

    email_row = Email(
        candidate_id=candidate_row.id,
        job_id=job.id,
        job_contact_id=job.job_contact_id,
        to_email=recruiter_email,
        from_email=profile.email.from_email,
        subject=subject,
        body=composed.body,
        resume_file_path=resume_version.file_path,
        status="draft",
    )
    db.add(email_row)
    db.commit()
    db.refresh(email_row)

    return PreparedApplication(
        email_id=email_row.id,
        to_email=recruiter_email,
        subject=subject,
        body=composed.body,
        resume_file_name=resume_version.file_name,
        resume_human_review_required=resume_version.human_review_required,
        resume_risk_notes=resume_version.risk_notes,
    )


@dataclass
class SendResult:
    email_id: int
    status: str
    gmail_object_id: str | None
    send_mode: str | None
    held_for_business_hours: bool = False


def send_prepared_email(db: Session, storage: Storage, email_id: int) -> SendResult:
    """Callers MUST have already obtained explicit confirmation before
    calling this -- there is no confirm param here because both call
    sites (single-send and batch-send endpoints) enforce it at the API
    layer, once, rather than each reimplementing the check."""
    email_row = db.query(Email).filter_by(id=email_id).one_or_none()
    if email_row is None:
        raise ApplicationError("Prepared email not found -- call /prepare first.")
    if email_row.status in ("sent", "approved"):
        raise ApplicationError(
            f"Already {'sent' if email_row.status == 'sent' else 'drafted in Gmail'} "
            f"(status={email_row.status})."
        )
    if not email_row.to_email:
        raise ApplicationError("No recruiter email on file for this job -- cannot send.")

    candidate_row = db.query(Candidate).filter_by(id=email_row.candidate_id).one_or_none()
    if candidate_row is None:
        raise ApplicationError("Candidate not found.")

    cred = (
        db.query(EmailAccountCredential)
        .filter_by(candidate_id=candidate_row.id, provider="gmail", status="connected")
        .one_or_none()
    )
    if cred is None:
        raise ApplicationError(f"{candidate_row.full_name} has no connected Gmail account.")

    resolution = resolve_candidate_profile_for_row(db, candidate_row)
    send_mode = resolution.profile.email.send_mode if resolution.status == "ok" else "draft_first"

    held_for_business_hours = False
    if candidate_row.organization_id is not None:
        from services.business_hours import is_within_business_hours
        from services.volume_limits import check_email_volume

        org = db.query(Organization).filter_by(id=candidate_row.organization_id).one_or_none()

        within_volume, volume_reason = check_email_volume(db, candidate_row.organization_id)
        if not within_volume:
            raise ApplicationError(volume_reason)

        if org is not None and send_mode == "send_directly" and not is_within_business_hours(org):
            # Held back, not blocked: draft it into the candidate's own
            # Gmail instead of erroring uselessly -- they (or the admin)
            # can send it manually, or it'll go out automatically next
            # time this runs within business hours.
            send_mode = "draft_first"
            held_for_business_hours = True

    resume_bytes = storage.read(email_row.resume_file_path) if email_row.resume_file_path else None
    resume_filename = email_row.resume_file_path.rsplit("/", 1)[-1] if email_row.resume_file_path else None

    raw_mime = build_mime_message(
        to_email=email_row.to_email,
        from_email=email_row.from_email or cred.account_email,
        subject=email_row.subject or "Application",
        body_text=email_row.body or "",
        attachment_bytes=resume_bytes,
        attachment_filename=resume_filename,
    )

    refresh_token = decrypt_secret(cred.encrypted_secret)

    try:
        if send_mode == "send_directly":
            gmail_object_id = send_message(refresh_token, raw_mime)
            email_row.status = "sent"
            email_row.sent_at = datetime.now(timezone.utc)
            if email_row.pipeline_stage is None:
                email_row.pipeline_stage = "contacted"
        else:
            gmail_object_id = create_draft(refresh_token, raw_mime)
            email_row.status = "approved"
    except Exception as e:  # noqa: BLE001
        email_row.status = "failed"
        email_row.error_message = str(e)
        db.commit()
        raise ApplicationError(f"Gmail API call failed: {e}")

    email_row.gmail_object_id = gmail_object_id
    db.commit()
    db.refresh(email_row)

    if email_row.status == "sent":
        # Follow-up scheduling only fires on a CONFIRMED send
        # (send_directly) -- not for draft_first's 'approved' status,
        # since there's no signal yet the candidate actually sent the
        # drafted email. See followup_service.py's docstring.
        from services.followup_service import schedule_initial_outreach_followup

        schedule_initial_outreach_followup(db, email_row)

    return SendResult(
        email_id=email_row.id,
        status=email_row.status,
        gmail_object_id=gmail_object_id,
        send_mode=send_mode,
        held_for_business_hours=held_for_business_hours,
    )
