"""도움말과 명령 예시. 파서와 화면이 같은 목록을 쓴다."""

from __future__ import annotations

COMMAND_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("/help", "명령과 단축키를 보여 줍니다."),
    ("/project list", "등록된 프로젝트를 보여 줍니다."),
    ("/project select demo-api", "프로젝트를 선택합니다."),
    ("/project add my-api 내 API", "LIVE에서 신뢰 workspace의 프로젝트를 등록합니다."),
    ("/task add my-check sample pass_check.py 10 통과 점검", "LIVE에서 {python} 스크립트 작업을 등록합니다."),
    (
        "/import-log trusted-sample Connection to localhost:5432 refused",
        "LIVE에서 실행 없이 실패 로그를 오류 사례로 가져옵니다.",
    ),
    ("/test", "DEMO는 가상 시나리오를 재생하고, LIVE는 대기 작업만 저장합니다."),
    ("/jobs", "이번 세션의 작업을 보여 줍니다."),
    ("/cancel job-0001", "실행 중인 가상 작업을 취소합니다."),
    ("/review", "Review 화면으로 이동합니다."),
    ("/similar Connection to localhost:5432 refused", "확정 기록과 해시 코사인으로 비슷한 실패를 찾습니다."),
    ("/advise case-0001", "선택한 오류 사례와 비슷한 확정 기록을 인용합니다."),
    ("/lab", "Lab 화면으로 이동합니다. DEMO에서는 학습하지 않습니다."),
    ("/history", "History 화면으로 이동합니다."),
    ("/quiet on", "캐릭터 대사만 숨깁니다."),
    ("/quiet off", "캐릭터 대사를 다시 보여 줍니다."),
)

SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("F1", "도움말"),
    ("F2", "Workspace"),
    ("F3", "Review"),
    ("F4", "Lab"),
    ("F5", "History"),
    ("Ctrl+L", "명령 입력창으로 포커스"),
    ("Ctrl+Q", "종료"),
)


def live_checklist_text(*, backend_url: str, worker: str, trainer: str) -> str:
    return "\n".join(
        [
            "첫 LIVE 체크리스트",
            f"백엔드: {backend_url}",
            f"worker: {worker}",
            f"trainer: {trainer}",
            "샘플: /project list  다음  /project select trusted-sample  다음  /test",
            "또는 /import-log trusted-sample Connection to localhost:5432 refused",
        ]
    )


def help_lines() -> list[str]:
    lines = [
        "MaidOps Lab 도움말",
        "DEMO는 가상 이벤트입니다. LIVE는 백엔드에 작업을 저장하지만, 실행 워커가 없으면 QUEUED로 남습니다.",
        "첫 LIVE 체크리스트: 백엔드 URL, worker와 trainer 연결, 샘플 1건.",
        "기동 예: .\\scripts\\run-live.ps1    점검 예: .\\scripts\\doctor-live.ps1",
        "샘플 예: /project list  다음  /project select trusted-sample  다음  /test",
        "가져오기 예: /import-log trusted-sample Connection to localhost:5432 refused",
        "백엔드만 켜면 worker와 trainer는 NOT_CONNECTED가 맞습니다. Compose 풀스택이면 둘 다 CONNECTED여야 합니다.",
        "세션 데이터는 프로그램을 종료하면 사라집니다.",
        "자연어는 해석하지 않습니다. 아래 명시적 명령만 동작합니다.",
        "",
        "명령",
    ]
    for example, description in COMMAND_EXAMPLES:
        lines.append(f"  {example}  {description}")
    lines.append("")
    lines.append("단축키")
    for key, description in SHORTCUTS:
        lines.append(f"  {key}  {description}")
    lines.extend(
        [
            "",
            "기본 프로젝트 demo-api는 가상 FAIL 시나리오입니다.",
            "PASS를 보려면 /project select demo-web 다음 /test 를 입력하세요.",
            "기본 모델이 없으면 실패 로그 초안은 규칙 기반(RULE_BASED)입니다. 기본 모델이 있으면 초안은 MODEL입니다.",
            "미검토 초안과 보류는 확정 라벨이 아닙니다. 라벨을 바꿔도 학습은 시작되지 않습니다.",
            "프로젝트 등록, 작업 등록, 실패 로그 가져오기는 LIVE에서만 사용할 수 있습니다.",
            "등록 명령은 workspace 안의 {python} 스크립트만 실행합니다. 임의 셸은 실행하지 않습니다.",
            "Lab 학습은 LIVE의 확정 라벨이 조건을 만족할 때만 시작합니다. DEMO에서는 점수를 만들지 않습니다.",
            "키워드 검색과 확정 기록의 해시 유사 검색을 함께 씁니다. 외부 LLM과 유료 임베딩 API는 없습니다.",
        ]
    )
    return lines
