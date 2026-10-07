"""Fetch and aggregate hourly Pstryk meter data."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PstrykApi, PstrykApiError
from .const import (
    CONF_API_KEY, CONF_HOLIDAYS, CONF_WEEKDAY_PEAK, CONF_WEEKEND_PEAK,
    DEFAULT_HOLIDAYS_OFFPEAK, DEFAULT_WEEKDAY_PEAK, DEFAULT_WEEKEND_PEAK,
    DOMAIN, HISTORY_DAYS, UPDATE_INTERVAL,
)
from .tariff import is_peak

WARSAW = ZoneInfo("Europe/Warsaw")


def _frames(payload: dict[str, Any]) -> list[dict[str, Any]]:
    frames = payload.get("frames", [])
    return frames if isinstance(frames, list) else []


def _nested(frame: dict[str, Any], metric: str) -> dict[str, Any]:
    value: Any = frame.get("metrics", frame)
    if isinstance(value, dict) and metric in value and isinstance(value[metric], dict):
        value = value[metric]
    return value if isinstance(value, dict) else frame


def _frame_time(frame: dict[str, Any]) -> datetime | None:
    for key in ("start", "timestamp", "time", "datetime", "period_start", "interval_start"):
        value = frame.get(key)
        if value:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return parsed.replace(tzinfo=WARSAW) if parsed.tzinfo is None else parsed.astimezone(WARSAW)
            except ValueError:
                continue
    return None


def _number(mapping: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


class PstrykCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate at a 30 minute cadence, below Pstryk's per-endpoint limit."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, logger=logging.getLogger(__package__), name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.entry = entry
        shared_state = hass.data.setdefault(DOMAIN, {}).setdefault("_api_state", {})
        self.api = PstrykApi(async_get_clientsession(hass), entry.data[CONF_API_KEY], shared_state)

    async def _async_update_data(self) -> dict[str, Any]:
        now = datetime.now(WARSAW)
        start = datetime.combine(now.date().replace(day=1), time.min, WARSAW)
        # Include enough previous-month data for daily/monthly stats near month start.
        start -= timedelta(days=HISTORY_DAYS - 1)
        end = now + timedelta(minutes=1)
        try:
            usage, cost = await asyncio.gather(
                self.api.fetch("/integrations/meter-data/energy-usage/", "hour", start, end),
                self.api.fetch("/integrations/meter-data/energy-cost/", "hour", start, end),
            )
        except PstrykApiError as err:
            raise UpdateFailed(str(err)) from err

        weekday = self.entry.options.get(CONF_WEEKDAY_PEAK, DEFAULT_WEEKDAY_PEAK)
        weekend = self.entry.options.get(CONF_WEEKEND_PEAK, DEFAULT_WEEKEND_PEAK)
        holidays_offpeak = self.entry.options.get(CONF_HOLIDAYS, DEFAULT_HOLIDAYS_OFFPEAK)
        daily: dict[str, dict[str, float]] = {}
        monthly: dict[str, dict[str, float]] = {}
        total = {"peak": 0.0, "offpeak": 0.0, "peak_cost": 0.0, "offpeak_cost": 0.0}
        month_costs = {"peak": 0.0, "offpeak": 0.0}
        usages: dict[str, float] = {}
        costs: dict[str, float] = {}
        for frame in _frames(usage):
            stamp = _frame_time(frame)
            values = _nested(frame, "energy_usage")
            amount = _number(values, "fae_usage", "energy_usage", "usage", "consumption")
            if stamp is not None and amount is not None:
                usages[stamp.isoformat()] = amount
        for frame in _frames(cost):
            stamp = _frame_time(frame)
            values = _nested(frame, "energy_cost")
            amount = _number(values, "fae_cost", "energy_cost", "cost", "cost_value")
            if stamp is not None and amount is not None:
                costs[stamp.isoformat()] = amount

        for stamp_key, amount in usages.items():
            stamp = datetime.fromisoformat(stamp_key)
            bucket = "peak" if is_peak(stamp, weekday, weekend, holidays_offpeak) else "offpeak"
            day_key, month_key = stamp.date().isoformat(), stamp.strftime("%Y-%m")
            daily.setdefault(day_key, {"peak": 0.0, "offpeak": 0.0})[bucket] += amount
            monthly.setdefault(month_key, {"peak": 0.0, "offpeak": 0.0})[bucket] += amount
            cost_value = costs.get(stamp_key)
            if stamp.strftime("%Y-%m") == now.strftime("%Y-%m") and cost_value is not None:
                month_costs[bucket] += cost_value
            if stamp.date() == now.date():
                total[bucket] += amount
                if cost_value is not None:
                    total[f"{bucket}_cost"] += cost_value

        today = daily.get(now.date().isoformat(), {"peak": 0.0, "offpeak": 0.0})
        current_month = monthly.get(now.strftime("%Y-%m"), {"peak": 0.0, "offpeak": 0.0})
        current_month_cost = sum(costs.get(key, 0.0) for key in costs if datetime.fromisoformat(key).strftime("%Y-%m") == now.strftime("%Y-%m"))
        day_cost = sum(costs.get(key, 0.0) for key in costs if datetime.fromisoformat(key).date() == now.date())
        return {
            "today": today, "month": current_month, "daily": daily, "monthly": monthly,
            "daily_cost": day_cost, "monthly_cost": current_month_cost,
            "today_cost_peak": total["peak_cost"], "today_cost_offpeak": total["offpeak_cost"],
            "month_cost_peak": month_costs["peak"], "month_cost_offpeak": month_costs["offpeak"],
            "last_update": now.isoformat(), "usage_frames": len(usages), "cost_frames": len(costs),
            "available": bool(usages), "today_available": now.date().isoformat() in daily,
            "month_available": now.strftime("%Y-%m") in monthly,
            "today_cost_available": any(datetime.fromisoformat(key).date() == now.date() for key in costs),
            "month_cost_available": any(datetime.fromisoformat(key).strftime("%Y-%m") == now.strftime("%Y-%m") for key in costs),
        }

    def diagnostics(self) -> dict[str, Any]:
        data = self.data or {}
        return {
            "api_key_configured": bool(self.entry.data.get(CONF_API_KEY)),
            "last_update": data.get("last_update"),
            "usage_frames": data.get("usage_frames", 0), "cost_frames": data.get("cost_frames", 0),
            "weekday_peak_hours": self.entry.options.get(CONF_WEEKDAY_PEAK, DEFAULT_WEEKDAY_PEAK),
            "weekend_peak_hours": self.entry.options.get(CONF_WEEKEND_PEAK, DEFAULT_WEEKEND_PEAK),
            "holidays_offpeak": self.entry.options.get(CONF_HOLIDAYS, DEFAULT_HOLIDAYS_OFFPEAK),
        }
