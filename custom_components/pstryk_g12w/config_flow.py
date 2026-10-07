"""Config flow for Pstryk G12W."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_API_KEY, CONF_HOLIDAYS, CONF_WEEKDAY_PEAK, CONF_WEEKEND_PEAK,
    DEFAULT_HOLIDAYS_OFFPEAK, DEFAULT_WEEKDAY_PEAK, DEFAULT_WEEKEND_PEAK,
    DOMAIN,
)
from .tariff import parse_ranges


class PstrykConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            if not key:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id("pstryk_meter")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Pstryk G12W",
                    data={CONF_API_KEY: key},
                    options={
                        CONF_WEEKDAY_PEAK: DEFAULT_WEEKDAY_PEAK,
                        CONF_WEEKEND_PEAK: DEFAULT_WEEKEND_PEAK,
                        CONF_HOLIDAYS: DEFAULT_HOLIDAYS_OFFPEAK,
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PstrykOptionsFlow(config_entry)


class PstrykOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            try:
                parse_ranges(user_input.get(CONF_WEEKDAY_PEAK, ""))
                parse_ranges(user_input.get(CONF_WEEKEND_PEAK, ""))
            except (ValueError, TypeError):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(),
                    errors={"base": "invalid_time_range"},
                )
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=self._schema())

    def _schema(self):
        options = self.config_entry.options
        return vol.Schema({
            vol.Optional(CONF_WEEKDAY_PEAK, default=options.get(CONF_WEEKDAY_PEAK, DEFAULT_WEEKDAY_PEAK)): str,
            vol.Optional(CONF_WEEKEND_PEAK, default=options.get(CONF_WEEKEND_PEAK, DEFAULT_WEEKEND_PEAK)): str,
            vol.Optional(CONF_HOLIDAYS, default=options.get(CONF_HOLIDAYS, DEFAULT_HOLIDAYS_OFFPEAK)): bool,
        })
