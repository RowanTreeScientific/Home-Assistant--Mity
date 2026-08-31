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
    MityApiError,
    MityConnectionError,
    MityInvalidEnrollCodeError,
    MityRejoinNotPermittedError,
)
from .const import (
    CONF_BASE_URL,
    CONF_DEVICE_API_KEY,
    CONF_ENROLL_CODE,
    CONF_INSTANCE_ID,
    CONF_REJOIN_TOKEN,
    CONF_STUDY_NICKNAME,
    DATA_CHANNELS,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_STUDY_NICKNAME,
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
        self._nickname: str = DEFAULT_STUDY_NICKNAME
        self._enrollment: dict[str, Any] = {}
        self._parameters: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Step 1: endpoint, terms agreement, enrollment code.

        Joining a second (or third...) study is just running this flow
        again with that study's own code -- a MiTY trial and a "study" are
        1:1, so there's no separate join/browse step. The nickname field
        exists purely so multiple joined studies stay distinguishable in
        the Home Assistant UI, since the enrollment response itself
        carries no study name to use automatically.
        """
        errors: dict[str, str] = {}

        if user_input is not None and not user_input.get("agree_terms"):
            errors["agree_terms"] = "must_agree_terms"

        if user_input is not None and not errors:
            self._base_url = user_input[CONF_BASE_URL]
            self._nickname = (
                user_input.get(CONF_STUDY_NICKNAME) or DEFAULT_STUDY_NICKNAME
            )
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
                vol.Optional(CONF_STUDY_NICKNAME): str,
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
                CONF_STUDY_NICKNAME: self._nickname,
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
                title=self._nickname,
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

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> Any:
        """Entered automatically when a submission gets a 401/403 from MiTY.

        Triggered by `coordinator.py` calling `entry.async_start_reauth()`
        on a `MityAuthError` -- e.g. an admin revoked this device's key on
        the MiTY side. Try the stored rejoin token first, since that's the
        credential designed to survive a revoked ingest key; fall back to
        asking for a fresh enrollment code only if the trial's rejoin
        policy blocks that.
        """
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = MityApiClient(session, entry.data[CONF_BASE_URL])
            try:
                result = await client.rejoin(entry.data[CONF_REJOIN_TOKEN])
            except MityRejoinNotPermittedError:
                return await self.async_step_reauth_new_code()
            except MityConnectionError:
                errors["base"] = "cannot_connect"
            except MityApiError:
                errors["base"] = "unknown"
            else:
                return await self._finish_reauth(entry, result)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"nickname": entry.title},
        )

    async def async_step_reauth_new_code(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Fallback when the trial's policy is 'new_identity_required'."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = MityApiClient(session, entry.data[CONF_BASE_URL])
            try:
                result = await client.enroll(user_input[CONF_ENROLL_CODE])
            except MityInvalidEnrollCodeError:
                errors["base"] = "invalid_enroll_code"
            except MityConnectionError:
                errors["base"] = "cannot_connect"
            except MityApiError:
                errors["base"] = "unknown"
            else:
                return await self._finish_reauth(entry, result)

        return self.async_show_form(
            step_id="reauth_new_code",
            data_schema=vol.Schema({vol.Required(CONF_ENROLL_CODE): str}),
            errors=errors,
            description_placeholders={"nickname": entry.title},
        )

    async def _finish_reauth(self, entry: ConfigEntry, result: Any) -> Any:
        self.hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_INSTANCE_ID: result.instance_id,
                CONF_DEVICE_API_KEY: result.device_api_key,
                CONF_REJOIN_TOKEN: result.rejoin_token,
            },
        )
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")


class MityOptionsFlow(OptionsFlow):
    """Edit parameter mapping and submission frequency after setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._pending: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        if user_input is not None:
            nickname = user_input.pop(CONF_STUDY_NICKNAME, None)
            if nickname:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    title=nickname,
                    data={**self._entry.data, CONF_STUDY_NICKNAME: nickname},
                )
            self._pending = {
                k: v for k, v in user_input.items() if v is not None
            }
            return await self.async_step_frequency()

        schema_dict = dict(_parameters_schema(dict(self._entry.options)).schema)
        schema_dict[
            vol.Optional(
                CONF_STUDY_NICKNAME,
                default=self._entry.data.get(
                    CONF_STUDY_NICKNAME, DEFAULT_STUDY_NICKNAME
                ),
            )
        ] = str
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
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
