"""The MiTY Research integration.

Contributes selected Home Assistant sensor data to the MiTY citizen-science
platform (via the HERD_IOT ingest contract) and, in return, surfaces MiTY's
own connection/submission status back into Home Assistant as entities,
events and services. See README.md for the full picture.
"""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    MityApiClient,
    MityApiError,
    MityConnectionError,
    MityRejoinNotPermittedError,
)
from .const import (
    ACTION_REMOVE_AND_DELETE,
    ACTION_REMOVE_ONLY,
    ATTR_ACTION,
    CONF_BASE_URL,
    CONF_DEVICE_API_KEY,
    CONF_INSTANCE_ID,
    CONF_REJOIN_TOKEN,
    DOMAIN,
    SERVICE_LEAVE_STUDY,
    SERVICE_REJOIN_STUDY,
    SERVICE_SEND_NOW,
)
from .coordinator import MityCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
]

LEAVE_STUDY_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Optional(ATTR_ACTION, default=ACTION_REMOVE_ONLY): vol.In(
            [ACTION_REMOVE_ONLY, ACTION_REMOVE_AND_DELETE]
        ),
    }
)
REJOIN_STUDY_SCHEMA = vol.Schema({vol.Required("entry_id"): cv.string})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MiTY Research from a config entry."""
    session = async_get_clientsession(hass)
    client = MityApiClient(session, entry.data[CONF_BASE_URL])
    coordinator = MityCoordinator(hass, entry, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except MityConnectionError as err:
        raise ConfigEntryNotReady(
            f"Cannot reach MiTY at {entry.data[CONF_BASE_URL]}"
        ) from err

    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a MiTY Research config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Best-effort withdraw from the study when the entry is deleted.

    Deleting a MiTY integration entry from Home Assistant and leaving its
    study are two different things server-side -- simply removing the
    entry would otherwise leave an orphaned device MiTY still considers
    active. Default to the least destructive withdrawal ("remove_only",
    keeping any already-submitted data) so a participant who just wants
    this study gone from Home Assistant isn't silently left enrolled.
    Failures here are logged, not raised -- the entry is being deleted
    either way, and a participant who wants to guarantee withdrawal
    happened can call `mity.leave_study` explicitly beforehand and check
    the result.
    """
    session = async_get_clientsession(hass)
    client = MityApiClient(session, entry.data[CONF_BASE_URL])
    try:
        await client.remove(entry.data[CONF_DEVICE_API_KEY], ACTION_REMOVE_ONLY)
    except MityApiError:
        _LOGGER.warning(
            "Could not confirm MiTY withdrawal for removed entry %s; "
            "the device may still show as active on the MiTY platform",
            entry.entry_id,
        )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-apply the submission interval when options change."""
    coordinator: MityCoordinator = entry.runtime_data
    coordinator.apply_new_interval()


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SEND_NOW):
        return

    async def _handle_send_now(call: ServiceCall) -> None:
        coordinator = _coordinator_for(hass, call.data["entry_id"])
        await coordinator.submit_now()

    async def _handle_leave_study(call: ServiceCall) -> None:
        coordinator = _coordinator_for(hass, call.data["entry_id"])
        entry = coordinator.entry
        try:
            result = await coordinator.client.remove(
                entry.data[CONF_DEVICE_API_KEY], call.data[ATTR_ACTION]
            )
        except MityApiError:
            _LOGGER.exception(
                "Failed to leave MiTY study for entry %s", entry.entry_id
            )
            return
        _LOGGER.info(
            "Left MiTY study (entry %s): "
            "data_will_be_deleted=%s deleted_immediately=%s",
            entry.entry_id,
            result.data_will_be_deleted,
            result.deleted_immediately,
        )
        coordinator.data.connected = False
        coordinator.data.last_status = "withdrawn"
        coordinator.async_update_listeners()

    async def _handle_rejoin_study(call: ServiceCall) -> None:
        coordinator = _coordinator_for(hass, call.data["entry_id"])
        entry = coordinator.entry
        try:
            result = await coordinator.client.rejoin(entry.data[CONF_REJOIN_TOKEN])
        except MityRejoinNotPermittedError:
            _LOGGER.error(
                "This trial requires a new enrollment after leaving; "
                "remove and re-add the MiTY integration to rejoin"
            )
            return
        except MityApiError:
            _LOGGER.exception(
                "Failed to rejoin MiTY study for entry %s", entry.entry_id
            )
            return

        new_data = {
            **entry.data,
            CONF_INSTANCE_ID: result.instance_id,
            CONF_DEVICE_API_KEY: result.device_api_key,
            CONF_REJOIN_TOKEN: result.rejoin_token,
        }
        hass.config_entries.async_update_entry(entry, data=new_data)
        coordinator.data.last_status = None
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_NOW, _handle_send_now, schema=REJOIN_STUDY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_LEAVE_STUDY, _handle_leave_study, schema=LEAVE_STUDY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REJOIN_STUDY, _handle_rejoin_study, schema=REJOIN_STUDY_SCHEMA
    )


def _coordinator_for(hass: HomeAssistant, entry_id: str) -> MityCoordinator:
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
    if coordinator is None:
        raise ValueError(f"No MiTY config entry with id {entry_id}")
    return coordinator
