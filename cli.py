"""
Minimal CLI for Phase 1 manual testing -- no DB, no browser, just:
paste a job description in, get an eligibility decision out.

Usage:
    CANDIDATE_EMAIL=you@example.com CANDIDATE_PHONE=555-555-5555 SENDER_EMAIL=you@example.com \\
    python cli.py check-job --config config/candidate.example.yaml --file path/to/job.txt \\
        --location "Austin, TX" --work-mode hybrid
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


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Recruiter Agent -- Phase 1 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    check_job = sub.add_parser("check-job", help="Run the eligibility filter on a job description file")
    check_job.add_argument("--config", default="config/candidate.example.yaml")
    check_job.add_argument("--file", required=True, help="Path to a .txt file containing the job description")
    check_job.add_argument("--location", default=None)
    check_job.add_argument("--work-mode", default=None, choices=["remote", "hybrid", "onsite"])
    check_job.set_defaults(func=cmd_check_job)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
