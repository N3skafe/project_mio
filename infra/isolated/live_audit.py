"""격리 API 18080에 대한 LIVE 검증. 기존 5432/8080에는 접속하지 않는다."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "http://127.0.0.1:18080"
ROOT = Path(__file__).resolve().parents[2]
COMPOSE = [
    "docker",
    "compose",
    "--project-name",
    "maidops-isolated",
    "-f",
    str(ROOT / "infra" / "isolated" / "docker-compose.yml"),
]
RESULTS: list[dict[str, object]] = []


def record(name: str, status: str, detail: str) -> None:
    RESULTS.append({"name": name, "status": status, "detail": detail})
    print(f"{status} {name}: {detail}", flush=True)


def request(method: str, path: str, body: dict | None = None, headers: dict | None = None, timeout: float = 30):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            payload = json.loads(raw.decode("utf-8")) if raw else None
            return response.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload


def create_job(key: str, task_id: str) -> dict:
    status, payload = request(
        "POST",
        "/api/v1/jobs",
        {"project_id": "trusted-sample", "task_id": task_id},
        {"Idempotency-Key": key},
    )
    if status != 201 or not isinstance(payload, dict):
        raise RuntimeError(f"job create {task_id} -> {status} {payload}")
    return payload


def wait_job(job_id: str, timeout: float = 40) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        status, payload = request("GET", f"/api/v1/jobs/{job_id}")
        if status == 200 and isinstance(payload, dict):
            last = payload
            if payload.get("status") not in {"QUEUED", "RUNNING", "CANCEL_REQUESTED"}:
                return payload
        time.sleep(0.4)
    return last


def events(job_id: str) -> list[dict]:
    status, payload = request("GET", f"/api/v1/jobs/{job_id}/events")
    if status != 200 or not isinstance(payload, dict):
        return []
    items = payload.get("items") or []
    return items if isinstance(items, list) else []


def texts(job_id: str) -> list[str]:
    return [str(item.get("text")) for item in events(job_id)]


def psql(database: str, sql: str) -> str:
    completed = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "maidops-isolated-postgres-1",
            "psql",
            "-U",
            "maidops",
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
        ],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout)
    return completed.stdout.strip()


def compose(*args: str) -> None:
    completed = subprocess.run([*COMPOSE, *args], check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout)


def case_for_job(job_id: str) -> dict | None:
    cursor = None
    while True:
        path = "/api/v1/error-cases?limit=100"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor, safe="")
        status, payload = request("GET", path)
        if status != 200 or not isinstance(payload, dict):
            return None
        for item in payload.get("items") or []:
            if isinstance(item, dict) and item.get("job_id") == job_id:
                return item
        cursor = payload.get("next_cursor")
        if not cursor:
            return None


def wait_case(job_id: str, timeout: float = 20) -> dict | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = case_for_job(job_id)
        if found is not None:
            return found
        time.sleep(0.4)
    return None


def register_tasks() -> None:
    sql = """
    INSERT INTO registered_tasks (id, project_id, name, plan_text, argv_json, relative_workdir, timeout_seconds)
    VALUES
    ('audit-tick', 'trusted-sample', '간격 출력', '감사 fixture', '["{python}","tick_check.py"]', 'sample', 20),
    ('audit-trim', 'trusted-sample', '보관 잘림', '감사 fixture', '["{python}","trim_check.py"]', 'sample', 20),
    ('audit-flood', 'trusted-sample', '출력 한도', '감사 fixture', '["{python}","flood_check.py"]', 'sample', 30),
    ('audit-hang', 'trusted-sample', '장시간 대기', '감사 fixture', '["{python}","hang_check.py"]', 'sample', 8),
    ('audit-tree', 'trusted-sample', '프로세스 트리', '감사 fixture', '["{python}","tree_check.py"]', 'sample', 20)
    ON CONFLICT (id) DO NOTHING;
    """
    psql("maidops_live_audit", sql)
    record("audit-tasks", "PASS", "격리 DB에 감사 작업 5개를 등록했다.")


def check_schema() -> None:
    versions = psql(
        "maidops_live_audit",
        "SELECT string_agg(version || ':' || success::text, ',' ORDER BY installed_rank) FROM flyway_schema_history;",
    )
    if versions == "1:true,2:true,3:true,4:true,5:true,6:true,7:true,8:true":
        record("empty-db-migrations", "PASS", versions)
    else:
        record("empty-db-migrations", "FAIL", versions)


def job_flow() -> None:
    passed = create_job("live-c-pass-1", "sample-pass")
    job_id = str(passed["id"])
    seen_running = False
    seen_tick = False
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status, payload = request("GET", f"/api/v1/jobs/{job_id}")
        if status == 200 and isinstance(payload, dict) and payload.get("status") == "RUNNING":
            seen_running = True
        if any(line == "check ok" for line in texts(job_id)):
            seen_tick = True
            if seen_running:
                break
        time.sleep(0.2)
    final = wait_job(job_id)
    record(
        "pass-job",
        "PASS" if final.get("status") == "SUCCEEDED" and final.get("termination_reason") == "COMPLETED" and seen_running and seen_tick else "FAIL",
        f"id={job_id} status={final.get('status')} reason={final.get('termination_reason')} running_seen={seen_running} log_before_idle={seen_tick}",
    )

    failed = wait_job(str(create_job("live-c-fail-1", "sample-fail")["id"]))
    fail_id = str(failed.get("id"))
    case = wait_case(fail_id)
    record(
        "fail-job-case",
        "PASS" if failed.get("status") == "FAILED" and failed.get("termination_reason") == "FAILED" and case else "FAIL",
        f"id={fail_id} status={failed.get('status')} reason={failed.get('termination_reason')} case={None if case is None else case.get('id')}",
    )
    if case:
        approved = request("POST", f"/api/v1/error-cases/{case['id']}/reviews", {"decision": "APPROVE"})
        record(
            "review-approve",
            "PASS" if approved[0] == 200 and approved[1].get("review_status") == "APPROVED" else "FAIL",
            str(approved[1].get("review_status") if isinstance(approved[1], dict) else approved),
        )

    revised_job = wait_job(str(create_job("live-c-revise-1", "sample-fail")["id"]))
    revised_case = wait_case(str(revised_job.get("id")))
    if revised_case:
        revised = request(
            "POST",
            f"/api/v1/error-cases/{revised_case['id']}/reviews",
            {"decision": "REVISE", "label": "INPUT_VALIDATION"},
        )
        record(
            "review-revise",
            "PASS" if revised[0] == 200 and isinstance(revised[1], dict) and revised[1].get("confirmed_label") == "INPUT_VALIDATION" else "FAIL",
            str(revised[1] if isinstance(revised[1], dict) else revised),
        )
        resolution = request(
            "POST",
            f"/api/v1/error-cases/{revised_case['id']}/resolutions",
            {"cause": "감사 원인 토큰", "method": "감사 방법 토큰"},
        )
        record(
            "resolution",
            "PASS" if resolution[0] == 200 else "FAIL",
            str(resolution[0]),
        )
        found = request("GET", "/api/v1/search?q=" + urllib.parse.quote("감사 원인 토큰"))
        hits = found[1].get("items") if isinstance(found[1], dict) else None
        record("search", "PASS" if found[0] == 200 and hits else "FAIL", f"status={found[0]} hits={0 if not hits else len(hits)}")

    deferred_job = wait_job(str(create_job("live-c-defer-1", "sample-fail")["id"]))
    deferred_case = wait_case(str(deferred_job.get("id")))
    if deferred_case:
        deferred = request("POST", f"/api/v1/error-cases/{deferred_case['id']}/reviews", {"decision": "DEFER"})
        record(
            "review-defer",
            "PASS" if deferred[0] == 200 and deferred[1].get("review_status") == "DEFERRED" else "FAIL",
            str(deferred[1].get("review_status") if isinstance(deferred[1], dict) else deferred),
        )

    tick = create_job("live-c-tick-1", "audit-tick")
    tick_id = str(tick["id"])
    saw_partial = False
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        lines = texts(tick_id)
        if "tick-0" in lines and "tick-5" not in lines:
            saw_partial = True
            break
        status, payload = request("GET", f"/api/v1/jobs/{tick_id}")
        if isinstance(payload, dict) and payload.get("status") not in {"QUEUED", "RUNNING", "CANCEL_REQUESTED"}:
            break
        time.sleep(0.15)
    final_tick = wait_job(tick_id)
    record(
        "incremental-log",
        "PASS" if saw_partial and final_tick.get("status") == "SUCCEEDED" else "FAIL",
        f"id={tick_id} partial={saw_partial} status={final_tick.get('status')} lines={texts(tick_id)}",
    )

    trimmed = wait_job(str(create_job("live-c-trim-1", "audit-trim")["id"]), timeout=30)
    trim_lines = texts(str(trimmed.get("id")))
    record(
        "server-trim",
        "PASS"
        if trimmed.get("status") == "SUCCEEDED"
        and trimmed.get("termination_reason") == "COMPLETED"
        and trimmed.get("output_truncated") is True
        and any(line.startswith("[출력 잘림]") for line in trim_lines)
        else "FAIL",
        f"status={trimmed.get('status')} reason={trimmed.get('termination_reason')} truncated={trimmed.get('output_truncated')}",
    )

    flooded = wait_job(str(create_job("live-c-flood-1", "audit-flood")["id"]), timeout=30)
    record(
        "output-limit",
        "PASS"
        if flooded.get("status") == "FAILED" and flooded.get("termination_reason") == "OUTPUT_LIMIT_EXCEEDED"
        else "FAIL",
        f"id={flooded.get('id')} status={flooded.get('status')} reason={flooded.get('termination_reason')}",
    )

    timed = wait_job(str(create_job("live-c-hang-1", "audit-hang")["id"]), timeout=25)
    record(
        "timeout",
        "PASS" if timed.get("status") == "FAILED" and timed.get("termination_reason") == "TIMED_OUT" else "FAIL",
        f"id={timed.get('id')} status={timed.get('status')} reason={timed.get('termination_reason')}",
    )

    tree = create_job("live-c-tree-1", "audit-tree")
    tree_id = str(tree["id"])
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        status, payload = request("GET", f"/api/v1/jobs/{tree_id}")
        if isinstance(payload, dict) and payload.get("status") == "RUNNING":
            break
        time.sleep(0.2)
    time.sleep(1)
    inside = subprocess.run(
        ["docker", "exec", "maidops-isolated-worker-1", "ps", "-ef"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    host = subprocess.run(["tasklist"], capture_output=True, text=True, check=False).stdout
    cancel_status, cancelled = request("POST", f"/api/v1/jobs/{tree_id}/cancel")
    final_tree = wait_job(tree_id, timeout=20)
    time.sleep(1)
    inside_after = subprocess.run(
        ["docker", "exec", "maidops-isolated-worker-1", "ps", "-ef"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    leftover = "tree_check.py" in inside_after
    record(
        "cancel-and-process-tree",
        "PASS"
        if cancel_status == 200
        and final_tree.get("status") == "CANCELLED"
        and "tree_check.py" in inside
        and not leftover
        and "tree_check.py" not in host
        else "FAIL",
        f"status={final_tree.get('status')} reason={final_tree.get('termination_reason')} saw_process={'tree_check.py' in inside} leftover={leftover}",
    )


def worker_api_controls() -> None:
    compose("stop", "worker")
    time.sleep(1)
    job = create_job("live-batch-1", "sample-pass")
    job_id = str(job["id"])
    claim_status, claimed = request("POST", "/api/v1/worker/claim", headers={"X-Worker-Id": "audit-worker-1"})
    record(
        "manual-claim",
        "PASS" if claim_status == 200 and isinstance(claimed, dict) and claimed.get("job_id") == job_id else "FAIL",
        f"{claim_status} {claimed if isinstance(claimed, dict) else claimed}",
    )
    batch = {"batch_id": f"{job_id}-b1", "lines": [{"stream": "STDOUT", "text": "batch-alpha"}]}
    first = request("POST", f"/api/v1/worker/jobs/{job_id}/events", batch, {"X-Worker-Id": "audit-worker-1"})
    replay = request("POST", f"/api/v1/worker/jobs/{job_id}/events", batch, {"X-Worker-Id": "audit-worker-1"})
    conflict = request(
        "POST",
        f"/api/v1/worker/jobs/{job_id}/events",
        {"batch_id": f"{job_id}-b1", "lines": [{"stream": "STDOUT", "text": "batch-beta"}]},
        {"X-Worker-Id": "audit-worker-1"},
    )
    other = request(
        "POST",
        f"/api/v1/worker/jobs/{job_id}/events",
        {"batch_id": f"{job_id}-b2", "lines": [{"stream": "STDOUT", "text": "other-worker"}]},
        {"X-Worker-Id": "audit-worker-2"},
    )
    unfinished = request(
        "POST",
        f"/api/v1/worker/jobs/{job_id}/finish",
        {"exit_code": 0, "process_exited": False, "timed_out": False, "termination_reason": "COMPLETED"},
        {"X-Worker-Id": "audit-worker-1"},
    )
    still = request("GET", f"/api/v1/jobs/{job_id}")
    finished = request(
        "POST",
        f"/api/v1/worker/jobs/{job_id}/finish",
        {
            "exit_code": 0,
            "process_exited": True,
            "timed_out": False,
            "output_truncated": False,
            "termination_reason": "COMPLETED",
            "log_storage_incomplete": False,
        },
        {"X-Worker-Id": "audit-worker-1"},
    )
    replay_after = request("POST", f"/api/v1/worker/jobs/{job_id}/events", batch, {"X-Worker-Id": "audit-worker-1"})
    rejected = request(
        "POST",
        f"/api/v1/worker/jobs/{job_id}/events",
        {"batch_id": f"{job_id}-b9", "lines": [{"stream": "STDOUT", "text": "after-finish"}]},
        {"X-Worker-Id": "audit-worker-1"},
    )
    record("batch-once", "PASS" if first[0] == 204 else "FAIL", str(first[0]))
    record("batch-replay", "PASS" if replay[0] == 204 and replay_after[0] == 204 else "FAIL", f"{replay[0]} {replay_after[0]}")
    record("batch-conflict", "PASS" if conflict[0] == 409 else "FAIL", str(conflict[0]))
    record("other-worker-rejected", "PASS" if other[0] == 409 else "FAIL", str(other[0]))
    record(
        "process-not-exited",
        "PASS"
        if unfinished[0] == 200
        and isinstance(still[1], dict)
        and still[1].get("status") == "RUNNING"
        and still[1].get("termination_reason") is None
        else "FAIL",
        str(still[1].get("status") if isinstance(still[1], dict) else still),
    )
    record(
        "finish-completed",
        "PASS" if finished[0] == 200 and finished[1].get("status") == "SUCCEEDED" else "FAIL",
        str(finished[1].get("status") if isinstance(finished[1], dict) else finished),
    )
    record("batch-after-finish", "PASS" if rejected[0] == 409 else "FAIL", str(rejected[0]))
    stored = psql(
        "maidops_live_audit",
        f"SELECT count(*) FROM job_events WHERE job_id = '{job_id}' AND text = 'batch-alpha';",
    )
    record("batch-stored-once", "PASS" if stored == "1" else "FAIL", stored)

    leased = create_job("live-lease-1", "audit-hang")
    lease_id = str(leased["id"])
    claim = request("POST", "/api/v1/worker/claim", headers={"X-Worker-Id": "audit-worker-1"})
    record(
        "lease-claim",
        "PASS" if claim[0] == 200 and isinstance(claim[1], dict) and claim[1].get("job_id") == lease_id else "FAIL",
        str(claim[1] if isinstance(claim[1], dict) else claim),
    )
    stranger = request("POST", f"/api/v1/worker/jobs/{lease_id}/heartbeat", headers={"X-Worker-Id": "audit-worker-2"})
    record("stale-other-worker", "PASS" if stranger[0] == 409 else "FAIL", str(stranger[0]))
    time.sleep(22)
    expired = request("GET", f"/api/v1/jobs/{lease_id}")
    late_beat = request("POST", f"/api/v1/worker/jobs/{lease_id}/heartbeat", headers={"X-Worker-Id": "audit-worker-1"})
    late_events = request(
        "POST",
        f"/api/v1/worker/jobs/{lease_id}/events",
        {"batch_id": f"{lease_id}-late", "lines": [{"stream": "STDOUT", "text": "late"}]},
        {"X-Worker-Id": "audit-worker-1"},
    )
    late_finish = request(
        "POST",
        f"/api/v1/worker/jobs/{lease_id}/finish",
        {"exit_code": 0, "process_exited": True, "timed_out": False, "termination_reason": "COMPLETED"},
        {"X-Worker-Id": "audit-worker-1"},
    )
    again = request("GET", f"/api/v1/jobs/{lease_id}")
    record(
        "job-lease-expired",
        "PASS"
        if isinstance(expired[1], dict)
        and expired[1].get("status") == "FAILED"
        and "자동 재실행하지 않습니다" in " ".join(texts(lease_id))
        else "FAIL",
        f"status={expired[1].get('status') if isinstance(expired[1], dict) else expired}",
    )
    stayed = isinstance(again[1], dict) and again[1].get("status") == "FAILED"
    record(
        "same-worker-late-write",
        "PASS" if late_beat[0] == 409 and late_events[0] == 409 and stayed else "FAIL",
        f"beat={late_beat[0]} events={late_events[0]} finish={late_finish[0]} status={again[1].get('status') if isinstance(again[1], dict) else again}",
    )
    record(
        "no-lease-generation",
        "NOT_APPLICABLE",
        "소유권은 worker_id뿐이다. 다른 worker 거부와 만료 후 상태 보호를 확인했고, 세대 토큰은 없다.",
    )
    compose("start", "worker")


def idempotency() -> None:
    def once(index: int):
        return request(
            "POST",
            "/api/v1/jobs",
            {"project_id": "trusted-sample", "task_id": "sample-pass"},
            {"Idempotency-Key": "live-parallel-key"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(once, (1, 2)))
    ids = {item[1].get("id") for item in results if isinstance(item[1], dict)}
    codes = [item[0] for item in results]
    record(
        "idempotency-parallel",
        "PASS" if codes.count(201) == 1 and codes.count(200) == 1 and len(ids) == 1 else "FAIL",
        f"codes={codes} ids={ids}",
    )


def training_lease() -> None:
    compose("stop", "trainer")
    status, created = request("POST", "/api/v1/training-runs")
    if status != 201:
        record("training-lease", "BLOCKED", f"학습을 만들지 못했다: {status} {created}")
        compose("start", "trainer")
        return
    run_id = str(created["id"])
    claim = request("POST", "/api/v1/trainer/claim", headers={"X-Trainer-Id": "audit-trainer-manual"})
    record(
        "training-claim",
        "PASS" if claim[0] == 200 and claim[1].get("training_run_id") == run_id else "FAIL",
        str(claim[0]),
    )
    time.sleep(125)
    expired = request("GET", f"/api/v1/training-runs/{run_id}")
    message = expired[1].get("error_message") if isinstance(expired[1], dict) else ""
    record(
        "training-lease-expired",
        "PASS"
        if isinstance(expired[1], dict)
        and expired[1].get("status") == "FAILED"
        and "다시 학습하지 않습니다" in str(message)
        else "FAIL",
        f"status={expired[1].get('status') if isinstance(expired[1], dict) else expired} message={message}",
    )
    compose("start", "trainer")
    time.sleep(3)
    again = request("GET", f"/api/v1/training-runs/{run_id}")
    record(
        "training-not-requeued",
        "PASS" if isinstance(again[1], dict) and again[1].get("status") == "FAILED" else "FAIL",
        str(again[1].get("status") if isinstance(again[1], dict) else again),
    )


def prepare_labels() -> bool:
    tasks = [
        "lab-harbor", "lab-ledger", "lab-kiln", "lab-maple", "lab-orchid",
        "lab-violet", "lab-walnut", "lab-xenon", "lab-yellow", "lab-zircon",
        "lab-falcon", "lab-granite", "lab-heron", "lab-ivory", "lab-juniper",
        "lab-prairie", "lab-ravine", "lab-squall", "lab-tundra", "lab-umbra",
        "lab-birch", "lab-clover", "lab-dune", "lab-elm", "lab-flint",
    ]
    approved = 0
    for index, task_id in enumerate(tasks):
        job = wait_job(str(create_job(f"live-label-{index}", task_id)["id"]), timeout=30)
        case = wait_case(str(job.get("id")))
        if case is None:
            continue
        if case.get("inference_state") == "PENDING":
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                status, payload = request("GET", f"/api/v1/error-cases/{case['id']}")
                if status == 200 and isinstance(payload, dict) and payload.get("inference_state") != "PENDING":
                    case = payload
                    break
                time.sleep(0.5)
        result = request("POST", f"/api/v1/error-cases/{case['id']}/reviews", {"decision": "APPROVE"})
        if result[0] == 200 and isinstance(result[1], dict) and result[1].get("review_status") == "APPROVED":
            approved += 1
    status, lab = request("GET", "/api/v1/lab/status")
    eligible = isinstance(lab, dict) and lab.get("eligible") is True
    record(
        "training-gate",
        "PASS" if eligible else "FAIL",
        f"approved={approved} eligible={eligible} reasons={lab.get('reasons') if isinstance(lab, dict) else lab}",
    )
    return eligible


def train_and_infer() -> None:
    if not prepare_labels():
        record("cpu-training", "BLOCKED", "확정 라벨 조건이 부족해 학습을 시작하지 않았다.")
        return
    status, created = request("POST", "/api/v1/training-runs")
    if status != 201 or not isinstance(created, dict):
        record("cpu-training", "FAIL", f"create {status} {created}")
        return
    run_id = str(created["id"])
    deadline = time.monotonic() + 180
    final: dict = {}
    while time.monotonic() < deadline:
        status, payload = request("GET", f"/api/v1/training-runs/{run_id}")
        if status == 200 and isinstance(payload, dict):
            final = payload
            if payload.get("status") in {"SUCCEEDED", "FAILED"}:
                break
        time.sleep(2)
    model = final.get("model") if isinstance(final.get("model"), dict) else {}
    record(
        "cpu-training",
        "PASS"
        if final.get("status") == "SUCCEEDED"
        and model.get("metric_policy") == "supported-class-macro-f1-v2"
        and model.get("checkpoint_evaluated") is True
        and model.get("is_default") is False
        else "FAIL",
        f"status={final.get('status')} policy={model.get('metric_policy')} evaluated={model.get('checkpoint_evaluated')} default={model.get('is_default')} f1={model.get('macro_f1')} error={final.get('error_message')}",
    )
    if final.get("status") != "SUCCEEDED":
        return
    model_id = str(model.get("id"))
    file_list = subprocess.run(
        ["docker", "exec", "maidops-isolated-trainer-1", "sh", "-c", "sha256sum /models/*.pt /models/*.meta.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    record(
        "checkpoint-files",
        "PASS" if model_id and model.get("checksum_sha256") and model_id in file_list.stdout and "maidops-mlp-v2" in file_list.stdout else "FAIL",
        f"model={model_id} api_checksum={model.get('checksum_sha256')} files={file_list.stdout.strip()} err={file_list.stderr.strip()}",
    )
    selected = request("POST", f"/api/v1/model-versions/{model_id}/select-default")
    record(
        "select-default",
        "PASS" if selected[0] == 200 and selected[1].get("is_default") is True else "FAIL",
        str(selected[0]),
    )
    fresh = wait_job(str(create_job("live-model-draft-1", "lab-birch")["id"]), timeout=30)
    case = wait_case(str(fresh.get("id")), timeout=20)
    if case and case.get("inference_state") == "PENDING":
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            status, payload = request("GET", f"/api/v1/error-cases/{case['id']}")
            if status == 200 and isinstance(payload, dict) and payload.get("inference_state") != "PENDING":
                case = payload
                break
            time.sleep(0.5)
    record(
        "model-draft",
        "PASS"
        if isinstance(case, dict)
        and case.get("draft_source") == "MODEL"
        and case.get("inference_state") == "READY"
        and case.get("model_version_id") == model_id
        else "FAIL",
        f"case={None if not isinstance(case, dict) else {key: case.get(key) for key in ('id', 'draft_source', 'inference_state', 'draft_label', 'model_version_id')}}",
    )


def restart_and_recreate() -> None:
    compose("restart", "backend", "worker", "trainer")
    deadline = time.monotonic() + 60
    healthy = False
    while time.monotonic() < deadline:
        status, payload = request("GET", "/api/v1/health")
        if status == 200:
            healthy = True
            break
        time.sleep(2)
    versions = psql(
        "maidops_live_audit",
        "SELECT count(*) FROM flyway_schema_history WHERE success;",
    )
    kept = psql(
        "maidops_live_audit",
        "SELECT review_status || ' ' || coalesce(confirmed_label, current_label, '') FROM error_cases WHERE id IN (SELECT id FROM error_cases ORDER BY created_at LIMIT 1);",
    )
    record("restart-api", "PASS" if healthy and versions == "8" else "FAIL", f"healthy={healthy} migrations={versions} sample={kept}")
    fresh = wait_job(str(create_job("live-after-restart-1", "lab-clover")["id"]), timeout=40)
    case = wait_case(str(fresh.get("id")), timeout=20)
    if isinstance(case, dict) and case.get("inference_state") == "PENDING":
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            status, payload = request("GET", f"/api/v1/error-cases/{case['id']}")
            if status == 200 and isinstance(payload, dict) and payload.get("inference_state") != "PENDING":
                case = payload
                break
            time.sleep(0.5)
    record(
        "inference-after-restart",
        "PASS" if isinstance(case, dict) and case.get("draft_source") == "MODEL" and case.get("inference_state") == "READY" else "FAIL",
        str(None if not isinstance(case, dict) else case.get("draft_source")),
    )
    compose("up", "-d", "--force-recreate", "--no-deps", "backend", "worker", "trainer")
    deadline = time.monotonic() + 70
    while time.monotonic() < deadline:
        status, _payload = request("GET", "/api/v1/health")
        if status == 200:
            break
        time.sleep(2)
    files = subprocess.run(
        ["docker", "exec", "maidops-isolated-trainer-1", "sh", "-c", "ls /models"],
        capture_output=True,
        text=True,
        check=False,
    )
    record(
        "volume-survives-recreate",
        "PASS" if ".pt" in files.stdout and ".meta.json" in files.stdout else "FAIL",
        files.stdout.strip() or files.stderr.strip(),
    )


def headless_tui() -> None:
    code = r"""
