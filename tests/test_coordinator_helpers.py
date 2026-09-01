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
    from custom_components.mity.coordinator import _coerce_value, _sanitize_device_id

    _SKIP = False
except ModuleNotFoundError:
    _SKIP = True

if not _SKIP:

    def test_coerce_occupancy_on() -> None:
        assert _coerce_value("occupancy", "on") is True

    def test_coerce_occupancy_off() -> None:
        assert _coerce_value("occupancy", "off") is False

    def test_coerce_numeric() -> None:
        assert _coerce_value("temperature", "21.4") == 21.4

    def test_coerce_non_numeric_passthrough() -> None:
        assert _coerce_value("temperature", "not-a-number") == "not-a-number"

    def test_sanitize_device_id_dots_and_underscores() -> None:
        assert (
            _sanitize_device_id("sensor.living_room_temperature")
            == "sensor-living-room-temperature"
        )

    def test_sanitize_device_id_lowercases() -> None:
        assert _sanitize_device_id("sensor.Kitchen_CO2") == "sensor-kitchen-co2"
