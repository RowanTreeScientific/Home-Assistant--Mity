"""Tests for the integration's setup/removal lifecycle.

Requires pytest-homeassistant-custom-component -- see tests/conftest.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mity.const import (
    CONF_BASE_URL,
    CONF_DEVICE_API_KEY,
    CONF_INSTANCE_ID,
    CONF_REJOIN_TOKEN,
    CONF_STUDY_NICKNAME,
    DOMAIN,
)


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="Test Study",
        data={
            CONF_BASE_URL: "http://api.mi-ty-tre.co.uk",
            CONF_INSTANCE_ID: 42,
            CONF_DEVICE_API_KEY: "device-key",
            CONF_REJOIN_TOKEN: "rejoin-token",
            CONF_STUDY_NICKNAME: "Test Study",
        },
        options={"scan_interval_minutes": 240, "paused": False},
    )


async def test_removing_entry_best_effort_leaves_study(hass: HomeAssistant) -> None:
    """Deleting the integration entry should withdraw from MiTY too."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.mity.api.MityApiClient.submit_herd_entities",
        new_callable=AsyncMock,
    ), patch(
        "custom_components.mity.api.MityApiClient.remove", new_callable=AsyncMock
    ) as mock_remove:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()

    mock_remove.assert_awaited_once_with("device-key", "remove_only")


async def test_removal_failure_does_not_raise(hass: HomeAssistant) -> None:
    """A failed withdrawal call must not block the entry from being removed."""
    from custom_components.mity.api import MityApiError

    entry = _make_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.mity.api.MityApiClient.submit_herd_entities",
        new_callable=AsyncMock,
    ), patch(
        "custom_components.mity.api.MityApiClient.remove",
        new_callable=AsyncMock,
        side_effect=MityApiError("boom"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Must complete without raising even though the API call failed.
        assert await hass.config_entries.async_remove(entry.entry_id)
