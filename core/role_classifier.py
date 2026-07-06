"""
Best-effort role/domain classifier for job description text.

Turns free-text JD content into a small set of category tags (e.g.
"Trading Platforms", "Digital Payments", "Core Banking"). Those
categories drive two downstream things:
  1. the opening line of the outreach email
     ("...aligns with my experience in building ... Trading, Payments...")
  2. which of the candidate's experience_highlights bullets get pulled
     in (core/email_composer.py only selects a bullet if its tags
     intersect the JD's matched categories)

Same design philosophy as core/eligibility.py: pure function, no LLM
call, regex/keyword based, auditable. A category is only attached
because a specific keyword pattern matched -- nothing here is inferred
"from vibes", and this module makes no claim about the candidate, only
about what's present in the job text. Extend ROLE_CATEGORY_KEYWORDS as
the candidate's target domains change; this is meant to be edited by a
human reading it, not retrained.
"""
from __future__ import annotations

import re

# category -> regex patterns that, if found in the JD, activate that
# category. Dict order is also the tie-break order when categories tie
# on hit count (earlier entries win ties) -- keep the candidate's
# strongest/most current focus areas near the top.
ROLE_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Trading Platforms": [
        r"\btrading\b",
        r"\border management\b",
        r"\boms\b",
        r"\bbuy[/\s-]?sell\b",
        r"\bsettlement\b",
        r"\breconciliation\b",
        r"\bt\+\d\b",
    ],
    "Digital Payments": [
        r"\bpayments?\b",
        r"\bfund transfer\b",
        r"\breal-time payment\b",
        r"\brtp\b",
        r"\bach\b",
        r"\bswift\b",
    ],
    "FinTech": [
        r"\bfintech\b",
        r"\bfinancial services\b",
        r"\bfinancial platform\b",
    ],
    "Core Banking": [
        r"\bcore banking\b",
        r"\bflexcube\b",
        r"\btemenos\b",
        r"\bfis\b",
    ],
    "Event-Driven Microservices": [
        r"\bkafka\b",
        r"\bevent-driven\b",
        r"\bevent driven\b",
        r"\bpub/sub\b",
        r"\bmessage queue\b",
    ],
    "Resilience & Compensation": [
        r"\bretry\b",
        r"\bcompensation\b",
        r"\bresilien\w*\b",
        r"\bcircuit breaker\b",
        r"\bsaga\b",
    ],
    "Cloud & DevOps": [
        r"\bazure\b",
        r"\baws\b",
        r"\bkubernetes\b",
        r"\bci/cd\b",
        r"\bdocker\b",
        r"\bopenshift\b",
    ],
}


def classify_role(job_description_text: str) -> list[str]:
    """Returns matched category names, ordered by number of distinct
    keyword-pattern hits (descending), ties broken by declaration order
    in ROLE_CATEGORY_KEYWORDS. Returns [] if nothing matched -- callers
    should treat that as "no specific domain signal detected", not guess
    further or fall back to a default category silently."""
    if not job_description_text:
        return []

    lower = job_description_text.lower()
    scored: list[tuple[str, int]] = []
    for category, patterns in ROLE_CATEGORY_KEYWORDS.items():
        hits = sum(1 for pattern in patterns if re.search(pattern, lower))
        if hits > 0:
            scored.append((category, hits))

    declared_order = {cat: i for i, cat in enumerate(ROLE_CATEGORY_KEYWORDS)}
    scored.sort(key=lambda item: (-item[1], declared_order[item[0]]))
    return [category for category, _ in scored]
