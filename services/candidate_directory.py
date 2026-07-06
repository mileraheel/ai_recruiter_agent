"""
Resolves ONE canonical CandidateProfile per (organization, slug) pair.

Fully database-driven now: Candidate.approved_profile_json holds the
personal/profile data (written only on admin approval), and
CandidateOperationalConfig holds search/application-policy/send-mode
(editable by an admin via API, see api/routers/candidate_config.py).
No YAML file is read anywhere in this module -- config/candidate.yaml
is retired for per-candidate data; only genuine deployment config
(DATABASE_URL, JWT secrets, etc, all env vars) remains outside the DB.

EVERY lookup in this module is organization-scoped. slug is only unique
WITHIN an organization (see db.models.Candidate), so a bare slug lookup
without an organization_id would be a cross-tenant data leak.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from config.schema import (
    ApplicationPolicyConfig,
    CandidateConfig,
    CandidateProfile,
    EmailConfig,
    SearchConfig,
    slugify_name,
)
from db.models import Candidate, CandidateOperationalConfig, Organization


def resume_storage_key(organization_name: str, candidate_slug: str) -> str:
    """Resume storage keys must be namespaced by organization, not just
    candidate slug -- slugs are only unique WITHIN an org (see
    db.models.Candidate), so two different corporates could each have a
    'john_smith' and would otherwise silently overwrite each other's
    resume file. Uses the org NAME (slugified), not its numeric id,
    since the name is known upfront while the id is only assigned once
    the row exists."""
    return f"resumes/{slugify_name(organization_name)}/{candidate_slug}.docx"


def generated_storage_prefix(organization_name: str, candidate_slug: str) -> str:
    return f"generated/{slugify_name(organization_name)}/{candidate_slug}"


@dataclass
class CandidateResolution:
    status: str  # "ok" | "needs_search_config" | "pending_approval" | "not_found"
    profile: CandidateProfile | None = None
    message: str | None = None


def get_or_create_operational_config(session: Session, candidate_id: int) -> CandidateOperationalConfig:
    config = session.query(CandidateOperationalConfig).filter_by(candidate_id=candidate_id).one_or_none()
    if config is None:
        # Safe defaults: strict matching on, draft-first sending, empty
        # search config (which itself means "not yet configured" --
        # resolve_candidate_profile_for_row treats an empty/missing
        # required_keywords as needs_search_config, not a permissive
        # match-everything default).
        config = CandidateOperationalConfig(candidate_id=candidate_id)
        session.add(config)
        session.flush()
    return config


def resolve_candidate_profile_for_row(session: Session, candidate_row: Candidate) -> CandidateResolution:
    if candidate_row.profile_status != "approved" or not candidate_row.approved_profile_json:
        return CandidateResolution(
            status="pending_approval",
            message=f"Candidate '{candidate_row.slug}' has no admin-approved profile yet.",
        )

    op_config = session.query(CandidateOperationalConfig).filter_by(candidate_id=candidate_row.id).one_or_none()
    search_json = op_config.search_config_json if op_config else None
    has_required_keywords = bool(search_json and search_json.get("required_keywords"))

    if not has_required_keywords:
        return CandidateResolution(
            status="needs_search_config",
            message=(
                f"Candidate '{candidate_row.slug}' is approved but has no search config "
                f"(required_keywords) set yet -- an admin needs to configure it before "
                f"job matching activates."
            ),
        )

    org = session.query(Organization).filter_by(id=candidate_row.organization_id).one_or_none()
    if org is None:
        return CandidateResolution(status="not_found", message="Organization not found.")

    candidate_config = CandidateConfig(
        **candidate_row.approved_profile_json,
        base_resume_path=resume_storage_key(org.name, candidate_row.slug),
    )
    search_config = SearchConfig(**search_json)
    application_policy = ApplicationPolicyConfig(
        strict_skill_match_required=op_config.strict_skill_match_required if op_config else True
    )
    email_config = EmailConfig(
        from_email=candidate_config.email,
        send_mode=op_config.send_mode if op_config else "draft_first",
    )

    profile = CandidateProfile(
        id=candidate_row.slug,
        organization_name=org.name,
        candidate=candidate_config,
        search=search_config,
        email=email_config,
        application_policy=application_policy,
    )
    return CandidateResolution(status="ok", profile=profile)


def resolve_candidate_profile(session: Session, organization_id: int, slug: str) -> CandidateResolution:
    candidate_row = (
        session.query(Candidate).filter_by(organization_id=organization_id, slug=slug).one_or_none()
    )
    if candidate_row is None:
        return CandidateResolution(status="not_found", message=f"No candidate with slug '{slug}' in this organization.")
    return resolve_candidate_profile_for_row(session, candidate_row)


def list_all_candidate_resolutions(session: Session, organization_id: int) -> list[tuple[str, CandidateResolution]]:
    """Every candidate within this organization, each resolved. Used by
    the candidates list UI and the job-posting fan-out, both of which
    must never see across an organization boundary."""
    rows = session.query(Candidate).filter_by(organization_id=organization_id).all()
    return [(row.slug, resolve_candidate_profile_for_row(session, row)) for row in rows]
