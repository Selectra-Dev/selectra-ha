"""Binary sensor platform for the Selectra integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SelectraCoordinator, SelectraData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Selectra binary sensor from a config entry."""
    coordinator: SelectraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SelectraPlannedRunSensor(coordinator, entry)])


class SelectraPlannedRunSensor(
    CoordinatorEntity[SelectraCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether now is a good time to run devices."""

    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_has_entity_name = True
    _attr_translation_key = "planned_run"

    def __init__(
        self, coordinator: SelectraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_planned_run"

    @property
    def is_on(self) -> bool | None:
        """Return true if current period is optimal for running devices."""
        data: SelectraData | None = self.coordinator.data
        if data is None or data.requalification:
            return None
        return data.binary_state

    @property
    def available(self) -> bool:
        """Return False if requalification is needed."""
        data: SelectraData | None = self.coordinator.data
        if data is not None and data.requalification:
            return False
        return super().available

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        data: SelectraData | None = self.coordinator.data
        if data is None:
            return {}

        attrs: dict = {
            "mode": self.coordinator.mode,
            "category": self.coordinator.category,
        }

        if data.current_period:
            attrs["current_period_name"] = data.current_period.get("name")
            attrs["current_price"] = data.current_period.get("price")

        if data.currency:
            attrs["currency"] = data.currency

        if data.next_change:
            attrs["next_change"] = data.next_change.isoformat()

        # Build prices list for attribute
        prices_attr = []
        for p in data.prices:
            prices_attr.append(
                {
                    "name": p.get("name", ""),
                    "price": p.get("price", 0.0),
                    "start": p["start"].isoformat()
                    if hasattr(p["start"], "isoformat")
                    else p["start"],
                    "end": p["end"].isoformat()
                    if hasattr(p["end"], "isoformat")
                    else p["end"],
                    "is_active": p.get("is_active", False),
                }
            )
        attrs["prices"] = prices_attr

        return attrs
