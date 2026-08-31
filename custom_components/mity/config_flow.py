"""Config flow for MiTY Research.

Implements the enrollment sequence from the project objectives and
architecture notes: set the MiTY endpoint, agree to the terms and enter the
study's enrollment code, receive a permanent device identity, choose which
Home Assistant entities to contribute, and set the submission frequency.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    MityApiClient,
    MityConnectionError,
    MityInvalidEnrollCodeError,
)
from .const import (
    CONF_BASE_URL,
    CONF_DEVICE_API_KEY,
    CONF_ENROLL_CODE,
    CONF_INSTANCE_ID,
    CONF_REJOIN_TOKEN,
    DATA_CHANNELS,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
    OPT_ENTITY_ENERGY_USAGE,
    OPT_ENTITY_HUMIDITY,
    OPT_ENTITY_MOTION,
    OPT_ENTITY_TEMPERATURE,
    OPT_PAUSED,
    OPT_SCAN_INTERVAL_MINUTES,
    TERMS_URL,
)

_LOGGER = logging.getLogger(__name__)

CHANNEL_DOMAIN_FILTER = {
    OPT_ENTITY_TEMPERATURE: "sensor",
    OPT_ENTITY_HUMIDITY: "sensor",
    OPT_ENTITY_ENERGY_USAGE: "sensor",
    OPT_ENTITY_MOTION: "binary_sensor",
}
CHANNEL_LABEL = {
    OPT_ENTITY_TEMPERATURE: "Indoor temperature",
    OPT_ENTITY_HUMIDITY: "Indoor humidity",
    OPT_ENTITY_MOTION: "Motion / occupancy",
    OPT_ENTITY_ENERGY_USAGE: "Energy usage",
}


def _parameters_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    fields: dict[Any, Any] = {}
    for channel in DATA_CHANNELS:
        fields[
            vol.Optional(channel, default=defaults.get(channel))
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=CHANNEL_DOMAIN_FILTER[channel])
        )
    return vol.Schema(fields)


def _frequency_schema(default_minutes: int) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                OPT_SCAN_INTERVAL_MINUTES, default=default_minutes
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL_MINUTES,
                    max=MAX_SCAN_INTERVAL_MINUTES,
                    step=1,
                    unit_of_measurement="minutes",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        }
    )


class MityConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle enrollment of a new MiTY citizen-science device."""

    VERSION = 1

    def __init__(self) -> None:
        self._base_url: str = DEFAULT_BASE_URL
        self._enrollment: dict[str, Any] = {}
        self._parameters: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Step 1: endpoint, terms agreement, enrollment code."""
        errors: dict[str, str] = {}

        if user_input is not None and not user_input.get("agree_terms"):
            errors["agree_terms"] = "must_agree_terms"

        if user_input is not None and not errors:
            self._base_url = user_input[CONF_BASE_URL]
            session = async_get_clientsession(self.hass)
            client = MityApiClient(session, self._base_url)
            try:
                result = await client.enroll(user_input[CONF_ENROLL_CODE])
            except MityInvalidEnrollCodeError:
                errors["base"] = "invalid_enroll_code"
            except MityConnectionError:
                errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error enrolling with MiTY")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(result.instance_id))
                self._abort_if_unique_id_configured()
                self._enrollment = {
                    CONF_INSTANCE_ID: result.instance_id,
                    CONF_DEVICE_API_KEY: result.device_api_key,
                    CONF_REJOIN_TOKEN: result.rejoin_token,
                }
                return await self.async_step_parameters()

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=self._base_url): str,
                vol.Required(CONF_ENROLL_CODE): str,
                vol.Required("agree_terms", default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"terms_url": TERMS_URL},
        )

    async def async_step_parameters(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Step 2: choose which HA entities to contribute to each channel."""
        if user_input is not None:
            self._parameters = {
                k: v for k, v in user_input.items() if v is not None
            }
            return await self.async_step_frequency()

        return self.async_show_form(
            step_id="parameters",
            data_schema=_parameters_schema(),
            description_placeholders={
                "instance_id": str(self._enrollment[CONF_INSTANCE_ID])
            },
        )

    async def async_step_frequency(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Step 3: submission frequency, then create the entry."""
        if user_input is not None:
            data = {
                CONF_BASE_URL: self._base_url,
                **self._enrollment,
            }
            options = {
                **self._parameters,
                OPT_SCAN_INTERVAL_MINUTES: int(
                    user_input[OPT_SCAN_INTERVAL_MINUTES]
                ),
                OPT_PAUSED: False,
            }
            return self.async_create_entry(
                title="MiTY Research",
                data=data,
                options=options,
            )

        return self.async_show_form(
            step_id="frequency",
            data_schema=_frequency_schema(DEFAULT_SCAN_INTERVAL_MINUTES),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MityOptionsFlow(config_entry)


class MityOptionsFlow(OptionsFlow):
    """Edit parameter mapping and submission frequency after setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._pending: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        if user_input is not None:
            self._pending = {
                k: v for k, v in user_input.items() if v is not None
            }
            return await self.async_step_frequency()

        return self.async_show_form(
            step_id="init",
            data_schema=_parameters_schema(dict(self._entry.options)),
        )

    async def async_step_frequency(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        if user_input is not None:
            options = {
                **self._pending,
                OPT_SCAN_INTERVAL_MINUTES: int(
                    user_input[OPT_SCAN_INTERVAL_MINUTES]
                ),
                OPT_PAUSED: self._entry.options.get(OPT_PAUSED, False),
            }
            return self.async_create_entry(title="", data=options)

        current = self._entry.options.get(
            OPT_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        return self.async_show_form(
            step_id="frequency", data_schema=_frequency_schema(current)
        )
