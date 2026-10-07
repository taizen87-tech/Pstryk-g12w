"""Unit tests for schedule and Polish calendar rules."""
from datetime import datetime
from zoneinfo import ZoneInfo

import importlib.util
from pathlib import Path

TARIFF_PATH = Path(__file__).parents[1] / "custom_components" / "pstryk_g12w" / "tariff.py"
SPEC = importlib.util.spec_from_file_location("pstryk_tariff", TARIFF_PATH)
TARIFF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TARIFF)
easter_sunday, is_peak, polish_holidays = TARIFF.easter_sunday, TARIFF.is_peak, TARIFF.polish_holidays

WARSAW = ZoneInfo("Europe/Warsaw")


def test_g12w_weekday_boundaries():
    assert is_peak(datetime(2026, 10, 7, 6, tzinfo=WARSAW), "06:00-13:00,15:00-22:00")
    assert not is_peak(datetime(2026, 10, 7, 13, tzinfo=WARSAW), "06:00-13:00,15:00-22:00")
    assert is_peak(datetime(2026, 10, 7, 15, tzinfo=WARSAW), "06:00-13:00,15:00-22:00")
    assert not is_peak(datetime(2026, 10, 7, 22, tzinfo=WARSAW), "06:00-13:00,15:00-22:00")


def test_weekend_and_holiday():
    assert not is_peak(datetime(2026, 10, 10, 10, tzinfo=WARSAW), "06:00-13:00", "")
    assert not is_peak(datetime(2026, 5, 1, 10, tzinfo=WARSAW), "06:00-13:00", "06:00-22:00")
    assert is_peak(datetime(2026, 5, 1, 10, tzinfo=WARSAW), "06:00-13:00", "06:00-22:00", False)


def test_movable_polish_holidays():
    assert easter_sunday(2026).isoformat() == "2026-04-05"
    holidays = polish_holidays(2026)
    assert datetime(2026, 4, 6).date() in holidays
    assert datetime(2026, 6, 4).date() in holidays
    assert datetime(2026, 12, 24).date() in holidays


def test_dst_aware_classification():
    # The repeated autumn hour still maps to the same local tariff interval.
    first = datetime.fromisoformat("2026-10-25T02:30:00+02:00")
    second = datetime.fromisoformat("2026-10-25T02:30:00+01:00")
    assert is_peak(first, "", "02:00-03:00")
    assert is_peak(second, "", "02:00-03:00")


def test_overnight_range_follows_day_it_started():
    # Friday overnight peak extends into Saturday even when weekends otherwise
    # have no peak interval. The corresponding Sunday night has no such range.
    assert is_peak(datetime(2026, 10, 10, 2, tzinfo=WARSAW), "22:00-06:00", "")
    assert not is_peak(datetime(2026, 10, 11, 2, tzinfo=WARSAW), "22:00-06:00", "")
