"""
Phase 1 CLI: paste a job description in, get an eligibility decision out,
optionally save it to the database so it's browsable in DBeaver.

Usage:
    python cli.py check-job --file path/to/job.txt --location "Austin, TX" --work-mode hybrid
    python cli.py check-job --file path/to/job.txt --location "Austin, TX" --work-mode hybrid --no-save
    python cli.py list-jobs
    python cli.py list-jobs --status skipped
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env in the current directory, if present, into os.environ

from config.loader import load_config
from core.eligibility import evaluate_eligibility


def cmd_check_job(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    text = Path(args.file).read_text(encoding="utf-8")

    result = evaluate_eligibility(
        job_description_text=text,
        candidate=cfg.candidate,
        search_config=cfg.search,
        job_location=args.location,
        job_work_mode=args.work_mode,
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

        job_title = args.title or Path(args.file).stem
        SessionFactory = get_session_factory()
        with SessionFactory() as session:
            job = save_job_check(
                session,
                job_title=job_title,
                description_text=text,
                eligibility_result=result,
                company_name=args.company,
                location=args.location,
                work_mode=args.work_mode,
            )
            print(f"Saved as job id {job.id} (status: {job.status})")
    except Exception as e:
        print(f"[Not saved to DB: {e}]")


def cmd_list_jobs(args: argparse.Namespace) -> None:
    from db.session import get_session_factory
    from db.models import Job

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
            if job.skip_reason:
                print(f"      reason: {job.skip_reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Recruiter Agent -- Phase 1 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    check_job = sub.add_parser("check-job", help="Run the eligibility filter on a job description file")
    check_job.add_argument("--config", default="config/candidate.yaml")
    check_job.add_argument("--file", required=True, help="Path to a .txt file containing the job description")
    check_job.add_argument("--location", default=None)
    check_job.add_argument("--work-mode", default=None, choices=["remote", "hybrid", "onsite"])
    check_job.add_argument("--title", default=None, help="Job title; defaults to the input filename")
    check_job.add_argument("--company", default=None)
    check_job.add_argument("--no-save", action="store_true", help="Run the check without writing to the database")
    check_job.set_defaults(func=cmd_check_job)

    list_jobs = sub.add_parser("list-jobs", help="List jobs saved to the database")
    list_jobs.add_argument("--status", default=None, choices=["discovered", "skipped", "needs_review"])
    list_jobs.add_argument("--limit", type=int, default=20)
    list_jobs.set_defaults(func=cmd_list_jobs)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
