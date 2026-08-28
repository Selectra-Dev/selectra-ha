"""Entity coverage for feed-in tariffs, from a real config entry setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

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

FEED_IN_SENSOR = "sensor.feed_in_price"
PLANNED_RUN = "binary_sensor.planned_run"

OPTED_IN_INPUTS = {
    "country_code": "fr",
    "feed_in": "yes",
    "fr_feed_in_tariff_id": 12,
}
PLAIN_INPUTS = {"country_code": "fr", "power_id": 3}


async def _setup(
    hass: HomeAssistant,
    inputs: dict[str, Any],
    details: dict[str, Any],
    prices: dict[str, Any],
) -> MockConfigEntry:
    """Set up a flat-rate entry against a mocked Selectra API."""
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

    client = AsyncMock()
    client.get_details = AsyncMock(return_value=details)
    client.get_prices = AsyncMock(return_value=prices)

    with patch(
        "custom_components.selectra.coordinator.SelectraApiClient",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_feed_in_sensor_holds_the_rate_and_its_extras(
    hass: HomeAssistant,
    flat_details: dict[str, Any],
    prices_with_feed_in: dict[str, Any],
) -> None:
    """The sensor state is the injection rate; the extras become attributes."""
    await _setup(hass, OPTED_IN_INPUTS, flat_details, prices_with_feed_in)

    state = hass.states.get(FEED_IN_SENSOR)
    assert state is not None
    assert float(state.state) == 0.1276
    assert state.attributes["unit_of_measurement"] == "EUR/kWh"
    assert state.attributes["feed_in_extra_text"] == "Vente du surplus"
    assert state.attributes["feed_in_yearly_fee_per_kw"] == 12.5
    # The rate is the state, not an attribute.
    assert "feed_in_price" not in state.attributes


async def test_no_feed_in_sensor_without_an_opt_in(
    hass: HomeAssistant,
    flat_details: dict[str, Any],
    prices_without_feed_in: dict[str, Any],
) -> None:
    """A contract that never opted in gets no feed-in entity at all."""
    await _setup(hass, PLAIN_INPUTS, flat_details, prices_without_feed_in)

    assert hass.states.get(FEED_IN_SENSOR) is None
    assert hass.states.get("sensor.current_price") is not None


async def test_prices_attribute_carries_the_feed_in_series(
    hass: HomeAssistant,
    flat_details: dict[str, Any],
    prices_with_feed_in: dict[str, Any],
) -> None:
    """Charts can plot consumption and injection from the same attribute."""
    await _setup(hass, OPTED_IN_INPUTS, flat_details, prices_with_feed_in)

    state = hass.states.get(PLANNED_RUN)
    assert state is not None
    assert state.attributes["prices"][0]["feed_in_price"] == 0.1276
    assert state.attributes["feed_in_price"] == 0.1276


async def test_prices_attribute_stays_clean_without_feed_in(
    hass: HomeAssistant,
    flat_details: dict[str, Any],
    prices_without_feed_in: dict[str, Any],
) -> None:
    """No opt-in means no feed-in keys anywhere in the payload."""
    await _setup(hass, PLAIN_INPUTS, flat_details, prices_without_feed_in)

    state = hass.states.get(PLANNED_RUN)
    assert state is not None
    assert not any(key.startswith("feed_in") for key in state.attributes["prices"][0])
    assert not any(key.startswith("feed_in") for key in state.attributes)
