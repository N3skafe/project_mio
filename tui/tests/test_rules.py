"""규칙 기반 초안. 미검토 초안은 확정 라벨이 아니다."""

from __future__ import annotations

from datetime import datetime, timezone

from maidops_tui.domain.display import summarize_cases
from maidops_tui.domain.models import (
    DataOrigin,
    ErrorCase,
    ErrorLabel,
    LabelRevision,
    LabelSource,
    ReviewStatus,
)
from maidops_tui.domain.rules import RULE_VERSION, classify_failure


def test_rules_cover_the_five_labels_without_a_score() -> None:
    assert classify_failure("permission denied for user").label is ErrorLabel.AUTH_PERMISSION
    assert classify_failure("status 403 from the api").matched_keyword == "403"
    database = classify_failure("org.postgresql.util.PSQLException: Connection to localhost:5432 refused")
    assert database.label is ErrorLabel.DB_CONNECTION
    assert database.matched_keyword == "postgresql"
    assert database.rule_version == RULE_VERSION
    validation = classify_failure("Validation failed: required field email is missing")
    assert validation.label is ErrorLabel.INPUT_VALIDATION
    assert validation.matched_keyword == "required field"
    network = classify_failure("Temporary failure in name resolution while calling https://api.example.invalid")
    assert network.label is ErrorLabel.EXTERNAL_NETWORK
    other = classify_failure("boom")
    assert other.label is ErrorLabel.OTHER
    assert other.matched_keyword is None
    assert not hasattr(other, "score")


def test_earlier_category_wins_and_embedded_digits_do_not_match() -> None:
    mixed = classify_failure("permission denied while opening the database")
    assert mixed.label is ErrorLabel.AUTH_PERMISSION
    assert classify_failure("code 14013 boom").label is ErrorLabel.OTHER


def test_unreviewed_rule_draft_is_not_a_confirmed_label() -> None:
    draft = classify_failure("org.postgresql.util.PSQLException: Connection to localhost:5432 refused")
    case = ErrorCase(
        id="case-rule",
        job_id="job-rule",
        project_id="trusted-sample",
        raw_text="connection text",
        draft_label=draft.label,
        draft_source=LabelSource.RULE_BASED,
        current_label=draft.label,
        review_status=ReviewStatus.DRAFT,
        revisions=[
            LabelRevision(
                at=datetime(2026, 10, 6, tzinfo=timezone.utc),
                label=draft.label,
                review_status=ReviewStatus.DRAFT,
                source=LabelSource.RULE_BASED,
                note="규칙 기반 초안",
            )
        ],
        origin=DataOrigin.SESSION,
        rule_version=draft.rule_version,
        matched_keyword=draft.matched_keyword,
    )
    assert case.confirmed_label is None
    assert summarize_cases([case]).confirmed == 0
    case.review_status = ReviewStatus.DEFERRED
    assert case.confirmed_label is None
    assert summarize_cases([case]).confirmed == 0
    case.review_status = ReviewStatus.REVISED
    case.current_label = ErrorLabel.OTHER
    assert case.confirmed_label is ErrorLabel.OTHER
    assert case.draft_label is ErrorLabel.DB_CONNECTION
    assert summarize_cases([case]).confirmed == 1
