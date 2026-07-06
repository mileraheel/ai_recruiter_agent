"""
Resume tailoring engine.

Pipeline: candidate's master resume + APPROVED skill inventory (never
pending/rejected) + job description -> structured tailored content ->
grounding check (strips anything not actually approved) -> rendered
.docx via services/resume_docx_writer.py.

Every rule embedded in the prompt below is something the user explicitly
specified across a long design conversation -- summarized here so the
enforcement points are traceable back to that agreement:

  - Match target job title at the top; reorder/rewrite skills by JD
    keywords; rewrite summary and recent-experience bullets for
    strongest match.
  - Skills may be surfaced explicitly in bullets/skills-section ONLY
    when they're already in the candidate's APPROVED inventory
    (core/component/secondary tiers). Exposure-tier skills go in a
    separate, honestly-labeled section, never backdated into a specific
    job's bullets.
  - Never invent a skill/experience claim that isn't grounded in the
    approved inventory or the master resume itself.
  - Title/seniority adjustments follow same-category-same-level rules:
    developer-focused JD -> drop architect-heavy titles; architect JD ->
    align only if defensible; manager/lead JD -> emphasize mentoring,
    code reviews, delivery ownership, sprint planning, stakeholder
    communication; production-support JD -> emphasize L2/L3, RCA,
    incident management, monitoring, on-call; AI-focused JD -> emphasize
    Python/RAG/LangChain/Agentic AI/vector search where defensible;
    full-stack Java/Angular JD -> emphasize the matching stack.
  - No category/level jumps (e.g. IC to C-suite) -- explicitly out of
    scope regardless of how strong the underlying experience is.

The grounding check (run_grounding_check) is the actual enforcement
mechanism -- the prompt asks the model to follow these rules, but
nothing downstream trusts that request on its own.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from db.models import SkillInventoryItem

_TAILORING_SYSTEM_PROMPT = """\
You tailor an existing, truthful resume to a specific job description. You \
are extending and re-emphasizing REAL content, never inventing new claims.

You will be given:
1. MASTER_RESUME_TEXT -- the candidate's full, real resume content.
2. APPROVED_SKILLS -- a JSON list of skills the candidate has verified they \
   possess, each with a tier:
   - core: primary, years of hands-on work
   - component: inherent part of something they have deep experience in
   - secondary: real hands-on work, supporting/adjacent to their primary role
   - exposure: course/self-study/light exposure only, NOT demonstrated \
     production work
3. JOB_DESCRIPTION_TEXT -- the target job posting.
4. MATCHED_CATEGORIES -- domain categories already detected as overlapping \
   between the candidate's background and this JD (e.g. "Trading Platforms").
5. JOB_EMPHASIS_RULES -- role-category-specific emphasis guidance to apply \
   if the JD matches that category.

STRICT RULES -- violating any of these makes the output unusable:
- Only use skills that appear in APPROVED_SKILLS or MASTER_RESUME_TEXT. \
  Never introduce a skill/technology/tool that appears in neither.
- core/component/secondary tier skills may appear in the professional \
  summary, the skills section, AND in specific experience bullets \
  (rewritten to surface them naturally where the real work supports it).
- exposure tier skills may ONLY appear in a separate \
  "additional_technical_exposure" list -- NEVER in experience bullets, \
  NEVER given a fabricated company/date/project association.
- Do not invent employers, job titles, dates, degrees, or certifications \
  not present in MASTER_RESUME_TEXT.
- Title changes must follow JOB_EMPHASIS_RULES exactly -- do not escalate \
  seniority/category (e.g. never turn an individual-contributor role into \
  an executive title like CTO/VP, regardless of scope of past work).
