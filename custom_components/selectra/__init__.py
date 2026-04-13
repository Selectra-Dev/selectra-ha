"""The Selectra integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_QUALIFICATION_INPUTS, DOMAIN
from .coordinator import SelectraCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Selectra from a config entry."""
    # Migration : renommer custom_off_peak_hours -> off_peak_hours
    inputs = entry.data.get(CONF_QUALIFICATION_INPUTS, {})
    if "custom_off_peak_hours" in inputs and "off_peak_hours" not in inputs:
        new_inputs = dict(inputs)
        new_inputs["off_peak_hours"] = new_inputs.pop("custom_off_peak_hours")
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_QUALIFICATION_INPUTS: new_inputs},
        )

    coordinator = SelectraCoordinator(hass, entry)

    # Fetch initial details (offer info)
    await coordinator.async_setup()

    # Perform first data refresh
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
