"""Pstryk consumption and cost sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import PstrykCoordinator


@dataclass(frozen=True)
class SensorDescription:
    key: str
    name: str
    unit: str
    bucket: str | None = None
    period: str | None = None
    currency: bool = False


DESCRIPTIONS = (
    SensorDescription("today_peak", "Zużycie dziś w szczycie", UnitOfEnergy.KILO_WATT_HOUR, "peak", "today"),
    SensorDescription("today_offpeak", "Zużycie dziś poza szczytem", UnitOfEnergy.KILO_WATT_HOUR, "offpeak", "today"),
    SensorDescription("today_peak_share", "Udział szczytu dziś", "%", "peak", "today"),
    SensorDescription("today_offpeak_share", "Udział poza szczytem dziś", "%", "offpeak", "today"),
    SensorDescription("month_peak", "Zużycie w szczycie w tym miesiącu", UnitOfEnergy.KILO_WATT_HOUR, "peak", "month"),
    SensorDescription("month_offpeak", "Zużycie poza szczytem w tym miesiącu", UnitOfEnergy.KILO_WATT_HOUR, "offpeak", "month"),
    SensorDescription("month_peak_share", "Udział szczytu w tym miesiącu", "%", "peak", "month"),
    SensorDescription("month_offpeak_share", "Udział poza szczytem w tym miesiącu", "%", "offpeak", "month"),
    SensorDescription("today_cost", "Koszt energii dziś wg Pstryk", "PLN", period="daily_cost", currency=True),
    SensorDescription("month_cost", "Koszt energii w tym miesiącu wg Pstryk", "PLN", period="monthly_cost", currency=True),
    SensorDescription("today_peak_cost", "Koszt dziś w szczycie wg Pstryk", "PLN", period="today_cost_peak", currency=True),
    SensorDescription("today_offpeak_cost", "Koszt dziś poza szczytem wg Pstryk", "PLN", period="today_cost_offpeak", currency=True),
    SensorDescription("month_peak_cost", "Koszt w szczycie w tym miesiącu wg Pstryk", "PLN", period="month_cost_peak", currency=True),
    SensorDescription("month_offpeak_cost", "Koszt poza szczytem w tym miesiącu wg Pstryk", "PLN", period="month_cost_offpeak", currency=True),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: PstrykCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PstrykSensor(coordinator, description) for description in DESCRIPTIONS)


class PstrykSensor(CoordinatorEntity[PstrykCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PstrykCoordinator, description: SensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = SensorDeviceClass.MONETARY if description.currency else (SensorDeviceClass.ENERGY if description.unit == UnitOfEnergy.KILO_WATT_HOUR else None)
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 2
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=NAME,
            manufacturer="Pstryk",
            model="Hourly usage API",
        )

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        desc = self.entity_description

        # Cost descriptions store a scalar; usage and share descriptions store a period dictionary.
        if desc.currency:
            is_today = desc.period == "daily_cost" or bool(desc.period and desc.period.startswith("today"))
            availability_key = "today_cost_available" if is_today else "month_cost_available"
            if not data.get(availability_key):
                return None
            value = data.get(desc.period or "")
            return round(float(value), 2) if isinstance(value, (int, float)) else None

        period = desc.period or "today"
        if not data.get("today_available" if period == "today" else "month_available"):
            return None
        values = data.get(period, {})
        if not isinstance(values, dict):
            return None
        peak = float(values.get("peak", 0))
        offpeak = float(values.get("offpeak", 0))
        total = peak + offpeak
        if desc.key.endswith("_share"):
            return round((peak if desc.bucket == "peak" else offpeak) * 100 / total, 2) if total else 0.0
        return round(float(values.get(desc.bucket or "peak", 0)), 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "ostatnia_aktualizacja": data.get("last_update"),
            "dostępne_godziny_zużycia": data.get("usage_frames", 0),
            "dane_dostępne": data.get("available", False),
        }
