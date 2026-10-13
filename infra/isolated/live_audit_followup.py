"""앞선 LIVE 스크립트가 남긴 항목만 다시 확인한다."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
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
OUT: list[dict[str, str]] = []


def record(name: str, status: str, detail: str) -> None:
    OUT.append({"name": name, "status": status, "detail": detail})
    print(f"{status} {name}: {detail}", flush=True)


def request(method: str, path: str, body: dict | None = None, headers: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload


def create_job(key: str, task_id: str) -> str:
    status, payload = request(
        "POST",
        "/api/v1/jobs",
        {"project_id": "trusted-sample", "task_id": task_id},
        {"Idempotency-Key": key},
    )
    if status not in {200, 201} or not isinstance(payload, dict):
        raise RuntimeError(f"{status} {payload}")
    return str(payload["id"])


def wait_terminal(job_id: str, timeout: float = 50) -> dict:
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


def psql(sql: str) -> str:
    completed = subprocess.run(
        ["docker", "exec", "-i", "maidops-isolated-postgres-1", "psql", "-U", "maidops", "-d", "maidops_live_audit", "-t", "-A"],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    return (completed.stdout or completed.stderr).strip()


def processes() -> str:
    completed = subprocess.run(
        [
            "docker",
            "exec",
            "maidops-isolated-worker-1",
            "python",
            "-c",
            "import os\n"
            "hits=[]\n"
            "for pid in os.listdir('/proc'):\n"
            "    if not pid.isdigit():\n"
            "        continue\n"
            "    try:\n"
            "        raw=open(f'/proc/{pid}/cmdline','rb').read().replace(b'\\x00', b' ').decode()\n"
            "    except OSError:\n"
            "        continue\n"
            "    if 'tree_check.py' in raw:\n"
            "        hits.append(raw)\n"
            "print('\\n'.join(hits))\n",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip()


def main() -> None:
    trim_id = create_job("live-c-trim-slow-1", "audit-trim")
    trimmed = wait_terminal(trim_id, 60)
    counts = psql(
        f"SELECT output_truncated::text || ' ' || log_storage_incomplete::text || ' ' || count(*) "
        f"FROM jobs j JOIN job_events e ON e.job_id = j.id WHERE j.id = '{trim_id}' GROUP BY 1;"
    )
    record(
        "server-trim-slow",
        "PASS"
        if trimmed.get("status") == "SUCCEEDED"
        and trimmed.get("termination_reason") == "COMPLETED"
        and trimmed.get("output_truncated") is True
        and counts.startswith("true false")
        else "FAIL",
        f"status={trimmed.get('status')} reason={trimmed.get('termination_reason')} truncated={trimmed.get('output_truncated')} db={counts}",
    )

    tree_id = create_job("live-c-tree-2", "audit-tree")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        _status, payload = request("GET", f"/api/v1/jobs/{tree_id}")
        if isinstance(payload, dict) and payload.get("status") == "RUNNING" and processes():
            break
        time.sleep(0.3)
    before = processes()
    request("POST", f"/api/v1/jobs/{tree_id}/cancel")
    final = wait_terminal(tree_id, 20)
    time.sleep(1)
    after = processes()
    record(
        "process-tree-observed",
        "PASS" if before and final.get("status") == "CANCELLED" and not after else "FAIL",
        f"status={final.get('status')} before={before!r} after={after!r}",
    )

    subprocess.run([*COMPOSE, "stop", "trainer"], check=False)
    status, created = request("POST", "/api/v1/training-runs")
    if status != 201 or not isinstance(created, dict):
        record("training-lease", "FAIL", f"{status} {created}")
    else:
        run_id = str(created["id"])
        claim = request("POST", "/api/v1/trainer/claim", headers={"X-Trainer-Id": "audit-trainer-manual"})
        record(
            "training-claim",
            "PASS" if claim[0] == 200 and isinstance(claim[1], dict) and claim[1].get("training_run_id") == run_id else "FAIL",
            str(claim[1] if isinstance(claim[1], dict) else claim),
        )
        time.sleep(125)
        expired = request("GET", f"/api/v1/training-runs/{run_id}")
        message = expired[1].get("error_message") if isinstance(expired[1], dict) else ""
        record(
            "training-lease-expired",
            "PASS"
            if isinstance(expired[1], dict) and expired[1].get("status") == "FAILED" and "다시 학습하지 않습니다" in str(message)
            else "FAIL",
            f"status={expired[1].get('status') if isinstance(expired[1], dict) else expired} message={message}",
        )
    subprocess.run([*COMPOSE, "start", "trainer"], check=False)
    time.sleep(5)

    subprocess.run([*COMPOSE, "restart", "backend", "worker", "trainer"], check=False)
    deadline = time.monotonic() + 70
    healthy = False
    while time.monotonic() < deadline:
        try:
            status, _payload = request("GET", "/api/v1/health")
        except Exception:
            status = 0
        if status == 200:
            healthy = True
            break
        time.sleep(2)
    record("restart-api", "PASS" if healthy else "FAIL", f"healthy={healthy}")
    infer_id = create_job("live-after-restart-2", "lab-clover")
    infer = wait_terminal(infer_id, 40)
    case = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, payload = request("GET", "/api/v1/error-cases?limit=100")
        if status == 200 and isinstance(payload, dict):
            for item in payload.get("items") or []:
                if isinstance(item, dict) and item.get("job_id") == infer_id:
                    case = item
        if isinstance(case, dict) and case.get("inference_state") == "READY":
            break
        time.sleep(0.5)
    record(
        "inference-after-restart",
        "PASS" if isinstance(case, dict) and case.get("draft_source") == "MODEL" and case.get("inference_state") == "READY" else "FAIL",
        str(None if not isinstance(case, dict) else {key: case.get(key) for key in ("draft_source", "inference_state", "model_version_id")}),
    )

    subprocess.run([*COMPOSE, "up", "-d", "--force-recreate", "--no-deps", "backend", "worker", "trainer"], check=False)
    deadline = time.monotonic() + 80
    while time.monotonic() < deadline:
        try:
            status, _payload = request("GET", "/api/v1/health")
        except Exception:
            status = 0
        if status == 200:
            break
        time.sleep(2)
    files = subprocess.run(
        ["docker", "exec", "maidops-isolated-trainer-1", "sh", "-c", "ls /models"],
        capture_output=True,
        text=True,
        check=False,
    )
    record("volume-survives-recreate", "PASS" if ".pt" in files.stdout and ".meta.json" in files.stdout else "FAIL", files.stdout.strip())
    infer2 = create_job("live-after-recreate-1", "lab-dune")
    wait_terminal(infer2, 40)
    case2 = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, payload = request("GET", "/api/v1/error-cases?limit=100")
        if status == 200 and isinstance(payload, dict):
            for item in payload.get("items") or []:
                if isinstance(item, dict) and item.get("job_id") == infer2:
                    case2 = item
        if isinstance(case2, dict) and case2.get("inference_state") == "READY":
            break
        time.sleep(0.5)
    record(
        "inference-after-recreate",
        "PASS" if isinstance(case2, dict) and case2.get("draft_source") == "MODEL" else "FAIL",
        str(None if not isinstance(case2, dict) else case2.get("draft_source")),
    )
    path = ROOT / "infra" / "isolated" / "live_audit_followup.json"
    path.write_text(json.dumps(OUT, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
