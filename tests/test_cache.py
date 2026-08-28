"""Cache coverage: /details for 48 hours, /prices until `next_update`.

The point of the cache is the calls a restart would otherwise repeat, so
every test here sets an entry up twice and counts what reached the API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.selectra.const import (
    CONF_CATEGORY,
    CONF_MODE,
    CONF_QUALIFICATION_INPUTS,
    CONF_TOKEN,
    DOMAIN,
    MODE_FLAT,
)

INPUTS = {"country_code": "fr", "power_id": 3}
NOW = "2026-08-28T10:00:00+00:00"


def _prices(start: str, end: str, next_update: str) -> dict[str, Any]:
    """A one-period price payload with an explicit deadline."""
    return {
        "currency": "EUR",
        "next_update": next_update,
        "prices": [
            {"name": "base", "price": 0.2516, "start": start, "end": end}
        ],
    }


def _entry(hass: HomeAssistant, inputs: dict[str, Any]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fixture Energy - Solar Plus",
        data={
            CONF_TOKEN: "fixture-token",
            CONF_QUALIFICATION_INPUTS: inputs,
            CONF_MODE: MODE_FLAT,
            CONF_CATEGORY: "flat_rate",
        },
    )
    entry.add_to_hass(hass)
    return entry


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    details: dict[str, Any],
    prices: dict[str, Any],
    *,
    unload: bool = True,
) -> AsyncMock:
    """Set up the entry against a counting API client.

    Unloading afterwards is what makes the next call stand in for a
    restart; pass `unload=False` to keep the entities around and assert
    on the states the cached payload produced.
    """
    client = AsyncMock()
    client.get_details = AsyncMock(return_value=details)
    client.get_prices = AsyncMock(return_value=prices)

    with patch(
        "custom_components.selectra.coordinator.SelectraApiClient",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        if unload:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()

    return client


async def test_details_are_reused_across_restarts(
    hass: HomeAssistant, flat_details: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """A reload within 48 hours doesn't re-fetch the contract details."""
    freezer.move_to(NOW)
    prices = _prices(
        "2026-08-28T00:00:00+00:00",
        "2026-08-29T00:00:00+00:00",
        "2026-08-28T23:00:00+00:00",
    )
    entry = _entry(hass, INPUTS)

    first = await _setup(hass, entry, flat_details, prices)
    assert first.get_details.await_count == 1

    freezer.move_to("2026-08-30T09:00:00+00:00")  # +47h
    second = await _setup(hass, entry, flat_details, prices)
    assert second.get_details.await_count == 0


async def test_details_are_refetched_once_the_48_hours_lapse(
    hass: HomeAssistant, flat_details: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """Past the retention window the details are fetched again."""
    freezer.move_to(NOW)
    prices = _prices(
        "2026-08-28T00:00:00+00:00",
        "2026-08-29T00:00:00+00:00",
        "2026-08-28T23:00:00+00:00",
    )
    entry = _entry(hass, INPUTS)

    await _setup(hass, entry, flat_details, prices)

    freezer.move_to("2026-08-30T11:00:00+00:00")  # +49h
    second = await _setup(hass, entry, flat_details, prices)
    assert second.get_details.await_count == 1


async def test_prices_are_reused_until_next_update(
    hass: HomeAssistant, flat_details: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """Before the deadline the cached series is served as-is."""
    freezer.move_to(NOW)
    prices = _prices(
        "2026-08-28T00:00:00+00:00",
        "2026-08-29T00:00:00+00:00",
        "2026-08-28T20:00:00+00:00",
    )
    entry = _entry(hass, INPUTS)

    first = await _setup(hass, entry, flat_details, prices)
    assert first.get_prices.await_count == 1

    freezer.move_to("2026-08-28T19:00:00+00:00")
    second = await _setup(hass, entry, flat_details, prices, unload=False)
    assert second.get_prices.await_count == 0

    # The cached payload drives the entities exactly like a fresh one.
    state = hass.states.get("sensor.current_price")
    assert state is not None
    assert float(state.state) == 0.2516


async def test_prices_are_refetched_after_next_update(
    hass: HomeAssistant, flat_details: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """Once the deadline passes the API is called again."""
    freezer.move_to(NOW)
    prices = _prices(
        "2026-08-28T00:00:00+00:00",
        "2026-08-29T00:00:00+00:00",
        "2026-08-28T20:00:00+00:00",
    )
    entry = _entry(hass, INPUTS)

    await _setup(hass, entry, flat_details, prices)

    freezer.move_to("2026-08-28T21:00:00+00:00")
    second = await _setup(hass, entry, flat_details, prices)
    assert second.get_prices.await_count == 1


async def test_expired_series_is_refetched_before_its_deadline(
    hass: HomeAssistant, flat_details: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """An unexpired payload whose periods have all run out is not served.

    A flat-rate offer refreshes monthly, so a long outage can leave a
    still-valid deadline over a series that ended days ago. Serving it
    would report `unknown` until that deadline.
    """
    freezer.move_to(NOW)
    prices = _prices(
        "2026-08-28T00:00:00+00:00",
        "2026-08-29T00:00:00+00:00",
        "2026-09-30T02:00:00+00:00",  # a month away
    )
    entry = _entry(hass, INPUTS)

    await _setup(hass, entry, flat_details, prices)

    freezer.move_to("2026-09-05T10:00:00+00:00")  # series long over, deadline not
    second = await _setup(hass, entry, flat_details, prices)
    assert second.get_prices.await_count == 1


async def test_reconfiguring_to_another_contract_misses_the_cache(
    hass: HomeAssistant, flat_details: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """The cache is keyed on the qualification inputs, not just the entry."""
    freezer.move_to(NOW)
    prices = _prices(
        "2026-08-28T00:00:00+00:00",
        "2026-08-29T00:00:00+00:00",
        "2026-08-28T23:00:00+00:00",
    )
    entry = _entry(hass, INPUTS)

    await _setup(hass, entry, flat_details, prices)

    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_QUALIFICATION_INPUTS: {**INPUTS, "offer_id": 99}},
    )
    second = await _setup(hass, entry, flat_details, prices)

    assert second.get_details.await_count == 1
    assert second.get_prices.await_count == 1


async def test_removing_the_entry_deletes_its_cache(
    hass: HomeAssistant,
    flat_details: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
) -> None:
    """No stale store is left behind for a contract the user dropped."""
    freezer.move_to(NOW)
    prices = _prices(
        "2026-08-28T00:00:00+00:00",
        "2026-08-29T00:00:00+00:00",
        "2026-08-28T23:00:00+00:00",
    )
    entry = _entry(hass, INPUTS)
    await _setup(hass, entry, flat_details, prices)

    store_key = f"{DOMAIN}.{entry.entry_id}.cache"
    assert store_key in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert hass_storage.get(store_key) in (None, {})
