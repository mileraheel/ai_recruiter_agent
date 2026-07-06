import pytest

from config.schema import SearchConfig
from core.role_match import evaluate_skill_match


@pytest.fixture
def java_search() -> SearchConfig:
    return SearchConfig(required_keywords=["Java"])


def test_matches_when_required_keyword_present(java_search):
    result = evaluate_skill_match("Senior Java Developer, Spring Boot, Kafka.", java_search)
    assert result.matched is True


def test_skips_when_required_keyword_absent(java_search):
    result = evaluate_skill_match("Senior .NET Developer with C# and Azure experience.", java_search)
    assert result.matched is False
    assert "Java" in result.missing_required_keywords


def test_negated_mention_does_not_count_as_match(java_search):
    """'No Java experience required' contains the substring 'Java' but
    should NOT count as a match -- this is the exact failure mode that
    would otherwise let a .NET job slip through a Java candidate's gate."""
    result = evaluate_skill_match(
        "Senior .NET Developer. No Java experience required.", java_search
    )
    assert result.matched is False


def test_strict_flag_disabled_skips_the_check_entirely(java_search):
    result = evaluate_skill_match(
        "Senior .NET Developer with C# and Azure experience.",
        java_search,
        strict_skill_match_required=False,
    )
    assert result.matched is True


def test_no_required_keywords_configured_defaults_to_match():
    empty_search = SearchConfig()
    result = evaluate_skill_match("Any job description at all.", empty_search)
    assert result.matched is True


def test_multiple_required_keywords_all_must_be_present():
    search = SearchConfig(required_keywords=["Java", "Kafka"])
    result = evaluate_skill_match("Senior Java Developer, Spring Boot.", search)
    assert result.matched is False
    assert result.missing_required_keywords == ["Kafka"]
