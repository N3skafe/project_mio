import json
import subprocess
import time
import urllib.request

def request(method, path, body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request("http://127.0.0.1:18080" + path, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
        return response.status, json.loads(raw.decode()) if raw else None

status, payload = request(
    "POST",
    "/api/v1/jobs",
    {"project_id": "trusted-sample", "task_id": "audit-trim"},
    {"Idempotency-Key": "live-c-trim-slow-2"},
)
job_id = payload["id"]
deadline = time.monotonic() + 70
last = {}
while time.monotonic() < deadline:
    _status, last = request("GET", f"/api/v1/jobs/{job_id}")
    if last.get("status") not in {"QUEUED", "RUNNING", "CANCEL_REQUESTED"}:
        break
    time.sleep(0.5)
sql = (
    "SELECT j.status || ' ' || j.termination_reason || ' ' || j.output_truncated::text || ' ' || "
    "j.log_storage_incomplete::text || ' ' || count(e.*) "
    f"FROM jobs j LEFT JOIN job_events e ON e.job_id = j.id WHERE j.id = '{job_id}' GROUP BY j.status, j.termination_reason, j.output_truncated, j.log_storage_incomplete;"
)
completed = subprocess.run(
    ["docker", "exec", "-i", "maidops-isolated-postgres-1", "psql", "-U", "maidops", "-d", "maidops_live_audit", "-t", "-A"],
    input=sql,
    text=True,
    capture_output=True,
    check=False,
)
print(job_id)
print(json.dumps({key: last.get(key) for key in ("status", "termination_reason", "output_truncated", "log_storage_incomplete")}, ensure_ascii=False))
print(completed.stdout.strip() or completed.stderr.strip())
