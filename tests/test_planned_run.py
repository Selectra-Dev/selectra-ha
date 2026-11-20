"""Planned Run entity behaviour that does not depend on the API payload."""

from __future__ import annotations

from custom_components.selectra.binary_sensor import SelectraPlannedRunSensor


def test_prices_attribute_is_kept_out_of_the_recorder() -> None:
    """The price series is too large for history; the rest is still recorded."""
    unrecorded = SelectraPlannedRunSensor._unrecorded_attributes

    assert "prices" in unrecorded
    for recorded in ("current_price", "current_period_name", "next_change"):
        assert recorded not in unrecorded
