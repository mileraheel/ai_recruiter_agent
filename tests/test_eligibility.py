import pytest

from config.schema import CandidateConfig, SearchConfig
from core.eligibility import evaluate_eligibility, EligibilityStatus


@pytest.fixture
def candidate() -> CandidateConfig:
    return CandidateConfig(
        full_name="Raheel Ahmed Khan",
        email="raheel@example.com",
        phone="555-555-5555",
        location="Virginia",
        base_resume_path="resumes/master_resume.docx",
        work_authorization="H1B",
        requires_sponsorship_or_transfer=True,
        c2c_allowed=True,
        w2_allowed=False,
        contract_allowed=True,
        contract_to_hire_allowed=True,
        full_time_allowed=False,
        has_security_clearance=False,
        public_trust_available=False,
        willing_to_work_remote=True,
        willing_to_work_hybrid=True,
        willing_to_work_onsite=False,
    )


@pytest.fixture
def search() -> SearchConfig:
    return SearchConfig(
        locations=["Remote", "Virginia", "New Jersey", "New York"],
        work_mode=["remote", "hybrid"],
    )


def test_skips_us_citizen_only(candidate, search):
    result = evaluate_eligibility(
        "This role requires US Citizen only due to client requirements.",
        candidate, search,
    )
    assert result.status == EligibilityStatus.SKIPPED
    assert "citizenship" in result.reason.lower() or "sponsorship" in result.reason.lower()


def test_skips_no_sponsorship(candidate, search):
    result = evaluate_eligibility(
        "We are unable to sponsor visas for this position.",
        candidate, search,
    )
    assert result.status == EligibilityStatus.SKIPPED


def test_skips_green_card_only(candidate, search):
    result = evaluate_eligibility(
        "Candidates must be Green Card only, no exceptions.",
        candidate, search,
    )
    assert result.status == EligibilityStatus.SKIPPED


def test_skips_w2_only_when_not_allowed(candidate, search):
    result = evaluate_eligibility(
        "Compensation is W2 only, we do not work with C2C vendors.",
        candidate, search,
    )
    assert result.status == EligibilityStatus.SKIPPED
    assert "w2" in result.reason.lower() or "c2c" in result.reason.lower()


def test_skips_no_c2c(candidate, search):
    result = evaluate_eligibility(
        "Direct candidates only, no third-party candidates please.",
        candidate, search,
    )
    assert result.status == EligibilityStatus.SKIPPED


def test_skips_security_clearance_required(candidate, search):
    result = evaluate_eligibility(
        "Active security clearance required for this federal engagement.",
        candidate, search,
    )
    assert result.status == EligibilityStatus.SKIPPED
    assert "clearance" in result.reason.lower()


def test_skips_onsite_only(candidate, search):
    result = evaluate_eligibility(
        "This is an onsite only role, no remote work permitted.",
        candidate, search,
        job_work_mode="onsite",
    )
    assert result.status == EligibilityStatus.SKIPPED
    assert "onsite" in result.reason.lower()


def test_keeps_hybrid_when_location_matches(candidate, search):
    result = evaluate_eligibility(
        "Hybrid role, 2 days a week in office. Strong Java and Spring Boot background needed.",
        candidate, search,
        job_location="Virginia",
        job_work_mode="hybrid",
    )
    assert result.status == EligibilityStatus.ELIGIBLE


def test_skips_hybrid_when_location_does_not_match(candidate, search):
    result = evaluate_eligibility(
        "Hybrid role based in Austin, Texas office.",
        candidate, search,
        job_location="Austin, Texas",
        job_work_mode="hybrid",
    )
    assert result.status == EligibilityStatus.SKIPPED
    assert "location" in result.reason.lower()


def test_eligible_clean_job(candidate, search):
    result = evaluate_eligibility(
        "Seeking a Senior Java Developer with Spring Boot and Kafka experience. "
        "Remote, contract, C2C accepted.",
        candidate, search,
        job_location="Remote",
        job_work_mode="remote",
    )
    assert result.status == EligibilityStatus.ELIGIBLE
    assert result.reason is None


def test_needs_human_review_when_local_only_but_location_unknown(candidate, search):
    result = evaluate_eligibility(
        "Local candidates only for this role.",
        candidate, search,
        job_location=None,
        job_work_mode=None,
    )
    assert result.status == EligibilityStatus.NEEDS_HUMAN_REVIEW


def test_public_trust_skipped_when_unavailable(candidate, search):
    result = evaluate_eligibility(
        "Public trust required prior to start date.",
        candidate, search,
    )
    assert result.status == EligibilityStatus.SKIPPED
    assert "public trust" in result.reason.lower()


