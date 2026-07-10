"""
Composes the outreach email sent alongside the tailored resume: greeting,
opening line, job-specific pointers, closing, and signature block.

Everything that varies is either:
  (a) EXTRACTED from the job posting text via core/extraction.py
      (recruiter name, job title), or
  (b) SELECTED -- never invented -- from candidate.yaml, matched against
      core/role_classifier.py categories (experience_highlights)

Static narrative (tech_stack_summary, closing_statement) and identity/
contact fields (name, employer, rate, work status, etc.) come straight
from config, unchanged, exactly like core/signature.py already does for
the plain-text signature. This module doesn't replace signature.py's
use case (a standalone signature block); it produces the full email
that goes out with a resume attached.

No LLM call happens here. If recruiter-name extraction failed, the
greeting falls back to "Hiring Manager" rather than guessing a name.
If nothing in the JD matches a known role category, the highlight
bullets fall back to any tagged "general" -- the email is never left
with zero pointers, but never gets a bullet that isn't already sitting
in the candidate's own config.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

from config.app_info import APP_NAME
from config.schema import CandidateConfig
from core.role_classifier import classify_role

MAX_HIGHLIGHT_BULLETS = 6
MAX_CATEGORY_PHRASE_ITEMS = 4


def _disclosure_line() -> str:
    """Appended to every outbound email. Two deliberate purposes:
    (1) transparency/anti-phishing -- a recruiter receiving an
    unsolicited document request in reply to this thread can verify the
    original outreach really was AI-assisted and legitimate, rather
    than the app's identity being usable as phishing cover; (2) a
    marketing touchpoint for the platform itself. App name comes from
    config/app_info.py (APP_NAME env var); the marketing URL is still
    env-configurable on its own since it isn't finalized yet."""
    app_name = APP_NAME
    url = os.environ.get("AI_RECRUITER_MARKETING_URL", "").strip()
    line = f"This email was prepared by {app_name} on behalf of the candidate, with their permission."
    if url:
        line += f" Interested in what we do? {url}"
    return line


@dataclass
class ComposedEmail:
    greeting: str
    matched_categories: list[str]
    highlight_bullets: list[str]
    years_experience: str
    body: str


def years_of_experience(career_start_date: date, as_of: date | None = None) -> str:
    """Computed, not hardcoded -- so it never needs manual updating.
    Rounds down to whole completed years and expresses it as 'N+',
    since a year currently in progress still counts as real experience
    in the field."""
    as_of = as_of or date.today()
    years = as_of.year - career_start_date.year
    if (as_of.month, as_of.day) < (career_start_date.month, career_start_date.day):
        years -= 1
    return f"{max(years, 0)}+"


def _select_highlight_bullets(
    candidate: CandidateConfig, matched_categories: list[str]
) -> list[str]:
    """Pulls bullets whose tags intersect matched_categories, preserving
    the order the candidate wrote them in candidate.yaml, capped at
    MAX_HIGHLIGHT_BULLETS. Falls back to bullets tagged 'general' only
    if nothing matched at all."""
    matched_set = set(matched_categories)
    selected = [
        h.text
        for h in candidate.experience_highlights
        if matched_set.intersection(h.tags)
    ]
    if not selected:
        selected = [
            h.text for h in candidate.experience_highlights if "general" in h.tags
        ]
    return selected[:MAX_HIGHLIGHT_BULLETS]


def compose_email(
    candidate: CandidateConfig,
    job_title: str,
    job_description_text: str,
    recruiter_name: str | None = None,
) -> ComposedEmail:
    if candidate.career_start_date is None:
        raise ValueError(
            "candidate.career_start_date is not set in config -- required to "
            "compute years of experience for the outreach email. Add it to "
            "candidate.yaml (e.g. career_start_date: \"2009-01-01\")."
        )

    greeting = f"Hello {recruiter_name}," if recruiter_name else "Hello Hiring Manager,"

    matched_categories = classify_role(job_description_text)
    highlight_bullets = _select_highlight_bullets(candidate, matched_categories)
    years = years_of_experience(candidate.career_start_date)

    category_phrase = (
        ", ".join(matched_categories[:MAX_CATEGORY_PHRASE_ITEMS])
        if matched_categories
        else "enterprise software"
    )

    lines: list[str] = [greeting, ""]

    lines.append(
        f"Please find my resume attached for the {job_title} opportunity "
        f"referenced in the subject line. The role strongly aligns with my "
        f"experience in building enterprise-grade {category_phrase} platforms."
    )
    lines.append("")

    relocation_clause = (
        " and open to relocation for full-time opportunities"
        if candidate.open_to_relocation and candidate.full_time_allowed
        else " and open to relocation" if candidate.open_to_relocation
        else ""
    )
    lines.append(f"I am currently based in {candidate.location}{relocation_clause}.")
    lines.append("")

    experience_intro = f"I bring {years} years of hands-on software development experience"
    if candidate.tech_stack_summary:
        experience_intro += f", {candidate.tech_stack_summary}"
    experience_intro += ". My recent work has been heavily concentrated in:"
    lines.append(experience_intro)
    lines.append("")

    for bullet in highlight_bullets:
        lines.append(f"* {bullet}")

    if candidate.closing_statement:
        lines.append("")
        lines.append(candidate.closing_statement)

    lines.append("")

    # --- Signature / detail block -----------------------------------
    lines.append(f"Full Legal Name : {candidate.full_name}")
    lines.append(f"Work Status : {candidate.work_authorization}")
    if candidate.c2c_rate:
        lines.append(f"C2C Rate : {candidate.c2c_rate}")
    if candidate.passport_number:
        lines.append(f"Passport Number : {candidate.passport_number}")
    lines.append(f"Current Location : {candidate.location}")
    lines.append(f"Open for Relocation : {'Yes' if candidate.open_to_relocation else 'No'}")
    lines.append(f"Number of Years in Experience : {years}")
    if candidate.linkedin_url:
        lines.append(f"LinkedIn : {candidate.linkedin_url}")

    if candidate.employer:
        lines.append("")
        lines.append("My employer details are below :")
        lines.append(candidate.employer.name)
        lines.append(candidate.employer.email)
        lines.append(candidate.employer.phone)

    lines.append("")
    lines.append("Regards,")
    lines.append(candidate.full_name)
    lines.append(candidate.phone)

    lines.append("")
    lines.append(_disclosure_line())

    body = "\n".join(lines)

    return ComposedEmail(
        greeting=greeting,
        matched_categories=matched_categories,
        highlight_bullets=highlight_bullets,
        years_experience=years,
        body=body,
    )
