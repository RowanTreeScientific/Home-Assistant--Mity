"""MiTY Research button entities."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MityCoordinator
from .entity import MityEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MiTY buttons for a config entry."""
    coordinator: MityCoordinator = entry.runtime_data
    async_add_entities(
        [
            MitySendNowButton(coordinator),
            MityRefreshButton(coordinator),
        ]
    )


class MitySendNowButton(MityEntity, CoordinatorEntity[MityCoordinator], ButtonEntity):
    """Submit the currently mapped parameters to MiTY immediately."""

    _attr_translation_key = "send_data_now"
    _attr_icon = "mdi:send"

    def __init__(self, coordinator: MityCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        MityEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{self._device_unique_id}_send_now"

    async def async_press(self) -> None:
        await self.coordinator.submit_now()


class MityRefreshButton(MityEntity, CoordinatorEntity[MityCoordinator], ButtonEntity):
    """Force a coordinator refresh, e.g. after changing entity mapping."""

    _attr_translation_key = "refresh_configuration"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: MityCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        MityEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{self._device_unique_id}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
