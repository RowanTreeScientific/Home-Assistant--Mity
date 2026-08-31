"""Shared fixtures for HA-dependent tests.

These fixtures need `pytest-homeassistant-custom-component` (and therefore
a real Home Assistant install) to collect at all -- see
requirements_test.txt and README.md's "Development" section for how to set
that up. They are skipped automatically by test_api.py and
test_coordinator_helpers.py, which deliberately avoid this dependency.
"""

from __future__ import annotations

import sys

import pytest

# aiohttp auto-selects a pycares/aiodns-backed DNS resolver instead of its
# plain ThreadedResolver whenever aiodns is importable. A pycares
# shutdown-logic regression now leaves a lingering `_run_safe_shutdown_loop`
# thread behind purely from that resolver being *selected* -- no actual DNS
# traffic needed -- which HA's own strict thread-leak-detecting test
# fixture then fails on. See
# github.com/MatthewFlamm/pytest-homeassistant-custom-component/issues/219
# (open, no released fix).
#
# This `sys.modules["aiodns"] = None` block (the documented CPython
# mechanism for making a future `import aiodns` raise ImportError, which
# aiohttp.resolver's own `try/except ImportError` already falls back
# cleanly from) is a best-effort local fallback, not the authoritative
# fix -- confirmed insufficient on its own in real CI: pytest-aiohttp and
# pytest-homeassistant-custom-component are loaded as entry-point plugins
# during pytest's own startup, before any conftest.py (even this one) is
# collected, so aiohttp.resolver's DefaultResolver can already be cached
# by the time this line runs. The actual fix is in
# .github/workflows/test.yml: uninstalling aiodns/pycares outright, which
# removes the possibility regardless of import timing. This block is kept
# for anyone running the test suite locally with aiodns installed and
# without following that workflow step.
sys.modules["aiodns"] = None  # type: ignore[assignment]

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components/ visible to Home Assistant during tests."""
    yield
