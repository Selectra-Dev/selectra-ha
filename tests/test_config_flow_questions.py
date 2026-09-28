"""Config flow coverage for how API questions reach the form.

Every country flow asks for fields strings.json knows nothing about
(tier_id, distributor_id...), and re-asks a question it rejected. These
tests replay the payloads Japan's `/planning/qualification` returns, where
both show up in the first two steps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .test_config_flow_feed_in import _configure, _qualify_responses, _start_flow

TRANSLATIONS = Path(__file__).parent.parent / "custom_components" / "selectra" / "translations"

POSTCODE_QUESTION = {
    "type": "input",
    "validation": "regex:/^\\d{3}-?\\d{4}$/",
    "field": "postcode",
    "label": "郵便番号",
}

DISTRIBUTOR_QUESTION = {
    "type": "select",
    "field": "distributor_id",
    "label": "ご契約の送配電事業者",
    "options": {"12": "東京電力パワーグリッド", "13": "中部電力パワーグリッド"},
}


async def test_untranslated_fields_are_labelled_by_the_api(
    hass: HomeAssistant, flat_details: dict[str, Any]
) -> None:
    """A field with no translation key shows the API label, not its name."""
    client = AsyncMock()
    client.qualify = _qualify_responses(
        {"done": False, "questions": [DISTRIBUTOR_QUESTION], "inputs": {"country_code": "jp"}},
        {"done": True, "questions": [], "inputs": {"country_code": "jp", "distributor_id": 12}},
    )
    client.get_details = AsyncMock(return_value=flat_details)

    result = await _start_flow(hass, client)

    assert "ご契約の送配電事業者" in result["data_schema"].schema
    assert "distributor_id" not in result["data_schema"].schema

    result = await _configure(
        hass, result["flow_id"], client, {"ご契約の送配電事業者": "12"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Submitted under the API field name, with the id cast back to an int.
    assert client.qualify.await_args.args[0]["distributor_id"] == 12


async def test_translated_fields_keep_their_key(
    hass: HomeAssistant, flat_details: dict[str, Any]
) -> None:
    """A field strings.json labels stays keyed on its name."""
    client = AsyncMock()
    client.qualify = _qualify_responses(
        {"done": False, "questions": [POSTCODE_QUESTION], "inputs": {"country_code": "jp"}}
    )

    result = await _start_flow(hass, client)

    assert "postcode" in result["data_schema"].schema


async def test_a_question_error_is_shown(
    hass: HomeAssistant, flat_details: dict[str, Any]
) -> None:
    """The API's reason for re-asking a question reaches the form."""
    client = AsyncMock()
    client.qualify = _qualify_responses(
        {"done": False, "questions": [POSTCODE_QUESTION], "inputs": {"country_code": "jp"}},
        {
            "done": False,
            "questions": [{**POSTCODE_QUESTION, "error": "この郵便番号に対応する送配電事業者が見つかりません。"}],
            "inputs": {"country_code": "jp"},
        },
    )

    result = await _start_flow(hass, client)
    result = await _configure(hass, result["flow_id"], client, {"postcode": "999-9999"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "question_error"}
    assert (
        result["description_placeholders"]["question_error"]
        == "この郵便番号に対応する送配電事業者が見つかりません。"
    )


async def test_a_silently_rejected_answer_is_flagged(
    hass: HomeAssistant, flat_details: dict[str, Any]
) -> None:
    """The same question back with no error still tells the user why."""
    client = AsyncMock()
    client.qualify = _qualify_responses(
        {"done": False, "questions": [POSTCODE_QUESTION], "inputs": {"country_code": "jp"}},
        {"done": False, "questions": [POSTCODE_QUESTION], "inputs": {"country_code": "jp"}},
    )

    result = await _start_flow(hass, client)
    result = await _configure(hass, result["flow_id"], client, {"postcode": "１００－０００１"})

    assert result["errors"] == {"base": "invalid_answer"}


async def test_the_next_question_is_not_an_error(
    hass: HomeAssistant, flat_details: dict[str, Any]
) -> None:
    """Moving on to a new question raises nothing."""
    client = AsyncMock()
    client.qualify = _qualify_responses(
        {"done": False, "questions": [POSTCODE_QUESTION], "inputs": {"country_code": "jp"}},
        {
            "done": False,
            "questions": [DISTRIBUTOR_QUESTION],
            "inputs": {"country_code": "jp", "postcode": "100-0001"},
        },
    )

    result = await _start_flow(hass, client)
    result = await _configure(hass, result["flow_id"], client, {"postcode": "100-0001"})

    assert result["errors"] == {}


def test_every_language_shows_the_question_labels() -> None:
    """Without the placeholder, the API labels never reach the dialog."""
    for path in sorted(TRANSLATIONS.glob("*.json")):
        strings = json.loads(path.read_text(encoding="utf-8"))
        description = strings["config"]["step"]["qualification"]["description"]
        assert "{question_labels}" in description, path.name
        assert strings["config"]["error"]["question_error"] == "{question_error}", path.name
