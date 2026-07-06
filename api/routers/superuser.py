"""
Superuser: platform-wide, read-only reporting across every
organization. Deliberately scoped narrow for now -- login and reports
only. Creating organizations/admins/candidates from the superuser side
is the invite system, still deferred; this only covers "what's
everyone doing" visibility.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import authenticate_superuser, create_access_token, hash_password
from api.deps import get_current_superuser, get_db
from api.schemas import OrganizationSummary, PlatformSummary, TokenResponse
from db.models import AdminUser, Candidate, Email, Interview, Job, Organization, Staff, SuperUser
from services.rate_limit import check_not_locked, record_failure, record_success

router = APIRouter(tags=["superuser"])


@router.post("/api/superuser-auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    account_key = f"superuser:{form_data.username.strip().lower()}"
    check_not_locked(db, account_key)

    user = authenticate_superuser(db, form_data.username, form_data.password)
    if not user:
        record_failure(db, account_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    record_success(db, account_key)
    token = create_access_token(user.username, role="superuser")
    return TokenResponse(access_token=token)


@router.get("/api/superuser/reports/summary", response_model=PlatformSummary, dependencies=[Depends(get_current_superuser)])
def platform_summary(db: Session = Depends(get_db)):
    orgs = db.query(Organization).order_by(Organization.created_at.asc()).all()

    org_summaries = []
    total_candidates = 0
    total_jobs = 0
    total_sent = 0
    total_interviews = 0

    for org in orgs:
        candidate_count = db.query(Candidate).filter_by(organization_id=org.id).count()
        admin_count = db.query(AdminUser).filter_by(organization_id=org.id).count()
        jobs_posted = db.query(Job).filter_by(organization_id=org.id).count()

        applications_sent = (
            db.query(Email)
            .join(Candidate, Email.candidate_id == Candidate.id)
            .filter(Candidate.organization_id == org.id, Email.status.in_(("sent", "approved")))
            .count()
        )
        interviews_scheduled = (
            db.query(Interview)
            .join(Email, Interview.email_id == Email.id)
            .join(Candidate, Email.candidate_id == Candidate.id)
            .filter(Candidate.organization_id == org.id)
            .count()
        )

        org_summaries.append(
            OrganizationSummary(
                organization_id=org.id,
                organization_name=org.name,
                candidate_count=candidate_count,
                admin_count=admin_count,
                jobs_posted=jobs_posted,
                applications_sent=applications_sent,
                interviews_scheduled=interviews_scheduled,
                created_at=org.created_at,
            )
        )
        total_candidates += candidate_count
        total_jobs += jobs_posted
        total_sent += applications_sent
        total_interviews += interviews_scheduled

    return PlatformSummary(
        organization_count=len(orgs),
        total_candidates=total_candidates,
        total_jobs_posted=total_jobs,
        total_applications_sent=total_sent,
        total_interviews=total_interviews,
        organizations=org_summaries,
    )


class CreateStaffRequest(BaseModel):
    username: str
    password: str


class StaffResponse(BaseModel):
    id: int
    username: str
    is_active: bool


@router.post("/api/superuser/staff", response_model=StaffResponse, dependencies=[Depends(get_current_superuser)])
def create_staff(
    payload: CreateStaffRequest,
    db: Session = Depends(get_db),
    superuser: SuperUser = Depends(get_current_superuser),
):
    """Only a superuser can create staff -- no self-signup, same
    reasoning as superuser itself: staff can create organizations and
    invite admins into them, which is real platform-level trust."""
    if db.query(Staff).filter_by(username=payload.username).one_or_none():
        raise HTTPException(status_code=409, detail="A staff account with this username already exists.")
    if len(payload.password) < 10:
        raise HTTPException(status_code=422, detail="Password must be at least 10 characters.")

    staff = Staff(
        username=payload.username,
        password_hash=hash_password(payload.password),
        created_by_superuser_id=superuser.id,
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return StaffResponse(id=staff.id, username=staff.username, is_active=staff.is_active)


class StaffPerformance(BaseModel):
    staff_id: int
    username: str
    is_active: bool
    organizations_onboarded: int
    active_organizations: int
    total_candidates_across_orgs: int


@router.get(
    "/api/superuser/staff/performance",
    response_model=list[StaffPerformance],
    dependencies=[Depends(get_current_superuser)],
)
def staff_performance(db: Session = Depends(get_db)):
    """Sales-performance view: how many orgs each staff member has
    onboarded, and how much candidate activity those orgs represent --
    the basis for future revenue attribution per staff member."""
    results = []
    for staff in db.query(Staff).order_by(Staff.created_at.asc()).all():
        orgs = db.query(Organization).filter_by(created_by_staff_id=staff.id).all()
        candidate_total = sum(db.query(Candidate).filter_by(organization_id=o.id).count() for o in orgs)
        results.append(
            StaffPerformance(
                staff_id=staff.id,
                username=staff.username,
                is_active=staff.is_active,
                organizations_onboarded=len(orgs),
                active_organizations=sum(1 for o in orgs if o.is_active),
                total_candidates_across_orgs=candidate_total,
            )
        )
    return results
