"""
Job-shape classifier: determines which of the candidate's agreed
title/emphasis rules apply to a given JD -- developer / architect /
manager-lead / production-support / AI / full-stack-java-angular. A
single JD can match more than one shape (e.g. "Java Architect - Team
Lead" is both architect and manager-lead); the emphasis text for all
matched shapes gets combined and handed to the tailoring prompt.

Same pattern as core/role_classifier.py: pure function, regex/keyword
based, no LLM call, auditable. This module encodes agreements reached
directly with the candidate about how their resume should shift shape
per job category -- edit ROLE_SHAPE_KEYWORDS/EMPHASIS_TEXT here if those
agreements change, not the tailoring prompt itself.
"""
from __future__ import annotations

import re

ROLE_SHAPE_KEYWORDS: dict[str, list[str]] = {
    "developer": [
        r"\bdeveloper\b", r"\bsoftware engineer\b", r"\bsde\b", r"\bindividual contributor\b",
    ],
    "architect": [
        r"\barchitect\b",
    ],
    "manager_lead": [
        r"\bmanager\b", r"\btech(nical)? lead\b", r"\bteam lead\b", r"\bengineering lead\b",
        r"\bdelivery lead\b", r"\bscrum master\b",
    ],
    "production_support": [
        r"\bproduction support\b", r"\bl2 support\b", r"\bl3 support\b", r"\bapplication support\b",
        r"\bon-?call\b", r"\bincident management\b", r"\brca\b",
    ],
    "ai": [
        r"\bagentic ai\b", r"\brag\b", r"\blangchain\b", r"\blanggraph\b", r"\bllm\b",
        r"\bvector search\b", r"\bprompt engineering\b", r"\bmachine learning\b", r"\bai engineer\b",
    ],
    "fullstack_java_angular": [
        r"\bfull\s*stack\b.{0,30}\b(java|angular)\b",
        r"\bjava\b.{0,30}\bangular\b",
        r"\bangular\b.{0,30}\bjava\b",
    ],
}

EMPHASIS_TEXT: dict[str, str] = {
    "developer": (
        "This is a developer-focused (not architect-focused) posting. Remove or soften "
        "architect-heavy titles from the target title and recent-role framing -- present as a "
        "senior/lead developer, not an architect, even where the underlying master resume lists "
        "an architect title. The work itself (real, hands-on) stays; only the title framing shifts."
    ),
    "architect": (
        "This is an architect-focused posting. Align recent titles toward Architect only where the "
        "master resume's actual scope of work defensibly supports it (system design ownership, "
        "cross-team technical decisions) -- do not inflate a developer/lead role into an architect "
        "title if the master resume doesn't already support that framing."
    ),
    "manager_lead": (
        "This is a manager/lead-focused posting. Emphasize mentoring, code reviews, delivery "
        "ownership, sprint planning, onboarding, performance feedback, technical escalation, and "
        "stakeholder communication -- pulling forward any real instances of these already present "
        "in the master resume, not inventing new ones."
    ),
    "production_support": (
        "This is a production-support-focused posting. Emphasize L2/L3 support, RCA, incident "
        "management, monitoring, Splunk, O&M, deployment support, weekend/shift/on-call readiness, "
        "Unix/Linux, and troubleshooting -- pulling forward any real instances already present in "
        "the master resume or approved skill inventory."
    ),
    "ai": (
        "This is an AI-focused posting. Emphasize Python, RAG, LangChain/LangGraph, Agentic AI, "
        "vector search, prompt engineering, and cloud/Kubernetes where the candidate has approved "
        "experience; reference enterprise Java architecture background only where it's defensibly "
        "relevant context (e.g. integrating AI components into existing Java systems), not as the "
        "headline of the resume."
    ),
    "fullstack_java_angular": (
        "This is a full-stack Java/Angular posting. Emphasize Java 17/21, Spring Boot, Angular "
        "17/18, TypeScript, REST, GraphQL, NgRx/state management if relevant, Azure/AWS, CI/CD, "
        "Docker/Kubernetes, JUnit, Jasmine/Karma exposure, and Agile delivery -- using only skills "
        "already in the approved inventory or master resume."
    ),
}

# CTO/executive-level titles are explicitly and permanently out of scope
# for automated title alignment, regardless of how strong the underlying
# leadership/delivery-ownership experience is -- agreed directly with
# the candidate. This is enforced in the emphasis text itself (manager_lead
# above stops at Lead/Manager framing) and restated here as a guardrail
# note included in every tailoring run.
EXECUTIVE_TITLE_GUARDRAIL = (
    "Never assign an executive-level title (CTO, VP, Chief Officer, etc.) regardless of the scope "
    "of leadership/delivery-ownership experience described in the master resume. Individual-"
    "contributor and lead/management titles (Architect, Tech Lead, Engineering Manager, Delivery "
    "Lead, etc.) are the ceiling for automated title alignment."
)


def classify_job_shapes(job_title: str | None, job_description_text: str) -> list[str]:
    combined = f"{job_title or ''}\n{job_description_text or ''}".lower()
    matched = [shape for shape, patterns in ROLE_SHAPE_KEYWORDS.items() if any(re.search(p, combined) for p in patterns)]
    return matched


def build_emphasis_rules_text(job_title: str | None, job_description_text: str) -> str:
    shapes = classify_job_shapes(job_title, job_description_text)
    if not shapes:
        return (
            "No specific role-shape signal detected (developer/architect/manager/support/AI/"
            "full-stack). Apply general tailoring: match title conservatively to the JD's stated "
            "title without escalating seniority, emphasize the closest overlapping real experience.\n\n"
            + EXECUTIVE_TITLE_GUARDRAIL
        )
    rule_text = "\n\n".join(EMPHASIS_TEXT[s] for s in shapes)
    return f"{rule_text}\n\n{EXECUTIVE_TITLE_GUARDRAIL}"
