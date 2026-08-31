"""Diagnostics support for MiTY Research.

Redacts every credential before it can end up in a shared diagnostics
download -- the device API key and rejoin token are exactly the two secrets
section 8.4 of the auto-enrollment design flags as sensitive.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_API_KEY, CONF_REJOIN_TOKEN
from .coordinator import MityCoordinator

TO_REDACT = {CONF_DEVICE_API_KEY, CONF_REJOIN_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a MiTY config entry."""
    coordinator: MityCoordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": dict(entry.options),
        "state": {
            "connected": coordinator.data.connected,
            "last_status": coordinator.data.last_status,
            "last_error": coordinator.data.last_error,
            "last_submission_at": coordinator.data.last_submission_at,
            "next_submission_at": coordinator.data.next_submission_at,
            "parameters_configured": coordinator.data.parameters_configured,
            "last_payload": coordinator.data.last_payload,
        },
    }
