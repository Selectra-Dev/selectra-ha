"""Price slots are matched to /details lines by key, not by name.

A Swiss contract set up in German got "Tarif haut" slots from /prices and
"Hochtarif" lines from /details: nothing matched, and Planned Run never
turned on. /prices now gives each slot the key of its line, which no
language changes, and the period choice is stored as those keys.
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
    CONF_SELECTED_PERIODS,
    CONF_TOKEN,
    DOMAIN,
    MODE_CLASSIC,
)
from custom_components.selectra.coordinator import (
    _match_lines,
    _selected_to_keys,
)

NOW = "2026-11-05T09:00:00+01:00"

# /details in German: the keys are the lines' own names, the names translated.
FEATURES = [
    {"key": "Standing charge", "name": "Grundgebühr", "type": "subscription"},
    {"key": "High tariff", "name": "Hochtarif", "type": "consumption"},
    {"key": "Low tariff", "name": "Niedertarif", "type": "consumption"},
]


def _slot(name: str, start: str, end: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "price": 0.25, "start": start, "end": end, **extra}


def _swiss_prices(**high: Any) -> dict[str, Any]:
    """Low tariff until 07:00, high tariff after, as /prices names them."""
    return {
        "currency": "CHF",
        "next_update": "2026-11-06T02:00:00+01:00",
        "prices": [
            _slot("Tarif bas", "2026-11-05T00:00:00+01:00", "2026-11-05T07:00:00+01:00",
                  label="Niedertarif", key="Low tariff"),
            _slot("Tarif haut", "2026-11-05T07:00:00+01:00", "2026-11-06T00:00:00+01:00",
                  label="Hochtarif", **high),
        ],
    }


def test_a_slot_takes_the_line_of_its_key() -> None:
    periods = [{"name": "Tarif haut", "label": "Hochtarif", "key": "High tariff"}]

    _match_lines(periods, FEATURES)

    assert periods == [{"name": "Hochtarif", "label": "Hochtarif", "key": "High tariff"}]


def test_a_slot_without_a_key_is_matched_by_its_label_or_name() -> None:
    """Responses from before the API sent keys, cached on disk."""
    periods = [
        {"name": "Tarif haut", "label": "Hochtarif"},
        {"name": "Low tariff"},
        {"name": "Spot"},
    ]

    _match_lines(periods, FEATURES)

    assert [(p["name"], p.get("key")) for p in periods] == [
        ("Hochtarif", "High tariff"),
        ("Niedertarif", "Low tariff"),
        ("Spot", None),
    ]


def test_a_choice_saved_as_names_is_read_as_keys() -> None:
    assert _selected_to_keys(["Hochtarif", "Low tariff", "Gone"], FEATURES) == [
        "High tariff",
        "Low tariff",
        "Gone",
    ]


async def test_planned_run_follows_the_chosen_line_in_any_language(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A choice saved as a German name turns on in the high tariff, and is
    stored as the line's key from then on."""
    freezer.move_to(NOW)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fixture Strom - Doppeltarif",
        data={
            CONF_TOKEN: "fixture-token",
            CONF_QUALIFICATION_INPUTS: {"country_code": "ch", "lang": "de"},
            CONF_MODE: MODE_CLASSIC,
            CONF_CATEGORY: "time_of_use",
            CONF_SELECTED_PERIODS: ["Hochtarif"],
        },
    )
    entry.add_to_hass(hass)

    client = AsyncMock()
    client.get_details = AsyncMock(
        return_value={"category": "time_of_use", "offer": {}, "features": FEATURES}
    )
    client.get_prices = AsyncMock(return_value=_swiss_prices(key="High tariff"))

    with patch(
        "custom_components.selectra.coordinator.SelectraApiClient",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = [
        s
        for s in hass.states.async_all("binary_sensor")
        if s.entity_id.endswith("planned_run")
    ]
    assert [s.state for s in states] == ["on"]
    assert states[0].attributes["current_period_name"] == "Hochtarif"
    keys = [p["key"] for p in states[0].attributes["prices"]]
    assert keys == ["Low tariff", "High tariff"]
    assert entry.data[CONF_SELECTED_PERIODS] == ["High tariff"]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
