"""MiTY Research sensor entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MAX_PARAMETERS
from .coordinator import MityCoordinator, MityData
from .entity import MityEntity


@dataclass(frozen=True, kw_only=True)
class MitySensorDescription(SensorEntityDescription):
    """Describes a MiTY sensor and how to read its value from MityData."""

    value_fn: Callable[[MityData], object] = lambda data: None


SENSOR_DESCRIPTIONS: tuple[MitySensorDescription, ...] = (
    MitySensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:cloud-sync",
        value_fn=lambda data: data.last_status,
    ),
    MitySensorDescription(
        key="last_submission",
        translation_key="last_submission",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_submission_at,
    ),
    MitySensorDescription(
        key="next_submission",
        translation_key="next_submission",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.next_submission_at,
    ),
    MitySensorDescription(
        key="parameters_configured",
        translation_key="parameters_configured",
        icon="mdi:format-list-checks",
        value_fn=lambda data: data.parameters_configured,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MiTY sensors for a config entry."""
    coordinator: MityCoordinator = entry.runtime_data
    async_add_entities(
        MitySensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class MitySensor(MityEntity, CoordinatorEntity[MityCoordinator], SensorEntity):
    """A single read-only MiTY status value."""

    entity_description: MitySensorDescription

    def __init__(
        self, coordinator: MityCoordinator, description: MitySensorDescription
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        MityEntity.__init__(self, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_unique_id}_{description.key}"

    @property
    def native_value(self):
        value = self.entity_description.value_fn(self.coordinator.data)
        if self.entity_description.key == "parameters_configured":
            return f"{value}/{MAX_PARAMETERS}"
        return value
