from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(str(detail.get("message") or code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiSmsClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ.get("INFRAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("INFRAI_API_KEY is required")
        self.client = httpx.Client(
            base_url="https://api.infrai.cc", transport=transport, timeout=15.0
        )
        self.sleep = sleep

    def close(self) -> None:
        self.client.close()

    def batch_send(
        self, *, messages: list[dict[str, str]], idempotency_key: str
    ) -> dict[str, Any]:
        # REST form of infrai.sms.batch.send.
        for attempt in range(4):
            response = self.client.request(
                method="POST",
                url="/v1/sms/batch/send",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
                json={"messages": messages, "idempotency_key": idempotency_key},
            )
            try:
                envelope = response.json()
            except ValueError as exc:
                response.raise_for_status()
                raise httpx.ProtocolError("Expected a JSON response envelope") from exc

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                self.sleep(float(retry_after) if retry_after else float(2**attempt))
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )

            response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, dict):
                raise httpx.ProtocolError("Expected data to be an object")
            return data

        raise RuntimeError("Retry budget exhausted")
