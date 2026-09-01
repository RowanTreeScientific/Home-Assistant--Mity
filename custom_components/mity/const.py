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

# A participant-chosen label distinguishing one enrolled study from another
# when the same Home Assistant install has joined several (see "Citizen
# Science Study Discovery API Design" -- a trial IS a study 1:1, so joining
# a second study is just adding this integration again with a second
# enrollment code; the nickname is what keeps multiple entries legible in
# the HA UI, since the enroll response itself carries no study name).
CONF_STUDY_NICKNAME: Final = "study_nickname"
DEFAULT_STUDY_NICKNAME: Final = "MiTY Research"

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

# --- HERD-IoT envelope (Specification v1.0, Rowan Tree Scientific) ---
#
# Per-channel (domain, measure, unitCode) triples, drawn from the domain
# and measure-type controlled vocabularies (Implementation Guide sections
# 3.2.1/3.2.2). unitCode follows Table 3.3 ("DEG_C" for temperature); the
# guide's own Figure 4.1 worked example uses "CEL" instead -- an apparent
# inconsistency in the source document -- so this picks the vocabulary
# table's value as authoritative over the example.
HERD_CHANNEL_ENVELOPE: Final[dict[str, tuple[str, str, str]]] = {
    OPT_ENTITY_TEMPERATURE: ("env", "temperature", "DEG_C"),
    OPT_ENTITY_HUMIDITY: ("env", "humidity", "PERCENT"),
    OPT_ENTITY_MOTION: ("structural", "occupancy", "DIMENSIONLESS"),
    OPT_ENTITY_ENERGY_USAGE: ("energy", "kwh-import", "KiloW-HR"),
}

HERD_VERSION: Final = "1.0.0"

# These two identifier components (Table 3.1, items 1-2) don't have an
# obvious value for a self-enrolled citizen-science device -- "programme"
# and "provider" are designed around a registered research programme and
# a housing-provider organisation collecting on a resident's behalf,
# neither of which exists in the anonymous auto-enrollment model. Fixed
# placeholders pending confirmation from whoever owns the rebuilt backend;
# see docs/HERD_IOT_MIGRATION.md.
HERD_PROGRAMME_ID: Final = "MiTy-TRE"
HERD_PROVIDER: Final = "citizen-science"

# Zone Classification vocabulary (Table 3.4) -- code, label pairs for the
# selector shown when mapping each sensor.
HERD_ZONES: Final[tuple[tuple[str, str], ...]] = (
    ("living-room", "Living Room / Lounge"),
    ("kitchen", "Kitchen"),
    ("bedroom-1", "Primary Bedroom"),
    ("bedroom-2", "Secondary Bedroom"),
    ("bathroom", "Bathroom"),
    ("hallway", "Hallway / Corridor"),
    ("ext-south", "External South Facade"),
    ("ext-roof", "Roof / Loft Space"),
    ("whole-property", "Whole Property"),
    ("garage", "Garage / Outbuilding"),
)

# Communication protocol vocabulary (section 4.3.1) for deviceProvenance.
HERD_COMM_PROTOCOLS: Final[tuple[str, ...]] = (
    "wifi",
    "ble",
    "zigbee",
    "zwave",
    "lorawan",
    "mqtt",
    "modbus",
    "mbus",
)

# --- Options keys: per-channel zone + shared device provenance ---
OPT_ZONE_PREFIX: Final = "zone_"  # + channel name, e.g. "zone_entity_temperature"
OPT_DEVICE_MANUFACTURER: Final = "device_manufacturer"
OPT_DEVICE_MODEL: Final = "device_model"
OPT_DEVICE_FIRMWARE_VERSION: Final = "device_firmware_version"
OPT_DEVICE_CALIBRATION_DATE: Final = "device_calibration_date"
OPT_DEVICE_MEASUREMENT_UNCERTAINTY: Final = "device_measurement_uncertainty"
OPT_DEVICE_COMM_PROTOCOL: Final = "device_comm_protocol"

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
