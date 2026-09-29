"""Replay real API exchanges through the whole integration.

tests/fixtures/api/<scenario>.json holds a qualification walk, /details and
/prices exactly as the Selectra API answered them (recorded by
scripts/record_api_fixtures.py). Only the HTTP layer is faked: the API
client, config flow, coordinator and entities all run for real, so the
integration is checked against what the API sends rather than against what
it was written to expect.

For every scenario, a user must be able to finish the setup dialog, and the
entry must come up with a real provider name and a current price.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.selectra.const import (
    DOMAIN,
    STRATEGY_CHEAPEST_PERCENT,
    resolve_localized_name,
)

FIXTURES = Path(__file__).parent / "fixtures" / "api"
RECORDINGS = sorted(p for p in FIXTURES.glob("*.json") if p.name != "scenarios.json")


def _shift_datetimes(value: Any, delta: timedelta) -> Any:
    """Move every ISO datetime string in a payload by `delta`."""
    if isinstance(value, dict):
        return {k: _shift_datetimes(v, delta) for k, v in value.items()}
    if isinstance(value, list):
        return [_shift_datetimes(v, delta) for v in value]
    if isinstance(value, str) and len(value) >= 19 and value[10:11] == "T":
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return (parsed + delta).isoformat()
    return value


def _current_prices(prices: dict[str, Any]) -> dict[str, Any]:
    """Move a recorded /prices payload so that it covers the present.

    A recording is only valid for the day it was made. The shift is a whole
    number of days, so every period keeps its time of day.
    """
    periods = prices.get("prices") or []
    starts = [datetime.fromisoformat(p["start"].replace("Z", "+00:00")) for p in periods]
    ends = [datetime.fromisoformat(p["end"].replace("Z", "+00:00")) for p in periods]
    if not starts:
        return prices

    now = dt_util.utcnow()
    base = (now.date() - min(starts).date()).days
    for days in (base, base - 1, base + 1):
        delta = timedelta(days=days)
        if min(starts) + delta <= now < max(ends) + delta:
            return _shift_datetimes(prices, delta)
    return _shift_datetimes(prices, timedelta(days=base))


class _ApiPlayer:
    """Answer SelectraApiClient._request from a recording."""

    def __init__(self, recording: dict[str, Any]) -> None:
        self._steps = recording["qualification"]
        self._details = recording["details"]["response"]
        self._prices = _current_prices(recording["prices"]["response"])
        self.qualification_calls = 0

    async def request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        payload = json_data or {}
        if path == "/planning/qualification":
            if self.qualification_calls >= len(self._steps):
                pytest.fail("the flow called /qualification more often than recorded")
            step = self._steps[self.qualification_calls]
            self.qualification_calls += 1
            # The flow must send what the recorded walk sent, or the recorded
            # answer does not apply to it.
            sent = {k: payload.get(k) for k in step["request"]}
            assert json.dumps(sent, sort_keys=True) == json.dumps(
                step["request"], sort_keys=True
            ), f"qualification call {self.qualification_calls} differs from the recording"
            return json.loads(json.dumps(step["response"]))
        if path == "/planning/details":
            return json.loads(json.dumps(self._details))
        if path == "/planning/prices":
            return json.loads(json.dumps(self._prices))
        pytest.fail(f"unexpected API call {method} {path}")


def _form_answers(result: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    """Fill a qualification form with the answers the recorded walk gave.

    The form keys follow the question order (some are the API label, not the
    field name), so questions and keys are paired by position.
    """
    questions = step["response"]["questions"]
    keys = [str(key) for key in result["data_schema"].schema]
    assert len(keys) == len(questions), "the form does not show every question"

    answers: dict[str, Any] = {}
    for key, question in zip(keys, questions):
        value = step["answers"][question["field"]]
        answers[key] = value if question.get("type") == "checkbox" else str(value)
    return answers


def _expected_provider(details: dict[str, Any], lang: str) -> str | None:
    offer = details.get("offer") or {}
    name = offer.get("provider_name")
    if name is None and isinstance(offer.get("provider"), dict):
        name = offer["provider"].get("name")
    return resolve_localized_name(name, lang) if name else None


@pytest.mark.parametrize("path", RECORDINGS, ids=[p.stem for p in RECORDINGS])
async def test_recorded_scenario_sets_up(hass: HomeAssistant, path: Path) -> None:
    recording = json.loads(path.read_text(encoding="utf-8"))
    lang = recording["lang"]
    details = recording["details"]["response"]
    hass.config.language = lang
    await hass.config.async_set_time_zone(recording["time_zone"])

    expected_category = recording["expect"].get("category")
    if expected_category:
        # A scenario that drifted to another kind of offer no longer tests
        # what it was written for: re-point it in scenarios.json.
        assert details.get("category") == expected_category

    player = _ApiPlayer(recording)
    with patch(
        "custom_components.selectra.api.SelectraApiClient._request",
        new=player.request,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": "fixture-token"}
        )

        for step in recording["qualification"][:-1]:
            assert result["type"] is FlowResultType.FORM, result
            assert result["step_id"] == "qualification", result
            assert not result.get("errors"), result["errors"]
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], _form_answers(result, step)
            )

        assert player.qualification_calls == len(recording["qualification"])

        selectable: list[str] = []
        if result.get("step_id") == "select_periods":
            selector = result["data_schema"].schema["selected_periods"]
            options = [o["value"] for o in selector.config["options"]]
            # The bug a Japanese user hit: nothing to tick, so no way through.
            assert options, "the period step offers nothing to select"
            selectable = options
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"selected_periods": options[:1]}
            )
        elif result.get("step_id") == "strategy":
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"strategy": STRATEGY_CHEAPEST_PERCENT}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"strategy_value": 30}
            )

        assert result["type"] is FlowResultType.CREATE_ENTRY, result
        await hass.async_block_till_done()

        provider = _expected_provider(details, lang)
        assert provider, "the details carry no provider name"
        assert result["title"].startswith(provider)

        entry = result["result"]
        assert entry.state is ConfigEntryState.LOADED

        # Entity ids are built from names translated into the HA language
        # (sensor.prix_actuel in French), so look entities up by unique id.
        registry = er.async_get(hass)

        def state_of(domain: str, key: str) -> str | None:
            entity_id = registry.async_get_entity_id(
                domain, DOMAIN, f"{entry.entry_id}_{key}"
            )
            assert entity_id, f"no {key} entity"
            state = hass.states.get(entity_id)
            return state.state if state else None

        price = state_of("sensor", "current_price")
        assert price not in (None, STATE_UNKNOWN, STATE_UNAVAILABLE), price
        float(price)

        assert state_of("sensor", "provider") == provider
        for key in ("offer", "option"):
            assert state_of("sensor", key) not in (
                None,
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ), key

        assert state_of("binary_sensor", "planned_run") in ("on", "off")

        if selectable:
            # Planned Run turns on when the current period is one the user
            # ticked. A choice matching no priced period can never do that.
            entity_id = registry.async_get_entity_id(
                "binary_sensor", DOMAIN, f"{entry.entry_id}_planned_run"
            )
            priced = {p["name"] for p in hass.states.get(entity_id).attributes["prices"]}
            assert priced & set(selectable), (
                f"no selectable period {selectable} matches a priced one {priced}"
            )

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
