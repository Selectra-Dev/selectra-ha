"""Coverage for the v2 /planning/details envelope.

Every country but FR, CH and DE answers in the v2 shape, where features sit
under `supply`. Read as legacy, a time-of-use offer there had no periods to
pick and the period step could not be submitted.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.selectra.api import normalize_details
from custom_components.selectra.const import DOMAIN


def _v2_time_of_use_details() -> dict[str, Any]:
    """A trimmed v2 payload for a Japanese time-of-use offer."""
    return {
        "schema_version": 2,
        "country_code": "jp",
        "category": "time_of_use",
        "offer": {
            "name": "Night Plan",
            "type": "Fixed",
            "provider": {"name": "Fixture Denki", "logo": "https://example.test/l.png"},
        },
        "option": {"name": "Night"},
        "supply": {
            "features": [
                {"key": "base", "name": "Base charge", "type": "subscription"},
                {"key": "day", "name": "Day", "type": "consumption"},
                {"key": "night", "name": "Night", "type": "consumption"},
            ]
        },
        "network": {"name": "Fixture Grid", "features": []},
    }


def test_normalize_details_lifts_v2_keys() -> None:
    details = normalize_details(_v2_time_of_use_details())

    assert [f["key"] for f in details["features"]] == ["base", "day", "night"]
    assert details["offer"]["provider_name"] == "Fixture Denki"
    assert details["offer"]["logo"] == "https://example.test/l.png"
    assert details["distributor"]["name"] == "Fixture Grid"


def test_normalize_details_leaves_legacy_payloads_alone() -> None:
    legacy = {
        "category": "time_of_use",
        "offer": {"name": "Tempo", "provider_name": "EDF"},
        "features": [{"key": "hp", "name": "HP", "type": "consumption"}],
    }

    assert normalize_details(dict(legacy)) == legacy


async def test_select_periods_lists_v2_consumption_features(
    hass: HomeAssistant,
) -> None:
    """The period step offers the v2 consumption features, and submits."""
    client = AsyncMock()
    client.qualify = AsyncMock(
        side_effect=[
            {"done": True, "inputs": {"country_code": "jp", "offer_id": 1}},
        ]
    )
    client.get_details = AsyncMock(
        return_value=normalize_details(_v2_time_of_use_details())
    )

    with patch(
        "custom_components.selectra.config_flow.SelectraApiClient",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": "fixture-token"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_periods"
        selector = result["data_schema"].schema["selected_periods"]
        values = [o["value"] for o in selector.config["options"]]
        assert values == ["Day", "Night"]

        with patch(
            "custom_components.selectra.async_setup_entry", return_value=True
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"selected_periods": ["Night"]}
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fixture Denki - Night Plan"


async def test_select_periods_falls_back_to_keys_for_unnamed_features(
    hass: HomeAssistant,
) -> None:
    """A feature with no display name is listed by its key.

    Australian catalogues leave `display_name` NULL; a `None` option value
    made Home Assistant reject the form, so setup could not go on.
    """
    details = _v2_time_of_use_details()
    for feature in details["supply"]["features"]:
        feature["name"] = None

    client = AsyncMock()
    client.qualify = AsyncMock(
        return_value={"done": True, "inputs": {"country_code": "au", "offer_id": 1}}
    )
    client.get_details = AsyncMock(return_value=normalize_details(details))

    with patch(
        "custom_components.selectra.config_flow.SelectraApiClient",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": "fixture-token"}
        )

    assert result["step_id"] == "select_periods"
    selector = result["data_schema"].schema["selected_periods"]
    assert [o["value"] for o in selector.config["options"]] == ["day", "night"]
