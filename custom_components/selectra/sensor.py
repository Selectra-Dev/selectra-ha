"""Sensor platform for the Selectra integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, resolve_localized_name
from .coordinator import SelectraCoordinator, SelectraData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Selectra sensors from a config entry."""
    coordinator: SelectraCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        SelectraCurrentPriceSensor(coordinator, entry),
        SelectraProviderSensor(coordinator, entry),
        SelectraOfferSensor(coordinator, entry),
        SelectraOptionSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class SelectraBaseSensor(CoordinatorEntity[SelectraCoordinator], SensorEntity):
    """Base class for Selectra sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SelectraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def available(self) -> bool:
        data: SelectraData | None = self.coordinator.data
        if data is not None and data.requalification:
            return False
        return super().available


class SelectraCurrentPriceSensor(SelectraBaseSensor):
    """Sensor showing the current electricity price per kWh."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_translation_key = "current_price"

    def __init__(
        self, coordinator: SelectraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_price"

    @property
    def native_value(self) -> float | None:
        data: SelectraData | None = self.coordinator.data
        if data is None or data.current_period is None:
            return None
        return data.current_period.get("price")

    @property
    def native_unit_of_measurement(self) -> str | None:
        data: SelectraData | None = self.coordinator.data
        if data is None or not data.currency:
            return None
        return f"{data.currency}/kWh"

    @property
    def extra_state_attributes(self) -> dict:
        data: SelectraData | None = self.coordinator.data
        if data is None or data.current_period is None:
            return {}

        attrs: dict = {
            "period_name": data.current_period.get("name"),
        }

        start = data.current_period.get("start")
        end = data.current_period.get("end")
        if start:
            attrs["period_start"] = (
                start.isoformat() if hasattr(start, "isoformat") else start
            )
        if end:
            attrs["period_end"] = (
                end.isoformat() if hasattr(end, "isoformat") else end
            )

        if data.next_update:
            attrs["next_update"] = data.next_update.isoformat()

        return attrs


class SelectraProviderSensor(SelectraBaseSensor):
    """Diagnostic sensor showing the electricity provider name."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "provider"

    def __init__(
        self, coordinator: SelectraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_provider"

    @property
    def native_value(self) -> str | None:
        details = self.coordinator.details
        if not details:
            return None
        lang = self.hass.config.language[:2].lower() if self.hass.config.language else "en"
        return resolve_localized_name(details.get("offer", {}).get("provider_name"), lang)


class SelectraOfferSensor(SelectraBaseSensor):
    """Diagnostic sensor showing the electricity offer name."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "offer"

    def __init__(
        self, coordinator: SelectraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_offer"

    @property
    def native_value(self) -> str | None:
        details = self.coordinator.details
        if not details:
            return None
        lang = self.hass.config.language[:2].lower() if self.hass.config.language else "en"
        return resolve_localized_name(details.get("offer", {}).get("name"), lang)

    @property
    def extra_state_attributes(self) -> dict:
        details = self.coordinator.details
        if not details:
            return {}

        offer = details.get("offer", {})
        option = details.get("option", {})
        distributor = details.get("distributor")
        off_peak = details.get("distributor_off_peak_hours")

        attrs: dict = {
            "category": details.get("category"),
            "offer_type": offer.get("type"),
            "logo_url": offer.get("logo"),
            "option_slug": option.get("slug"),
            "option_description": option.get("description"),
            "period_set_name": option.get("period_set_name"),
            "distributor": distributor.get("name") if distributor else None,
            "tier": details.get("tier"),
            "features": details.get("features", []),
        }

        if off_peak:
            attrs["off_peak_hours_current"] = off_peak.get("current")
            attrs["off_peak_hours_future"] = off_peak.get("future")

        return attrs


class SelectraOptionSensor(SelectraBaseSensor):
    """Diagnostic sensor showing the electricity option name."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "option"

    def __init__(
        self, coordinator: SelectraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_option"

    @property
    def native_value(self) -> str | None:
        details = self.coordinator.details
        if not details:
            return None
        return details.get("option", {}).get("name")
