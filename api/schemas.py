"""
API-layer Pydantic schemas -- request/response shapes for the FastAPI
routers. Kept separate from config/schema.py (which validates
candidate.yaml) and db/models.py (SQLAlchemy ORM): this layer is what
the React frontend actually talks to.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, EmailStr, Field

from config.schema import EmployerConfig, ExperienceHighlight


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CandidateSummary(BaseModel):
    id: int
    slug: str
    full_name: str
    resume_path: str | None = None
    resume_exists: bool
    strict_skill_match_required: bool
    pending_skill_count: int
    status: str = "ok"  # "ok" | "needs_search_config" | "pending_approval" | "not_found"
    status_message: str | None = None

    class Config:
        from_attributes = True


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class SkillInventoryItemResponse(BaseModel):
    id: int
    candidate_id: int
    skill_name: str
    tier: str
    source_bullet: str | None
    source_project_or_role: str | None
    suggested_by: str
    confidence: float | None
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SkillApprovalDecision(BaseModel):
    decision: str  # "approve" | "reject"
    tier_override: str | None = None  # let the reviewer correct the suggested tier on approval
    review_notes: str | None = None


class ResumeIngestionRunResponse(BaseModel):
    id: int
    candidate_id: int
    resume_file_path: str
    status: str
    new_skills_suggested: int
    error_message: str | None
    triggered_by: str
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class JobCheckRequest(BaseModel):
    candidate_slug: str
    job_description_text: str
    job_location: str | None = None
    job_work_mode: str | None = None
    save: bool = True


class JobCheckResponse(BaseModel):
    job_title: str | None
    company_name: str | None
    location: str | None
    work_mode: str | None
    recruiter_email: str | None
    recruiter_name: str | None
    status: str
    reason: str | None
    matched_signals: list[str]
    saved_job_id: int | None = None


class WatchCycleResponse(BaseModel):
    resumes: list[dict]


# --- Self-service candidate ------------------------------------------

class CandidateSignupRequest(BaseModel):
    full_name: str
    login_email: EmailStr
    password: str
    organization_name: str


class CandidateLoginRequest(BaseModel):
    login_email: EmailStr
    password: str


class SelfServiceCandidateProfile(BaseModel):
    """Everything a candidate fills in about themselves -- same shape as
    config.schema.CandidateConfig minus base_resume_path, which the
    system always derives from the candidate's slug rather than letting
    it be typed (a candidate choosing their own resume path could
    otherwise point outside their own storage namespace)."""
    full_name: str
    email: EmailStr
    phone: str
    location: str
    linkedin_url: str | None = None

    work_authorization: str
    requires_sponsorship_or_transfer: bool

    career_start_date: date | None = None
    tech_stack_summary: str | None = None
    closing_statement: str | None = None
    experience_highlights: list[ExperienceHighlight] = Field(default_factory=list)

    passport_number: str | None = None
    c2c_rate: str | None = None
    employer: EmployerConfig | None = None
    open_to_relocation: bool = False

    c2c_allowed: bool
    w2_allowed: bool
    contract_allowed: bool
    contract_to_hire_allowed: bool
    full_time_allowed: bool

    has_security_clearance: bool
    public_trust_available: bool

    willing_to_work_remote: bool
    willing_to_work_hybrid: bool
    willing_to_work_onsite: bool


class CandidateMeResponse(BaseModel):
    id: int
    slug: str
    full_name: str
    login_email: str | None
    profile_status: str
    approved_profile: dict | None
    latest_submission_status: str | None


class CandidateProfileSubmissionResponse(BaseModel):
    id: int
    candidate_id: int
    submitted_profile_json: dict
    resume_uploaded: bool
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileApprovalDecision(BaseModel):
    decision: str  # "approve" | "reject"
    review_notes: str | None = None


# --- Reporting / applications history --------------------------------

class InterviewResponse(BaseModel):
    id: int
    round_name: str | None
    scheduled_at: datetime | None
    status: str
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class InterviewCreateRequest(BaseModel):
    round_name: str | None = None
    scheduled_at: datetime | None = None
    notes: str | None = None


class InterviewUpdateRequest(BaseModel):
    round_name: str | None = None
    scheduled_at: datetime | None = None
    status: str | None = None
    notes: str | None = None


class ApplicationSummary(BaseModel):
    email_id: int
    candidate_slug: str
    candidate_full_name: str
    job_id: int
    job_title: str | None
    company_name: str | None
    to_email: str | None
    send_status: str  # Email.status -- did our delivery/draft succeed
    pipeline_stage: str | None
    submitted_to_client_at: datetime | None
    interview_count: int
    latest_interview_at: datetime | None
    sent_at: datetime | None
    created_at: datetime


class ApplicationDetail(ApplicationSummary):
    subject: str | None
    body: str | None
    resume_file_name: str | None
    pipeline_notes: str | None
    interviews: list[InterviewResponse]
    dedup_warning: str | None = None


class PipelineUpdateRequest(BaseModel):
    pipeline_stage: str | None = None  # contacted | client_submitted | interviewing | offer | rejected | withdrawn
    pipeline_notes: str | None = None
    mark_submitted_to_client_now: bool = False
    # Captured when pipeline_stage='client_submitted' -- feeds the
    # resubmission dedup check (don't submit the same candidate to the
    # same end client/location again within the cooldown window).
    end_client_name: str | None = None
    implementation_partner_name: str | None = None
    location: str | None = None


class ApplicationsReportSummary(BaseModel):
    total_prepared: int
    total_sent: int
    total_client_submitted: int
    total_interviewing: int
    total_offers: int
    total_rejected: int
    by_candidate: dict[str, int]


# --- Superuser reporting -----------------------------------------------

class OrganizationSummary(BaseModel):
    organization_id: int
    organization_name: str
    candidate_count: int
    admin_count: int
    jobs_posted: int
    applications_sent: int
    interviews_scheduled: int
    created_at: datetime
    sales_person: str | None = None  # staff username, or "superuser: <username>" if onboarded directly
    trial_expires_at: date | None = None
    trial_days_remaining: int | None = None


class PlatformSummary(BaseModel):
    organization_count: int
    total_candidates: int
    total_jobs_posted: int
    total_applications_sent: int
    total_interviews: int
    organizations: list[OrganizationSummary]
