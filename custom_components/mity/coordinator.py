"""DataUpdateCoordinator for the MiTY Research integration.

Owns the periodic /v1/ingest submission cycle and tracks the last-known
connection/submission state that every sensor, binary_sensor and button
entity reads from.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import (
    IngestResult,
    MityApiClient,
    MityApiError,
    MityAuthError,
    MityConnectionError,
)
from .const import (
    CHANNEL_FIELD_NAMES,
    DATA_CHANNELS,
    DOMAIN,
    EVENT_DATA_ACCEPTED,
    EVENT_DATA_ERROR,
    EVENT_DATA_REJECTED,
    OPT_PAUSED,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class MityData:
    """Latest known state of this MiTY device, consumed by every entity."""

    connected: bool = False
    last_status: str | None = None  # "accepted" | "rejected" | "error" | None
    last_error: str | None = None
    last_submission_at: datetime | None = None
    next_submission_at: datetime | None = None
    last_submission_id: Any = None
    parameters_configured: int = 0
    last_payload: dict[str, Any] = field(default_factory=dict)


class MityCoordinator(DataUpdateCoordinator[MityData]):
    """Coordinates periodic MiTY data submission for one enrolled device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MityApiClient,
    ) -> None:
        self.entry = entry
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self._interval(),
        )
        self.data = MityData()

    def _interval(self) -> timedelta:
        minutes = self.entry.options.get(
            "scan_interval_minutes",
            self.entry.data.get("scan_interval_minutes", 240),
        )
        return timedelta(minutes=minutes)

    def apply_new_interval(self) -> None:
        """Re-read the configured interval after an options update."""
        self.update_interval = self._interval()

    def _build_payload(self) -> dict[str, Any]:
        """Read the currently mapped HA entities and build the ingest body.

        Only channels the participant has actually mapped to an entity are
        included -- an unmapped channel is simply omitted, never sent as a
        null/zero value.
        """
        payload: dict[str, Any] = {
            "timestamp": dt_util.utcnow().isoformat(),
        }
        count = 0
        for channel in DATA_CHANNELS:
            entity_id = self.entry.options.get(channel)
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unknown", "unavailable"):
                continue
            field_name = CHANNEL_FIELD_NAMES[channel]
            payload[field_name] = _coerce_value(field_name, state.state)
            count += 1
        self.data.parameters_configured = count
        return payload

    async def _async_update_data(self) -> MityData:
        paused = self.entry.options.get(OPT_PAUSED, False)
        if paused:
            _LOGGER.debug("MiTY contribution is paused; skipping submission")
            self.data.last_status = "paused"
            return self.data

        payload = self._build_payload()
        if len(payload) <= 1:
            # Only the timestamp is present -- nothing mapped to send yet.
            _LOGGER.debug("No MiTY parameters mapped; skipping submission")
            self.data.last_status = "unconfigured"
            return self.data

        await self.submit_now(payload)
        return self.data

    async def submit_now(
        self, payload: dict[str, Any] | None = None
    ) -> IngestResult | None:
        """Submit a data payload immediately, outside the normal schedule.

        Used both by the periodic update and by the "Send Data Now" button.
        """
        if payload is None:
            payload = self._build_payload()

        instance_id = self.entry.data["instance_id"]
        device_api_key = self.entry.data["device_api_key"]

        try:
            result = await self.client.submit(device_api_key, instance_id, payload)
        except MityAuthError as err:
            self._record_error(str(err))
            self.hass.bus.async_fire(
                EVENT_DATA_ERROR, {"reason": "auth", "error": str(err)}
            )
            return None
        except MityConnectionError as err:
            self._record_error(str(err))
            self.hass.bus.async_fire(
                EVENT_DATA_ERROR, {"reason": "connection", "error": str(err)}
            )
            return None
        except MityApiError as err:
            self._record_error(str(err))
            self.hass.bus.async_fire(
                EVENT_DATA_ERROR, {"reason": "api", "error": str(err)}
            )
            return None

        self.data.last_payload = payload
        self.data.last_submission_at = dt_util.utcnow()
        self.data.next_submission_at = dt_util.utcnow() + self._interval()
        self.data.last_submission_id = result.submission_id

        if result.success:
            self.data.connected = True
            self.data.last_status = "accepted"
            self.data.last_error = None
            self.hass.bus.async_fire(
                EVENT_DATA_ACCEPTED,
                {"submission_id": result.submission_id, "parameters": len(payload) - 1},
            )
        else:
            self.data.connected = True
            self.data.last_status = "rejected"
            self.hass.bus.async_fire(
                EVENT_DATA_REJECTED, {"submission_id": result.submission_id}
            )

        return result

    def _record_error(self, message: str) -> None:
        self.data.connected = False
        self.data.last_status = "error"
        self.data.last_error = message
        _LOGGER.warning("MiTY submission failed: %s", message)


def _coerce_value(field_name: str, raw_state: str) -> Any:
    """Convert a HA state string into the JSON type MiTY expects for a field."""
    if field_name == "motion":
        return raw_state.lower() in ("on", "true", "1", "home", "detected")
    try:
        return float(raw_state)
    except (TypeError, ValueError):
        return raw_state
