"""
Generates a plain-text email signature from candidate.yaml. No job-specific
content -- the signature itself doesn't change per posting, only its
filename does (to keep it paired with the job it was generated alongside).
Availability/authorization notes are template-driven off candidate config,
never invented.
"""
from __future__ import annotations

from config.schema import CandidateConfig


def generate_signature(candidate: CandidateConfig) -> str:
    lines = [candidate.full_name]

    if candidate.linkedin_url:
        lines.append(candidate.linkedin_url)

    contact_line = f"{candidate.phone} | {candidate.email}"
    lines.append(contact_line)

    if candidate.location:
        lines.append(candidate.location)

    # Work authorization note -- only stated plainly from config, never
    # inferred or embellished. Omitted entirely if the candidate has no
    # sponsorship/transfer requirement to disclose.
    if candidate.requires_sponsorship_or_transfer:
        lines.append(f"Work Authorization: {candidate.work_authorization} (requires sponsorship/transfer)")
    else:
        lines.append(f"Work Authorization: {candidate.work_authorization}")

    engagement_terms = []
    if candidate.c2c_allowed:
        engagement_terms.append("C2C")
    if candidate.contract_allowed:
        engagement_terms.append("Contract")
    if candidate.contract_to_hire_allowed:
        engagement_terms.append("Contract-to-Hire")
    if candidate.full_time_allowed:
        engagement_terms.append("Full-Time")
    if engagement_terms:
        lines.append(f"Open to: {', '.join(engagement_terms)}")

    availability_terms = []
    if candidate.willing_to_work_remote:
        availability_terms.append("Remote")
    if candidate.willing_to_work_hybrid:
        availability_terms.append("Hybrid")
    if candidate.willing_to_work_onsite:
        availability_terms.append("Onsite")
    if availability_terms:
        lines.append(f"Availability: {', '.join(availability_terms)}")

    return "\n".join(lines)
