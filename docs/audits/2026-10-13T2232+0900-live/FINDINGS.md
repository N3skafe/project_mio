# 발견

제품 코드는 고치지 않았다.

## F-L1 낮음: 보관 잘림 문구가 한 작업에 여러 번 남는다

- 상태: 관찰. 이번 검증의 보관 잘림 판정 자체는 통과다.
- 증거: `job-00000046`은 `SUCCEEDED`, `COMPLETED`, `output_truncated=true`, 이벤트 500이다. 그 안에 `[출력 잘림] 최근 500줄만 표시합니다.`가 6행 있다.
- 위치: `backend/src/main/java/lab/maidops/job/JobService.java`의 한도 초과 분기.
- 영향: 최근 500줄 안에 같은 안내가 반복된다. 작업 성공과 `OUTPUT_LIMIT_EXCEEDED`의 구분은 유지된다.
- 수정은 별도 승인 뒤에 한다.

## F-L2 정보: 추론이 연 checksum을 추론 기록에 남기지 않는다

- 상태: 한계. 왕복 실패는 아니다.
- 증거: `draft_inferences`에는 모델 id와 상태가 있고, 실제로 연 파일의 checksum 열은 없다.
- 이번 확인: `model_versions.checksum_sha256`, `/models/mv-00000001.pt`, `.meta.json`의 `checkpoint_sha256`이 모두 `b33e0c05ff218464e5e0c48db303d55285b3494209849f3d2a75b13a88939694`이고 초안은 `MODEL`/`READY`다.
- 제안: 추론 완료 시 그 checksum을 초안 기록에 한 열로 남기면 나중에 파일과 분리해서 볼 수 있다.

## F-L3 정보: lease 세대 토큰은 여전히 없다

- 상태: 기존 잔여. 이번 검증으로 새로 만든 결함이 아니다.
- 확인: 다른 `worker_id`는 409다. 만료로 `FAILED`가 된 작업에 같은 `audit-worker-1`이 heartbeat와 새 배치를 보내도 409이고, finish가 200을 돌려도 상태는 `FAILED`로 남는다.
- 이 결과만으로 세대 토큰이 있다고 말하지 않는다.

## 하지 않은 주입

- 감독 실패(`SUPERVISION_FAILED`)를 격리 워커에서 재현하지 않았다. BLOCKED.
- 실제 터미널 화면은 보지 않았다. BLOCKED.
