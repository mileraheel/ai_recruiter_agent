"""
Pydantic models for the AI Recruiter Agent configuration.

Loading candidate.yaml through these models means bad config fails fast,
at startup, with a clear error -- rather than causing confusing behavior
later in the eligibility filter or resume tailoring steps.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, EmailStr


class CandidateConfig(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    location: str
    linkedin_url: str | None = None
    base_resume_path: str

    work_authorization: str
    requires_sponsorship_or_transfer: bool

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


class AppConfig(BaseModel):
    version: int = 1
    candidate: CandidateConfig
    search: SearchConfig
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    follow_up: FollowUpConfig = Field(default_factory=FollowUpConfig)
    resume_refresh: ResumeRefreshConfig = Field(default_factory=ResumeRefreshConfig)
    email: EmailConfig
