"""
Follow-up email text -- deliberately templated, not an LLM call. Unlike
the initial outreach email (which needs to synthesize JD-specific
pointers) or inbound classification (which needs real language
understanding), a follow-up nudge is formulaic by nature: "I sent you
X on date Y, any update?" Templating this is more reliable and costs
nothing, versus an LLM call that could drift in tone or invent details.
"""
from __future__ import annotations

from datetime import date

from db.models import Email, Job


def compose_initial_outreach_followup(email_row: Email, job: Job, candidate_full_name: str) -> str:
    sent_date = email_row.sent_at.date() if email_row.sent_at else date.today()
    job_title = job.job_title or "the role"
    return (
        f"Hello,\n\n"
        f"I wanted to follow up on my application for the {job_title} position -- "
        f"I sent my resume on {sent_date.strftime('%B %d, %Y')}. "
        f"Please let me know if you need anything further from me, or if there's "
        f"any update on next steps.\n\n"
        f"Regards,\n{candidate_full_name}"
    )


def compose_client_submission_followup(
    email_row: Email, job: Job, candidate_full_name: str, end_client_name: str | None
) -> str:
    submitted_date = email_row.submitted_to_client_at.date() if email_row.submitted_to_client_at else date.today()
    client_phrase = f" to {end_client_name}" if end_client_name else ""
    job_title = job.job_title or "the role"
    return (
        f"Hello,\n\n"
        f"Following up on the {job_title} position -- my resume was submitted{client_phrase} "
        f"on {submitted_date.strftime('%B %d, %Y')}. Could you let me know if there's any "
        f"feedback or update on the status?\n\n"
        f"Regards,\n{candidate_full_name}"
    )


def compose_post_interview_followup(email_row: Email, job: Job, candidate_full_name: str) -> str:
    job_title = job.job_title or "the role"
    return (
        f"Hello,\n\n"
        f"Thank you again for the opportunity to interview for the {job_title} position. "
        f"I wanted to check in and see if there's any feedback or update on next steps.\n\n"
        f"Regards,\n{candidate_full_name}"
    )


FOLLOW_UP_COMPOSERS = {
    "initial_outreach": compose_initial_outreach_followup,
    "client_submission": compose_client_submission_followup,
    "post_interview": compose_post_interview_followup,
}