def test_public_trust_not_skipped_when_available():
    cand = CandidateConfig(
        full_name="Test User", email="t@example.com", phone="555", location="VA",
        base_resume_path="x.docx", work_authorization="H1B",
        requires_sponsorship_or_transfer=True, c2c_allowed=True, w2_allowed=False,
        contract_allowed=True, contract_to_hire_allowed=True, full_time_allowed=False,
        has_security_clearance=False, public_trust_available=True,
        willing_to_work_remote=True, willing_to_work_hybrid=True, willing_to_work_onsite=False,
    )
    search = SearchConfig(locations=["Remote"])
    result = evaluate_eligibility(
        "Public trust required prior to start date. Java and Spring Boot needed.",
        cand, search, job_location="Remote", job_work_mode="remote",
    )
    assert result.status == EligibilityStatus.ELIGIBLE


def test_config_driven_excluded_keyword_not_covered_by_regex_bank(candidate):
    # A phrase that isn't in any hardcoded regex pattern, only in the
    # config's excluded_keywords list -- proves the fallback layer works
    # without requiring a code change for new exclusion phrases.
    search = SearchConfig(
        locations=["Remote"],
        excluded_keywords=["must relocate immediately upon offer"],
    )
    result = evaluate_eligibility(
        "Great Java Spring Boot role. Candidate must relocate immediately upon offer.",
        candidate, search, job_location="Remote", job_work_mode="remote",
    )
    assert result.status == EligibilityStatus.SKIPPED
    assert "must relocate immediately upon offer" in result.reason.lower()


def test_categorized_reason_preferred_over_generic_when_both_match(candidate):
    # "no sponsorship" is both a categorized pattern and could be listed
    # verbatim in excluded_keywords -- categorized reason should win.
    search = SearchConfig(
        locations=["Remote"],
        excluded_keywords=["no sponsorship"],
    )
    result = evaluate_eligibility(
        "This role offers no sponsorship for any candidates.",
        candidate, search, job_location="Remote", job_work_mode="remote",
    )
    assert result.status == EligibilityStatus.SKIPPED
    assert "sponsorship" in result.reason.lower()
    assert "excluded keyword" not in result.reason.lower()


@pytest.mark.parametrize("phrase", [
    "This position requires an active security clearance.",
    "Candidate must possess a current security clearance.",
    "Must have active DoD Secret clearance.",
    "Requires TS/SCI clearance.",
    "US Government security clearance needed.",
])
def test_skips_real_world_clearance_phrasing_variants(candidate, search, phrase):
    # Regression coverage: the original hardcoded patterns only matched
    # rigid phrasings like "security clearance required" and missed all
    # of these common real-world variants, letting clearance-required
    # jobs through as eligible.
    result = evaluate_eligibility(phrase, candidate, search, job_location="Remote", job_work_mode="remote")
    assert result.status == EligibilityStatus.SKIPPED, f"Failed to skip: {phrase}"


@pytest.mark.parametrize("phrase", [
    "Great Java Spring Boot contract role, remote, C2C accepted, no clearance needed.",
    "No security clearance required. Remote Java Spring Boot role.",
])
def test_negated_clearance_language_stays_eligible(candidate, search, phrase):
    # Regression coverage: proximity-based matching (needed to catch the
    # variants above) can over-match negated phrasing like "no clearance
    # required" unless explicitly guarded against.
    result = evaluate_eligibility(phrase, candidate, search, job_location="Remote", job_work_mode="remote")
    assert result.status == EligibilityStatus.ELIGIBLE, f"Incorrectly skipped: {phrase}"


def test_negated_clearance_phrase_in_excluded_keywords_list_stays_eligible(candidate):
    # Regression coverage: the config-driven excluded_keywords fallback
    # does substring matching, which -- without a negation guard -- would
    # match "security clearance required" inside "No security clearance
    # required" and incorrectly skip the job.
    search = SearchConfig(
        locations=["Remote"],
        excluded_keywords=["Security clearance required"],
    )
    result = evaluate_eligibility(
        "No security clearance required. Remote Java Spring Boot role.",
        candidate, search, job_location="Remote", job_work_mode="remote",
    )
    assert result.status == EligibilityStatus.ELIGIBLE


def test_skips_independent_visa_only(candidate, search):
    # Staffing-industry jargon: "Independent Visa Only" excludes H1B
    # candidates (who require sponsorship/transfer) without using the
    # word "sponsorship" directly.
    result = evaluate_eligibility(
        "Visa: Independent Visa Only. H4 EAD Candidates must be Local. "
        "Java, Spring Boot, Hibernate role.",
        candidate, search, job_location="Mountain View, CA", job_work_mode="hybrid",
    )
    assert result.status == EligibilityStatus.SKIPPED
