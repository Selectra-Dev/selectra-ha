"""Config flow for the Selectra integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import SelectraApiClient, SelectraApiError, SelectraAuthError
from .const import (
    CATEGORY_DYNAMIC,
    CATEGORY_FLAT_RATE,
    CONF_CATEGORY,
    CONF_MODE,
    CONF_QUALIFICATION_INPUTS,
    CONF_SELECTED_PERIODS,
    CONF_STRATEGY,
    CONF_STRATEGY_VALUE,
    CONF_TOKEN,
    DOMAIN,
    MODE_CLASSIC,
    MODE_DYNAMIC,
    MODE_FLAT,
    STRATEGY_CHEAPEST_CONSECUTIVE,
    STRATEGY_CHEAPEST_PERCENT,
    resolve_localized_name,
)

_LOGGER = logging.getLogger(__name__)


def _get_ha_language(hass: HomeAssistant) -> str:
    """Get the 2-letter language code from HA config."""
    lang = hass.config.language
    if lang and len(lang) >= 2:
        return lang[:2].lower()
    return "en"


def _build_schema_from_questions(questions: list[dict[str, Any]]) -> vol.Schema:
    """Build a voluptuous schema from API questions using HA selectors."""
    schema: dict = {}
    for question in questions:
        q_type = question.get("type", "text")
        field = question["field"]

        if q_type == "select":
            options = question.get("options", [])
            select_options: list[SelectOptionDict] = []

            if isinstance(options, dict):
                for key, opt_label in options.items():
                    select_options.append(
                        SelectOptionDict(value=str(key), label=opt_label)
                    )
            elif isinstance(options, list):
                for opt in options:
                    if isinstance(opt, dict):
                        select_options.append(
                            SelectOptionDict(
                                value=str(opt.get("value", "")),
                                label=opt.get("label", str(opt.get("value", ""))),
                            )
                        )
                    else:
                        select_options.append(
                            SelectOptionDict(value=str(opt), label=str(opt))
                        )

            schema[vol.Required(field)] = SelectSelector(
                SelectSelectorConfig(options=select_options)
            )

        elif q_type == "checkbox":
            schema[vol.Optional(field, default=False)] = BooleanSelector()

        else:
            schema[vol.Required(field)] = TextSelector()

    return vol.Schema(schema)


def _cast_select_values(
    user_input: dict[str, Any], questions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Cast string values from select fields back to int for _id fields."""
    select_fields = {q["field"] for q in questions if q.get("type") == "select"}
    result: dict[str, Any] = {}
    for key, value in user_input.items():
        if key in select_fields and isinstance(value, str):
            # _id fields should be int, except off_peak_hours_id
            if key.endswith("_id") and key != "off_peak_hours_id":
                try:
                    result[key] = int(value)
                except ValueError:
                    try:
                        result[key] = float(value)
                    except ValueError:
                        result[key] = value
            else:
                result[key] = value
        else:
            result[key] = value
    return result


class SelectraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Selectra."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._token: str = ""
        self._qualification_inputs: dict[str, Any] = {}
        self._questions: list[dict[str, Any]] = []
        self._mode: str = ""
        self._consumption_features: list[dict[str, Any]] = []
        self._details: dict[str, Any] = {}
        self._strategy: str = ""
        self._is_reconfigure: bool = False

    def _get_client(self) -> SelectraApiClient:
        """Create an API client."""
        session = async_get_clientsession(self.hass)
        return SelectraApiClient(self._token, session)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle step 1: API token entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._token = user_input[CONF_TOKEN]
            client = self._get_client()
            lang = _get_ha_language(self.hass)
            try:
                result = await client.qualify({}, lang=lang)
            except SelectraAuthError:
                errors["base"] = "invalid_auth"
            except SelectraApiError:
                errors["base"] = "cannot_connect"
            else:
                self._qualification_inputs = result.get("inputs", {})
                self._questions = result.get("questions", [])

                if result.get("done"):
                    return await self._async_step_detect_mode()

                return await self.async_step_qualification()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_TOKEN): TextSelector()}
            ),
            errors=errors,
            description_placeholders={
                "register_url": "https://api.selectra.com/ha/register",
                "support_email": "support.home-assistant@selectra.info",
            },
        )

    async def async_step_qualification(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle dynamic qualification steps."""
        errors: dict[str, str] = {}

        if user_input is not None:
            previous_inputs = dict(self._qualification_inputs)

            try:
                casted = _cast_select_values(user_input, self._questions)
                self._qualification_inputs.update(casted)

                client = self._get_client()
                lang = _get_ha_language(self.hass)
                result = await client.qualify(self._qualification_inputs, lang=lang)

                if not isinstance(result, dict):
                    self._qualification_inputs = previous_inputs
                    _LOGGER.warning("Unexpected API response: %s", result)
                    errors["base"] = "qualification_error"
                elif result.get("message"):
                    self._qualification_inputs = previous_inputs
                    _LOGGER.warning("Qualification API message: %s", result["message"])
                    errors["base"] = "qualification_error"
                elif result.get("done"):
                    self._qualification_inputs = result.get(
                        "inputs", self._qualification_inputs
                    )
                    return await self._async_step_detect_mode()
                else:
                    self._qualification_inputs = result.get("inputs", {})
                    self._questions = result.get("questions", [])

            except SelectraApiError as err:
                self._qualification_inputs = previous_inputs
                _LOGGER.warning("Qualification API error: %s", err)
                errors["base"] = "qualification_error"

        if not self._questions:
            return self.async_abort(reason="no_questions")

        schema = _build_schema_from_questions(self._questions)

        return self.async_show_form(
            step_id="qualification",
            data_schema=schema,
            errors=errors,
        )

    async def _async_step_detect_mode(self) -> ConfigFlowResult:
        """Detect mode from the category field in the details response."""
        client = self._get_client()

        try:
            self._details = await client.get_details(self._qualification_inputs)
        except SelectraApiError as err:
            _LOGGER.error("Details API error: %s", err)
            return self.async_abort(reason="api_error")

        category = self._details.get("category")

        if category == CATEGORY_FLAT_RATE:
            self._mode = MODE_FLAT
            return await self._create_entry()
        elif category == CATEGORY_DYNAMIC:
            self._mode = MODE_DYNAMIC
            return await self.async_step_strategy()
        else:
            # time_of_use, demand_response, or unknown — classic mode with period selection
            self._mode = MODE_CLASSIC
            features = self._details.get("features", [])
            self._consumption_features = [
                f for f in features if f.get("type") == "consumption"
            ]
            return await self.async_step_select_periods()

    async def async_step_select_periods(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Classic mode: let user select which consumption periods to use."""
        if user_input is not None:
            selected = user_input.get("selected_periods", [])
            return await self._create_entry(selected_periods=selected)

        period_options = [
            SelectOptionDict(
                value=f.get("key", f["name"]),
                label=f["name"],
            )
            for f in self._consumption_features
        ]

        return self.async_show_form(
            step_id="select_periods",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_periods"): SelectSelector(
                        SelectSelectorConfig(
                            options=period_options,
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_strategy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dynamic mode step A: choose strategy."""
        if user_input is not None:
            self._strategy = user_input["strategy"]
            return await self.async_step_strategy_value()

        return self.async_show_form(
            step_id="strategy",
            data_schema=vol.Schema(
                {
                    vol.Required("strategy"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                STRATEGY_CHEAPEST_PERCENT,
                                STRATEGY_CHEAPEST_CONSECUTIVE,
                            ],
                            translation_key="strategy",
                        )
                    )
                }
            ),
        )

    async def async_step_strategy_value(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dynamic mode step B: enter strategy parameter value."""
        errors: dict[str, str] = {}

        if user_input is not None:
            value = user_input.get("strategy_value", 0)
            if isinstance(value, float):
                value = int(value)
            if self._strategy == STRATEGY_CHEAPEST_PERCENT:
                if 1 <= value <= 100:
                    return await self._create_entry(strategy_value=value)
                errors["base"] = "invalid_percent"
            else:
                if 1 <= value <= 24:
                    return await self._create_entry(strategy_value=value)
                errors["base"] = "invalid_hours"

        lang = _get_ha_language(self.hass)
        if self._strategy == STRATEGY_CHEAPEST_PERCENT:
            max_val = 100
            default_val = 30
            value_description = (
                "Pourcentage de la journ\u00e9e \u00e0 couvrir avec les heures les moins ch\u00e8res (1\u2013100)."
                if lang == "fr"
                else "Percentage of the day to cover with the cheapest hours (1\u2013100)."
            )
        else:
            max_val = 24
            default_val = 6
            value_description = (
                "Nombre d'heures cons\u00e9cutives les moins ch\u00e8res \u00e0 s\u00e9lectionner (1\u201324)."
                if lang == "fr"
                else "Number of consecutive cheapest hours to select (1\u201324)."
            )

        return self.async_show_form(
            step_id="strategy_value",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "strategy_value", default=default_val
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=max_val,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
            description_placeholders={"value_description": value_description},
            errors=errors,
        )

    async def _create_entry(
        self,
        selected_periods: list[str] | None = None,
        strategy_value: int | None = None,
    ) -> ConfigFlowResult:
        """Create the config entry with all collected data."""
        data: dict[str, Any] = {
            CONF_TOKEN: self._token,
            CONF_QUALIFICATION_INPUTS: self._qualification_inputs,
            CONF_MODE: self._mode,
            CONF_CATEGORY: self._details.get("category"),
        }

        if self._mode == MODE_CLASSIC:
            data[CONF_SELECTED_PERIODS] = selected_periods or []
        elif self._mode == MODE_DYNAMIC:
            data[CONF_STRATEGY] = self._strategy
            data[CONF_STRATEGY_VALUE] = strategy_value or 0
        # MODE_FLAT: no additional config needed

        # Build title from offer details
        lang = _get_ha_language(self.hass)
        offer = self._details.get("offer", {})
        provider = resolve_localized_name(offer.get("provider_name", "Selectra"), lang)
        offer_name = resolve_localized_name(offer.get("name", ""), lang)
        title = f"{provider} - {offer_name}" if offer_name else provider

        # Build unique ID
        unique_id_parts = [
            str(self._qualification_inputs.get("country_code", "")),
            str(self._qualification_inputs.get("provider_id", "")),
            str(self._qualification_inputs.get("offer_id", "")),
            str(self._qualification_inputs.get("option_id", "")),
            str(self._qualification_inputs.get("power_id", "")),
        ]
        unique_id = "_".join(unique_id_parts)

        if self._is_reconfigure:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                title=title,
                data=data,
            )

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=title, data=data)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration (re-launches qualification)."""
        self._is_reconfigure = True
        self._token = self._get_reconfigure_entry().data[CONF_TOKEN]

        # Kick off qualification
        client = self._get_client()
        lang = _get_ha_language(self.hass)
        try:
            result = await client.qualify({}, lang=lang)
        except SelectraApiError:
            return self.async_abort(reason="cannot_connect")

        self._qualification_inputs = result.get("inputs", {})
        self._questions = result.get("questions", [])

        if result.get("done"):
            return await self._async_step_detect_mode()

        return await self.async_step_qualification()
