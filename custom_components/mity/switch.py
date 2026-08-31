"""MiTY Research switch entities."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MityApiError
from .const import CONF_DEVICE_API_KEY, OPT_PAUSED
from .coordinator import MityCoordinator
from .entity import MityEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MiTY pause switch for a config entry."""
    coordinator: MityCoordinator = entry.runtime_data
    async_add_entities([MityPauseSwitch(coordinator)])


class MityPauseSwitch(MityEntity, CoordinatorEntity[MityCoordinator], SwitchEntity):
    """Pause or resume MiTY data contribution.

    Per the API design, MiTY never enforces pause server-side -- this switch
    is what actually stops the coordinator from submitting, and separately
    tells MiTY's own dashboards the device is paused so a quiet device
    doesn't look broken to a researcher.
    """

    _attr_translation_key = "pause_contribution"
    _attr_icon = "mdi:pause-circle"

    def __init__(self, coordinator: MityCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        MityEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{self._device_unique_id}_pause"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.entry.options.get(OPT_PAUSED, False))

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_paused(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_paused(False)

    async def _set_paused(self, paused: bool) -> None:
        entry = self.coordinator.entry
        self.hass.config_entries.async_update_entry(
            entry, options={**entry.options, OPT_PAUSED: paused}
        )
        try:
            await self.coordinator.client.set_paused(
                entry.data[CONF_DEVICE_API_KEY], paused
            )
        except MityApiError:
            _LOGGER.warning(
                "Could not tell MiTY the pause state changed; local pause "
                "still applies and submissions will still stop"
            )
        self.coordinator.async_update_listeners()
