"""
Wipe one or more Organizations and every row that hangs off them
(candidates, jobs, emails, applications, resumes, subscriptions,
skill inventory, etc.), while leaving SuperUser and Staff accounts
untouched.

This is a hard delete, not the app's normal "deactivate, don't
delete" behavior (see Organization.is_active) -- that's deliberate:
this script exists specifically to let you throw away disposable
test organizations you created while validating flows, which is a
different situation from a staff member removing a real org.

Usage:
    # See what would be deleted, no changes made
    python -m db.scripts.clear_test_data --org "Acme Test Corp" --dry-run

    # Delete one or more named organizations (exact name match)
    python -m db.scripts.clear_test_data --org "Acme Test Corp" --org "Beta Test Inc"

    # Delete every organization in the database (asks for typed confirmation)
    python -m db.scripts.clear_test_data --all-orgs

    # Skip the confirmation prompt (e.g. for scripting/CI)
    python -m db.scripts.clear_test_data --all-orgs --yes

SuperUser and Staff rows are never touched by this script, by design
-- there's no flag to delete those, since re-bootstrapping your login
is more disruptive than useful during test-data cleanup.
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models import (
    AdminUser,
    Application,
    ApplicationStatus,
    Candidate,
    CandidateDocument,
    CandidateOperationalConfig,
    CandidateProfileSubmission,
    ClientSubmission,
    Email,
    EmailAccountCredential,
    FollowUp,
    Interview,
    Invite,
    Job,
    Organization,
    PendingAction,
    PushSubscription,
    ResumeIngestionRun,
    ResumeVersion,
    SkillInventoryItem,
    Subscription,
    SystemLog,
)
from db.session import get_session_factory


def _ids(session: Session, stmt) -> list[int]:
    return [row[0] for row in session.execute(stmt).all()]


def clear_organizations(session: Session, org_ids: list[int], dry_run: bool = False) -> dict[str, int]:
    """Deletes every row scoped to the given organization ids, in FK-safe
    order (children before parents). Returns a dict of table -> row count
    (the count of what was, or would be, deleted)."""
    if not org_ids:
        return {}

    counts: dict[str, int] = {}

    candidate_ids = _ids(session, select(Candidate.id).where(Candidate.organization_id.in_(org_ids)))
    admin_ids = _ids(session, select(AdminUser.id).where(AdminUser.organization_id.in_(org_ids)))
    job_ids = _ids(
        session,
        select(Job.id).where(
            Job.organization_id.in_(org_ids) | Job.candidate_id.in_(candidate_ids or [-1])
        ),
    )
    email_ids = _ids(
        session,
        select(Email.id).where(
            Email.job_id.in_(job_ids or [-1]) | Email.candidate_id.in_(candidate_ids or [-1])
        ),
    )
    application_ids = _ids(session, select(Application.id).where(Application.job_id.in_(job_ids or [-1])))

    # Order matters: each delete below only targets rows whose parent
    # (job/email/candidate/org) is about to disappear, and every delete
    # happens before that parent's own delete.
    plan = [
        ("interviews", delete(Interview).where(Interview.email_id.in_(email_ids or [-1]))),
        (
            "follow_ups",
            delete(FollowUp).where(
                FollowUp.organization_id.in_(org_ids)
                | FollowUp.job_id.in_(job_ids or [-1])
                | FollowUp.email_id.in_(email_ids or [-1])
            ),
        ),
        (
            "client_submissions",
            delete(ClientSubmission).where(
                ClientSubmission.candidate_id.in_(candidate_ids or [-1])
                | ClientSubmission.email_id.in_(email_ids or [-1])
            ),
        ),
        ("application_status", delete(ApplicationStatus).where(ApplicationStatus.job_id.in_(job_ids or [-1]))),
        (
            "pending_actions (applications)",
            delete(PendingAction).where(
                (PendingAction.reference_table == "applications") & (PendingAction.reference_id.in_(application_ids or [-1]))
            ),
        ),
        (
            "pending_actions (emails)",
            delete(PendingAction).where(
                (PendingAction.reference_table == "emails") & (PendingAction.reference_id.in_(email_ids or [-1]))
            ),
        ),
        ("applications", delete(Application).where(Application.job_id.in_(job_ids or [-1]))),
        ("system_logs", delete(SystemLog).where(SystemLog.job_id.in_(job_ids or [-1]))),
        (
            "resume_versions",
            delete(ResumeVersion).where(
                ResumeVersion.job_id.in_(job_ids or [-1]) | ResumeVersion.candidate_id.in_(candidate_ids or [-1])
            ),
        ),
        ("emails", delete(Email).where(Email.id.in_(email_ids or [-1]))),
        ("jobs", delete(Job).where(Job.id.in_(job_ids or [-1]))),
        ("skill_inventory_items", delete(SkillInventoryItem).where(SkillInventoryItem.candidate_id.in_(candidate_ids or [-1]))),
        ("resume_ingestion_runs", delete(ResumeIngestionRun).where(ResumeIngestionRun.candidate_id.in_(candidate_ids or [-1]))),
        ("candidate_documents", delete(CandidateDocument).where(CandidateDocument.candidate_id.in_(candidate_ids or [-1]))),
        (
            "candidate_operational_configs",
            delete(CandidateOperationalConfig).where(CandidateOperationalConfig.candidate_id.in_(candidate_ids or [-1])),
        ),
        (
            "candidate_profile_submissions",
            delete(CandidateProfileSubmission).where(CandidateProfileSubmission.candidate_id.in_(candidate_ids or [-1])),
        ),
        ("email_account_credentials", delete(EmailAccountCredential).where(EmailAccountCredential.candidate_id.in_(candidate_ids or [-1]))),
        (
            "push_subscriptions (candidate)",
            delete(PushSubscription).where(
                (PushSubscription.owner_type == "candidate") & (PushSubscription.owner_id.in_(candidate_ids or [-1]))
            ),
        ),
        (
            "push_subscriptions (admin)",
            delete(PushSubscription).where(
                (PushSubscription.owner_type == "admin") & (PushSubscription.owner_id.in_(admin_ids or [-1]))
            ),
        ),
        ("subscriptions", delete(Subscription).where(Subscription.candidate_id.in_(candidate_ids or [-1]))),
        ("admin_users", delete(AdminUser).where(AdminUser.organization_id.in_(org_ids))),
        ("invites", delete(Invite).where(Invite.organization_id.in_(org_ids))),
        ("candidates", delete(Candidate).where(Candidate.id.in_(candidate_ids or [-1]))),
        ("organizations", delete(Organization).where(Organization.id.in_(org_ids))),
    ]

    for label, stmt in plan:
        if dry_run:
            # Build an equivalent SELECT count() for dry-run reporting
            # without touching the DB.
            count_stmt = select(stmt.table).where(stmt.whereclause) if stmt.whereclause is not None else select(stmt.table)
            counts[label] = len(session.execute(count_stmt).all())
        else:
            result = session.execute(stmt)
            counts[label] = result.rowcount

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear test organizations and their data")
    parser.add_argument("--org", action="append", default=[], help="Exact organization name to clear (repeatable)")
    parser.add_argument("--all-orgs", action="store_true", help="Clear every organization in the database")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be deleted, make no changes")
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation prompt")
    args = parser.parse_args()

    if not args.org and not args.all_orgs:
        raise SystemExit("Specify --org \"Exact Name\" (repeatable) or --all-orgs.")

    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        if args.all_orgs:
            orgs = session.execute(select(Organization.id, Organization.name)).all()
        else:
            orgs = session.execute(
                select(Organization.id, Organization.name).where(Organization.name.in_(args.org))
            ).all()
            found_names = {name for _, name in orgs}
            missing = set(args.org) - found_names
            if missing:
                print(f"Warning: no organization found with name(s): {', '.join(sorted(missing))}")

        if not orgs:
            print("No matching organizations -- nothing to do.")
            return

        org_ids = [org_id for org_id, _ in orgs]
        org_names = [name for _, name in orgs]

        print(f"{'[DRY RUN] ' if args.dry_run else ''}Target organizations ({len(org_ids)}):")
        for name in org_names:
            print(f"  - {name}")

        if not args.dry_run and not args.yes:
            confirm = input(f"\nType 'delete {len(org_ids)}' to permanently delete these organizations and all their data: ")
            if confirm.strip() != f"delete {len(org_ids)}":
                raise SystemExit("Confirmation did not match -- aborted, nothing deleted.")

        counts = clear_organizations(session, org_ids, dry_run=args.dry_run)

        if not args.dry_run:
            session.commit()

        print(f"\n{'Would delete' if args.dry_run else 'Deleted'} (table: row count):")
        for label, count in counts.items():
            if count:
                print(f"  {label}: {count}")

        if args.dry_run:
            print("\nNo changes made (dry run). Re-run without --dry-run to actually delete.")
        else:
            print("\nDone. SuperUser and Staff accounts were not touched.")


if __name__ == "__main__":
    main()
