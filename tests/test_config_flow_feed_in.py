"""Config flow coverage for the feed-in tariff sub-flow.

The API asks the opt-in question only for tokens whose team carries the
feature; the integration sends nothing to trigger it, so these tests drive
the flow with the payloads `/planning/qualification` actually returns.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.selectra.const import CONF_QUALIFICATION_INPUTS, DOMAIN

FEED_IN_QUESTION = {
    "type": "select",
    "field": "feed_in",
    "label": "Do you have solar panels?",
    "hint": "We can then show what your exported kWh earn you.",
    "options": {"yes": "Yes", "no": "No"},
}

KWP_QUESTION = {
    "type": "input",
    "field": "feed_in_kwp",
    "label": "Peak power (kWc)",
    "placeholder": "e.g. 6 or 9.5",
}


def _qualify_responses(*responses: dict[str, Any]) -> AsyncMock:
    """Return an async mock replaying the given qualification responses."""
    return AsyncMock(side_effect=list(responses))


async def _start_flow(hass: HomeAssistant, client: AsyncMock) -> dict[str, Any]:
    """Run the token step and return the resulting flow result."""
    with patch(
        "custom_components.selectra.config_flow.SelectraApiClient",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": "fixture-token"}
        )


async def _configure(
    hass: HomeAssistant, flow_id: str, client: AsyncMock, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Submit a step while the patched API client is in place."""
    with patch(
        "custom_components.selectra.config_flow.SelectraApiClient",
        return_value=client,
    ):
        return await hass.config_entries.flow.async_configure(flow_id, user_input)


async def test_feed_in_question_is_shown_with_its_hint(
    hass: HomeAssistant, flat_details: dict[str, Any]
) -> None:
    """The opt-in question renders, and its hint reaches the description."""
    client = AsyncMock()
    client.qualify = _qualify_responses(
        {"done": False, "questions": [FEED_IN_QUESTION], "inputs": {"country_code": "fr"}}
    )
    client.get_details = AsyncMock(return_value=flat_details)

    result = await _start_flow(hass, client)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "qualification"
    assert "feed_in" in result["data_schema"].schema
    labels = result["description_placeholders"]["question_labels"]
    assert "Do you have solar panels?" in labels
    assert "We can then show what your exported kWh earn you." in labels


async def test_opting_in_runs_the_sub_flow_and_stores_its_inputs(
    hass: HomeAssistant, flat_details: dict[str, Any]
) -> None:
    """Answering yes collects the sub-flow answers into the entry."""
    client = AsyncMock()
    client.qualify = _qualify_responses(
        {"done": False, "questions": [FEED_IN_QUESTION], "inputs": {"country_code": "fr"}},
        {
            "done": False,
            "questions": [KWP_QUESTION],
            "inputs": {"country_code": "fr", "feed_in": "yes"},
        },
        {
            "done": True,
            "questions": [],
            "inputs": {
                "country_code": "fr",
                "feed_in": "yes",
                "feed_in_kwp": "9.5",
                "fr_feed_in_tariff_id": 12,
            },
        },
    )
    client.get_details = AsyncMock(return_value=flat_details)

    result = await _start_flow(hass, client)
    result = await _configure(hass, result["flow_id"], client, {"feed_in": "yes"})

    assert result["type"] is FlowResultType.FORM
    assert "feed_in_kwp" in result["data_schema"].schema

    result = await _configure(hass, result["flow_id"], client, {"feed_in_kwp": "9.5"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    inputs = result["data"][CONF_QUALIFICATION_INPUTS]
    assert inputs["feed_in"] == "yes"
    assert inputs["fr_feed_in_tariff_id"] == 12
    assert inputs["feed_in_kwp"] == "9.5"


async def test_opt_in_is_restamped_when_the_api_drops_it(
    hass: HomeAssistant, flat_details: dict[str, Any]
) -> None:
    """Germany resolves the opt-in to an eeg_rate_id and drops the flag.

    /planning/prices only decorates the series with injection rates when it
    sees `feed_in`, so the flow has to put the answer back.
    """
    client = AsyncMock()
    client.qualify = _qualify_responses(
        {"done": False, "questions": [FEED_IN_QUESTION], "inputs": {"country_code": "de"}},
        {"done": True, "questions": [], "inputs": {"country_code": "de", "eeg_rate_id": 7}},
    )
    client.get_details = AsyncMock(return_value=flat_details)

    result = await _start_flow(hass, client)
    result = await _configure(hass, result["flow_id"], client, {"feed_in": "yes"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    inputs = result["data"][CONF_QUALIFICATION_INPUTS]
    assert inputs["eeg_rate_id"] == 7
    assert inputs["feed_in"] == "yes"


async def test_declining_feed_in_finishes_the_flow_untouched(
    hass: HomeAssistant, flat_details: dict[str, Any]
) -> None:
    """Saying no leaves the rest of the qualification exactly as it was."""
    client = AsyncMock()
    client.qualify = _qualify_responses(
        {"done": False, "questions": [FEED_IN_QUESTION], "inputs": {"country_code": "fr"}},
        {"done": True, "questions": [], "inputs": {"country_code": "fr", "feed_in": "no"}},
    )
    client.get_details = AsyncMock(return_value=flat_details)

    result = await _start_flow(hass, client)
    result = await _configure(hass, result["flow_id"], client, {"feed_in": "no"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    inputs = result["data"][CONF_QUALIFICATION_INPUTS]
    assert inputs["feed_in"] == "no"
    assert not any(key.startswith("feed_in_") for key in inputs)
