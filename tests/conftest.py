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

# Note on the lingering `_run_safe_shutdown_loop` thread issue some commits
# on this branch chased: aiodns/pycares CANNOT be blocked or removed here.
# homeassistant/helpers/aiohttp_client.py constructs `AsyncResolver()`
# directly with no ThreadedResolver fallback, so async_get_clientsession()
# -- which this integration's own config_flow.py/__init__.py call, matching
# real production behaviour -- hard-requires aiodns to be genuinely
# importable and working. The actual fix is a version pin in
# requirements_test.txt (pycares<4.9.0, below the version that introduced
# the shutdown-logic regression -- see
# github.com/MatthewFlamm/pytest-homeassistant-custom-component/issues/219),
# not anything in this file.


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components/ visible to Home Assistant during tests."""
    yield
