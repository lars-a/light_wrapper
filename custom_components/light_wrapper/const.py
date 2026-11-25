"""Konstanten für Light Wrapper."""

from __future__ import annotations

DOMAIN = "light_wrapper"

# Option keys (werden in entry.options gespeichert)
CONF_DEFAULT_BRIGHTNESS = "default_brightness_pct"
CONF_DEFAULT_COLOR_TEMP = "default_color_temp_kelvin"

DEFAULT_KEYS = (CONF_DEFAULT_BRIGHTNESS, CONF_DEFAULT_COLOR_TEMP)

# Wertebereiche für die Einstellungen
MIN_BRIGHTNESS_PCT = 1
MAX_BRIGHTNESS_PCT = 100
MIN_COLOR_TEMP_KELVIN = 2000
MAX_COLOR_TEMP_KELVIN = 6500
