"""Tests for the pure-logic helpers in coordinator.py.

`_coerce_value` has no Home Assistant dependency, so it's loaded the same
way as api.py in test_api.py -- directly from source, without pulling in
the rest of the package (and therefore without needing `homeassistant`
installed). Full coordinator behaviour (entity state reads, scheduling)
is exercised separately under pytest-homeassistant-custom-component.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_coordinator_module():
    module_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "mity"
        / "coordinator.py"
    )
    spec = importlib.util.spec_from_file_location(
        "mity_coordinator_helpers", module_path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError:
        return None
    return module


_coordinator = _load_coordinator_module()

if _coordinator is not None:
    _coerce_value = _coordinator._coerce_value

    def test_coerce_motion_on() -> None:
        assert _coerce_value("motion", "on") is True

    def test_coerce_motion_off() -> None:
        assert _coerce_value("motion", "off") is False

    def test_coerce_numeric() -> None:
        assert _coerce_value("temperature", "21.4") == 21.4

    def test_coerce_non_numeric_passthrough() -> None:
        assert _coerce_value("temperature", "not-a-number") == "not-a-number"
