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
# plain ThreadedResolver whenever aiodns happens to be importable (it's a
# transitive dependency here, via pytest-homeassistant-custom-component /
# homeassistant core). That selection is computed once, at aiohttp.resolver
# module import time, and cached module-wide for the rest of the process --
# whichever ClientSession gets constructed *first* anywhere in the whole
# test session (test code or Home Assistant's own internals) triggers it.
# A pycares shutdown-logic regression now leaves a lingering
# `_run_safe_shutdown_loop` thread behind purely from that selection, which
# HA's own strict thread-leak-detecting test fixture then fails on --
# confirmed against a real, currently-open upstream issue rather than
# guessed: github.com/MatthewFlamm/pytest-homeassistant-custom-component/issues/219.
# Blocking the aiodns import here, before anything else in the test session
# gets a chance to trigger that selection, fixes it at the actual root
# cause in one place rather than in every individual fixture that happens
# to construct a session. `sys.modules[name] = None` is the documented
# CPython mechanism for making a future `import name` raise ImportError --
# exactly the branch aiohttp.resolver's own `try: import aiodns / except
# ImportError` already expects and falls back cleanly from.
sys.modules["aiodns"] = None  # type: ignore[assignment]

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make custom_components/ visible to Home Assistant during tests."""
    yield