import json, os
os.environ["MAIDOPS_MODE"] = "LIVE"
os.environ["MAIDOPS_BACKEND_URL"] = "http://127.0.0.1:18080"
from maidops_tui.config import load_config
from maidops_tui.services.factory import build_service
import asyncio
async def main():
    service = build_service(load_config())
    projects = await service.list_projects()
    jobs = await service.list_jobs()
    print(json.dumps({"projects": len(projects), "jobs": len(jobs), "mode": "LIVE"}))
asyncio.run(main())
"""
    completed = subprocess.run(
        ["..\\tui\\.venv\\Scripts\\python.exe", "-c", code],
        cwd=str(ROOT / "tui"),
        capture_output=True,
        text=True,
        check=False,
        env={**os_env(), "PYTHONPATH": str(ROOT / "tui" / "src")},
    )
    record(
        "headless-tui-live",
        "PASS" if completed.returncode == 0 and '"mode": "LIVE"' in completed.stdout else "FAIL",
        (completed.stdout or completed.stderr).strip()[:500],
    )
    record("visual-tui", "BLOCKED", "실제 터미널 화면을 사람이 보지 않았다. headless 서비스 조회만 수행했다.")


def os_env() -> dict[str, str]:
    import os

    return dict(os.environ)


def main() -> None:
    health = request("GET", "/api/v1/health")
    record("health", "PASS" if health[0] == 200 else "FAIL", str(health[1]))
    check_schema()
    register_tasks()
    for name, func in (
        ("job-flow", job_flow),
        ("idempotency", idempotency),
        ("worker-controls", worker_api_controls),
        ("training-lease", training_lease),
        ("train-infer", train_and_infer),
        ("restart", restart_and_recreate),
        ("tui", headless_tui),
    ):
        try:
            func()
        except Exception as exc:
            record(name, "FAIL", f"{type(exc).__name__}: {exc}")
    record("supervision-live", "BLOCKED", "상태 조회 예외를 격리 스택에서 안전하게 주입하지 않았다. 제품 단위 테스트와 별개다.")
    out = ROOT / "infra" / "isolated" / "live_audit_results.json"
    out.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    print(f"FAILS={len(failed)}", flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
