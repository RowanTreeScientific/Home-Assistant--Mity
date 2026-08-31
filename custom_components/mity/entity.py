"""Shared base entity for MiTY Research -- gives every entity the same device."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import CONF_INSTANCE_ID, DOMAIN
from .coordinator import MityCoordinator


class MityEntity(Entity):
    """Mixin providing a shared MiTY `DeviceInfo` for all platform entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MityCoordinator) -> None:
        instance_id = coordinator.entry.data[CONF_INSTANCE_ID]
        self._device_unique_id = f"{DOMAIN}_{instance_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(instance_id))},
            name="MiTY Research",
            manufacturer="MiTY",
            model="Citizen Science Device",
            configuration_url="https://www.mi-ty-tre.co.uk",
        )
