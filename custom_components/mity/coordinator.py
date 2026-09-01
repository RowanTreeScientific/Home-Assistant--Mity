"""DataUpdateCoordinator for the MiTY Research integration.

Owns the periodic HERD-IoT submission cycle (POST /api/v1/herd/direct,
per the HERD-IoT Implementation Guide v1.0) and tracks the last-known
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
    HerdSubmitResult,
    MityApiClient,
    MityApiError,
    MityAuthError,
    MityConnectionError,
)
from .const import (
    DATA_CHANNELS,
    DOMAIN,
    EVENT_DATA_ACCEPTED,
    EVENT_DATA_ERROR,
    EVENT_DATA_REJECTED,
    HERD_CHANNEL_ENVELOPE,
    HERD_PROGRAMME_ID,
    HERD_PROVIDER,
    HERD_VERSION,
    OPT_DEVICE_CALIBRATION_DATE,
    OPT_DEVICE_COMM_PROTOCOL,
    OPT_DEVICE_FIRMWARE_VERSION,
    OPT_DEVICE_MANUFACTURER,
    OPT_DEVICE_MEASUREMENT_UNCERTAINTY,
    OPT_DEVICE_MODEL,
    OPT_PAUSED,
    OPT_ZONE_PREFIX,
)
from .uuid7 import uuid7

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
    last_payload: list[dict[str, Any]] = field(default_factory=list)


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

    def _device_provenance(self) -> dict[str, Any] | None:
        """Build the shared Layer 2 deviceProvenance block, if configured.

        A single provenance block applies to every mapped channel in this
        first pass -- the spec models provenance per physical device, but
        asking for six fields per channel (four channels) in one config
        flow screen is a poor first-pass UX trade against a real gain.
        Only built at all once manufacturer+model are both set, since a
        partial provenance block is arguably worse than none.
        """
        options = self.entry.options
        manufacturer = options.get(OPT_DEVICE_MANUFACTURER)
        model = options.get(OPT_DEVICE_MODEL)
        if not manufacturer or not model:
            return None

        provenance: dict[str, Any] = {
            "manufacturer": manufacturer,
            "model": model,
            "samplingInterval": int(self._interval().total_seconds()),
            "communicationProtocol": options.get(OPT_DEVICE_COMM_PROTOCOL, "wifi"),
        }
        if firmware := options.get(OPT_DEVICE_FIRMWARE_VERSION):
            provenance["firmwareVersion"] = firmware
        if calibration := options.get(OPT_DEVICE_CALIBRATION_DATE):
            provenance["calibrationDate"] = calibration
        return provenance

    def _measurement_uncertainty(self, unit_code: str) -> dict[str, Any] | None:
        value = self.entry.options.get(OPT_DEVICE_MEASUREMENT_UNCERTAINTY)
        if value in (None, ""):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return {
            "value": numeric,
            "unitCode": unit_code,
            "coverageFactor": 2,
            "confidenceLevel": 0.95,
        }

    def _property_token(self) -> str:
        """Placeholder GDV-format property token.

        Real property tokens are minted by the Glass Door Vault, not the
        client -- the whole point of GDV pseudonymisation is that it's a
        one-way mapping only the vault can produce (Appendix B). This
        integration has no such token to report from the current
        enrollment response shape, so it derives a deterministic
        placeholder in the required `GDV-{8 hex}` format instead of
        omitting the field outright. Needs replacing with a real token
        once the rebuilt backend's enrollment response supplies one --
        see docs/HERD_IOT_MIGRATION.md.
        """
        instance_id = self.entry.data["instance_id"]
        return f"GDV-{instance_id:08x}"

    def _observed_at(self) -> str:
        """ISO 8601 UTC timestamp with mandatory trailing Z (section 4.2.1)."""
        now = dt_util.utcnow()
        return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

    def _build_herd_entities(self) -> list[dict[str, Any]]:
        """Read the currently mapped HA entities and build one HERDObservation
        entity per channel with a usable current value.

        Only channels the participant has actually mapped -- to an entity
        AND a zone, since the identifier scheme requires one -- are
        included. A channel missing its zone is skipped with a warning
        rather than sent with a made-up zone.
        """
        entities: list[dict[str, Any]] = []
        observed_at = self._observed_at()
        provenance = self._device_provenance()
        property_token = self._property_token()

        for channel in DATA_CHANNELS:
            entity_id = self.entry.options.get(channel)
            if not entity_id:
                continue
            zone = self.entry.options.get(f"{OPT_ZONE_PREFIX}{channel}")
            if not zone:
                _LOGGER.warning(
                    "MiTY channel %s is mapped to %s but has no zone configured; "
                    "skipping until a zone is set in the integration's options",
                    channel,
                    entity_id,
                )
                continue
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unknown", "unavailable"):
                continue

            domain, measure, unit_code = HERD_CHANNEL_ENVELOPE[channel]
            value = _coerce_value(measure, state.state)
            device_id = _sanitize_device_id(entity_id)
            observation_id = str(uuid7())
            uri = (
                f"urn:herd-iot:{HERD_PROGRAMME_ID}:{HERD_PROVIDER}:"
                f"{property_token}:{zone}:{domain}:{measure}:{device_id}:"
                f"{observation_id}"
            )

            entity: dict[str, Any] = {
                "id": uri,
                "type": "HERDObservation",
                "observedAt": observed_at,
                "hasSimpleResult": {
                    "type": "Property",
                    "value": value,
                    "unitCode": unit_code,
                },
                "herdVersion": HERD_VERSION,
            }
            uncertainty = self._measurement_uncertainty(unit_code)
            if provenance is not None:
                entity_provenance = dict(provenance)
                if uncertainty is not None:
                    entity_provenance["measurementUncertainty"] = uncertainty
                entity["deviceProvenance"] = {
                    "type": "Property",
                    "value": entity_provenance,
                }
            entities.append(entity)

        self.data.parameters_configured = len(entities)
        return entities

    async def _async_update_data(self) -> MityData:
        paused = self.entry.options.get(OPT_PAUSED, False)
        if paused:
            _LOGGER.debug("MiTY contribution is paused; skipping submission")
            self.data.last_status = "paused"
            return self.data

        entities = self._build_herd_entities()
        if not entities:
            _LOGGER.debug("No MiTY parameters mapped; skipping submission")
            self.data.last_status = "unconfigured"
            return self.data

        await self.submit_now(entities)
        return self.data

    async def submit_now(
        self, entities: list[dict[str, Any]] | None = None
    ) -> HerdSubmitResult | None:
        """Submit HERD-IoT entities immediately, outside the normal schedule.

        Used both by the periodic update and by the "Send Data Now" button.
        """
        if entities is None:
            entities = self._build_herd_entities()
        if not entities:
            return None

        device_api_key = self.entry.data["device_api_key"]

        try:
            result = await self.client.submit_herd_entities(device_api_key, entities)
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

        self.data.last_payload = entities
        self.data.last_submission_at = dt_util.utcnow()
        self.data.next_submission_at = dt_util.utcnow() + self._interval()
        self.data.last_submission_id = (
            result.results[0].observation_id if result.results else None
        )

        if result.all_accepted:
            self.data.connected = True
            self.data.last_status = "accepted"
            self.data.last_error = None
            self.hass.bus.async_fire(
                EVENT_DATA_ACCEPTED,
                {
                    "observation_ids": [r.observation_id for r in result.results],
                    "parameters": len(entities),
                },
            )
        else:
            self.data.connected = True
            self.data.last_status = "rejected"
            rejected = [r for r in result.results if not r.accepted]
            self.hass.bus.async_fire(
                EVENT_DATA_REJECTED,
                {
                    "rejected_count": len(rejected),
                    "errors": [e for r in rejected for e in r.errors],
                },
            )

        return result

    def _record_error(self, message: str) -> None:
        self.data.connected = False
        self.data.last_status = "error"
        self.data.last_error = message
        _LOGGER.warning("MiTY submission failed: %s", message)


def _sanitize_device_id(entity_id: str) -> str:
    """Derive a HERD-IoT-legal device-id from a HA entity_id.

    Governance rules (section 3.3) require lowercase ASCII with hyphens
    as the only separator. `sensor.living_room_temperature` becomes
    `sensor-living-room-temperature`. Real per-sensor device registration
    (section 3.3: "must be registered in the Device Profile Table before
    data submission... Observations from unregistered devices will be
    rejected") isn't something this integration can satisfy on its own --
    flagged as an open item in docs/HERD_IOT_MIGRATION.md, not solved here.
    """
    return entity_id.lower().replace(".", "-").replace("_", "-")


def _coerce_value(measure: str, raw_state: str) -> Any:
    """Convert a HA state string into the JSON type MiTY expects for a measure."""
    if measure == "occupancy":
        return raw_state.lower() in ("on", "true", "1", "home", "detected")
    try:
        return float(raw_state)
    except (TypeError, ValueError):
        return raw_state
