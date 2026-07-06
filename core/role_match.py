"""
Skill/role match check -- the "is this even the right kind of job for
this candidate" gate, evaluated BEFORE eligibility's compliance checks
and BEFORE any resume tailoring.

This is deliberately separate from core/role_classifier.py:
  - role_classifier.py answers "which of the candidate's *domain*
    experience (Trading, Payments, Core Banking...) does this JD touch",
    used to pick outreach-email bullets for a job the candidate is
    already being applied to.
  - role_match.py (this module) answers the earlier, blunter question:
    "does this job even belong to the candidate's core technology stack
    at all" -- e.g. is a Java candidate looking at a Java job, not a
    .NET job. This is what stops a bench-sales style "resume alteration
    for every posting" pipeline from quietly turning a Java developer
    into a fabricated ".NET developer" for a role they've never worked.

Pure function, no LLM call, same auditable style as eligibility.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from config.schema import SearchConfig


@dataclass
class SkillMatchResult:
    matched: bool
    missing_required_keywords: list[str] = field(default_factory=list)
    reason: str | None = None


_NEGATION_LOOKBEHIND = re.compile(r"\b(no|not|without|isn't|doesn't|does\s*n[o']?t|never)\s*$", re.IGNORECASE)


def _preceded_by_negation(text: str, match_start: int, window: int = 20) -> bool:
    """Same negation guard as core/eligibility.py -- stops a phrase like
    'No Java required' or '.NET (Java not needed)' from counting as a
    Java match just because the word 'Java' appears somewhere nearby."""
    prefix = text[max(0, match_start - window):match_start]
    return bool(_NEGATION_LOOKBEHIND.search(prefix))


def _keyword_present(text: str, keyword: str) -> bool:
    keyword_clean = keyword.strip()
    if not keyword_clean:
        return True  # an empty configured keyword can't fail a match
    for match in re.finditer(re.escape(keyword_clean), text, re.IGNORECASE):
        if not _preceded_by_negation(text, match.start()):
            return True
    return False


def evaluate_skill_match(
    job_description_text: str,
    search_config: SearchConfig,
    strict_skill_match_required: bool = True,
) -> SkillMatchResult:
    """search_config.required_keywords is treated as the candidate's core
    role identity (e.g. ["Java"] for a Java candidate). When strict
    matching is required, every required_keyword must appear somewhere
    in the job text or the match fails outright -- no partial credit,
    since the point is precisely to prevent "close enough" tech-stack
    substitution.

    When strict_skill_match_required is False, this check is skipped
    entirely and matched=True is returned -- callers relying on looser
    matching should apply their own adjacent-role logic on top, but this
    function makes no attempt to guess "close enough" itself, since a
    wrong guess here is exactly the failure mode this module exists to
    prevent.
    """
    text = job_description_text or ""

    if not strict_skill_match_required:
        return SkillMatchResult(
            matched=True,
            reason="Strict skill match disabled for this candidate; matching not enforced by role_match.",
        )

    if not search_config.required_keywords:
        return SkillMatchResult(
            matched=True,
            reason="No required_keywords configured -- nothing to check, treated as a match.",
        )

    missing = [
        kw.strip()
        for kw in search_config.required_keywords
        if kw.strip() and not _keyword_present(text, kw)
    ]

    if missing:
        return SkillMatchResult(
            matched=False,
            missing_required_keywords=missing,
            reason=(
                "Job description does not mention required core skill(s): "
                f"{missing}. Candidate's required_keywords represent their "
                "core technology identity -- this job is being treated as "
                "a different role, not tailored/applied to."
            ),
        )

    return SkillMatchResult(matched=True, reason="All required_keywords found in job description.")
