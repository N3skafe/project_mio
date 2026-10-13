"""URI와 기존 토큰 마스킹. 여기의 비밀번호는 전부 가짜다."""

from __future__ import annotations

from maidops_worker.masking import mask_secrets

_SAMPLE = "sample-pw"


def test_basic_uri_password_is_removed() -> None:
    raw = f"postgresql://app:{_SAMPLE}@127.0.0.1:5432/maidops"
    masked = mask_secrets(raw)
    assert _SAMPLE not in masked
    assert "postgresql://app:[REDACTED]@127.0.0.1:5432/maidops" == masked


def test_percent_encoded_password_is_removed() -> None:
    raw = "postgresql://app:p%40ss@db.internal/maidops"
    masked = mask_secrets(raw)
    assert "p%40ss" not in masked
    assert "postgresql://app:[REDACTED]@db.internal/maidops" == masked


def test_jdbc_userinfo_and_several_uris_on_one_line() -> None:
    raw = (
        "jdbc:postgresql://app:left-pw@db/one "
        "failed; see postgres://ro:right-pw@db/two"
    )
    masked = mask_secrets(raw)
    assert "left-pw" not in masked
    assert "right-pw" not in masked
    assert "jdbc:postgresql://app:[REDACTED]@db/one" in masked
    assert "postgres://ro:[REDACTED]@db/two" in masked


def test_assignment_and_uri_together() -> None:
    raw = f"token=abc.def postgresql://app:{_SAMPLE}@db/maidops"
    masked = mask_secrets(raw)
    assert "abc.def" not in masked
    assert _SAMPLE not in masked
    assert "token=[REDACTED]" in masked
    assert "postgresql://app:[REDACTED]@db/maidops" in masked


def test_passwordless_uri_and_plain_url_stay() -> None:
    database = "postgresql://127.0.0.1:5432/maidops"
    site = "https://example.com/docs"
    user_only = "https://reader@example.com/docs"
    assert mask_secrets(database) == database
    assert mask_secrets(site) == site
    assert mask_secrets(user_only) == user_only


def test_existing_token_and_bearer_patterns() -> None:
    assert mask_secrets("token=abc.def password = hunter2") == "token=[REDACTED] password = [REDACTED]"
    assert "secret-value" not in mask_secrets("Authorization Bearer secret-value")


def test_masking_twice_is_stable() -> None:
    raw = f"연결 실패 postgresql://app:{_SAMPLE}@db/maidops token=abc"
    once = mask_secrets(raw)
    twice = mask_secrets(once)
    assert once == twice
    assert _SAMPLE not in twice
    assert "연결 실패" in twice


def test_korean_and_symbols_around_the_secret_remain() -> None:
    raw = f"오류(한글): postgresql://앱:{_SAMPLE}@호스트/db — 끝"
    masked = mask_secrets(raw)
    assert _SAMPLE not in masked
    assert masked.startswith("오류(한글): ")
    assert masked.endswith(" — 끝")


def test_exception_text_containing_a_uri_can_be_masked() -> None:
    message = f"httpx.ConnectError: postgresql://app:{_SAMPLE}@127.0.0.1/db"
    assert _SAMPLE not in mask_secrets(message)
