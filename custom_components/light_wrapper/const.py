"""Constants for Light Wrapper."""

from __future__ import annotations

DOMAIN = "light_wrapper"

# There is exactly one config entry ("Light Wrapper"). Its options are the
# global settings; each light group is a subentry.
SUBENTRY_TYPE_GROUP = "light_group"
ENTRY_TITLE = "Light Wrapper"

# Setting keys (global ones in entry.options, groups in subentry.data)
CONF_DEFAULT_BRIGHTNESS = "default_brightness_pct"
CONF_DEFAULT_COLOR_TEMP = "default_color_temp_kelvin"
CONF_DEFAULT_TRANSITION_ON = "default_transition_on"
CONF_DEFAULT_TRANSITION_OFF = "default_transition_off"

TRANSITION_KEYS = (CONF_DEFAULT_TRANSITION_ON, CONF_DEFAULT_TRANSITION_OFF)
DEFAULT_KEYS = (CONF_DEFAULT_BRIGHTNESS, CONF_DEFAULT_COLOR_TEMP, *TRANSITION_KEYS)

# Apply the defaults even if the group is already on.
# On by default; only a disabled switch (False) is stored.
CONF_APPLY_WHEN_ON = "apply_defaults_when_on"
DEFAULT_APPLY_WHEN_ON = True

# Value ranges for the settings
MIN_BRIGHTNESS_PCT = 1
MAX_BRIGHTNESS_PCT = 100
MIN_COLOR_TEMP_KELVIN = 2000
MAX_COLOR_TEMP_KELVIN = 6500
MIN_TRANSITION = 0.0
MAX_TRANSITION = 10.0
TRANSITION_STEP = 0.1

# Start values of the sliders while no default is stored
FALLBACK_BRIGHTNESS_PCT = 100
FALLBACK_COLOR_TEMP_KELVIN = 3000
FALLBACK_TRANSITION = 0.5
