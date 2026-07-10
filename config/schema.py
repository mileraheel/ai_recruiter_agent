"""
Pydantic models for the Role Pace candidate configuration.

Loading candidate.yaml through these models means bad config fails fast,
at startup, with a clear error -- rather than causing confusing behavior
later in the eligibility filter or resume tailoring steps.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, EmailStr


class EmployerConfig(BaseModel):
    """The staffing agency / employer-of-record submitting the candidate
    -- not the candidate's own contact info. Appears as a distinct block
    in the outreach email signature so the recruiter has a direct line
    for rate negotiation and submission paperwork."""
    name: str
    email: EmailStr
    phone: str


class ExperienceHighlight(BaseModel):
    """One bullet describing real, already-performed work, written once
    by the candidate. `tags` are role-classification categories (see
    core/role_classifier.py) -- a bullet is only pulled into an outreach
    email when the job description matches at least one of its tags.
    This is a selection mechanism, not a generation mechanism: the agent
    chooses among bullets the candidate wrote, it never invents new ones.
    Tag a bullet "general" to make it a fallback used when no category
    matches the job description at all."""
    text: str
    tags: list[str]


class CandidateConfig(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    location: str
    linkedin_url: str | None = None
    base_resume_path: str

    work_authorization: str
    requires_sponsorship_or_transfer: bool

    # Used to compute "16+ years experience" dynamically at generation
    # time (today - career_start_date), instead of a hardcoded number
    # that silently goes stale as time passes. Optional so configs/tests
    # that don't touch email composition don't need to set it; the
    # composer requires it be set at call time, though (see
    # core/email_composer.py) since a missing years-of-experience line
    # would otherwise be silently wrong rather than loudly absent.
    career_start_date: date | None = None

    # Static narrative lines that don't change per-job -- distinct from
    # experience_highlights, which ARE selected per-job. Kept here (not
    # invented at generation time) so every claim in the email traces
    # back to something the candidate actually wrote.
    tech_stack_summary: str | None = None
    closing_statement: str | None = None
    experience_highlights: list[ExperienceHighlight] = Field(default_factory=list)

    # Sensitive fields -- intended to be sourced via ${ENV_VAR} in
    # candidate.yaml (same pattern as email/phone), never committed as
    # plain text, since candidate.yaml (unlike candidate.example.yaml)
    # is the real, git-ignored config.
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


class SearchConfig(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    nice_to_have_keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_mode: list[Literal["remote", "hybrid", "onsite"]] = Field(default_factory=list)
    employment_type: list[str] = Field(default_factory=list)


class SourceConfig(BaseModel):
    enabled: bool = False
    mode: Literal[
        "human_in_loop",
        "browser_automated",
        "configurable_source_adapter",
    ] = "human_in_loop"


class LimitsConfig(BaseModel):
    max_jobs_per_day: int = 50
    max_emails_per_day: int = 20
    max_applications_per_day: int = 20
    max_browser_actions_per_source_per_day: int = 100
    delay_between_actions_seconds_min: int = 45
    delay_between_actions_seconds_max: int = 180
    session_reuse_enabled: bool = True
    dry_run_mode: bool = True
    require_human_approval_before_send: bool = True
    require_human_approval_before_apply: bool = True
    circuit_breaker_error_threshold: int = 3
    pause_on_captcha_detected: bool = True
    pause_on_unexpected_page_structure: bool = True


class FollowUpConfig(BaseModel):
    first_follow_up_after_days: int = 2
    follow_up_every_days: int = 2
    max_follow_ups: int = 3
    stop_follow_up_on_reply: bool = True
    stop_follow_up_on_rejection: bool = True
    stop_follow_up_if_recruiter_says_no: bool = True


class ResumeRefreshConfig(BaseModel):
    enabled: bool = True
    frequency: Literal["daily", "weekly", "biweekly", "monthly"] = "weekly"
    sources: list[str] = Field(default_factory=list)
    rule: str = ""


class EmailConfig(BaseModel):
    provider: Literal["gmail_or_microsoft_graph"] = "gmail_or_microsoft_graph"
    from_email: EmailStr
    send_mode: Literal["draft_first", "send_directly"] = "draft_first"
    signature_enabled: bool = True


def slugify_name(full_name: str) -> str:
    """'Raheel Ahmed Khan' -> 'raheel_ahmed_khan'. Used both as the
    candidate's config id default and as the expected base-resume
    filename stem (resumes/<slug>.docx), so the two stay in sync without
    the config author having to type the same string twice."""
    lowered = full_name.strip().lower()
    lowered = re.sub(r"[^a-z0-9\s_-]", "", lowered)
    return re.sub(r"[\s-]+", "_", lowered).strip("_")


class ApplicationPolicyConfig(BaseModel):
    """Governs whether a job is applied to at all, evaluated BEFORE any
    resume tailoring happens -- this is the "apply for everything vs.
    only matching jobs" flag.

    strict_skill_match_required=True (default, recommended): the job
    description must actually mention the candidate's required_keywords
    (search.required_keywords -- the candidate's core role identity,
    e.g. ["Java"]). A Java candidate is matched to Java/Spring Boot/JVM
    roles; a job posting for ".NET Developer" that never mentions Java
    is skipped, full stop, before a resume is ever touched.

    strict_skill_match_required=False: loosens the MATCHING threshold
    for genuinely adjacent/borderline roles (e.g. a "Full Stack
    Developer" posting that's backend-agnostic, or a fuzzier seniority
    label). It does NOT authorize inventing skills or experience the
    candidate doesn't have -- resume tailoring stays grounded in the
    candidate's real, config-declared background no matter how this
    flag is set. See core/role_match.py for the matching logic and the
    resume-tailoring grounding check (once built) for how truthfulness
    is enforced independently of this flag.
    """
    strict_skill_match_required: bool = True


class CandidateProfile(BaseModel):
    """One candidate the agent is applying on behalf of. The top-level
    config holds a list of these -- an in-house recruiter running this
    for multiple bench candidates just adds another entry, each with its
    own identity, search criteria, sending email, and match policy."""
    id: str | None = None  # slug, e.g. "raheel_ahmed_khan"; also expected resume filename stem. Defaults from candidate.full_name if omitted.
    # Which corporate/tenant owns this candidate -- must match an
    # existing Organization.name (created via admin signup). Required so
    # YAML-managed candidates fit the same tenant-isolation model as
    # self-service ones; there is no org-less candidate.
    organization_name: str
    candidate: CandidateConfig
    search: SearchConfig
    email: EmailConfig
    application_policy: ApplicationPolicyConfig = Field(default_factory=ApplicationPolicyConfig)

    def resolved_id(self) -> str:
        return self.id or slugify_name(self.candidate.full_name)


class AppConfig(BaseModel):
    version: int = 1
    # Retired as the source of per-candidate data -- candidates now live
    # entirely in the DB (Candidate.approved_profile_json +
    # CandidateOperationalConfig), created via signup/invite and
    # configured via the admin API, not this file. Kept as an optional
    # list only for any transitional/legacy entries; new deployments
    # should leave this empty.
    candidates: list[CandidateProfile] = Field(default_factory=list)
    # Shared across all candidates -- job sources, daily limits, and
    # follow-up cadence are organization-wide operating policy, not
    # per-person identity, so they stay outside the candidates list.
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    follow_up: FollowUpConfig = Field(default_factory=FollowUpConfig)
    resume_refresh: ResumeRefreshConfig = Field(default_factory=ResumeRefreshConfig)
