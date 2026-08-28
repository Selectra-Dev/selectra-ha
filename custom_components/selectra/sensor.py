"""Sensor platform for the Selectra integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_QUALIFICATION_INPUTS,
    DOMAIN,
    FEED_IN_PRICE_KEY,
    extract_feed_in_fields,
    has_feed_in_opt_in,
    resolve_localized_name,
)
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

    # Feed-in tariffs are optional: the sensor is only worth creating for a
    # contract that qualified with an injection tariff. Reading the opt-in
    # from the stored inputs (rather than from the current payload alone)
    # keeps the entity stable across restarts and days without a rate.
    if _entry_has_feed_in(coordinator, entry):
        entities.append(SelectraFeedInPriceSensor(coordinator, entry))

    async_add_entities(entities)


def _entry_has_feed_in(
    coordinator: SelectraCoordinator, entry: ConfigEntry
) -> bool:
    """Tell whether this entry carries a feed-in tariff."""
    if has_feed_in_opt_in(entry.data.get(CONF_QUALIFICATION_INPUTS, {})):
        return True
    data: SelectraData | None = coordinator.data
    return data is not None and data.has_feed_in


class SelectraBaseSensor(CoordinatorEntity[SelectraCoordinator], SensorEntity):
    """Base class for Selectra sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SelectraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        data: SelectraData | None = self.coordinator.data
        if data is not None and data.requalification:
            return False
        return super().available


class SelectraCurrentPriceSensor(SelectraBaseSensor):
    """Sensor showing the current electricity price per kWh."""

    _attr_state_class = SensorStateClass.MEASUREMENT
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


class SelectraFeedInPriceSensor(SelectraBaseSensor):
    """Sensor showing the current feed-in (injection) tariff per kWh."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "feed_in_price"

    def __init__(
        self, coordinator: SelectraCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_feed_in_price"

    @property
    def native_value(self) -> float | None:
        data: SelectraData | None = self.coordinator.data
        if data is None or data.current_period is None:
            return None
        return data.current_period.get(FEED_IN_PRICE_KEY)

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

        # Every feed-in decoration except the rate itself, which is the state:
        # grid fees, scheme, band, and the free-form conditions some markets
        # attach. Which ones are present depends on the country.
        attrs: dict = {
            key: value
            for key, value in extract_feed_in_fields(data.current_period).items()
            if key != FEED_IN_PRICE_KEY
        }
        attrs["period_name"] = data.current_period.get("name")

        return attrs
