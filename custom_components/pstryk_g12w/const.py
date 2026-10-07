"""Constants for Pstryk G12W."""
from datetime import timedelta

DOMAIN = "pstryk_g12w"
NAME = "Pstryk G12W"
API_BASE = "https://api.pstryk.pl"
CONF_API_KEY = "api_key"
CONF_WEEKDAY_PEAK = "weekday_peak"
CONF_WEEKEND_PEAK = "weekend_peak"
CONF_HOLIDAYS = "holidays_offpeak"
DEFAULT_WEEKDAY_PEAK = "06:00-13:00,15:00-22:00"
DEFAULT_WEEKEND_PEAK = ""
DEFAULT_HOLIDAYS_OFFPEAK = True
UPDATE_INTERVAL = timedelta(minutes=30)
HISTORY_DAYS = 35
