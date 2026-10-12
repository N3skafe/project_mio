"""도움말과 명령 예시. 파서와 화면이 같은 목록을 쓴다."""

from __future__ import annotations

COMMAND_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("/help", "명령과 단축키를 보여 줍니다."),
    ("/project list", "등록된 가상 프로젝트를 보여 줍니다."),
    ("/project select demo-api", "프로젝트를 선택합니다."),
    ("/test", "DEMO는 가상 시나리오를 재생하고, LIVE는 대기 작업만 저장합니다."),
    ("/jobs", "이번 세션의 작업을 보여 줍니다."),
    ("/cancel job-0001", "실행 중인 가상 작업을 취소합니다."),
    ("/review", "Review 화면으로 이동합니다."),
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


def help_lines() -> list[str]:
    lines = [
        "MaidOps Lab 도움말",
        "DEMO는 가상 이벤트입니다. LIVE는 백엔드에 작업을 저장하지만, 실행 워커가 없으면 QUEUED로 남습니다.",
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
            "Lab 학습은 LIVE의 확정 라벨이 조건을 만족할 때만 시작합니다. DEMO에서는 점수를 만들지 않습니다.",
            "의미 검색과 외부 LLM은 없습니다.",
        ]
    )
    return lines
