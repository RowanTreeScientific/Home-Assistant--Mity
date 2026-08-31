"""MiTY Research binary sensor entities."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import OPT_PAUSED
from .coordinator import MityCoordinator
from .entity import MityEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MiTY binary sensors for a config entry."""
    coordinator: MityCoordinator = entry.runtime_data
    async_add_entities(
        [
            MityConnectedBinarySensor(coordinator),
            MitySubmissionHealthyBinarySensor(coordinator),
            MityPausedBinarySensor(coordinator),
        ]
    )


class MityConnectedBinarySensor(
    MityEntity, CoordinatorEntity[MityCoordinator], BinarySensorEntity
):
    """Whether the last attempted MiTY submission reached the server."""

    _attr_translation_key = "connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: MityCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        MityEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{self._device_unique_id}_connected"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.connected


class MitySubmissionHealthyBinarySensor(
    MityEntity, CoordinatorEntity[MityCoordinator], BinarySensorEntity
):
    """Off when the most recent submission was rejected or errored."""

    _attr_translation_key = "submission_healthy"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: MityCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        MityEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{self._device_unique_id}_submission_healthy"

    @property
    def is_on(self) -> bool:
        # PROBLEM device class: "on" means there IS a problem.
        return self.coordinator.data.last_status in ("rejected", "error")


class MityPausedBinarySensor(
    MityEntity, CoordinatorEntity[MityCoordinator], BinarySensorEntity
):
    """Mirrors the pause switch, for automations that prefer a sensor."""

    _attr_translation_key = "paused"

    def __init__(self, coordinator: MityCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        MityEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{self._device_unique_id}_paused"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.entry.options.get(OPT_PAUSED, False))
