"""
Lightweight extraction helpers for Phase 1 manual job input.

These are deliberately simple, regex-based, best-effort extractors -- not
a full parser. Their job is to reduce the most common and costly class of
human error in this workflow: a person manually retyping --location or
--work-mode and getting it wrong (e.g. typing their own location instead
of the job's). An explicit CLI flag always overrides whatever gets
auto-extracted here; this is a fallback, not a source of truth.

Once real source adapters exist (Dice, Monster, etc.), each adapter's own
extract_job_details() will likely be more reliable than these regexes for
its platform's specific formatting -- this module is the Phase-1 stand-in
for that, usable with plain pasted text from any source.
"""
from __future__ import annotations

import re

_LOCATION_LINE_PATTERNS = [
    r"(?:📍\s*)?Location\s*:\s*([^\n(]+)",
    r"(?:📍\s*)?Job\s*Location\s*:\s*([^\n(]+)",
]

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def extract_location(text: str) -> str | None:
    """Looks for a 'Location:' line and returns the text after it, stripped
    of trailing parenthetical notes like '(Onsite/Hybrid)'. Returns None if
    no such line is found -- callers should treat that as 'unknown', not
    guess further."""
    for pattern in _LOCATION_LINE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            location = m.group(1).strip().strip("-").strip()
            if location:
                return location
    return None


def extract_work_mode(text: str) -> str | None:
    """Best-effort work-mode guess from free text. Checks in order
    remote > hybrid > onsite because postings that mention multiple
    (e.g. '(Onsite/Hybrid)') are usually hybrid-leaning roles describing
    both possibilities, and remote is the most specific/unambiguous signal
    when present. This is a heuristic, not a guarantee -- pass --work-mode
    explicitly whenever the posting's wording is unclear or contradictory."""
    lower = text.lower()
    if re.search(r"\bremote\b", lower):
        return "remote"
    if re.search(r"\bhybrid\b", lower):
        return "hybrid"
    if re.search(r"\bonsite\b|\bon-site\b|\bon\s+site\b", lower):
        return "onsite"
    return None


def extract_emails(text: str) -> list[str]:
    """Returns all email addresses found in the text, in order of
    appearance, de-duplicated. The first one is generally the best guess
    for 'primary recruiter contact' on typical postings, but callers
    should surface all of them rather than silently discarding the rest."""
    seen: list[str] = []
    for match in _EMAIL_PATTERN.findall(text):
        if match not in seen:
            seen.append(match)
    return seen


def extract_recruiter_name(text: str, recruiter_email: str | None = None) -> str | None:
    """Best-effort recruiter name guess: looks for a short line (likely a
    person's name, not a sentence) immediately preceding the recruiter's
    email address in the text. Deliberately conservative -- returns None
    rather than guessing wrong, since a wrong name is worse than no name."""
    if not recruiter_email:
        return None
    lines = [l.strip() for l in text.splitlines()]
    try:
        email_line_idx = next(i for i, l in enumerate(lines) if recruiter_email in l)
    except StopIteration:
        return None

    for i in range(email_line_idx - 1, max(email_line_idx - 4, -1), -1):
        candidate = lines[i].strip()
        # Heuristic for "looks like a name, not a sentence or heading":
        # short, no punctuation-heavy formatting, not an email itself.
        if (
            candidate
            and len(candidate) <= 40
            and "@" not in candidate
            and not candidate.endswith(":")
            and len(candidate.split()) <= 4
            and not any(ch in candidate for ch in "|✅🔹📩📍📄🆔⚠️")
        ):
            return candidate
    return None


_TITLE_LINE_PATTERNS = [
    r"^(?:Hiring|Job\s*Title|Position|Role|Now\s*Hiring)\s*:?\s*(.+)$",
]

_EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]+",
    re.UNICODE,
)


def extract_job_title(text: str) -> str | None:
    """Looks for an explicit 'Hiring:' / 'Job Title:' / 'Position:' /
    'Role:' line first. Falls back to the first non-empty line of the
    text that isn't just an email address (since real recruiter
    messages often lead with contact info -- name/email -- before the
    actual posting), stripped of emoji/decoration. Returns None if no
    such line exists -- a wrong title guess sent out in a real email is
    worse than no title, same principle as extract_recruiter_name's
    conservative fallback."""
    for pattern in _TITLE_LINE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            title = _EMOJI_PATTERN.sub("", m.group(1)).strip()
            if title:
                return title

    for line in text.splitlines():
        stripped = _EMOJI_PATTERN.sub("", line).strip()
        if not stripped:
            continue
        if _EMAIL_PATTERN.fullmatch(stripped):
            continue  # a bare email address is contact info, not a title
        return stripped
    return None


_COMPANY_LINE_PATTERNS = [
    r"^(?:Company|Client|Employer)\s*:\s*(.+)$",
]


def extract_company_name(text: str, recruiter_email: str | None = None) -> str | None:
    """Looks for an explicit 'Company:' / 'Client:' / 'Employer:' line
    first. Falls back to guessing from the recruiter's email domain
    (e.g. rachael@sidramtech.com -> 'Sidramtech') if no explicit label is
    found -- a rough guess, but usually right for small/mid staffing
    shops where the domain *is* the company name. Pass --company
    explicitly whenever the domain doesn't match the actual company
    (e.g. a recruiter emailing from a generic Gmail address)."""
    for pattern in _COMPANY_LINE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            company = m.group(1).strip()
            if company:
                return company

    if recruiter_email and "@" in recruiter_email:
        domain = recruiter_email.split("@", 1)[1]
        domain_root = domain.split(".")[0]
        generic_domains = {"gmail", "yahoo", "outlook", "hotmail", "icloud", "aol"}
        if domain_root.lower() not in generic_domains and domain_root:
            return domain_root.capitalize()
    return None
