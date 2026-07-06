"""
Screenshot job-posting ingestion: an image goes through Claude's vision
API and comes back as the same structured fields extract.py already
produces from pasted text (title, company, location, work mode,
recruiter contact, and the raw text itself). From that point on it's
the exact same pipeline as paste-text -- eligibility, role_match,
role_classifier all run on job_description_text regardless of which
adapter produced it.

Server-side call using ANTHROPIC_API_KEY, same as resume_ingestion.py
-- no client-side vision call, no third-party OCR service.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

_EXTRACTION_SYSTEM_PROMPT = """\
You are reading a screenshot of a job posting (from LinkedIn, Dice, \
email, or similar). Extract what's visible and return ONLY a JSON object \
with these fields:

- job_title: string or null
- company_name: string or null
- location: string or null
- work_mode: one of "remote", "hybrid", "onsite", or null if not stated
- recruiter_name: string or null
- recruiter_email: string or null
- raw_text: the full visible job posting text, transcribed as accurately \
  as possible, preserving line breaks as \\n

Rules:
- Only extract what is actually visible in the image. Do not guess or \
  infer fields that aren't shown.
- raw_text should be a faithful transcription, not a summary.
- Output ONLY the JSON object. No prose, no markdown fences.
"""


@dataclass
class ExtractedJobPosting:
    job_title: str | None
    company_name: str | None
    location: str | None
    work_mode: str | None
    recruiter_name: str | None
    recruiter_email: str | None
    raw_text: str


_MEDIA_TYPE_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def extract_job_posting_from_screenshot(image_bytes: bytes, filename: str) -> ExtractedJobPosting:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set -- required for screenshot extraction. "
            "Set it in your .env before uploading screenshots."
        )

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    media_type = _MEDIA_TYPE_BY_EXT.get(ext)
    if not media_type:
        raise ValueError(f"Unsupported image type '{ext}'. Supported: {list(_MEDIA_TYPE_BY_EXT)}")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        system=_EXTRACTION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(image_bytes).decode("utf-8"),
                        },
                    },
                    {"type": "text", "text": "Extract the job posting fields as instructed."},
                ],
            }
        ],
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
        raise RuntimeError(f"Screenshot extraction returned non-JSON output: {e}\nRaw: {raw_text[:500]}") from e

    return ExtractedJobPosting(
        job_title=parsed.get("job_title"),
        company_name=parsed.get("company_name"),
        location=parsed.get("location"),
        work_mode=parsed.get("work_mode"),
        recruiter_name=parsed.get("recruiter_name"),
        recruiter_email=parsed.get("recruiter_email"),
        raw_text=parsed.get("raw_text") or "",
    )
