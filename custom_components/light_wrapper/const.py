"""Constants for Light Wrapper."""

from __future__ import annotations

DOMAIN = "light_wrapper"

# Action to change a group's defaults, targeting its light entity
SERVICE_SET_DEFAULTS = "set_defaults"

# There are exactly two config entries, both created automatically:
# - "Global settings": its options are the global settings (default transitions)
# - "Light groups": each light group is a subentry of it
# The type is stored in entry.data and also used as the entry's unique_id.
CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_GLOBAL = "global"
ENTRY_TYPE_GROUPS = "groups"
ENTRY_TYPES = (ENTRY_TYPE_GROUPS, ENTRY_TYPE_GLOBAL)
# Keys in the data of an import flow (besides CONF_ENTRY_TYPE)
IMPORT_TITLE = "title"
IMPORT_OPTIONS = "options"
SUBENTRY_TYPE_GROUP = "light_group"

# Entry titles are not translated by Home Assistant, so they are picked once
# from the system language when the entries are created.
ENTRY_TITLES = {
    ENTRY_TYPE_GLOBAL: {"de": "Globale Einstellungen", "en": "Global settings"},
    ENTRY_TYPE_GROUPS: {"de": "Lichtgruppen", "en": "Light groups"},
}

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

# The group only counts as on when all members are on (instead of any member).
# Only a setting in the group's edit dialog, no entity. Off by default;
# only an enabled setting (True) is stored.
CONF_ON_WHEN_ALL_ON = "on_when_all_on"
DEFAULT_ON_WHEN_ALL_ON = False

# Hide the member lights in the UI (entity registry hidden_by=integration),
# like Home Assistant's group helper. Only a setting in the group's edit
# dialog. Off by default; only an enabled setting (True) is stored.
CONF_HIDE_MEMBERS = "hide_members"
# Workaround: send the color temperature again shortly after turning a light on
# (dialog only, no entity; stored only as True)
CONF_RESEND_COLOR_TEMP = "resend_color_temp"
# Seconds between the turn_on that switches a light on and the second one
RESEND_COLOR_TEMP_DELAY = 0.5
# Area for the group's device; only used when the device is created
CONF_AREA = "area_id"

# Value ranges for the settings
MIN_BRIGHTNESS_PCT = 1
MAX_BRIGHTNESS_PCT = 100
MIN_COLOR_TEMP_KELVIN = 2000
MAX_COLOR_TEMP_KELVIN = 6500
MIN_TRANSITION = 0.0
MAX_TRANSITION = 10.0
TRANSITION_STEP = 0.1

# Start values of the sliders while no default is stored
FALLBACK_BRIGHTNESS_PCT = 60
FALLBACK_COLOR_TEMP_KELVIN = 3300
FALLBACK_TRANSITION = 0.5
