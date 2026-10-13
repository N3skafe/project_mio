# 남긴 자원

검증이 끝난 뒤 볼륨과 모델 파일은 지우지 않았다. 컨테이너는 `stop`만 했다.

## 컨테이너

| 이름 | 종료 상태 | 역할 |
| --- | --- | --- |
| `maidops-isolated-postgres-1` | Exited 0 | 격리 Postgres |
| `maidops-isolated-backend-1` | Exited 143 | 격리 API. 호스트 `127.0.0.1:18080` |
| `maidops-isolated-worker-1` | Exited 137 | `audit-worker-1` |
| `maidops-isolated-trainer-1` | Exited 137 | CPU trainer |
| `maidops-isolated-flyway-v6` | Exited 1 | V6까지만 적용한 일회성 앱. JPA 검증에서 종료 |
| `maidops-isolated-flyway-latest` | Exited 143 | 업그레이드 DB를 V8로 올린 일회성 앱 |

## 네트워크와 볼륨

- 네트워크: `maidops-isolated_default`
- 볼륨: `maidops-isolated_isolated-postgres`, `maidops-isolated_isolated-models`
- `container_name`과 external volume은 없다.
- 기존 `maidops-models` 볼륨은 쓰지 않았다.

## 데이터베이스

격리 서버 안에만 있다.

- `maidops_isolated`: 클러스터 기본 DB
- `maidops_live_audit`: 작업·학습·모델 검증 DB. schema version 8
- `maidops_upgrade_audit`: V6 fixture를 유지한 채 V8인 DB

## 워크스페이스

`infra/isolated/workspace/sample`

- 신뢰 샘플 `pass_check.py`, `fail_check.py`, `slow_check.py`, `lab_failures.py` 복사본
- 감사 추가: `tick_check.py`, `trim_check.py`, `flood_check.py`, `hang_check.py`, `tree_check.py`

바인드는 이 디렉터리만 읽기 전용으로 `/trusted`에 붙었다.

## 모델

볼륨 `maidops-isolated_isolated-models`:

- `mv-00000001.pt`
- `mv-00000001.meta.json`

`run-00000002`는 lease 만료로 `mv-00000002`를 예약만 했다. 그 파일은 쓰지 않았다.

## 프로세스

`tree_check.py`의 부모·자식·손자는 워커 컨테이너 안에서만 생겼다. 취소 후 그 프로세스는 없었다. 호스트 작업 목록에는 없었다.

## 삭제하지 않은 이유

볼륨을 지우려면 대상 목록을 따로 확인받아야 한다. 이번 종료에서는 지우지 않았다.
