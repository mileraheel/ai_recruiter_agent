"""
Phase 1 CLI. Only the job file path is required -- everything else comes
from either config/candidate.yaml (your info, preferences, exclusion
rules) or is auto-extracted from the job text itself (title, company,
location, work mode, recruiter contact). You should never need to
manually type your own location/visa/work-mode preferences -- those live
in candidate.yaml. The optional override flags exist only for the rare
case where auto-extraction guesses wrong on a specific posting.

Usage:
    python cli.py check-job sample_jobs/some_job.txt
    python cli.py check-job sample_jobs/some_job.txt --location "Austin, TX"   # override, rarely needed
    python cli.py check-job sample_jobs/some_job.txt --no-save
    python cli.py list-jobs
    python cli.py list-jobs --status skipped
    python cli.py list-recruiters
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env in the current directory, if present, into os.environ

from config.loader import load_config
from core.eligibility import evaluate_eligibility
from core.extraction import (
    extract_company_name,
    extract_emails,
    extract_job_title,
    extract_location,
    extract_recruiter_name,
    extract_work_mode,
)
from core.signature import generate_signature


def _resolve_candidate_profile(cfg, candidate_id: str | None):
    """Picks one CandidateProfile out of cfg.candidates. Required once
    there's more than one candidate in config; auto-selected when there's
    only one, so single-candidate setups don't need --candidate on every
    command."""
    if candidate_id:
        for profile in cfg.candidates:
            if profile.resolved_id() == candidate_id:
                return profile
        available = [p.resolved_id() for p in cfg.candidates]
        raise SystemExit(f"No candidate with id '{candidate_id}'. Available: {available}")

    if len(cfg.candidates) == 1:
        return cfg.candidates[0]

    available = [p.resolved_id() for p in cfg.candidates]
    raise SystemExit(
        f"Multiple candidates configured -- pass --candidate <id>. Available: {available}"
    )


def cmd_list_candidates(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    for profile in cfg.candidates:
        policy = "strict-match-only" if profile.application_policy.strict_skill_match_required else "apply-broadly"
        print(f"{profile.resolved_id():25s} | {profile.candidate.full_name:25s} | {policy} | required_keywords={profile.search.required_keywords}")


def cmd_check_job(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    profile = _resolve_candidate_profile(cfg, args.candidate)
    text = Path(args.file).read_text(encoding="utf-8")

    # Everything below is auto-extracted from the job text by default.
    # Explicit flags (all optional) override a specific field only when
    # auto-extraction guesses wrong for a particular posting.
    job_title = args.title or extract_job_title(text) or Path(args.file).stem
    location = args.location or extract_location(text)
    work_mode = args.work_mode or extract_work_mode(text)
    emails_found = extract_emails(text)
    recruiter_email = args.recruiter_email or (emails_found[0] if emails_found else None)
    recruiter_name = args.recruiter_name or extract_recruiter_name(text, recruiter_email)
    company_name = args.company or extract_company_name(text, recruiter_email)

    print(f"Candidate: {profile.candidate.full_name} ({profile.resolved_id()})")
    print(f"Job title: {job_title}")
    if location:
        print(f"Location: {location}")
    if work_mode:
        print(f"Work mode: {work_mode}")
    if company_name:
        print(f"Company: {company_name}")
    if recruiter_email:
        extra = f" ({recruiter_name})" if recruiter_name else ""
        print(f"Recruiter: {recruiter_email}{extra}")
    if len(emails_found) > 1:
        print(f"[Note: {len(emails_found)} email addresses found in posting: {emails_found}. Using the first as primary.]")

    result = evaluate_eligibility(
        job_description_text=text,
        candidate=profile.candidate,
        search_config=profile.search,
        job_location=location,
        job_work_mode=work_mode,
        strict_skill_match_required=profile.application_policy.strict_skill_match_required,
    )

    print(f"Status: {result.status.value}")
    if result.reason:
        print(f"Reason: {result.reason}")
    if result.matched_signals:
        print(f"Matched signals: {result.matched_signals}")

    if args.no_save:
        return

    # Saving is best-effort: if DATABASE_URL isn't set or the DB isn't
    # reachable, the eligibility check itself still worked and already
    # printed its result above -- a DB hiccup shouldn't make check-job look
    # like it failed entirely. --no-save is available if you want to
    # sanity-check phrasing without touching the DB at all.
    try:
        from db.session import get_session_factory
        from db.repository import save_job_check

        SessionFactory = get_session_factory()
        with SessionFactory() as session:
            job = save_job_check(
                session,
                job_title=job_title,
                description_text=text,
                eligibility_result=result,
                candidate_slug=profile.resolved_id(),
                candidate_full_name=profile.candidate.full_name,
                company_name=company_name,
                location=location,
                work_mode=work_mode,
                recruiter_email=recruiter_email,
                recruiter_name=recruiter_name,
            )
            print(f"Saved as job id {job.id} (status: {job.status})")
    except Exception as e:
        print(f"[Not saved to DB: {e}]")


def cmd_list_jobs(args: argparse.Namespace) -> None:
    from db.session import get_session_factory
    from db.models import Job, JobContact

    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        query = session.query(Job).order_by(Job.last_checked_at.desc())
        if args.status:
            query = query.filter(Job.status == args.status)
        jobs = query.limit(args.limit).all()

        if not jobs:
            print("No jobs found.")
            return

        for job in jobs:
            print(f"[{job.id}] {job.status:15s} | {job.job_title} @ {job.company_name or '-'} | {job.location or '-'}")
            if job.job_contact_id:
                contact = session.get(JobContact, job.job_contact_id)
                if contact:
                    print(f"      recruiter: {contact.recruiter_email}" + (f" ({contact.recruiter_name})" if contact.recruiter_name else ""))
            if job.skip_reason:
                print(f"      reason: {job.skip_reason}")


def cmd_list_recruiters(args: argparse.Namespace) -> None:
    from db.session import get_session_factory
    from db.models import JobContact, Job

    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        contacts = session.query(JobContact).order_by(JobContact.updated_at.desc()).limit(args.limit).all()
        if not contacts:
            print("No recruiters found.")
            return
        for c in contacts:
            job_count = session.query(Job).filter_by(job_contact_id=c.id).count()
            print(f"{c.recruiter_email:35s} | {c.recruiter_name or '-':20s} | {c.recruiter_company or '-':20s} | {job_count} job(s)")


def cmd_generate_signature(args: argparse.Namespace) -> None:
    from pathlib import Path as _Path

    cfg = load_config(args.config)
    profile = _resolve_candidate_profile(cfg, args.candidate)
    signature_text = generate_signature(profile.candidate)

    out_dir = _Path(args.output_dir)
    out_dir.mkdir(exist_ok=True)
    stem = _Path(args.file).stem
    out_path = out_dir / f"{profile.resolved_id()}_{stem}_signature.txt"
    out_path.write_text(signature_text, encoding="utf-8")

    print(signature_text)
    print(f"\nSaved to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Recruiter Agent -- Phase 1 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    check_job = sub.add_parser("check-job", help="Run the eligibility filter on a job description file")
    check_job.add_argument("file", help="Path to a .txt file containing the job description")
    check_job.add_argument("--config", default="config/candidate.yaml")
    check_job.add_argument("--candidate", default=None, help="Candidate id to check against (required if config has multiple candidates)")
    check_job.add_argument("--location", default=None, help="Override auto-detected location (rarely needed)")
    check_job.add_argument("--work-mode", default=None, choices=["remote", "hybrid", "onsite"], help="Override auto-detected work mode (rarely needed)")
    check_job.add_argument("--title", default=None, help="Override auto-detected job title (rarely needed)")
    check_job.add_argument("--company", default=None, help="Override auto-detected company (rarely needed)")
    check_job.add_argument("--recruiter-email", default=None, help="Override auto-detected recruiter email (rarely needed)")
    check_job.add_argument("--recruiter-name", default=None, help="Override auto-detected recruiter name (rarely needed)")
    check_job.add_argument("--no-save", action="store_true", help="Run the check without writing to the database")
    check_job.set_defaults(func=cmd_check_job)

    list_jobs = sub.add_parser("list-jobs", help="List jobs saved to the database")
    list_jobs.add_argument("--status", default=None, choices=["discovered", "skipped", "needs_review"])
    list_jobs.add_argument("--limit", type=int, default=20)
    list_jobs.set_defaults(func=cmd_list_jobs)

    list_recruiters = sub.add_parser("list-recruiters", help="List recruiters saved to the database")
    list_recruiters.add_argument("--limit", type=int, default=20)
    list_recruiters.set_defaults(func=cmd_list_recruiters)

    list_candidates = sub.add_parser("list-candidates", help="List candidates configured in candidate.yaml")
    list_candidates.add_argument("--config", default="config/candidate.yaml")
    list_candidates.set_defaults(func=cmd_list_candidates)

    generate_signature_parser = sub.add_parser("generate-signature", help="Generate an email signature for a job (temporary folder-based storage for testing)")
    generate_signature_parser.add_argument("file", help="Job file this signature is paired with (used only for output naming)")
    generate_signature_parser.add_argument("--config", default="config/candidate.yaml")
    generate_signature_parser.add_argument("--candidate", default=None, help="Candidate id to generate for (required if config has multiple candidates)")
    generate_signature_parser.add_argument("--output-dir", default="generated")
    generate_signature_parser.set_defaults(func=cmd_generate_signature)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
