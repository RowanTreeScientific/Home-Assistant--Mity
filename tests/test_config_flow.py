"""Tests for the MiTY config flow.

Requires pytest-homeassistant-custom-component -- see tests/conftest.py.
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
    assert result["title"] == "MiTY Research"
    assert result["data"]["study_nickname"] == "MiTY Research"


async def test_study_nickname_used_as_title(
    hass: HomeAssistant, mock_enroll
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**VALID_ENROLL_INPUT, "study_nickname": "Indoor Air Study"},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"scan_interval_minutes": 240}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Indoor Air Study"
    assert result["data"]["study_nickname"] == "Indoor Air Study"


async def test_second_study_creates_separate_entry(
    hass: HomeAssistant, mock_enroll
) -> None:
    """Joining a second study is just running the flow again with its own
    code -- since each enrollment yields a different instance_id, it must
    create a second, independent config entry rather than aborting."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**VALID_ENROLL_INPUT, "study_nickname": "Study One"},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"scan_interval_minutes": 240}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    mock_enroll.return_value = EnrollmentResult(
        instance_id=99, device_api_key="device-key-2", rejoin_token="rejoin-2"
    )
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {**VALID_ENROLL_INPUT, "study_nickname": "Study Two"},
    )
    result2 = await hass.config_entries.flow.async_configure(result2["flow_id"], {})
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"scan_interval_minutes": 240}
    )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Study Two"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert {e.data["instance_id"] for e in entries} == {42, 99}


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
