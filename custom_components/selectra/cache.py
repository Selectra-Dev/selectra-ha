"""Persistent response cache for the Selectra API.

Both planning endpoints have a known shelf life. `/planning/details`
describes the contract itself — offer, option, distributor, features — and
barely moves from one day to the next. `/planning/prices` carries its own
deadline in `next_update`, the moment the API says it will have something
new to say.

The cache lives on disk (Home Assistant's `Store`) rather than in memory,
because the calls worth saving are the ones a restart would otherwise
repeat: `/planning/details` is fetched on every entry setup, and the first
price poll fires as soon as the entry loads.

Each entry gets its own store, keyed by a fingerprint of the qualification
inputs the response was fetched for — reconfiguring to another contract
misses the cache instead of serving the previous one's data.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


def _fingerprint(inputs: dict[str, Any]) -> str:
    """Fingerprint the qualification inputs a response was fetched for."""
    canonical = json.dumps(inputs, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize a deadline to an aware UTC datetime."""
    if value is None:
        return None
    if value.tzinfo is None:
        return dt_util.as_utc(value)
    return value.astimezone(dt_util.UTC)


class SelectraCache:
    """On-disk cache of the planning responses for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.cache"
        )
        self._data: dict[str, Any] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Read the cache from disk. Repeated calls are no-ops."""
        if self._loaded:
            return
        stored = await self._store.async_load()
        self._data = stored if isinstance(stored, dict) else {}
        self._loaded = True

    def get(self, endpoint: str, inputs: dict[str, Any]) -> dict[str, Any] | None:
        """Return a cached response, or None if there is nothing usable.

        A miss is the normal outcome for an expired deadline, a different
        contract, or a store written by a version that shaped things
        differently — every one of them just means "call the API".
        """
        entry = self._data.get(endpoint)
        if not isinstance(entry, dict):
            return None

        if entry.get("fingerprint") != _fingerprint(inputs):
            return None

        expires_at = _as_utc(dt_util.parse_datetime(str(entry.get("expires_at"))))
        if expires_at is None or expires_at <= dt_util.utcnow():
            return None

        payload = entry.get("payload")
        if not isinstance(payload, dict):
            return None

        _LOGGER.debug(
            "Serving %s from cache, valid until %s", endpoint, expires_at.isoformat()
        )
        return payload

    async def async_store(
        self,
        endpoint: str,
        inputs: dict[str, Any],
        payload: dict[str, Any],
        expires_at: datetime | None,
    ) -> None:
        """Cache a response until `expires_at`.

        A deadline that is missing or already past means the response has
        nothing left to give, so it is not written at all.
        """
        deadline = _as_utc(expires_at)
        if deadline is None or deadline <= dt_util.utcnow():
            return

        self._data[endpoint] = {
            "fingerprint": _fingerprint(inputs),
            "expires_at": deadline.isoformat(),
            "payload": payload,
        }
        await self._store.async_save(self._data)
        _LOGGER.debug("Cached %s until %s", endpoint, deadline.isoformat())

    async def async_remove(self) -> None:
        """Delete the store, for when the config entry goes away."""
        await self._store.async_remove()
        self._data = {}
        self._loaded = True
