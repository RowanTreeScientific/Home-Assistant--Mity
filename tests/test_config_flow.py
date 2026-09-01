"""Tests for the MiTY config flow.

Requires pytest-homeassistant-custom-component -- see tests/conftest.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mity.api import (
    EnrollmentResult,
    MityInvalidEnrollCodeError,
    MityRejoinNotPermittedError,
)
from custom_components.mity.const import (
    CONF_BASE_URL,
    CONF_DEVICE_API_KEY,
    CONF_INSTANCE_ID,
    CONF_REJOIN_TOKEN,
    CONF_STUDY_NICKNAME,
    DOMAIN,
)

VALID_ENROLL_INPUT = {
    "base_url": "http://api.mi-ty-tre.co.uk",
    "enroll_code": "8f2a1c9e4b7d3f0a6c5e2b8d1f4a7c9e",
    "agree_terms": True,
}


async def _skip_zones_and_provenance(hass: HomeAssistant, flow_id: str):
    """Submit the still-open parameters form with nothing mapped, then
    walk through the zones and device_provenance steps that follow with
    nothing filled in either -- valid when no channels were mapped, since
    zones then has nothing to ask for and device_provenance is all-optional
    regardless. Returns the result of reaching the frequency step.
    """
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["step_id"] == "zones"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "device_provenance"
    return await hass.config_entries.flow.async_configure(result["flow_id"], {})


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

    result = await _skip_zones_and_provenance(hass, result["flow_id"])
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
    result = await _skip_zones_and_provenance(hass, result["flow_id"])
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"scan_interval_minutes": 240}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Indoor Air Study"
    assert result["data"]["study_nickname"] == "Indoor Air Study"


async def test_zone_and_provenance_flow_through_to_options(
    hass: HomeAssistant, mock_enroll
) -> None:
    """Mapping a real channel makes the zones step ask for exactly that
    channel's zone, and both zone and device-provenance answers end up
    in the created entry's options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_ENROLL_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"entity_temperature": "sensor.living_room_temperature"}
    )
    assert result["step_id"] == "zones"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"zone_entity_temperature": "living-room"}
    )
    assert result["step_id"] == "device_provenance"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device_manufacturer": "Aico",
            "device_model": "Environmental Sensor Gen 3",
            "device_comm_protocol": "zigbee",
        },
    )
    assert result["step_id"] == "frequency"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"scan_interval_minutes": 240}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"]["entity_temperature"] == "sensor.living_room_temperature"
    assert result["options"]["zone_entity_temperature"] == "living-room"
    assert result["options"]["device_manufacturer"] == "Aico"
    assert result["options"]["device_comm_protocol"] == "zigbee"
    # Optional fields left blank must not appear at all (see
    # config_flow.py's _optional_field -- a forced None default breaks
    # selector validation the same way it did for entity mapping).
    assert "device_firmware_version" not in result["options"]


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
    result = await _skip_zones_and_provenance(hass, result["flow_id"])
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
    result2 = await _skip_zones_and_provenance(hass, result2["flow_id"])
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"scan_interval_minutes": 240}
    )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Study Two"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert {e.data["instance_id"] for e in entries} == {42, 99}


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="42",
        title="Test Study",
        data={
            CONF_BASE_URL: "http://api.mi-ty-tre.co.uk",
            CONF_INSTANCE_ID: 42,
            CONF_DEVICE_API_KEY: "stale-key",
            CONF_REJOIN_TOKEN: "rejoin-token",
            CONF_STUDY_NICKNAME: "Test Study",
        },
        options={"scan_interval_minutes": 240, "paused": False},
    )


async def _start_reauth(hass: HomeAssistant, entry: MockConfigEntry):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )


async def test_reauth_via_rejoin_succeeds(hass: HomeAssistant) -> None:
    entry = _make_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.mity.config_flow.MityApiClient.rejoin",
        new_callable=AsyncMock,
        return_value=EnrollmentResult(
            instance_id=42, device_api_key="fresh-key", rejoin_token="fresh-rejoin"
        ),
    ):
        result = await _start_reauth(hass, entry)
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_DEVICE_API_KEY] == "fresh-key"
    assert entry.data[CONF_REJOIN_TOKEN] == "fresh-rejoin"
    assert entry.data[CONF_INSTANCE_ID] == 42


async def test_reauth_falls_back_to_new_code(hass: HomeAssistant) -> None:
    entry = _make_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.mity.config_flow.MityApiClient.rejoin",
        new_callable=AsyncMock,
        side_effect=MityRejoinNotPermittedError(),
    ):
        result = await _start_reauth(hass, entry)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {}
        )

    assert result["step_id"] == "reauth_new_code"

    with patch(
        "custom_components.mity.config_flow.MityApiClient.enroll",
        new_callable=AsyncMock,
        return_value=EnrollmentResult(
            instance_id=77, device_api_key="new-device-key", rejoin_token="new-rejoin"
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"enroll_code": "a-fresh-code"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_INSTANCE_ID] == 77
    assert entry.data[CONF_DEVICE_API_KEY] == "new-device-key"


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
    result = await _skip_zones_and_provenance(hass, result["flow_id"])
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