- Prefer specific, defensible phrasing over vague inflation ("supported \
  Terraform configuration for AKS deployments" is fine if that's what \
  APPROVED_SKILLS/MASTER_RESUME_TEXT supports; "Terraform Infrastructure \
  Lead" is not, unless the master resume already says something equivalent).
- Every experience bullet should read as something a specific, real person \
  did -- action verb, concrete outcome, JD-relevant keyword where truthful.

Output ONLY a JSON object with this exact shape, no prose, no markdown fences:
{
  "target_title": string,
  "professional_summary": string,
  "core_skills_section": [string, ...],
  "additional_technical_exposure": [string, ...],
  "experience": [
    {
      "company": string,
      "title": string,
      "dates": string,
      "bullets": [string, ...]
    }, ...
  ],
  "tailoring_summary": string,   // 2-3 sentences: what was emphasized/reordered and why
  "risk_notes": string           // anything a human reviewer should double check, or "" if none
}
"""


@dataclass
class TailoredResumeContent:
    target_title: str
    professional_summary: str
    core_skills_section: list[str]
    additional_technical_exposure: list[str]
    experience: list[dict]
    tailoring_summary: str
    risk_notes: str
    grounding_flags: list[str] = field(default_factory=list)


def _approved_skills_payload(items: list[SkillInventoryItem]) -> list[dict]:
    return [{"skill_name": i.skill_name, "tier": i.tier} for i in items if i.status == "approved"]


def build_tailoring_prompt(
    master_resume_text: str,
    approved_skills: list[SkillInventoryItem],
    job_description_text: str,
    matched_categories: list[str],
    job_emphasis_rules: str,
) -> str:
    payload = {
        "MASTER_RESUME_TEXT": master_resume_text,
        "APPROVED_SKILLS": _approved_skills_payload(approved_skills),
        "JOB_DESCRIPTION_TEXT": job_description_text,
        "MATCHED_CATEGORIES": matched_categories,
        "JOB_EMPHASIS_RULES": job_emphasis_rules,
    }
    return json.dumps(payload, indent=2)


def tailor_resume(
    master_resume_text: str,
    approved_skills: list[SkillInventoryItem],
    job_description_text: str,
    matched_categories: list[str],
    job_emphasis_rules: str,
) -> TailoredResumeContent:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set -- required for resume tailoring."
        )

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    user_payload = build_tailoring_prompt(
        master_resume_text, approved_skills, job_description_text, matched_categories, job_emphasis_rules
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        system=_TAILORING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_payload}],
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
        raise RuntimeError(f"Resume tailoring returned non-JSON output: {e}\nRaw: {raw_text[:800]}") from e

    content = TailoredResumeContent(
        target_title=parsed.get("target_title", ""),
        professional_summary=parsed.get("professional_summary", ""),
        core_skills_section=list(parsed.get("core_skills_section", [])),
        additional_technical_exposure=list(parsed.get("additional_technical_exposure", [])),
        experience=list(parsed.get("experience", [])),
        tailoring_summary=parsed.get("tailoring_summary", ""),
        risk_notes=parsed.get("risk_notes", ""),
    )

    run_grounding_check(content, approved_skills)
    return content


def run_grounding_check(
    content: TailoredResumeContent, approved_skills: list[SkillInventoryItem]
) -> TailoredResumeContent:
    """The actual enforcement mechanism, not just a prompt instruction.

    1. Every entry in core_skills_section must exactly match (case-
       insensitive) an approved skill with tier in {core, component,
       secondary} -- anything else is stripped and logged.
    2. Every entry in additional_technical_exposure must match an
       approved skill with tier='exposure' -- anything else stripped.
    3. Best-effort bullet scan: flags (does not silently strip, since
       free text can't be safely auto-edited) any bullet that mentions a
       skill name the candidate has on record as PENDING or REJECTED
       (i.e. explicitly not yet approved) -- this is the direct defense
       against the "resume update quietly adds a trending skill" failure
       mode reaching a tailored output before human approval.

    Mutates `content` in place (stripping ungrounded list entries) and
    returns it; content.grounding_flags accumulates anything caught.
    """
    approved_names = {
        s.skill_name.strip().lower(): s.tier
        for s in approved_skills
        if s.status == "approved"
    }
    non_approved_names = {
        s.skill_name.strip().lower()
        for s in approved_skills
        if s.status in ("pending", "rejected")
    }

    kept_core: list[str] = []
    for skill in content.core_skills_section:
        tier = approved_names.get(skill.strip().lower())
        if tier in ("core", "component", "secondary"):
            kept_core.append(skill)
        else:
            content.grounding_flags.append(
                f"Removed '{skill}' from core skills section -- not an approved core/component/secondary skill."
            )
    content.core_skills_section = kept_core

    kept_exposure: list[str] = []
    for skill in content.additional_technical_exposure:
        tier = approved_names.get(skill.strip().lower())
        if tier == "exposure":
            kept_exposure.append(skill)
        else:
            content.grounding_flags.append(
                f"Removed '{skill}' from exposure section -- not an approved exposure-tier skill."
            )
    content.additional_technical_exposure = kept_exposure

    for entry in content.experience:
        for bullet in entry.get("bullets", []):
            bullet_lower = bullet.lower()
            for name in non_approved_names:
                if name and name in bullet_lower:
                    content.grounding_flags.append(
                        f"Bullet mentions '{name}', which is pending/rejected (not approved) for this "
                        f"candidate: \"{bullet}\" -- flagged for human review, not auto-removed from free text."
                    )

    return content
