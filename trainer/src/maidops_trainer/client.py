"""학습기 전용 API. 사용자 입력을 명령으로 만들지 않는다."""

from __future__ import annotations

from typing import Any

import httpx


class TrainerApi:
    def __init__(self, base_url: str, trainer_id: str, *, client: httpx.Client | None = None) -> None:
        self._trainer_id = trainer_id
        self._client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def claim(self) -> dict[str, Any] | None:
        response = self._client.post("/api/v1/trainer/claim", headers=self._headers())
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        body = response.json()
        return body if isinstance(body, dict) else None

    def examples(self, run_id: str) -> list[dict[str, Any]]:
        response = self._client.get(f"/api/v1/trainer/runs/{run_id}/examples", headers=self._headers())
        response.raise_for_status()
        items = response.json()["items"]
        return items if isinstance(items, list) else []

    def heartbeat(self, run_id: str) -> dict[str, Any]:
        response = self._client.post(f"/api/v1/trainer/runs/{run_id}/heartbeat", headers=self._headers())
        response.raise_for_status()
        body = response.json()
        return body if isinstance(body, dict) else {}

    def complete(self, run_id: str, payload: dict[str, Any]) -> None:
        response = self._client.post(
            f"/api/v1/trainer/runs/{run_id}/complete",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()

    def claim_inference(self) -> dict[str, Any] | None:
        response = self._client.post("/api/v1/trainer/inferences/claim", headers=self._headers())
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        body = response.json()
        return body if isinstance(body, dict) else None

    def complete_inference(self, inference_id: str, label: str) -> None:
        response = self._client.post(
            f"/api/v1/trainer/inferences/{inference_id}/complete",
            headers=self._headers(),
            json={"label": label},
        )
        response.raise_for_status()

    def fail_inference(self, inference_id: str, message: str) -> None:
        response = self._client.post(
            f"/api/v1/trainer/inferences/{inference_id}/fail",
            headers=self._headers(),
            json={"message": message[:2000]},
        )
        response.raise_for_status()

    def fail(self, run_id: str, message: str) -> None:
        response = self._client.post(
            f"/api/v1/trainer/runs/{run_id}/fail",
            headers=self._headers(),
            json={"message": message[:2000]},
        )
        response.raise_for_status()

    def _headers(self) -> dict[str, str]:
        return {"X-Trainer-Id": self._trainer_id}
