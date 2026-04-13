"""Constants for the Selectra integration."""

from __future__ import annotations

from typing import Any

DOMAIN = "selectra"

API_BASE_URL = "https://api.selectra.com/api"

MIN_POLL_INTERVAL_SECONDS = 60
DEFAULT_POLL_INTERVAL_SECONDS = 900  # 15 minutes

MODE_CLASSIC = "classic"
MODE_DYNAMIC = "dynamic"
MODE_FLAT = "flat"

CATEGORY_FLAT_RATE = "flat_rate"
CATEGORY_DYNAMIC = "dynamic"

STRATEGY_CHEAPEST_PERCENT = "cheapest_percent"
STRATEGY_CHEAPEST_CONSECUTIVE = "cheapest_consecutive"

CONF_TOKEN = "token"
CONF_CATEGORY = "category"
CONF_QUALIFICATION_INPUTS = "qualification_inputs"
CONF_MODE = "mode"
CONF_SELECTED_PERIODS = "selected_periods"
CONF_STRATEGY = "strategy"
CONF_STRATEGY_VALUE = "strategy_value"


def resolve_localized_name(value: Any, lang: str = "en") -> str:
    """Resolve a localized name field.

    If value is a dict like {"fr": "Nom"}, return the entry for lang,
    or fall back to the first available value. If value is already a
    string, return it as-is.
    """
    if isinstance(value, dict):
        if lang in value:
            return value[lang]
        if value:
            return next(iter(value.values()))
        return ""
    if isinstance(value, str):
        return value
    return str(value) if value else ""
