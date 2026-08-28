"""Constants for the Selectra integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

DOMAIN = "selectra"

API_BASE_URL = "https://api.selectra.com/api"

MIN_POLL_INTERVAL_SECONDS = 60
DEFAULT_POLL_INTERVAL_SECONDS = 900  # 15 minutes

# Cached responses, keyed by endpoint. Details describe the contract and
# barely move; prices carry their own deadline in `next_update`.
CACHE_DETAILS = "details"
CACHE_PRICES = "prices"
DETAILS_CACHE_TTL = timedelta(hours=48)

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

# Feed-in (injection) tariffs. The API asks the opt-in question only when the
# token's team carries the feature; every field it then collects, and every key
# it decorates the price rows with, shares this prefix.
FEED_IN_FIELD = "feed_in"
FEED_IN_PREFIX = "feed_in"
FEED_IN_PRICE_KEY = "feed_in_price"

# Germany resolves the opt-in to an EEG rate id instead of echoing `feed_in`,
# so it is the only marker of an opted-in German entry.
FEED_IN_RATE_ID_FIELD = "eeg_rate_id"


def has_feed_in_opt_in(inputs: dict[str, Any]) -> bool:
    """Tell whether qualification inputs describe a feed-in opt-in.

    True when the user answered the opt-in question with "yes", when a
    country sub-flow resolved a rate id, or when any feed-in field was
    collected along the way.
    """
    if inputs.get(FEED_IN_FIELD) == "yes":
        return True
    if inputs.get(FEED_IN_RATE_ID_FIELD) is not None:
        return True
    return any(key.startswith(f"{FEED_IN_PREFIX}_") for key in inputs)


def extract_feed_in_fields(source: dict[str, Any]) -> dict[str, Any]:
    """Pull every feed-in key out of an API price row.

    The set of decorations differs per country (rate, fees, scheme, band,
    free-form conditions...) and grows over time, so anything the API
    prefixes with `feed_in` is carried through rather than allow-listed.
    """
    return {
        key: value
        for key, value in source.items()
        if key.startswith(FEED_IN_PREFIX)
    }


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
