"""
SQLAlchemy models matching the design doc's schema.
Run `python -m db.init_db` to create tables against DATABASE_URL.
"""
from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text,
    JSON, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CandidateOperationalConfig(Base):
    """Replaces candidate.yaml's per-candidate `search:`/`application_policy:`/
    `email:` blocks -- the DB is now the source of truth for these, same
    as everything else about a candidate. Editable via an admin API
    endpoint instead of a file, which is the actual point: an org admin
    can configure their own candidates' search keywords from the UI
    without server/file access.

    search_config_json matches config.schema.SearchConfig's shape
    exactly (validated against it on read) -- kept as JSON rather than
    individual columns since it's a handful of string lists that are
    only ever read/written as a unit, never queried by individual field."""
    __tablename__ = "candidate_operational_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), unique=True, nullable=False)
    search_config_json: Mapped[dict | None] = mapped_column(JSON)
    strict_skill_match_required: Mapped[bool] = mapped_column(Boolean, default=True)
    send_mode: Mapped[str] = mapped_column(String, default="draft_first")  # draft_first | send_directly
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Staff(Base):
    """Created only by a superuser -- no self-signup, same as SuperUser
    itself. A staff member invites organizations (and each org's first
    admin) on the platform's behalf; Organization.created_by_staff_id
    is the attribution this exists to support -- sales performance /
    future revenue tracking, per org onboarded."""
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String)
    # Needed for self-service password reset (OTP sent here). Populated
    # from the invite's email at redemption time -- see api/routers/invite.py.
    email: Mapped[str | None] = mapped_column(String, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_by_superuser_id: Mapped[int | None] = mapped_column(ForeignKey("super_users.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invite(Base):
    """An OTP-based invitation. The OTP is the sole source of truth for
    role + organization -- the registrant never chooses these, they're
    read off this row when the invite is redeemed (see
    api/routers/invite.py). otp_hash is bcrypt-hashed like a password,
    never stored/logged in plaintext. max_attempts guards against
    brute-forcing a 6-digit code; the invite is dead (not just the
    attempt) once exceeded, requiring a fresh one to be issued."""
    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "admin" | "candidate" | "staff"
    # Nullable because a staff invite has no organization at all --
    # staff aren't scoped to one. Every admin/candidate invite still
    # always sets this.
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    invited_by_type: Mapped[str] = mapped_column(String, nullable=False)  # "staff" | "admin" | "superuser"
    invited_by_id: Mapped[int] = mapped_column(Integer, nullable=False)
    otp_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    """OTP-based password reset, same mechanism as Invite (bcrypt-hashed
    OTP, expiry, attempt limit) but for an EXISTING account instead of
    creating a new one. account_type distinguishes which table
    account_id points into, since admin/candidate are separate tables."""
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_type: Mapped[str] = mapped_column(String, nullable=False)  # "admin" | "candidate"
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    otp_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginAttempt(Base):
    """Account-based lockout tracking (not IP-based -- that layer
    belongs at the reverse-proxy/infra level once deployed, not in app
    code). Standard pattern: N consecutive failures locks the account
    for a cooldown window; a successful login clears the counter.
    account_key is a role-prefixed identifier (e.g. 'admin:jsmith',
    'candidate:john@x.com') so all four login types share one table."""
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_key: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CandidateDocument(Base):
    """A supporting document for a candidate -- passport copy, visa
    copy, I-94, degree certificate, etc. document_type is free text
    (the label the uploader gives it), not a fixed enum, since document
    requirements vary a lot by visa status/client. Same pending-until-
    admin-approved gate as everything else a candidate submits: the
    future autonomous email-reply engine only ever attaches
    status='approved' documents to a recruiter, never a freshly
    self-uploaded one."""
    __tablename__ = "candidate_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | approved | rejected
    uploaded_by: Mapped[str] = mapped_column(String, default="candidate")  # candidate | admin
    reviewed_by: Mapped[str | None] = mapped_column(String)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PushSubscription(Base):
    """One browser's Web Push subscription for one user (admin or
    candidate -- owner_type distinguishes which table owner_id points
    into, same pattern as PasswordResetToken). A user can have several
    of these (phone + desktop, multiple browsers) -- notify() sends to
    all of them and treats success on any one as delivered."""
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(String, nullable=False)  # "admin" | "candidate"
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh_key: Mapped[str] = mapped_column(String, nullable=False)
    auth_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Status(Base):
    """Shared account-status vocabulary for Organization and Candidate
    (trial, extended_trial, active, suspended, ...) -- a lookup table
    rather than a hardcoded string/enum so a superuser can see the full
    set and the app can grow it without a schema change. Seeded by
    db/seed.py. Distinct from Candidate.profile_status (admin-review
    workflow state) and Candidate.availability_status (job-search
    intent) -- this one specifically tracks account/billing standing,
    superuser-controlled, not automatically transitioned by any
    trial-expiry logic today (see trial_service.py's extend_trial_days,
    which changes dates but never touches status_id itself)."""
    __tablename__ = "statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Organization(Base):
    """A 'corporate' -- one staffing agency/recruiter's tenant. Every
    Candidate and AdminUser belongs to exactly one. This is the hard
    isolation boundary: an admin from one organization must never be
    able to see, list, or act on another organization's candidates,
    resumes, jobs, or emails, even by guessing a numeric id."""
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    status_id: Mapped[int | None] = mapped_column(ForeignKey("statuses.id"))
    created_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"))
    # A superuser can also onboard an organization directly (skipping
    # the staff-invite flow entirely) -- exactly one of
    # created_by_staff_id / created_by_superuser_id is set, never both,
    # since either identifies the "sales person" of record for this
    # account. Both nullable because neither applies to an org created
    # some other way (e.g. self-service signup has neither -- see
    # api/routers/auth.py::signup).
    created_by_superuser_id: Mapped[int | None] = mapped_column(ForeignKey("super_users.id"))
    # 'agency': a staffing company -- separate admin(s) managing a bench
    # of candidates, each candidate approves nothing about anyone else's
    # profile, only their own submissions go to the admin for review.
    # 'individual': a single person signed up directly, with no
    # separate staffing company -- this person IS both the admin and
    # the candidate. See AdminUser.linked_candidate_id and
    # api/deps.py::get_current_candidate for how one login covers both
    # capabilities (self-approving their own resume/document/email-draft
    # updates) without a separate account.
    account_type: Mapped[str] = mapped_column(String, default="agency")
    # Deactivation, not deletion -- a staff member removing an org they
    # created must not orphan/cascade-delete real candidates, jobs, and
    # email history. Deactivated orgs simply stop resolving for
    # login/matching; the data stays intact and auditable.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Master feature flag: while False (the default), every app-composed
    # outbound email -- including future autonomous recruiter replies,
    # negotiation responses, document sends -- lands as a draft
    # requiring explicit admin approval before it goes anywhere,
    # regardless of any per-candidate send_mode setting. Only once an
    # org admin flips this on does per-candidate send_mode (draft_first
    # vs send_directly) actually govern autonomous sending.
    autonomous_email_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Configurable follow-up cadence, per org -- three distinct timers
    # for three distinct moments in an application's lifecycle:
    initial_outreach_follow_up_days: Mapped[int] = mapped_column(Integer, default=2)
    client_submission_follow_up_days: Mapped[int] = mapped_column(Integer, default=2)
    post_interview_follow_up_days: Mapped[int] = mapped_column(Integer, default=3)
    # The "don't submit the same candidate to the same end client for
    # the same location twice within N days" rule -- configurable, not
    # hardcoded to a week.
    resubmission_cooldown_days: Mapped[int] = mapped_column(Integer, default=7)
    # How often (minutes) the not-yet-built inbox-polling loop checks a
    # candidate's connected Gmail for new recruiter emails. Configurable
    # per org rather than a hardcoded interval, since polling frequency
    # is a real tradeoff against API quota/cost.
    inbox_poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    # Login lockout, configurable per org -- staff/superuser logins
    # (not org-scoped) use the module-level defaults in
    # services/rate_limit.py instead, since there's no org to read from
    # at that point.
    max_failed_login_attempts: Mapped[int] = mapped_column(Integer, default=5)
    lockout_minutes: Mapped[int] = mapped_column(Integer, default=15)
    # When False, notify() never falls back to email -- push/in-app only,
    # even if push is unavailable or fails. Default True since a
    # brand-new org has no push subscriptions set up yet; without email
    # as a fallback they'd miss everything.
    email_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Daily volume caps -- existed as YAML config in an earlier phase,
    # migrated here to match every other per-org setting.
    max_jobs_per_day: Mapped[int] = mapped_column(Integer, default=200)
    max_applications_per_day: Mapped[int] = mapped_column(Integer, default=50)
    max_emails_per_day: Mapped[int] = mapped_column(Integer, default=50)
    # Business-hours-only sending -- an email landing in a recruiter's
    # inbox at 3am undermines the "looks human" positioning. Hours are
    # plain 0-23 integers in business_hours_timezone (IANA name, e.g.
    # "America/New_York"). When send_only_business_hours is True and
    # the current time in that timezone falls outside the window, a
    # send_directly request is held back as a draft instead of erroring
    # -- see services/application_service.py.
    send_only_business_hours: Mapped[bool] = mapped_column(Boolean, default=False)
    business_hours_start_hour: Mapped[int] = mapped_column(Integer, default=9)
    business_hours_end_hour: Mapped[int] = mapped_column(Integer, default=18)
    business_hours_timezone: Mapped[str] = mapped_column(String, default="America/New_York")
    # Free-trial / subscription expiry for this whole account -- covers
    # both an agency's overall access and, for an 'individual' account,
    # that same person's own access (an individual IS the org). Null
    # means no expiry is tracked (e.g. a paid, non-trial account with
    # billing handled some other way). Set at onboarding time by
    # whichever superuser/staff created the org -- never editable by
    # the org's own admin, or they could just extend their own trial.
    trial_expires_at: Mapped[date | None] = mapped_column(Date)
    # Guards against sending the "expiring soon" reminder email more
    # than once for the same expiry -- set the first time
    # services/trial_service.py actually sends one, cleared whenever
    # trial_expires_at is changed (a renewal) so a new reminder can
    # fire for the new date.
    trial_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StoredFile(Base):
    """Blob storage backing services/storage.py's DatabaseStorage --
    used so resumes/generated documents aren't tied to any one app
    instance's local disk, which breaks once more than one instance (or
    later, load-balanced pods) serves the same app. `key` uses the exact
    same logical path scheme as LocalStorage (e.g.
    'resumes/john_smith.docx') -- callers never know or care which
    backend is active."""
    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmailAccountCredential(Base):
    """One connected inbox for a user -- admin or candidate (owner_type
    distinguishes which table owner_id points into, same pattern as
    PushSubscription/PasswordResetToken). OAuth2 (Gmail) is the
    preferred path -- the app never sees the user's real password,
    only a refresh token scoped to specific permissions, revocable from
    their Google account at any time. Encrypted app-password is a
    fallback for providers without OAuth2.

    The plaintext secret is NEVER stored -- encrypted_secret (via
    services/crypto.py) is only ever decrypted transiently, inside the
    email-sending/monitoring service, immediately before an API call,
    never logged or persisted decrypted.

    scopes_granted (Gmail) and imap_host/imap_port (SMTP fallback)
    anticipate the future email-monitoring/auto-reply/calendar phase
    (read inbox, send replies, manage interview events) so this schema
    doesn't need to change when that phase is built -- this table only
    covers connect/store/disconnect; the monitoring loop itself
    (matching an inbound reply to a sent Email row, feeding "no reply"
    into services/followup_service.py) is a separate, later piece of
    work -- credentials are captured now, the poller isn't built yet.
    """
    __tablename__ = "email_account_credentials"
    __table_args__ = (UniqueConstraint("owner_type", "owner_id", "provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(String, nullable=False)  # "admin" | "candidate"
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)  # "gmail" | "microsoft" | "smtp" | "other"
    account_email: Mapped[str] = mapped_column(String, nullable=False)
    # Only set when provider="smtp" -- the manual-entry fallback path.
    # One username/password authenticates both directions (standard for
    # every mainstream provider -- Gmail app passwords, Zoho, Outlook,
    # etc. -- so encrypted_secret below is shared, not duplicated per
    # protocol); only the host/port genuinely differ between sending
    # (SMTP) and reading (IMAP).
    smtp_host: Mapped[str | None] = mapped_column(String)
    smtp_port: Mapped[int | None] = mapped_column(Integer)
    smtp_username: Mapped[str | None] = mapped_column(String)
    imap_host: Mapped[str | None] = mapped_column(String)
    imap_port: Mapped[int | None] = mapped_column(Integer)
    secret_type: Mapped[str] = mapped_column(String, nullable=False)  # "oauth_refresh_token" | "app_password"
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    scopes_granted: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="connected")  # connected | revoked | error
    last_error: Mapped[str | None] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Subscription(Base):
    """Billing lifecycle for one candidate -- per-candidate-per-month,
    per the agreed pricing model. This table tracks STATUS and the
    pause/resume lifecycle only; it does NOT process real payments
    (charging a card, invoicing) -- that's a distinct future
    integration (Stripe or similar). What this DOES do today: gate
    whether the app applies for a candidate at all. A paused or
    cancelled subscription means zero job-matching/application activity
    for that candidate, and (once real billing exists) zero charge for
    the period.

    paused_by distinguishes who initiated a pause -- the candidate
    themselves, or the org -- since either can pause per the agreed
    design, and it matters for support/audit ("why did this stop
    applying") to know which."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), unique=True, nullable=False)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")  # active | paused | cancelled
    monthly_rate: Mapped[float | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String, default="USD")
    paused_by: Mapped[str | None] = mapped_column(String)  # "candidate" | "org" | null
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_start: Mapped[date | None] = mapped_column(Date)
    current_period_end: Mapped[date | None] = mapped_column(Date)
    # Same dedup purpose as Organization.trial_reminder_sent_at, but for
    # an individual candidate's own trial/subscription period end
    # (current_period_end above) -- an agency admin can set a
    # per-candidate trial distinct from the org's own trial_expires_at.
    trial_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Candidate(Base):
    """Mirrors one entry in config.candidates for admin-managed
    candidates (slug + full_name, config.candidate.yaml is the source of
    truth) -- OR, for self-service candidates, this row's
    approved_profile_json IS the source of truth for their personal/
    profile data. Either way, search config and application_policy stay
    in candidate.yaml, keyed by (organization + slug) -- see
    services/candidate_directory.py for how the two are merged into one
    CandidateProfile at read time.

    slug is unique WITHIN an organization, not globally -- two different
    corporates can each have a "john_smith". Every lookup by slug
    elsewhere in the app must also be scoped by organization_id, or one
    org's admin could act on another org's candidate by guessing a slug.
    """
    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("organization_id", "slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    # Account/billing standing (trial, extended_trial, active, suspended,
    # ...) -- see Status's docstring for how this differs from
    # profile_status and availability_status below.
    status_id: Mapped[int | None] = mapped_column(ForeignKey("statuses.id"))
    # Job-search intent -- separate concept from Subscription.status
    # (billing). A candidate can be actively subscribed/billed but
    # temporarily not looking (between contracts, on a project, etc.);
    # either this OR a paused/cancelled subscription independently stops
    # the app from applying on their behalf. 'active_looking' | 'not_looking'
    availability_status: Mapped[str] = mapped_column(String, default="active_looking")

    # Self-service login -- null for candidates that only exist via
    # admin-managed candidate.yaml (no self-service account). Globally
    # unique (not per-org) since login happens before we know the org.
    login_email: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String)

    # 'no_account' | 'pending' | 'approved' | 'rejected' -- reflects the
    # status of the MOST RECENT CandidateProfileSubmission. A candidate's
    # profile is only usable by matching/tailoring while approved.
    profile_status: Mapped[str] = mapped_column(String, default="no_account")
    # Last APPROVED submission's data, in the exact shape of
    # config.schema.CandidateConfig (minus base_resume_path, which is
    # always derived from slug). This -- not the pending submission --
    # is what candidate_directory.py reads for an active candidate.
    approved_profile_json: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CandidateProfileSubmission(Base):
    """One self-reported profile submission -- created every time a
    candidate fills out/edits their profile via the self-service UI.
    Mirrors the SkillInventoryItem pattern: nothing here is live until
    status='approved', at which point Candidate.approved_profile_json
    and Candidate.profile_status get updated from this row. A resume
    upload accompanying this submission goes through the EXISTING
    resume-ingestion/skill-approval pipeline separately -- this table
    only covers the factual/administrative profile fields, not skills."""
    __tablename__ = "candidate_profile_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    submitted_profile_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    resume_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | approved | rejected
    reviewed_by: Mapped[str | None] = mapped_column(String)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)  # browser_automated | human_in_loop | configurable_source_adapter
    mode: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, default="idle")  # idle | running | error | circuit_open
    error_message: Mapped[str | None] = mapped_column(Text)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("candidate_id", "source_id", "external_job_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Direct FK, not just derived via candidate_id -- an admin's job
    # posting must never fan out or become visible/actionable outside
    # their own organization, and this makes that boundary a queryable
    # column in its own right rather than something only reachable via
    # a join that every future query has to remember to include.
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("job_sources.id"))
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    external_job_id: Mapped[str | None] = mapped_column(String)
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String)
    work_mode: Mapped[str | None] = mapped_column(String)
    employment_type: Mapped[str | None] = mapped_column(String)
    c2c_mentioned: Mapped[bool | None] = mapped_column(Boolean)
    w2_mentioned: Mapped[bool | None] = mapped_column(Boolean)
    sponsorship_status: Mapped[str | None] = mapped_column(String)  # unknown | allows | excludes
    job_url: Mapped[str | None] = mapped_column(String)
    post_url: Mapped[str | None] = mapped_column(String)
    description_text: Mapped[str | None] = mapped_column(Text)
    authorization_text: Mapped[str | None] = mapped_column(Text)
    salary_or_rate: Mapped[str | None] = mapped_column(String)
    job_contact_id: Mapped[int | None] = mapped_column(ForeignKey("job_contacts.id"))
    role_classification: Mapped[list[str] | None] = mapped_column(JSON)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, default="discovered")
    skip_reason: Mapped[str | None] = mapped_column(Text)
    dedup_hash: Mapped[str | None] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class JobContact(Base):
    """The recruiter/contact entity, deduplicated by email. A job posting
    has exactly one recruiter (many-to-one: many jobs can point at the
    same job_contacts row), not the other way around -- so the FK lives
    on jobs.job_contact_id, and this table has no job_id. Re-encountering
    the same recruiter_email on a new job reuses this row rather than
    creating a new one."""
    __tablename__ = "job_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recruiter_email: Mapped[str] = mapped_column(String, unique=True, index=True)
    recruiter_name: Mapped[str | None] = mapped_column(String)
    recruiter_company: Mapped[str | None] = mapped_column(String)
    recruiter_phone: Mapped[str | None] = mapped_column(String)
    recruiter_linkedin_url: Mapped[str | None] = mapped_column(String)
    source_name: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    target_role: Mapped[str | None] = mapped_column(String)
    company_name: Mapped[str | None] = mapped_column(String)
    file_name: Mapped[str | None] = mapped_column(String)
    file_path: Mapped[str | None] = mapped_column(String)
    tailoring_summary: Mapped[str | None] = mapped_column(Text)
    risk_notes: Mapped[str | None] = mapped_column(Text)
    # Any skill the LLM used in tailored content that wasn't found in the
    # candidate's approved skill inventory -- should be empty in normal
    # operation, since the grounding check strips these before the docx
    # is written. Non-empty means the grounding check caught and removed
    # something; kept here as an audit trail, not silently discarded.
    grounding_flags: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2))
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    job_contact_id: Mapped[int | None] = mapped_column(ForeignKey("job_contacts.id"))
    to_email: Mapped[str | None] = mapped_column(String)
    from_email: Mapped[str | None] = mapped_column(String)
    subject: Mapped[str | None] = mapped_column(String)
    body: Mapped[str | None] = mapped_column(Text)
    resume_file_path: Mapped[str | None] = mapped_column(String)
    # The Gmail-side id -- either a draft id (draft_first mode, sitting
    # in the candidate's own Gmail for them to review/send) or a sent
    # message id (send_directly mode, after the explicit send action).
    gmail_object_id: Mapped[str | None] = mapped_column(String)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Send-mechanics status: did OUR email delivery/draft-creation
    # succeed. draft|awaiting_approval|approved|sent|bounced|failed
    status: Mapped[str] = mapped_column(String, default="draft")
    # Business-pipeline stage: where this application actually stands
    # with the recruiter/client, as observed/reported -- distinct from
    # the above, and currently updated manually by the admin (no inbox
    # monitoring yet). 'contacted' is the default once an email is
    # actually sent; earlier than that, pipeline_stage is null (nothing
    # has left the building yet). Future email-monitoring can update
    # these same fields automatically without a schema change.
    # null | contacted | client_submitted | interviewing | offer | rejected | withdrawn
    pipeline_stage: Mapped[str | None] = mapped_column(String)
    submitted_to_client_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pipeline_notes: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    reply_received: Mapped[bool] = mapped_column(Boolean, default=False)
    last_reply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Interview(Base):
    """One interview round for one application (Email row). A single
    application can have several of these -- phone screen, technical,
    final, etc, hence a separate table rather than a single field.
    Manually entered by the admin for now; the deferred email-monitoring
    phase would populate these same rows automatically from parsed
    recruiter replies, not a different structure."""
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id"), nullable=False)
    round_name: Mapped[str | None] = mapped_column(String)  # e.g. "Phone Screen", "Technical", "Final" -- free text for now
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, default="scheduled")  # scheduled | completed | cancelled | rescheduled
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    source_name: Mapped[str | None] = mapped_column(String)
    application_url: Mapped[str | None] = mapped_column(String)
    application_method: Mapped[str | None] = mapped_column(String)  # browser_automated | human_in_loop
    resume_file_path: Mapped[str | None] = mapped_column(String)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FollowUp(Base):
    """One scheduled follow-up nudge for one application (Email row).
    follow_up_type distinguishes the three distinct moments this can
    fire for, each with its own configurable delay on Organization:
      - 'initial_outreach': after the first application email is
        actually sent, no reply yet -- "I sent my resume on <date>, any
        update?"
      - 'client_submission': after the recruiter confirms the resume
        was submitted to the end client -- "any feedback from <client>
        yet?"
      - 'post_interview': after an interview is marked completed --
        "checking in after the interview, any feedback?"
    """
    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id"))
    follow_up_type: Mapped[str] = mapped_column(String, default="initial_outreach")
    next_follow_up_date: Mapped[date | None] = mapped_column(Date)
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="scheduled")  # scheduled | sent | cancelled
    last_follow_up_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClientSubmission(Base):
    """One confirmed submission of a candidate's resume to an end
    client, via some implementation partner/vendor, for some location.
    Recorded whenever an application's pipeline_stage is set to
    'client_submitted' with client info attached. Checked before any
    new submission to the SAME (candidate, end_client, location) within
    Organization.resubmission_cooldown_days -- the "don't double-submit"
    rule. end_client_name/location are stored normalized (lowercased,
    trimmed) for matching, alongside the original as-typed values for
    display."""
    __tablename__ = "client_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id"))
    end_client_name: Mapped[str] = mapped_column(String, nullable=False)
    end_client_name_normalized: Mapped[str] = mapped_column(String, nullable=False, index=True)
    implementation_partner_name: Mapped[str | None] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String)
    location_normalized: Mapped[str | None] = mapped_column(String, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileRefresh(Base):
    __tablename__ = "profile_refreshes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str | None] = mapped_column(String)
    resume_file_path: Mapped[str | None] = mapped_column(String)
    refresh_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    human_action_required: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ApplicationStatus(Base):
    __tablename__ = "application_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    status: Mapped[str | None] = mapped_column(String)
    submitted_to_client: Mapped[bool] = mapped_column(Boolean, default=False)
    client_name: Mapped[str | None] = mapped_column(String)
    rate_discussed: Mapped[str | None] = mapped_column(String)
    rate_submitted: Mapped[str | None] = mapped_column(String)
    last_contact_date: Mapped[date | None] = mapped_column(Date)
    next_action_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ConfigurationSnapshot(Base):
    __tablename__ = "configuration_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str | None] = mapped_column(String)
    source_name: Mapped[str | None] = mapped_column(String)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    message: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SkillInventoryItem(Base):
    """One skill claim for one candidate, with provenance. This is the
    single source of truth the per-job matching/tailoring pipeline reads
    from -- nothing here is usable for matching until status='approved'.

    tier: 'core' | 'component' | 'secondary' | 'exposure'
      - core: primary, years of hands-on work (e.g. Java for a Java architect)
      - component: inherent part of something the candidate has deep
        experience in (e.g. S3 within years of AWS work, TypeScript
        within Angular work)
      - secondary: real hands-on work, but supporting/adjacent to the
        candidate's primary role (e.g. Terraform/AKS support work done
        alongside a DevOps team)
      - exposure: course/self-study/POC only, no real production work --
        surfaced separately in resumes/emails, never backdated into a
        specific job's experience bullets

    status: 'pending' | 'approved' | 'rejected'. Populated either at
    initial candidate setup or by resume-diff ingestion (see
    ResumeIngestionRun) -- either way, nothing here is usable for
    matching/tailoring until a human approves it. This is the exact gate
    that stops a candidate's resume update (e.g. suddenly adding "C++"
    because C++ jobs are trending) from silently becoming a usable claim.
    """
    __tablename__ = "skill_inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    skill_name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    source_bullet: Mapped[str | None] = mapped_column(Text)  # the resume text this was extracted from, for reviewer context
    source_project_or_role: Mapped[str | None] = mapped_column(String)
    suggested_by: Mapped[str] = mapped_column(String, default="claude_extraction")  # claude_extraction | manual
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    status: Mapped[str] = mapped_column(String, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    ingestion_run_id: Mapped[int | None] = mapped_column(ForeignKey("resume_ingestion_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ResumeIngestionRun(Base):
    """One resume-extraction event -- triggered either by the resume file
    watcher detecting a change, a manual re-ingest, or a candidate's own
    upload. Groups the SkillInventoryItem suggestions it produced.

    The uploaded FILE ITSELF now also requires admin approval before it
    becomes the active resume used for tailoring -- not just the skills
    extracted from it. A newly uploaded resume lands at
    pending_storage_key; only once resume_approval_status='approved'
    does it get copied to active_storage_key (the real
    base_resume_path), via services/resume_service.py's promotion step.
    Until then, the previous active resume (if any) keeps being used --
    an unreviewed upload never silently becomes what gets sent out."""
    __tablename__ = "resume_ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), nullable=False)
    resume_file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Extraction/ingestion process status -- pending | processing | completed | failed
    status: Mapped[str] = mapped_column(String, default="pending")
    new_skills_suggested: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(String, default="file_watcher")  # file_watcher | manual | candidate_upload

    # The resume FILE's own approval gate, separate from the extraction
    # process status above. pending | approved | rejected
    resume_approval_status: Mapped[str] = mapped_column(String, default="pending")
    pending_storage_key: Mapped[str | None] = mapped_column(String)
    active_storage_key: Mapped[str | None] = mapped_column(String)
    resume_approved_by: Mapped[str | None] = mapped_column(String)
    resume_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FileWatchState(Base):
    """Last-seen hash for every watched file (config/candidate.yaml, and
    each resumes/<slug>.docx), so the watcher survives process restarts
    without re-triggering ingestion on files that haven't actually
    changed. file_path is the unique key; file_kind distinguishes config
    vs resume so the watcher loop can branch cleanly."""
    __tablename__ = "file_watch_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_path: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    file_kind: Mapped[str] = mapped_column(String, nullable=False)  # candidate_config | resume
    last_hash: Mapped[str | None] = mapped_column(String)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SuperUser(Base):
    """Platform-level account (you, the app's creator) -- sees across
    every organization for reporting purposes, and can onboard
    organizations/staff directly. Bootstrapped via CLI script only (no
    self-signup, by design -- platform-level trust)."""
    __tablename__ = "super_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String)
    # Needed for self-service password reset (OTP sent here). Optional --
    # bootstrap scripts can set it via --email / DEV_SUPERUSER_EMAIL.
    email: Mapped[str | None] = mapped_column(String, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlatformSettings(Base):
    """Singleton row (always id=1) for platform-wide, superuser-editable
    configuration that doesn't belong to any one organization -- start
    with just invite expiry, but this is the natural home for any
    future platform-level knob. Created lazily on first read/write (see
    services/platform_settings_service.py::get_or_create_platform_settings)
    rather than seeded by a migration, so it never needs a special
    bootstrap step."""
    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invite_expire_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    # The trial length new org-creation forms pre-fill (staff/superuser
    # can still type a different number per org) -- was a hardcoded
    # constant (trial_service.DEFAULT_TRIAL_DAYS) until now.
    default_trial_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AdminUser(Base):
    """App login for a recruiter/admin. Belongs to exactly one
    Organization -- self-signup always creates a NEW organization (see
    api/routers/auth.py::signup) rather than letting someone join an
    existing one by typing its name, since an admin has full visibility
    into every candidate's PII in their org. Adding a second admin to an
    existing org is a deliberate future 'invite teammate' feature, not
    open self-signup.

    For an individual (Organization.account_type='individual'), this
    row is linked to exactly one Candidate row via linked_candidate_id
    -- the same person, same login, acting in both capacities. Their
    admin token can act on their own linked candidate's self-service
    endpoints (see api/deps.py::get_current_candidate) so they approve
    their own resume/document/email-draft updates without a second
    account or login."""
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    # The immutable identifier -- never editable via the self-service
    # profile endpoints (api/routers/admin_self.py), unlike email/full_name.
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String)
    # Needed for self-service password reset (OTP sent here). Populated
    # at signup/invite-registration time, editable later via admin_self.py.
    email: Mapped[str | None] = mapped_column(String, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    linked_candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PendingAction(Base):
    """The human-approval gate. Nothing in emails/applications/profile_refreshes
    actually executes (send / submit / upload) until the matching row here
    is flipped from 'awaiting_approval' to 'approved'."""
    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_type: Mapped[str] = mapped_column(String, nullable=False)  # send_email | submit_application | upload_resume
    reference_table: Mapped[str] = mapped_column(String, nullable=False)
    reference_id: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="awaiting_approval")
    reviewed_by: Mapped[str | None] = mapped_column(String)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
