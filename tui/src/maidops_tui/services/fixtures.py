"""PHASE 1 가상 데이터.

실행할 때마다 같은 내용을 쓴다. 세션 중에 이 상수를 수정하지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from maidops_tui.domain.models import (
    DataOrigin,
    ErrorLabel,
    Project,
    RegisteredTask,
    ResolutionRecord,
    VirtualOutcome,
)

PROJECTS: tuple[Project, ...] = (
    Project(
        id="demo-api",
        name="데모 API",
        summary="가상 API 모듈. 기본 시나리오는 데이터베이스 연결 실패입니다.",
        default_task_id="api-db-check",
    ),
    Project(
        id="demo-web",
        name="데모 Web",
        summary="가상 웹 모듈. 기본 시나리오는 상태 점검 성공입니다.",
        default_task_id="web-health",
    ),
)

TASKS: dict[str, RegisteredTask] = {
    "api-db-check": RegisteredTask(
        id="api-db-check",
        project_id="demo-api",
        name="가상 DB 연결 점검",
        plan_text="등록된 가상 시나리오 api-db-check를 재생합니다. 프로세스를 시작하지 않습니다.",
        outcome=VirtualOutcome.FAIL,
        draft_label=ErrorLabel.DB_CONNECTION,
        output_lines=(
            "demo-runner: start virtual scenario api-db-check",
            "virtual socket 127.0.0.1:5432 refused the session",
            "ERROR could not open the virtual database session",
            "demo-runner: scenario finished with a failure",
        ),
    ),
    "web-health": RegisteredTask(
        id="web-health",
        project_id="demo-web",
        name="가상 상태 점검",
        plan_text="등록된 가상 시나리오 web-health를 재생합니다. 프로세스를 시작하지 않습니다.",
        outcome=VirtualOutcome.PASS,
        draft_label=None,
        output_lines=(
            "demo-runner: start virtual scenario web-health",
            "virtual health check returned ok",
            "virtual config shape check returned ok",
            "demo-runner: scenario finished",
        ),
    ),
}

_FIXED_TIME = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)


def _resolution(
    record_id: str,
    case_id: str,
    label: ErrorLabel,
    cause: str,
    method: str,
) -> ResolutionRecord:
    return ResolutionRecord(
        id=record_id,
        error_case_id=case_id,
        project_id="demo-api",
        label=label,
        cause=cause,
        method=method,
        origin=DataOrigin.FIXTURE,
        created_at=_FIXED_TIME,
    )


SEED_RESOLUTIONS: tuple[ResolutionRecord, ...] = (
    _resolution(
        "fixture-resolution-db",
        "fixture-case-db",
        ErrorLabel.DB_CONNECTION,
        "가상 사례: PostgreSQL 소켓이 연결을 거부했습니다.",
        "가상 해결: 5432 포트와 데이터베이스 기동 상태를 확인합니다.",
    ),
    _resolution(
        "fixture-resolution-auth",
        "fixture-case-auth",
        ErrorLabel.AUTH_PERMISSION,
        "가상 사례: 토큰이 없어 403 응답을 받았습니다.",
        "가상 해결: 요청 권한과 토큰 발급 절차를 확인합니다.",
    ),
    _resolution(
        "fixture-resolution-network",
        "fixture-case-network",
        ErrorLabel.EXTERNAL_NETWORK,
        "가상 사례: api.example.invalid 호출이 시간 초과되었습니다.",
        "가상 해결: 외부 주소와 타임아웃 설정을 확인합니다.",
    ),
    _resolution(
        "fixture-resolution-input",
        "fixture-case-input",
        ErrorLabel.INPUT_VALIDATION,
        "가상 사례: email 필드가 없어 입력 검증에 실패했습니다.",
        "가상 해결: 필수 필드 email의 형식과 존재 여부를 확인합니다.",
    ),
    _resolution(
        "fixture-resolution-other",
        "fixture-case-other",
        ErrorLabel.OTHER,
        "가상 사례: 작업 디스크가 가득 찬 상태로 기록에 실패했습니다.",
        "가상 해결: 디스크 여유 공간을 확보한 뒤 다시 기록합니다.",
    ),
)
