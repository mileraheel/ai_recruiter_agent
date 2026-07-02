"""
Eligibility filter engine.

Pure function: (job description text + candidate config) -> a decision.
No network, no DB, no LLM call -- this is deliberately the simplest,
most testable, most auditable piece of the whole system, because it's
the thing standing between the candidate and applying to a job that
explicitly excludes them.

Every decision carries a specific, human-readable reason. "Unclear"
inputs are never silently treated as eligible -- they fall through to
needs_human_review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from config.schema import CandidateConfig, SearchConfig


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    SKIPPED = "skipped"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


@dataclass
class EligibilityResult:
    status: EligibilityStatus
    reason: str | None = None
    matched_signals: list[str] = field(default_factory=list)


# --- Phrase banks -----------------------------------------------------
# Each entry: (regex pattern, human-readable category tag).
# Patterns are intentionally simple substring/word-boundary matches --
# resist the urge to get clever with NLP here; false negatives are safer
# to catch via needs_human_review than false positives are to catch via
# an over-eager regex silently skipping an eligible job.

_CITIZENSHIP_OR_NO_SPONSORSHIP_PATTERNS = [
    r"\bUS\s*Citizen(s)?\s*only\b",
    r"\bU\.?S\.?\s*citizenship\s*(is\s*)?required\b",
    r"\bGreen\s*Card\s*only\b",
    r"\bGC\s*only\b",
    r"\bUSC\s*/?\s*GC\s*only\b",
    r"\bno\s*sponsorship\b",
    r"\bunable\s*to\s*sponsor\b",
    r"\bcannot\s*sponsor\b",
    r"\bsponsorship\s*(is\s*)?not\s*available\b",
    r"\bno\s*visa\s*sponsorship\b",
    r"\bno\s*H-?1B\b",
    r"\bH-?1B\s*not\s*accepted\b",
    r"\bmust\s*be\s*authorized\s*(to\s*work\s*)?without\s*sponsorship\b",
    r"\bmust\s*not\s*require\s*sponsorship\s*(now\s*or\s*in\s*the\s*future)?\b",
]

_W2_ONLY_PATTERNS = [
    r"\bW-?2\s*only\b",
    r"\bonly\s*W-?2\b",
]

_NO_C2C_PATTERNS = [
    r"\bno\s*C2C\b",
    r"\bC2C\s*not\s*accepted\b",
    r"\bno\s*third[-\s]?party\s*candidates?\b",
    r"\bno\s*vendors?\b",
    r"\bno\s*employer\s*layers?\b",
    r"\bdirect\s*candidates?\s*only\b",
]

_SECURITY_CLEARANCE_PATTERNS = [
    # Explicit clearance type named directly before "clearance"
    r"\b(secret|top\s*secret|ts\s*/?\s*sci)\s*clearance\b",
    # "clearance" near a requirement word, in either order, allowing a
    # bounded gap for words in between (e.g. "clearance is required",
    # "active security clearance needed", "required to hold a clearance").
    # This proximity approach -- rather than exact adjacency -- is what
    # catches real-world phrasing variety without needing an exhaustive
    # literal phrase list.
    r"\bclearance\b.{0,20}\b(required|needed|necessary|mandatory)\b",
    r"\b(required|needed|necessary|mandatory)\b.{0,20}\bclearance\b",
    r"\brequir(e[sd]?|ing)\b.{0,40}\bclearance\b",
    r"\bmust\s+(have|possess|hold|maintain)\b.{0,40}\bclearance\b",
    r"\bneeds?\b.{0,40}\bclearance\b",
]

# Negated phrasing that should NOT be treated as a clearance requirement,
# e.g. "no clearance needed", "clearance not required", "without a clearance".
# Checked first; if any of these match, the positive patterns above are
# skipped for this job (proximity matching is deliberately loose, so an
# explicit negation guard is needed to avoid flipping the meaning).
_CLEARANCE_NEGATION_PATTERNS = [
    r"\bno\s+(active\s+)?(security\s+)?clearance\s*(is\s*)?(required|needed|necessary)?\b",
    r"\bclearance\s+(is\s+)?not\s+(required|needed|necessary)\b",
    r"\bwithout\s+(a\s+)?(security\s+)?clearance\b",
    r"\bdoes\s*n[o']?t\s+require\b.{0,40}\bclearance\b",
    r"\bclearance\s+not\s+(a\s+)?(requirement|required)\b",
]

_PUBLIC_TRUST_PATTERNS = [
    r"\bpublic\s*trust\s*(clearance\s*)?required\b",
]

_ONSITE_ONLY_PATTERNS = [
    r"\bonsite\s*only\b",
    r"\bno\s*remote\b",
    r"\bmust\s*be\s*(on[-\s]?site|in[-\s]?office)\s*(5\s*days|full[-\s]?time)?\b",
]

_LOCAL_ONLY_PATTERNS = [
    r"\blocal\s*candidates?\s*only\b",
    r"\bmust\s*be\s*local\b",
]


def _find_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(0)
    return None


_NEGATION_LOOKBEHIND = re.compile(r"\b(no|not|without|isn't|doesn't|does\s*n[o']?t|never)\s*$", re.IGNORECASE)


def _preceded_by_negation(text: str, match_start: int, window: int = 20) -> bool:
    """True if a negation word (no/not/without/doesn't/never) appears in the
    `window` characters immediately before match_start. Used to stop plain
    substring/keyword matching from flipping the meaning of phrases like
    'No security clearance required' into a false skip."""
    prefix = text[max(0, match_start - window):match_start]
    return bool(_NEGATION_LOOKBEHIND.search(prefix))


def evaluate_eligibility(
    job_description_text: str,
    candidate: CandidateConfig,
    search_config: SearchConfig,
    job_location: str | None = None,
    job_work_mode: str | None = None,  # "remote" | "hybrid" | "onsite" | None
) -> EligibilityResult:
    text = job_description_text or ""

    # 1. Sponsorship / citizenship requirements
    if candidate.requires_sponsorship_or_transfer:
        match = _find_match(text, _CITIZENSHIP_OR_NO_SPONSORSHIP_PATTERNS)
        if match:
            return EligibilityResult(
                EligibilityStatus.SKIPPED,
                reason=f"Skipped because job requires citizenship/no sponsorship (matched: '{match}').",
                matched_signals=[match],
            )

    # 2. W2-only / no-C2C requirements
    if not candidate.w2_allowed:
        w2_match = _find_match(text, _W2_ONLY_PATTERNS)
        if w2_match:
            return EligibilityResult(
                EligibilityStatus.SKIPPED,
                reason=f"Skipped because job says W2 only and candidate config says W2 is not allowed (matched: '{w2_match}').",
                matched_signals=[w2_match],
            )
        no_c2c_match = _find_match(text, _NO_C2C_PATTERNS)
        if no_c2c_match:
            return EligibilityResult(
                EligibilityStatus.SKIPPED,
                reason=f"Skipped because job says no C2C (matched: '{no_c2c_match}').",
                matched_signals=[no_c2c_match],
            )

    # 3. Security clearance
    clearance_negated = _find_match(text, _CLEARANCE_NEGATION_PATTERNS)
    clearance_match = None if clearance_negated else _find_match(text, _SECURITY_CLEARANCE_PATTERNS)
    if clearance_match and not candidate.has_security_clearance:
        return EligibilityResult(
            EligibilityStatus.SKIPPED,
            reason=f"Skipped because job requires active security clearance (matched: '{clearance_match}').",
            matched_signals=[clearance_match],
        )

    # 4. Public trust -- only skip if explicitly unavailable, or paired
    #    with citizenship-only language (checked above already, so here
    #    we only need the "public_trust_available: false" branch).
    trust_match = _find_match(text, _PUBLIC_TRUST_PATTERNS)
    if trust_match and not candidate.public_trust_available:
        return EligibilityResult(
            EligibilityStatus.SKIPPED,
            reason=f"Skipped because job requires public trust and candidate config says public trust is not available (matched: '{trust_match}').",
            matched_signals=[trust_match],
        )

    # 5. Onsite-only
    onsite_match = _find_match(text, _ONSITE_ONLY_PATTERNS)
    if (onsite_match or job_work_mode == "onsite") and not candidate.willing_to_work_onsite:
        return EligibilityResult(
            EligibilityStatus.SKIPPED,
            reason="Skipped because job is onsite only and onsite is disabled in config.",
            matched_signals=[onsite_match] if onsite_match else ["work_mode=onsite"],
        )

    # 6. Local-candidates-only / location mismatch
    local_match = _find_match(text, _LOCAL_ONLY_PATTERNS)
    if local_match or job_work_mode == "hybrid":
        if job_location and search_config.locations:
            location_ok = any(
                loc.strip().lower() in job_location.lower()
                or job_location.lower() in loc.strip().lower()
                for loc in search_config.locations
            )
            if not location_ok:
                return EligibilityResult(
                    EligibilityStatus.SKIPPED,
                    reason="Skipped because job location does not match configured locations.",
                    matched_signals=[local_match] if local_match else ["work_mode=hybrid, location mismatch"],
                )
        elif local_match and not job_location:
            # Says "local only" but we don't know the job's location --
            # can't confirm a match either way. Don't guess.
            return EligibilityResult(
                EligibilityStatus.NEEDS_HUMAN_REVIEW,
                reason="Job says local candidates only, but job location could not be determined to compare against configured locations.",
                matched_signals=[local_match],
            )

    # 7. Remote work_mode with candidate unwilling
    if job_work_mode == "remote" and not candidate.willing_to_work_remote:
        return EligibilityResult(
            EligibilityStatus.SKIPPED,
            reason="Skipped because job is remote and candidate config says remote is not desired.",
            matched_signals=["work_mode=remote"],
        )

    # 8. Config-driven excluded_keywords fallback.
    # The categorized checks above (1-3) give specific, well-tested reasons
    # for the common cases. This pass exists so that adding a new exclusion
    # phrase to candidate.yaml -- one the categorized regexes don't already
    # cover -- takes effect immediately, with no code change required.
    # It runs last so a categorized reason is always preferred when both
    # would match the same text.
    text_lower = text.lower()
    for keyword in search_config.excluded_keywords:
        keyword_clean = keyword.strip()
        if not keyword_clean:
            continue
        match = re.search(re.escape(keyword_clean), text, re.IGNORECASE)
        if match and not _preceded_by_negation(text, match.start()):
            return EligibilityResult(
                EligibilityStatus.SKIPPED,
                reason=f"Skipped because job contains excluded keyword: '{keyword}'.",
                matched_signals=[keyword],
            )

    return EligibilityResult(EligibilityStatus.ELIGIBLE)
