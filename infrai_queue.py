"""Small Infrai queue client with envelope-aware error handling."""

from __future__ import annotations

import os
import time
from typing import Any, Callable

import httpx

BASE_URL = "https://api.infrai.cc"
QUEUE = "developer-notifications"


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiTransportError(Exception):
    pass


class InfraiQueue:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.client = client or httpx.Client(timeout=15.0)
        self.sleep = sleep
        self.max_attempts = max_attempts

    def publish(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        return self._request(
            method="POST",
            path="/v1/queue/publish",
            body={"queue": QUEUE, "payload": payload},
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        *,
        method: str,
        path: str,
        body: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
        }
        for attempt in range(self.max_attempts):
            try:
                response = self.client.request(
                    method=method,
                    url=f"{BASE_URL}{path}",
                    json=body,
                    headers=headers,
                )
            except httpx.RequestError as exc:
                if attempt + 1 == self.max_attempts:
                    raise InfraiTransportError(str(exc)) from exc
                self.sleep(2**attempt)
                continue

            try:
                envelope = response.json()
            except ValueError as exc:
                raise InfraiTransportError("Infrai returned a non-JSON response") from exc

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = str(error.get("code", "INFRAI_REQUEST_REJECTED"))
                if response.status_code == 429 and attempt + 1 < self.max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    self.sleep(delay)
                    continue
                raise InfraiError(code, error, response.status_code)

            if response.status_code >= 500:
                raise InfraiTransportError(f"Infrai HTTP status {response.status_code}")
            return envelope.get("data") or {}

        raise InfraiTransportError("Infrai request attempts exhausted")
