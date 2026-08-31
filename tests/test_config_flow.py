"""Tests for the MiTY config flow.

Requires pytest-homeassistant-custom-component -- see tests/ha/conftest.py.
Run with: pytest tests/ha
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.mity.api import EnrollmentResult, MityInvalidEnrollCodeError
from custom_components.mity.const import DOMAIN

VALID_ENROLL_INPUT = {
    "base_url": "http://api.mi-ty-tre.co.uk",
    "enroll_code": "8f2a1c9e4b7d3f0a6c5e2b8d1f4a7c9e",
    "agree_terms": True,
}


@pytest.fixture
def mock_enroll():
    with patch(
        "custom_components.mity.config_flow.MityApiClient.enroll",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = EnrollmentResult(
            instance_id=42, device_api_key="device-key", rejoin_token="rejoin-token"
        )
        yield mock


async def test_full_flow_creates_entry(hass: HomeAssistant, mock_enroll) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_ENROLL_INPUT
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "parameters"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "frequency"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"scan_interval_minutes": 240}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["instance_id"] == 42
    assert result["data"]["device_api_key"] == "device-key"
    assert result["options"]["scan_interval_minutes"] == 240
    assert result["options"]["paused"] is False


async def test_requires_terms_agreement(hass: HomeAssistant, mock_enroll) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**VALID_ENROLL_INPUT, "agree_terms": False}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["agree_terms"] == "must_agree_terms"
    mock_enroll.assert_not_called()


async def test_invalid_enroll_code(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.mity.config_flow.MityApiClient.enroll",
        new_callable=AsyncMock,
        side_effect=MityInvalidEnrollCodeError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_ENROLL_INPUT
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_enroll_code"


async def test_duplicate_instance_aborts(hass: HomeAssistant, mock_enroll) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_ENROLL_INPUT
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"scan_interval_minutes": 240}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], VALID_ENROLL_INPUT
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
