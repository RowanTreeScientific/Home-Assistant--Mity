"""Shared fixtures for HA-dependent tests.

These fixtures need `pytest-homeassistant-custom-component` (and therefore
a real Home Assistant install) to collect at all -- see
requirements_test.txt and README.md's "Development" section for how to set
that up. They are skipped automatically by test_api.py and
test_coordinator_helpers.py, which deliberately avoid this dependency.
"""

from __future__ import annotations

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components/ visible to Home Assistant during tests."""
    yield
