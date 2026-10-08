"""MiTY Research button entities."""

from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MityApiError, MityRecordNotInGdvError
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
            MityRecordLinkButton(coordinator),
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


class MityRecordLinkButton(
    MityEntity, CoordinatorEntity[MityCoordinator], ButtonEntity
):
    """Show a single-use link to the participant's own GDV record.

    The link opens the GDV portal already signed in, works once and expires
    within minutes; it appears as a Home Assistant notification (replaced on
    each press) and is never stored by the integration.
    """

    _attr_translation_key = "open_gdv_record"
    _attr_icon = "mdi:shield-account"

    def __init__(self, coordinator: MityCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        MityEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{self._device_unique_id}_gdv_record"

    async def async_press(self) -> None:
        key = self.coordinator.entry.data["device_api_key"]
        notification_id = f"mity_gdv_record_{self.coordinator.entry.entry_id}"
        try:
            result = await self.coordinator.client.record_link(key)
        except MityRecordNotInGdvError:
            persistent_notification.async_create(
                self.hass,
                "This study keeps its records in MiTY, not in the Glass Door "
                "Vault, so there is no GDV record to open.",
                title="MiTY research: your record",
                notification_id=notification_id,
            )
            return
        except MityApiError as err:
            raise HomeAssistantError(
                f"Could not get a link to your record: {err}"
            ) from err
        if not result.link:
            raise HomeAssistantError("The Glass Door Vault did not return a link")
        persistent_notification.async_create(
            self.hass,
            f"[Open your record in the Glass Door Vault]({result.link})\n\n"
            "This link works once and expires within 10 minutes. "
            "Anyone with access to this Home Assistant can see it until then.",
            title="MiTY research: your record",
            notification_id=notification_id,
        )
