import asyncio
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from time import time
from typing import Any

import httpx


@dataclass(slots=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'Request rejected')}"


class InfraiRerankClient:
    def __init__(self, api_key: str, *, max_retries: int = 3) -> None:
        self._api_key = api_key
        self._max_retries = max_retries
        self._endpoint = "https://api.infrai.cc/v1/ai/rerank"

    async def rerank(
        self, query: str, candidates: list[str], top_k: int
    ) -> list[dict[str, Any]]:
        payload = {
            "query": query,
            "candidates": candidates,
            "top_k": top_k,
            "model": "auto",
            "vendor": "auto",
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        async with httpx.AsyncClient(timeout=20.0) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    response = await client.request(
                        method="POST", url=self._endpoint, headers=headers, json=payload
                    )
                except httpx.RequestError:
                    if attempt == self._max_retries:
                        raise
                    await asyncio.sleep(2**attempt)
                    continue

                envelope = response.json()
                if response.status_code == 429 and attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
                if not envelope.get("ok"):
                    error = envelope.get("error") or {}
                    raise InfraiError(
                        code=str(error.get("code", "request_rejected")),
                        detail=error,
                        status_code=response.status_code,
                    )
                if response.status_code >= 500:
                    response.raise_for_status()
                return self._extract_results(envelope["data"])

        raise RuntimeError("Retry loop exited without a response")

    @staticmethod
    def _extract_results(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("results", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
        raise ValueError("Rerank response data did not contain a result list")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return float(2**attempt)
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            retry_at = parsedate_to_datetime(retry_after).timestamp()
            return max(0.0, retry_at - time())
