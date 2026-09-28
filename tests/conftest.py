"""Shared fixtures for the Selectra integration tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def _period_around_now() -> tuple[str, str, str]:
    """A price period running now, and its next update, as ISO strings.

    Fixed dates only hold on the day they were written: once the period has
    ended, the current price is unknown and the entities have nothing to show.
    """
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat(), (end + timedelta(hours=2)).isoformat()


@pytest.fixture
def prices_with_feed_in() -> dict[str, Any]:
    """A /planning/prices payload decorated with an injection tariff."""
    start, end, next_update = _period_around_now()
    return {
        "currency": "EUR",
        "next_update": next_update,
        "prices": [
            {
                "name": "base",
                "price": 0.2516,
                "start": start,
                "end": end,
                "feed_in_price": 0.1276,
                "feed_in_extra_text": "Vente du surplus",
                "feed_in_yearly_fee_per_kw": 12.5,
            }
        ],
    }


@pytest.fixture
def prices_without_feed_in() -> dict[str, Any]:
    """The same payload for a contract that never opted in."""
    start, end, next_update = _period_around_now()
    return {
        "currency": "EUR",
        "next_update": next_update,
        "prices": [
            {
                "name": "base",
                "price": 0.2516,
                "start": start,
                "end": end,
            }
        ],
    }
