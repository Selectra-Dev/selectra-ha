"""API client for the Selectra Planning API."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp

from .const import API_BASE_URL


def _parse_retry_after(header_value: str | None) -> int | None:
    """Parse an HTTP Retry-After header.

    Per RFC 9110 the value can be either a non-negative integer (seconds)
    or an HTTP-date. Returns the delay in seconds, or None if unparseable.
    """
    if not header_value:
        return None

    value = header_value.strip()
    if value.isdigit():
        return int(value)

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_at is None:
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)

    delta = (retry_at - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(delta))


class SelectraApiError(Exception):
    """Base exception for Selectra API errors."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class SelectraAuthError(SelectraApiError):
    """Authentication error (401/403)."""


class SelectraRequalificationError(SelectraApiError):
    """Raised when the API indicates requalification is needed."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SelectraRateLimitError(SelectraApiError):
    """Raised when the API returns 429 Too Many Requests."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, status=status)
        self.retry_after = retry_after


class SelectraServerError(SelectraApiError):
    """Raised when the API returns a 5xx server error."""


class SelectraApiClient:
    """Client for the Selectra Planning API."""

    def __init__(self, token: str, session: aiohttp.ClientSession) -> None:
        self._token = token
        self._session = session
        self._base_url = API_BASE_URL

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Make an API request."""
        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method, url, json=json_data, params=params, headers=self._headers
            ) as resp:
                if resp.status in (401, 403):
                    raise SelectraAuthError(
                        "Authentication failed. Check your API token.",
                        status=resp.status,
                    )
                if resp.status == 429:
                    retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                    raise SelectraRateLimitError(
                        "Rate limited by the Selectra API.",
                        status=429,
                        retry_after=retry_after,
                    )
                if 500 <= resp.status < 600:
                    raise SelectraServerError(
                        f"Server error {resp.status}",
                        status=resp.status,
                    )
                data = await resp.json()
                if resp.status in (400, 422):
                    message = data.get("message", "Unknown API error")
                    raise SelectraApiError(message, status=resp.status)
                resp.raise_for_status()
                return data
        except aiohttp.ClientError as err:
            raise SelectraApiError(f"API request failed: {err}") from err

    async def qualify(
        self, inputs: dict[str, Any], lang: str | None = None
    ) -> dict[str, Any]:
        """Call POST /planning/qualification with the given inputs.

        Returns the full qualification response containing done, questions, and inputs.
        """
        payload = {**inputs}
        if lang:
            payload["lang"] = lang
        return await self._request("POST", "/planning/qualification", json_data=payload)

    async def get_details(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Call POST /planning/details with qualification inputs.

        Returns offer details including features.
        """
        return await self._request("POST", "/planning/details", json_data=inputs)

    async def get_prices(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Call POST /planning/prices with qualification inputs.

        Returns prices, next_update, currency, and optional requalification_reason.
        """
        data = await self._request("POST", "/planning/prices", json_data=inputs)

        requalification_reason = data.get("requalification_reason")
        if requalification_reason:
            raise SelectraRequalificationError(requalification_reason)

        return data
