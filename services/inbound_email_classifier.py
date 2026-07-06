"""
Classifies one inbound email and, for job-opportunity emails, runs it
through the EXACT SAME eligibility/skill-match pipeline already used
for outbound job postings (core/eligibility.py, core/role_match.py) --
no separate, more lenient matching logic for inbound mail. A recruiter
emailing a Java candidate about a .NET role or a Desktop Analyst role
gets skipped here for the identical reason a pasted .NET job posting
gets skipped in the Post Job flow: required_keywords aren't present.

Two-stage pipeline:
  1. classify_inbound_email() -- a single Claude call determines the
     email's category (job_opportunity / document_request /
     rate_negotiation / interview_related / other) and, for job
     opportunities, extracts the JD-like text and a job title. This is
     a classification/extraction task, not a matching decision --
     nothing here decides whether to reply.
  2. evaluate_inbound_opportunity() -- for job_opportunity emails only,
     calls evaluate_eligibility() with the extracted JD text, reusing
     the same skill-match gate as everything else in this app. THIS is
     where the actual accept/reject decision happens, and it's the
     same code, not new logic.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from config.schema import CandidateProfile
from core.eligibility import EligibilityResult, EligibilityStatus, evaluate_eligibility

_CLASSIFICATION_SYSTEM_PROMPT = """\
You classify one inbound email a job candidate received. Determine what \
kind of email this is and extract relevant details. Output ONLY a JSON \
object with this shape, no prose, no markdown fences:

{
  "category": "job_opportunity" | "document_request" | "rate_negotiation" | \
"interview_related" | "form_to_fill" | "status_inquiry" | "other",
  "job_title": string or null,          // only for job_opportunity
  "job_description_text": string or null, // only for job_opportunity -- the \
full JD content from the email, verbatim, not summarized
  "requested_documents": [string, ...], // only for document_request -- e.g. \
["passport copy", "visa copy", "I-94"]
  "proposed_rate": string or null,      // only for rate_negotiation -- e.g. "$70/hr"
  "end_client_name": string or null,    // if mentioned anywhere in the email
  "implementation_partner_name": string or null, // if mentioned anywhere
  "summary": string                     // one sentence, what this email is asking for
}

Rules:
- category must be your single best judgment of the PRIMARY intent of the email.
- job_description_text should be the actual job requirements text, not the \
whole email (strip signature blocks, disclaimers, boilerplate).
- Only extract what's actually present in the email -- null/empty for \
anything not mentioned. Do not infer or guess.
"""


@dataclass
class InboundEmailClassification:
    category: str
    job_title: str | None
    job_description_text: str | None
    requested_documents: list[str]
    proposed_rate: str | None
    end_client_name: str | None
    implementation_partner_name: str | None
    summary: str


def classify_inbound_email(email_text: str, subject: str = "") -> InboundEmailClassification:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set -- required for inbound email classification.")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    user_content = f"Subject: {subject}\n\n{email_text}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=_CLASSIFICATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[len("json"):]
        raw_text = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Email classification returned non-JSON output: {e}\nRaw: {raw_text[:500]}") from e

    return InboundEmailClassification(
        category=parsed.get("category", "other"),
        job_title=parsed.get("job_title"),
        job_description_text=parsed.get("job_description_text"),
        requested_documents=list(parsed.get("requested_documents") or []),
        proposed_rate=parsed.get("proposed_rate"),
        end_client_name=parsed.get("end_client_name"),
        implementation_partner_name=parsed.get("implementation_partner_name"),
        summary=parsed.get("summary", ""),
    )


@dataclass
class InboundOpportunityDecision:
    eligibility: EligibilityResult
    matched: bool
    dedup_blocked_by: str | None = None  # set if a resubmission dedup match blocked this


def evaluate_inbound_opportunity(
    classification: InboundEmailClassification,
    profile: CandidateProfile,
    db=None,
    candidate_id: int | None = None,
    organization_id: int | None = None,
) -> InboundOpportunityDecision:
    """The actual accept/reject gate -- identical function call to what
    the Post Job flow uses. A recruiter's job_opportunity email is
    matched (or not) by the exact same required_keywords/eligibility
    rules as a pasted job posting; nothing inbound-specific is invented
    here.

    If db/candidate_id/organization_id are provided AND the
    classification extracted an end_client_name, also runs the
    resubmission dedup check -- a recruiter pitching a role whose end
    client we already submitted this candidate to recently is treated
    as not worth replying to, even if the skills genuinely match,
    since that's the "don't double-submit" rule."""
    if classification.category != "job_opportunity" or not classification.job_description_text:
        return InboundOpportunityDecision(
            eligibility=EligibilityResult(
                status=EligibilityStatus.SKIPPED, reason="Not a job-opportunity email.", matched_signals=[]
            ),
            matched=False,
        )

    result = evaluate_eligibility(
        job_description_text=classification.job_description_text,
        candidate=profile.candidate,
        search_config=profile.search,
        strict_skill_match_required=profile.application_policy.strict_skill_match_required,
    )
    matched = result.status.value == "eligible"

    if matched and db is not None and candidate_id is not None:
        from db.models import Candidate as _Candidate
        from services.billing_service import is_candidate_active

        candidate_row = db.query(_Candidate).filter_by(id=candidate_id).one_or_none()
        if candidate_row is not None:
            active, inactive_reason = is_candidate_active(db, candidate_row)
            if not active:
                matched = False
                result.reason = inactive_reason

    dedup_blocked_by = None
    if matched and classification.end_client_name and db is not None and candidate_id and organization_id:
        from services.followup_service import check_resubmission_dedup

        existing = check_resubmission_dedup(
            db, candidate_id, organization_id, classification.end_client_name, None
        )
        if existing:
            matched = False
            dedup_blocked_by = (
                f"Already submitted to '{existing.end_client_name}' on "
                f"{existing.submitted_at.date().isoformat()} -- within the resubmission cooldown."
            )

    return InboundOpportunityDecision(eligibility=result, matched=matched, dedup_blocked_by=dedup_blocked_by)
