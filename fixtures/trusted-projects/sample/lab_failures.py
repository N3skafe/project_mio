"""신뢰 샘플의 등록 실패 시나리오.

argv의 두 번째 값은 서버에 등록된 시나리오 이름이다. 사용자 입력을 셸로 실행하지 않는다.
같은 문장은 학습 분할에서 한 그룹이 되므로, 시나리오마다 서로 다른 문장을 남긴다.
"""

from __future__ import annotations

import sys

SCENARIOS: dict[str, dict[str, str]] = {
    "harbor": {
        "label": "DB_CONNECTION",
        "name": "결제 저장소 연결 실패",
        "plan": "결제 서비스가 postgres 주 저장소에 접속하지 못하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "checkout-service harbor: opening the order store",
                "org.postgresql.util.PSQLException: connection to the harbor primary failed",
                "jdbc url uses the database harbor_checkout",
                "the session ended before the first query",
            ]
        ),
    },
    "ledger": {
        "label": "DB_CONNECTION",
        "name": "정산 풀 고갈",
        "plan": "정산 작업이 jdbc 풀에서 postgres 연결을 받지 못하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "billing-ledger: waiting for a pooled connection",
                "HikariPool ledger exhausted",
                "postgres backend rejected the new database session",
                "no jdbc connection became available",
            ]
        ),
    },
    "kiln": {
        "label": "DB_CONNECTION",
        "name": "카탈로그 SQLSTATE",
        "plan": "카탈로그 준비 중 postgres가 SQLSTATE를 반환하고 끊기는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "catalog-kiln: warming product rows",
                "SQLSTATE 08006 from the kiln database",
                "server closed the connection unexpectedly",
                "retrying the jdbc session did not help",
            ]
        ),
    },
    "maple": {
        "label": "DB_CONNECTION",
        "name": "이전 작업 접속 실패",
        "plan": "스키마 이전이 postgresql에 도달하지 못하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "migrator maple: applying pending revisions",
                "could not connect to postgresql",
                "the maple database refused the migration session",
                "flyway stopped on the first statement",
            ]
        ),
    },
    "orchid": {
        "label": "DB_CONNECTION",
        "name": "복제본 세션 단절",
        "plan": "조회 복제본과의 database 세션이 중간에 끊기는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "reader-orchid: selecting recent invoices",
                "the orchid database closed the replica session",
                "postgres reported the backend process was gone",
                "the read query was aborted",
            ]
        ),
    },
    "quartz": {
        "label": "DB_CONNECTION",
        "name": "준비 상태 저장소 실패",
        "plan": "준비 상태 검사가 postgres 백엔드에 닿지 못하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "readiness-quartz: probing the store",
                "postgres is not accepting connections for quartz",
                "database startup has not finished",
                "the probe marked the instance down",
            ]
        ),
    },
    "ridge": {
        "label": "DB_CONNECTION",
        "name": "백업 클러스터 접속 실패",
        "plan": "백업 작업이 database 클러스터에 붙지 못하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "backup-ridge: opening the cluster",
                "could not attach to the ridge database",
                "pg_basebackup lost the postgresql stream",
                "the backup file was not created",
            ]
        ),
    },
    "saffron": {
        "label": "DB_CONNECTION",
        "name": "스키마 검사 세션 손실",
        "plan": "스키마 검사가 jdbc 세션을 잃는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "schema-saffron: comparing expected tables",
                "the jdbc session to saffron dropped",
                "database metadata query returned no rows",
                "the check aborted",
            ]
        ),
    },
    "talon": {
        "label": "DB_CONNECTION",
        "name": "주문 트랜잭션 중단",
        "plan": "주문 트랜잭션 도중 database가 재시작해 롤백되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "orders-talon: committing the reservation",
                "the talon database restarted during the transaction",
                "postgres rolled the unit of work back",
                "the reservation was not stored",
            ]
        ),
    },
    "willow": {
        "label": "DB_CONNECTION",
        "name": "감사 로그 저장 실패",
        "plan": "감사 로그를 남기는 jdbc 쓰기가 database에서 실패하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "audit-willow: appending the change record",
                "jdbc batch for the willow database failed",
                "postgresql ended the write transaction",
                "the audit row is missing",
            ]
        ),
    },
    "violet": {
        "label": "AUTH_PERMISSION",
        "name": "저장소 권한 거부",
        "plan": "배포 계정이 산출물 저장소에서 permission denied를 받는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "publisher-violet: uploading the build artifact",
                "permission denied for the violet release bucket",
                "the service account is not on the writer list",
                "the upload stopped",
            ]
        ),
    },
    "walnut": {
        "label": "AUTH_PERMISSION",
        "name": "관리 API 인증 실패",
        "plan": "관리 API가 authentication failed를 반환하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "admin-walnut: calling the member endpoint",
                "authentication failed for the walnut operator",
                "the presented credential was rejected",
                "the call returned without a body",
            ]
        ),
    },
    "xenon": {
        "label": "AUTH_PERMISSION",
        "name": "토큰 없는 조회",
        "plan": "만료된 자격으로 unauthorized가 반환되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "reader-xenon: loading the private report",
                "unauthorized response from the xenon gateway",
                "the bearer token is no longer accepted",
                "the report was not loaded",
            ]
        ),
    },
    "yellow": {
        "label": "AUTH_PERMISSION",
        "name": "역할 없는 삭제",
        "plan": "삭제 역할이 없어 not authorized가 되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "cleanup-yellow: removing an expired draft",
                "not authorized to delete yellow records",
                "the role binding does not include erase",
                "the draft remains",
            ]
        ),
    },
    "zircon": {
        "label": "AUTH_PERMISSION",
        "name": "금지된 설정 변경",
        "plan": "설정 변경이 forbidden으로 막히는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "settings-zircon: updating the retention window",
                "forbidden by the zircon policy",
                "only the owner role may change retention",
                "the previous window is unchanged",
            ]
        ),
    },
    "amber": {
        "label": "AUTH_PERMISSION",
        "name": "파일 권한 비트",
        "plan": "로그 디렉터리 쓰기가 eacces로 실패하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "shipper-amber: rotating the local log",
                "eacces while creating the amber archive",
                "the process user cannot write that directory",
                "rotation aborted",
            ]
        ),
    },
    "bison": {
        "label": "AUTH_PERMISSION",
        "name": "접근 거부된 비밀",
        "plan": "비밀 저장소가 access denied를 반환하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "secrets-bison: reading the signing key",
                "access denied by the bison vault",
                "the workload identity is outside the policy",
                "the key was not returned",
            ]
        ),
    },
    "cedar": {
        "label": "AUTH_PERMISSION",
        "name": "상태 코드 인증 실패",
        "plan": "파트너 API가 401을 반환하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "partner-cedar: refreshing the session",
                "status 401 from the cedar identity provider",
                "the client secret does not match",
                "no session cookie was issued",
            ]
        ),
    },
    "delta": {
        "label": "AUTH_PERMISSION",
        "name": "상태 코드 권한 부족",
        "plan": "내부 API가 403을 반환하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "gateway-delta: forwarding the export",
                "status 403 from the delta export route",
                "the caller lacks the export role",
                "the file was not generated",
            ]
        ),
    },
    "ember": {
        "label": "AUTH_PERMISSION",
        "name": "소유자만 가능한 잠금",
        "plan": "잠금 해제가 permission denied로 끝나는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "locker-ember: releasing a stale lock",
                "permission denied for the ember lock owner",
                "another account holds the lease",
                "the lock stays in place",
            ]
        ),
    },
    "falcon": {
        "label": "INPUT_VALIDATION",
        "name": "주문 수량 검증",
        "plan": "주문 수량이 validation에 걸려 거절되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "orders-falcon: accepting a reservation",
                "validation failed for the falcon quantity",
                "the value must be a positive whole number",
                "the reservation was rejected",
            ]
        ),
    },
    "granite": {
        "label": "INPUT_VALIDATION",
        "name": "필수 이메일 누락",
        "plan": "가입 요청에 required field가 없어 거절되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "signup-granite: creating a member",
                "required field email is missing for granite",
                "the payload has a name and no address",
                "the member was not created",
            ]
        ),
    },
    "heron": {
        "label": "INPUT_VALIDATION",
        "name": "잘못된 날짜 입력",
        "plan": "조회 범위가 invalid input으로 거절되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "report-heron: parsing the requested window",
                "invalid input for the heron start date",
                "the end date is earlier than the start date",
                "the report was not queued",
            ]
        ),
    },
    "ivory": {
        "label": "INPUT_VALIDATION",
        "name": "인자 형식 오류",
        "plan": "배치 인자가 illegal argument로 거절되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "batch-ivory: reading the currency code",
                "illegal argument in the ivory options",
                "the code is not a known currency",
                "the batch did not start",
            ]
        ),
    },
    "juniper": {
        "label": "INPUT_VALIDATION",
        "name": "필수 헤더 누락",
        "plan": "요청 헤더가 missing required 상태로 거절되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "ingress-juniper: checking the request envelope",
                "missing required header for the juniper client",
                "the contract version header is absent",
                "the request was refused at the edge",
            ]
        ),
    },
    "kelp": {
        "label": "INPUT_VALIDATION",
        "name": "형식 불량 요청",
        "plan": "본문 형식이 bad request로 거절되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "intake-kelp: reading the submitted form",
                "bad request from the kelp parser",
                "a list was provided where an object is required",
                "nothing was stored",
            ]
        ),
    },
    "lichen": {
        "label": "INPUT_VALIDATION",
        "name": "주소 필드 검증",
        "plan": "주소 형식이 입력 검증에 걸리는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "shipping-lichen: checking the destination",
                "입력 검증에서 lichen 주소가 거절되었습니다",
                "the postal code shape does not match the region",
                "the shipment was not created",
            ]
        ),
    },
    "moss": {
        "label": "INPUT_VALIDATION",
        "name": "페이지 크기 검증",
        "plan": "목록 페이지 크기가 validation 한도를 넘는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "listing-moss: preparing the page query",
                "validation rejected the moss page size",
                "the requested size is above the allowed maximum",
                "the list was not returned",
            ]
        ),
    },
    "nectar": {
        "label": "INPUT_VALIDATION",
        "name": "쿠폰 코드 검증",
        "plan": "쿠폰 문자가 invalid input으로 거절되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "promo-nectar: applying a coupon",
                "invalid input in the nectar coupon",
                "spaces and punctuation are not allowed",
                "the price was left unchanged",
            ]
        ),
    },
    "otter": {
        "label": "INPUT_VALIDATION",
        "name": "첨부 이름 검증",
        "plan": "첨부 파일 이름이 required field 규칙을 어겨 거절되는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "inbox-otter: storing an attachment",
                "required field filename is blank for otter",
                "an empty name cannot be stored",
                "the message stayed in the intake area",
            ]
        ),
    },
    "prairie": {
        "label": "EXTERNAL_NETWORK",
        "name": "이름 해석 실패",
        "plan": "파트너 호스트의 name resolution이 실패하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "notifier-prairie: contacting the partner host",
                "temporary failure in name resolution for prairie",
                "the resolver returned no address",
                "the notice was not delivered",
            ]
        ),
    },
    "ravine": {
        "label": "EXTERNAL_NETWORK",
        "name": "호스트 이름 없음",
        "plan": "외부 호스트가 name or service not known으로 실패하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "fetcher-ravine: downloading the daily feed",
                "name or service not known: ravine partner",
                "the feed host is not in the resolver",
                "the file was not saved",
            ]
        ),
    },
    "squall": {
        "label": "EXTERNAL_NETWORK",
        "name": "주소 조회 실패",
        "plan": "getaddrinfo가 외부 주소를 찾지 못하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "webhook-squall: sending the receipt event",
                "getaddrinfo failed for the squall endpoint",
                "no address record was returned",
                "the event remains queued locally",
            ]
        ),
    },
    "tundra": {
        "label": "EXTERNAL_NETWORK",
        "name": "경로 없는 호스트",
        "plan": "결제 대행으로 no route to host가 나오는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "payments-tundra: reaching the acquirer",
                "no route to host while calling tundra",
                "the path to that network is missing",
                "the charge was not sent",
            ]
        ),
    },
    "umbra": {
        "label": "EXTERNAL_NETWORK",
        "name": "도달 불가 네트워크",
        "plan": "상태 콜백이 network is unreachable로 실패하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "status-umbra: posting the callback",
                "network is unreachable for the umbra callback",
                "the outbound interface has no route",
                "the callback was skipped",
            ]
        ),
    },
    "velvet": {
        "label": "EXTERNAL_NETWORK",
        "name": "연결 시간 초과",
        "plan": "재고 서비스 연결이 connection timed out으로 끝나는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "inventory-velvet: opening the remote catalog",
                "connection timed out talking to velvet",
                "the handshake did not finish",
                "stock counts were not refreshed",
            ]
        ),
    },
    "whisper": {
        "label": "EXTERNAL_NETWORK",
        "name": "연결 거부",
        "plan": "메트릭 수집기가 connection refused를 받는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "metrics-whisper: scraping the remote endpoint",
                "connection refused by the whisper collector",
                "the remote port is closed",
                "this interval has no samples",
            ]
        ),
    },
    "yarn": {
        "label": "EXTERNAL_NETWORK",
        "name": "질의 시간 초과",
        "plan": "지도 타일 요청이 timeout으로 끝나는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "tiles-yarn: requesting a map image",
                "timeout while waiting for yarn",
                "the remote did not answer",
                "the image was left blank",
            ]
        ),
    },
    "zenith": {
        "label": "EXTERNAL_NETWORK",
        "name": "DNS 조회 실패",
        "plan": "알림 릴레이의 dns 조회가 실패하는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "relay-zenith: resolving the notify host",
                "dns lookup failed for zenith",
                "the name server returned a failure",
                "the message was not relayed",
            ]
        ),
    },
    "apple": {
        "label": "EXTERNAL_NETWORK",
        "name": "응답 대기 초과",
        "plan": "날씨 제공자가 timed out으로 끝나는 등록 실패입니다.",
        "stderr": "\n".join(
            [
                "weather-apple: reading the forecast",
                "the apple provider timed out",
                "no forecast body arrived",
                "the previous forecast remains on screen",
            ]
        ),
    },
    "birch": {
        "label": "OTHER",
        "name": "청구서 널 참조",
        "plan": "청구서 서식이 빈 참조로 중단되는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "invoice-birch: rendering the monthly statement",
                "NullPointerException in the birch formatter",
                "the customer block was absent",
                "the statement file was not written",
            ]
        ),
    },
    "clover": {
        "label": "OTHER",
        "name": "캐시 단정 실패",
        "plan": "캐시 세대 단정이 깨져 작업이 멈추는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "cache-clover: swapping the prepared generation",
                "assertion failed on the clover stamp",
                "the new generation is older than the current one",
                "the swap was cancelled",
            ]
        ),
    },
    "dune": {
        "label": "OTHER",
        "name": "스풀 용량 초과",
        "plan": "출력 스풀의 용량이 차서 쓰기가 멈추는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "spool-dune: writing the rendered page",
                "no space left on the dune spool",
                "the volume reported a full device",
                "the page stays in memory",
            ]
        ),
    },
    "elm": {
        "label": "OTHER",
        "name": "프로토콜 버퍼 손상",
        "plan": "작업 메시지의 버퍼가 깨져 해석이 멈추는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "worker-elm: decoding the assigned message",
                "malformed protobuf in the elm payload",
                "the length prefix does not match the body",
                "the message was moved aside",
            ]
        ),
    },
    "flint": {
        "label": "OTHER",
        "name": "메모리 잠금 교착",
        "plan": "프로세스 안 잠금이 교착되어 진행이 멈추는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "scheduler-flint: acquiring two local locks",
                "deadlock detected in the flint lock table",
                "both waiters already hold the other lock",
                "the cycle was aborted",
            ]
        ),
    },
    "grove": {
        "label": "OTHER",
        "name": "플러그인 클래스 없음",
        "plan": "플러그인 클래스를 찾지 못해 기동이 멈추는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "loader-grove: starting the optional exporter",
                "ClassNotFoundException for the grove plugin",
                "the declared entry is not on the classpath",
                "the exporter was left disabled",
            ]
        ),
    },
    "hazel": {
        "label": "OTHER",
        "name": "템플릿 스택 초과",
        "plan": "템플릿 재귀가 스택을 넘어서 렌더가 멈추는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "render-hazel: expanding the nested layout",
                "StackOverflowError in the hazel renderer",
                "a partial includes itself",
                "the layout was not produced",
            ]
        ),
    },
    "iris": {
        "label": "OTHER",
        "name": "범위 밖 색인",
        "plan": "보고서 행 색인이 범위를 벗어나 생성이 멈추는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "report-iris: reading a summary cell",
                "IndexOutOfBoundsException in the iris table",
                "the requested column is past the row width",
                "the summary was skipped",
            ]
        ),
    },
    "jade": {
        "label": "OTHER",
        "name": "스케줄 상태 불일치",
        "plan": "스케줄러 상태가 예상과 달라 한 주기가 멈추는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "clock-jade: firing the hourly job",
                "IllegalStateException in the jade scheduler",
                "the job is running and queued at the same time",
                "this tick was dropped",
            ]
        ),
    },
    "koi": {
        "label": "OTHER",
        "name": "로컬 파이프 단절",
        "plan": "같은 호스트의 파이프가 끊어져 전달이 멈추는 등록 실패입니다. 규칙 키워드가 없습니다.",
        "stderr": "\n".join(
            [
                "bridge-koi: writing to the local helper",
                "broken pipe on the koi channel",
                "the helper closed its end first",
                "the bytes were not delivered",
            ]
        ),
    },
}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in SCENARIOS:
        print("등록된 시나리오 이름이 필요합니다.", file=sys.stderr)
        return 2
    print(SCENARIOS[argv[1]]["stderr"], file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
