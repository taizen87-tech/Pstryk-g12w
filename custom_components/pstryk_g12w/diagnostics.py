"""Redacted diagnostics."""
from homeassistant.components.diagnostics import async_redact_data

from .coordinator import PstrykCoordinator

TO_REDACT = {"api_key", "Authorization", "token"}


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator: PstrykCoordinator = hass.data[entry.domain][entry.entry_id]
    return async_redact_data(coordinator.diagnostics(), TO_REDACT)
