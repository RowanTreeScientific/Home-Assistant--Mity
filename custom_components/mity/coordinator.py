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
    CONF_STUDY_NICKNAME,
    DATA_CHANNELS,
    DOMAIN,
    EVENT_DATA_ACCEPTED,
    EVENT_DATA_ERROR,
    EVENT_DATA_REJECTED,
    OPT_DEVICE_COMM_PROTOCOL,
    OPT_DEVICE_MANUFACTURER,
    OPT_DEVICE_MODEL,
    OPT_PAUSED,
    OPT_ZONE,
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

    def _device_id(self) -> str:
        """A short, human-readable label for this device, sent as the
        optional `deviceId` field (API spec section 3). Reuses the study
        nickname the participant already chose rather than asking for a
        separate label -- sanitized to something reasonable to display
        in MiTY's own dashboards.
        """
        nickname = self.entry.data.get(CONF_STUDY_NICKNAME, "")
        slug = "-".join(nickname.lower().split())
        return slug or f"ha-{self.entry.data['instance_id']}"

    def _meta(self) -> dict[str, Any] | None:
        """Optional `_meta` block: provenance/zone enrichment (API spec
        section 4). Entirely optional and free text on this backend --
        omitted altogether if the participant left every field blank.
        """
        options = self.entry.options
        manufacturer = options.get(OPT_DEVICE_MANUFACTURER)
        model = options.get(OPT_DEVICE_MODEL)
        protocol = options.get(OPT_DEVICE_COMM_PROTOCOL)
        zone = options.get(OPT_ZONE)

        meta: dict[str, Any] = {}
        if manufacturer or model or protocol:
            provenance: dict[str, Any] = {
                "samplingInterval": int(self._interval().total_seconds())
            }
            if manufacturer:
                provenance["manufacturer"] = manufacturer
            if model:
                provenance["model"] = model
            if protocol:
                provenance["communicationProtocol"] = protocol
            meta["deviceProvenance"] = provenance
        if zone:
            meta["zone"] = zone

        return meta or None

    def _build_payload(self) -> dict[str, Any]:
        """Read the currently mapped HA entities and build the ingest body.

        Only channels the participant has actually mapped to an entity are
        included -- an unmapped channel is simply omitted, never sent as a
        null/zero value.
        """
        payload: dict[str, Any] = {
            "deviceId": self._device_id(),
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

        if meta := self._meta():
            payload["_meta"] = meta

        return payload

    async def _async_update_data(self) -> MityData:
        paused = self.entry.options.get(OPT_PAUSED, False)
        if paused:
            _LOGGER.debug("MiTY contribution is paused; skipping submission")
            self.data.last_status = "paused"
            return self.data

        payload = self._build_payload()
        if self.data.parameters_configured == 0:
            # deviceId/timestamp (and maybe _meta) are always present --
            # check the tracked mapped-channel count instead of payload
            # size, since that's what "nothing mapped to send yet" means.
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
            # The device's own key was rejected -- likely revoked on the
            # MiTY side outside this integration's knowledge. Prompt the
            # user to reauthenticate rather than just failing silently
            # forever; config_flow.py's reauth step tries the stored
            # rejoin token first.
            self.entry.async_start_reauth(self.hass)
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
                {
                    "submission_id": result.submission_id,
                    "parameters": self.data.parameters_configured,
                },
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
