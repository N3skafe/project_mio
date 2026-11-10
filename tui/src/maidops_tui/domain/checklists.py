"""라벨별 점검 문구. 조언을 보여줄 뿐 확정 라벨이나 학습 점수가 아니다."""

from __future__ import annotations

from maidops_tui.domain.models import ErrorLabel

CHECKLISTS: dict[ErrorLabel, tuple[str, ...]] = {
    ErrorLabel.DB_CONNECTION: (
        "호스트와 포트가 기대한 데이터베이스를 가리키는지 확인합니다.",
        "계정, 비밀번호, 데이터베이스 이름이 맞는지 확인합니다.",
        "방화벽과 네트워크에서 해당 포트가 열리는지 확인합니다.",
        "커넥션 풀 한도와 대상 서버의 최대 연결 수를 확인합니다.",
    ),
    ErrorLabel.AUTH_PERMISSION: (
        "호출 주체에게 필요한 권한이 있는지 확인합니다.",
        "토큰 또는 세션이 만료되지 않았는지 확인합니다.",
        "403과 401 중 어느 응답인지 구분합니다.",
        "역할과 리소스 범위가 요청과 맞는지 확인합니다.",
    ),
    ErrorLabel.EXTERNAL_NETWORK: (
        "대상 호스트 이름과 DNS 조회 결과를 확인합니다.",
        "타임아웃과 재시도 한도를 확인합니다.",
        "프록시와 방화벽이 외부 주소를 막는지 확인합니다.",
        "대상 서비스의 상태와 인증서 기간을 확인합니다.",
    ),
    ErrorLabel.INPUT_VALIDATION: (
        "빠진 필수 필드와 형식 오류를 확인합니다.",
        "요청 본문과 스키마가 같은 버전인지 확인합니다.",
        "경계값과 빈 문자열이 거절되는지 확인합니다.",
        "클라이언트가 보낸 값과 서버가 읽은 값이 같은지 확인합니다.",
    ),
    ErrorLabel.OTHER: (
        "로그의 예외 종류와 종료 코드를 확인합니다.",
        "재현에 필요한 입력과 환경을 남깁니다.",
        "기존 다섯 라벨로 설명되지 않는 이유를 적습니다.",
        "원인과 해결을 확정하기 전에 추가 로그가 더 필요한지 확인합니다.",
    ),
}


def checklist_text(label: ErrorLabel | None, *, pending: bool) -> str:
    if pending or label is None:
        return "초안 대기 중에는 점검 목록을 라벨에 묶지 않습니다. 체크리스트는 확정 라벨이나 학습 점수가 아닙니다."
    lines = [f"점검 목록 ({label.value}). 조언이며 자동으로 고치지 않습니다."]
    lines.extend(f"- {item}" for item in CHECKLISTS[label])
    return "\n".join(lines)
