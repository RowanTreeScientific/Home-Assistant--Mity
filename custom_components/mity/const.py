"""Constants for the MiTY Research integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "mity"

# --- Config entry data keys (immutable once set, secrets) ---
CONF_BASE_URL: Final = "base_url"
CONF_ENROLL_CODE: Final = "enroll_code"
CONF_INSTANCE_ID: Final = "instance_id"
CONF_DEVICE_API_KEY: Final = "device_api_key"
CONF_REJOIN_TOKEN: Final = "rejoin_token"

# --- Options keys (editable after setup) ---
OPT_SCAN_INTERVAL_MINUTES: Final = "scan_interval_minutes"
OPT_PAUSED: Final = "paused"
OPT_ENTITY_TEMPERATURE: Final = "entity_temperature"
OPT_ENTITY_HUMIDITY: Final = "entity_humidity"
OPT_ENTITY_MOTION: Final = "entity_motion"
OPT_ENTITY_ENERGY_USAGE: Final = "entity_energy_usage"

# The four canonical HERD_IOT:citizen.home-assistant terms a device can
# report, beyond deviceId/timestamp which the platform derives automatically.
# See "Citizen Science AutoEnrollment Design" section 6 -- this list is the
# fixed schema shared by every citizen-science trial, not something the
# integration can extend on its own.
DATA_CHANNELS: Final = (
    OPT_ENTITY_TEMPERATURE,
    OPT_ENTITY_HUMIDITY,
    OPT_ENTITY_MOTION,
    OPT_ENTITY_ENERGY_USAGE,
)

# Raw JSON field name sent in the /v1/ingest payload for each channel.
# These must match the raw-field-name -> canonical-term-key mapping that
# MiTY's fixed citizen-science field-map expects. Kept 1:1 with the
# canonical term keys for clarity; if the MiTY-side mapping is ever
# finalised with different raw names, only this dict needs to change.
CHANNEL_FIELD_NAMES: Final[dict[str, str]] = {
    OPT_ENTITY_TEMPERATURE: "temperature",
    OPT_ENTITY_HUMIDITY: "humidity",
    OPT_ENTITY_MOTION: "motion",
    OPT_ENTITY_ENERGY_USAGE: "energyUsage",
}

CHANNEL_DEVICE_CLASS: Final[dict[str, str]] = {
    OPT_ENTITY_TEMPERATURE: "temperature",
    OPT_ENTITY_HUMIDITY: "humidity",
    OPT_ENTITY_MOTION: "motion",
    OPT_ENTITY_ENERGY_USAGE: "energy",
}

DEFAULT_BASE_URL: Final = "http://api.mi-ty-tre.co.uk"

# Per "Mity - Home Assistant - Objectives": default/min/max submission
# frequency and the maximum number of parameters a participant may share.
DEFAULT_SCAN_INTERVAL_MINUTES: Final = 240
MIN_SCAN_INTERVAL_MINUTES: Final = 60
MAX_SCAN_INTERVAL_MINUTES: Final = 10080
MAX_PARAMETERS = len(DATA_CHANNELS)

TERMS_URL: Final = "https://www.mi-ty-tre.co.uk/terms"

# --- Events fired on the HA event bus ---
EVENT_DATA_ACCEPTED: Final = "mity_data_accepted"
EVENT_DATA_REJECTED: Final = "mity_data_rejected"
EVENT_DATA_ERROR: Final = "mity_data_error"

# --- Services ---
SERVICE_SEND_NOW: Final = "send_now"
SERVICE_LEAVE_STUDY: Final = "leave_study"
SERVICE_REJOIN_STUDY: Final = "rejoin_study"
ATTR_ACTION: Final = "action"
ACTION_REMOVE_ONLY: Final = "remove_only"
ACTION_REMOVE_AND_DELETE: Final = "remove_and_delete"

LOGGER_NAME: Final = "custom_components.mity"
