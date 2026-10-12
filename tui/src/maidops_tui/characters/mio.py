"""오리지널 고양이 수인 메이드의 표정과 대사.

기존 작품의 이름, 아트, 대사를 복제하지 않는다.
"""

from __future__ import annotations

from maidops_tui.domain.models import CharacterState

FACES: dict[CharacterState, str] = {
    CharacterState.IDLE: "^.^",
    CharacterState.WORKING: ">.<",
    CharacterState.NEEDS_REVIEW: "o.o",
    CharacterState.FAILED: "x.x",
    CharacterState.TRAINING: "-.o",
    CharacterState.REPORTING: "^.-",
    CharacterState.DISCONNECTED: "-.-",
}

DIALOGUES: dict[CharacterState, str] = {
    CharacterState.IDLE: "등록된 작업을 준비해 두었습니다.",
    CharacterState.WORKING: "테스트 출력을 확인하고 있어요.",
    CharacterState.NEEDS_REVIEW: "이 라벨은 확인이 필요합니다.",
    CharacterState.FAILED: "작업이 실패했습니다. 로그를 남겼어요.",
    CharacterState.TRAINING: "확정된 데이터로 학습하고 있습니다.",
    CharacterState.REPORTING: "평가 결과를 확인해 주세요.",
    CharacterState.DISCONNECTED: "백엔드에 연결되지 않았습니다.",
}


def portrait(state: CharacterState) -> str:
    face = FACES[state]
    return "\n".join(
        [
            r"  /\_/\  ",
            f" ( {face} ) ",
            r"  > ^ <  ",
            r" /|___|\ ",
            r"  |:::|  ",
            r" /|   |\ ",
        ]
    )


def dialogue_for(state: CharacterState) -> str:
    return DIALOGUES[state]
