"""실행 중 로그를 감독 루프 밖에서 배치로 보낸다.

감독 루프는 큐에 넣기만 한다. POST의 timeout과 재시도는 이 스레드에만 있다.
같은 batch_id는 서버가 확인하기 전에는 다음 배치로 넘어가지 않는다.
재시도는 그 배치의 전송만 다시 하며, 프로세스를 다시 실행하지 않는다.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any

from maidops_worker.client import BatchRejected
from maidops_worker.masking import mask_secrets


class LogShipper:
    def __init__(
        self,
        api: Any,
        job_id: str,
        *,
        batch_size: int = 8,
        flush_interval: float = 0.25,
        max_buffered_lines: int = 200,
        max_retries: int = 3,
        request_timeout: float = 1.0,
        retry_pause: float = 0.05,
    ) -> None:
        self._api = api
        self._job_id = job_id
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._max_retries = max_retries
        self._request_timeout = request_timeout
        self._retry_pause = retry_pause
        self._lines: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=max_buffered_lines)
        self._stop = threading.Event()
        self._abandon = threading.Event()
        self.incomplete = False
        self.overflow = False
        self._thread = threading.Thread(target=self._run, name=f"maidops-logs-{job_id}", daemon=True)
        self._next_batch = 1

    def start(self) -> None:
        self._thread.start()

    def offer(self, stream: str, text: str) -> None:
        masked = mask_secrets(text)
        if masked.strip() == "":
            return
        try:
            self._lines.put_nowait((stream, masked))
        except queue.Full:
            self.overflow = True
            self.incomplete = True

    def close(self, timeout: float) -> bool:
        self._stop.set()
        self._thread.join(timeout)
        if self._thread.is_alive() or self.overflow:
            self._abandon.set()
            self.incomplete = True
        return not self.incomplete

    def _run(self) -> None:
        pending: tuple[str, list[tuple[str, str]]] | None = None
        buffer: list[tuple[str, str]] = []
        retries = 0
        last_flush = time.monotonic()
        while not self._abandon.is_set():
            try:
                buffer.append(self._lines.get(timeout=0.05))
            except queue.Empty:
                pass
            now = time.monotonic()
            due = pending is not None or len(buffer) >= self._batch_size
            due = due or (bool(buffer) and now - last_flush >= self._flush_interval)
            due = due or (self._stop.is_set() and bool(buffer))
            if not due:
                if self._stop.is_set() and pending is None and not buffer and self._lines.empty():
                    return
                continue
            if pending is None:
                batch_id = f"{self._job_id}-b{self._next_batch}"
                self._next_batch += 1
                pending = (batch_id, list(buffer))
                buffer.clear()
            if self._abandon.is_set():
                self.incomplete = True
                return
            try:
                self._send(pending[0], pending[1])
            except BatchRejected:
                self.incomplete = True
                pending = None
                retries = 0
                last_flush = time.monotonic()
            except Exception:
                retries += 1
                if retries > self._max_retries:
                    self.incomplete = True
                    pending = None
                    retries = 0
                    last_flush = time.monotonic()
                else:
                    time.sleep(self._retry_pause)
            else:
                pending = None
                retries = 0
                last_flush = time.monotonic()
            if self._stop.is_set() and pending is None and not buffer and self._lines.empty():
                return
        self.incomplete = True

    def _send(self, batch_id: str, lines: list[tuple[str, str]]) -> None:
        if self._abandon.is_set():
            raise RuntimeError("로그 전송을 중단했습니다.")
        append_batch = getattr(self._api, "append_batch", None)
        if append_batch is not None:
            append_batch(self._job_id, batch_id, lines, timeout=self._request_timeout)
            return
        self._api.append_events(self._job_id, lines)
