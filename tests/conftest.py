"""Shared fixtures for the Selectra integration tests."""

from __future__ import annotations

from typing import Any

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load the integration from custom_components/."""
    return


@pytest.fixture
def flat_details() -> dict[str, Any]:
    """A minimal /planning/details payload for a flat-rate offer.

    Flat rate keeps the config flow short: qualification is followed
    straight by entry creation, with no period or strategy step.
    """
    return {
        "category": "flat_rate",
        "offer": {"name": {"en": "Solar Plus"}, "provider_name": "Fixture Energy"},
        "option": {"name": "Base"},
        "features": [],
    }


@pytest.fixture
def prices_with_feed_in() -> dict[str, Any]:
    """A /planning/prices payload decorated with an injection tariff."""
    return {
        "currency": "EUR",
        "next_update": "2026-08-29T02:00:00+02:00",
        "prices": [
            {
                "name": "base",
                "price": 0.2516,
                "start": "2026-08-28T00:00:00+02:00",
                "end": "2026-08-29T00:00:00+02:00",
                "feed_in_price": 0.1276,
                "feed_in_extra_text": "Vente du surplus",
                "feed_in_yearly_fee_per_kw": 12.5,
            }
        ],
    }


@pytest.fixture
def prices_without_feed_in() -> dict[str, Any]:
    """The same payload for a contract that never opted in."""
    return {
        "currency": "EUR",
        "next_update": "2026-08-29T02:00:00+02:00",
        "prices": [
            {
                "name": "base",
                "price": 0.2516,
                "start": "2026-08-28T00:00:00+02:00",
                "end": "2026-08-29T00:00:00+02:00",
            }
        ],
    }
