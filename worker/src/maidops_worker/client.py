"""백엔드의 워커 API만 호출한다. 사용자 문자열로 명령을 만들지 않는다."""

from __future__ import annotations

from typing import Any

import httpx


class WorkerApi:
    def __init__(self, base_url: str, worker_id: str, *, client: httpx.Client | None = None) -> None:
        self._worker_id = worker_id
        self._client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=10.0)

    def close(self) -> None:
        self._client.close()

    def heartbeat(self) -> None:
        self._client.post("/api/v1/worker/heartbeat", headers=self._headers())

    def claim(self) -> dict[str, Any] | None:
        response = self._client.post("/api/v1/worker/claim", headers=self._headers())
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        body = response.json()
        return body if isinstance(body, dict) else None

    def heartbeat_job(self, job_id: str) -> bool:
        response = self._client.post(f"/api/v1/worker/jobs/{job_id}/heartbeat", headers=self._headers())
        return response.status_code < 300

    def job_status(self, job_id: str) -> str:
        response = self._client.get(f"/api/v1/jobs/{job_id}")
        response.raise_for_status()
        return str(response.json()["status"])

    def append_events(self, job_id: str, lines: list[tuple[str, str]]) -> None:
        if not lines:
            return
        payload = [{"stream": stream, "text": text} for stream, text in lines]
        response = self._client.post(
            f"/api/v1/worker/jobs/{job_id}/events",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()

    def finish(
        self,
        job_id: str,
        *,
        exit_code: int | None,
        process_exited: bool,
        timed_out: bool,
    ) -> None:
        response = self._client.post(
            f"/api/v1/worker/jobs/{job_id}/finish",
            headers=self._headers(),
            json={
                "exit_code": exit_code,
                "process_exited": process_exited,
                "timed_out": timed_out,
            },
        )
        response.raise_for_status()

    def _headers(self) -> dict[str, str]:
        return {"X-Worker-Id": self._worker_id}
