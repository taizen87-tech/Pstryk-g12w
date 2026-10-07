"""Small async client for Pstryk's documented meter data endpoints."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import API_BASE


class PstrykApiError(Exception):
    """API request, authorization, or response error."""


class PstrykApi:
    def __init__(self, session: ClientSession, api_key: str, shared_state: dict[str, Any]) -> None:
        self._session = session
        self._api_key = api_key
        self._shared_state = shared_state
        self._locks: dict[str, asyncio.Lock] = {}

    async def fetch(self, endpoint: str, resolution: str, start: datetime, end: datetime) -> dict[str, Any]:
        params = {
            "resolution": resolution,
            "window_start": start.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "window_end": end.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "for_tz": "Europe/Warsaw",
        }
        # Pstryk's published examples use both the raw API key and Bearer. Remember
        # the working format across entry reloads and retry only on auth failure.
        preferred = self._shared_state.get("authorization_mode", "raw")
        modes = [preferred, "bearer" if preferred == "raw" else "raw"]
        lock = self._locks.setdefault(endpoint, asyncio.Lock())
        async with lock:
            # The API terms permit at most 3 requests/hour per endpoint. One call
            # every 20 minutes stays within that cap, including manual reloads.
            last = self._shared_state.setdefault("last_request", {}).get(endpoint)
            if last is not None:
                await asyncio.sleep(max(0.0, 1200 - (time.monotonic() - last)))
            for mode in modes:
                authorization = self._api_key if mode == "raw" else f"Bearer {self._api_key}"
                self._shared_state["last_request"][endpoint] = time.monotonic()
                try:
                    async with self._session.get(
                        f"{API_BASE}{endpoint}", params=params,
                        headers={"Authorization": authorization, "Accept": "application/json"},
                        timeout=20,
                    ) as response:
                        if response.status in (401, 403) and mode != modes[-1]:
                            continue
                        response.raise_for_status()
                        payload = await response.json(content_type=None)
                        if not isinstance(payload, dict):
                            raise PstrykApiError("API zwróciło nieoczekiwany format danych")
                        self._shared_state["authorization_mode"] = mode
                        return payload
                except ClientResponseError as err:
                    if err.status in (401, 403) and mode != modes[-1]:
                        continue
                    if err.status in (401, 403):
                        raise PstrykApiError("Nieprawidłowy klucz API lub brak uprawnień") from err
                    if err.status == 429:
                        raise PstrykApiError("Limit zapytań Pstryk został osiągnięty (HTTP 429)") from err
                    raise PstrykApiError(f"Pstryk API zwróciło HTTP {err.status}") from err
                except (ClientError, TimeoutError, ValueError) as err:
                    raise PstrykApiError("Nie można połączyć się z Pstryk API lub odczytać odpowiedzi") from err
        raise PstrykApiError("Nieprawidłowy klucz API")
