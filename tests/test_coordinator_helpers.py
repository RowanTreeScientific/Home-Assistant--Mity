"""Tests for the pure-logic helpers in coordinator.py.

`_coerce_value` has no real Home Assistant dependency -- it's plain string
coercion -- but `coordinator.py` itself does `from .api import (...)`, a
relative import that only resolves when the module is loaded as part of
its real package. So unlike api.py (loaded standalone in test_api.py),
this imports `custom_components.mity.coordinator` normally rather than by
file path. That still means `homeassistant` needs to be importable
(`custom_components/mity/__init__.py` imports it), so this module is
skipped gracefully when it isn't -- e.g. in a lightweight local venv used
to iterate on api.py/coordinator.py logic without the full HA test stack.
Full coordinator behaviour (entity state reads, scheduling) is exercised
separately under pytest-homeassistant-custom-component.
"""

from __future__ import annotations

try:
    from custom_components.mity.coordinator import _coerce_value

    _SKIP = False
except ModuleNotFoundError:
    _SKIP = True

if not _SKIP:

    def test_coerce_motion_on() -> None:
        assert _coerce_value("motion", "on") is True

    def test_coerce_motion_off() -> None:
        assert _coerce_value("motion", "off") is False

    def test_coerce_numeric() -> None:
        assert _coerce_value("temperature", "21.4") == 21.4

    def test_coerce_non_numeric_passthrough() -> None:
        assert _coerce_value("temperature", "not-a-number") == "not-a-number"

if not _SKIP:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from custom_components.mity.coordinator import assemble_fields, entity_description

    def _state(entity_id, state, **attrs):
        return SimpleNamespace(entity_id=entity_id, state=state, attributes=attrs,
                               last_updated=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc))

    def test_entity_description_reports_only_what_ha_knows() -> None:
        d = entity_description(_state("sensor.house_energy", "4123.6", device_class="energy", state_class="total_increasing", unit_of_measurement="kWh"))
        assert d == {"entity_id": "sensor.house_energy", "domain": "sensor", "device_class": "energy", "state_class": "total_increasing",
                     "unit_of_measurement": "kWh", "last_updated": "2026-10-05T12:00:00+00:00"}
        bare = entity_description(_state("sensor.mystery", "3"))
        assert set(bare) == {"entity_id", "domain", "last_updated"}, "nothing is invented"

    def test_assemble_fields_extras_and_descriptions() -> None:
        fields, entities = assemble_fields({
            "temperature": _state("sensor.kitchen_temperature", "21.4", device_class="temperature", state_class="measurement", unit_of_measurement="°C"),
            "motion": _state("binary_sensor.hall_motion", "on", device_class="motion"),
            "ha:sensor.office_pm25": _state("sensor.office_pm25", "7.5", device_class="pm25", state_class="measurement", unit_of_measurement="µg/m³"),
            "ha:sensor.gone": _state("sensor.gone", "unavailable"),
            "energyUsage": None,
        })
        assert fields == {"temperature": 21.4, "motion": True, "ha:sensor.office_pm25": 7.5}
        assert set(entities) == set(fields)
        assert entities["ha:sensor.office_pm25"]["device_class"] == "pm25"
        assert entities["motion"]["domain"] == "binary_sensor"
