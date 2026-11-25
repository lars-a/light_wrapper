"""Konstanten für Light Wrapper."""

from __future__ import annotations

DOMAIN = "light_wrapper"

# Es gibt genau einen Config Entry („Light Wrapper“). Seine Optionen sind die
# globalen Einstellungen; jede Lichtgruppe ist ein Untereintrag (Subentry).
SUBENTRY_TYPE_GROUP = "light_group"
ENTRY_TITLE = "Light Wrapper"

# Schlüssel der Einstellungen (globale in entry.options, Gruppen in subentry.data)
CONF_DEFAULT_BRIGHTNESS = "default_brightness_pct"
CONF_DEFAULT_COLOR_TEMP = "default_color_temp_kelvin"
CONF_DEFAULT_TRANSITION_ON = "default_transition_on"
CONF_DEFAULT_TRANSITION_OFF = "default_transition_off"

TRANSITION_KEYS = (CONF_DEFAULT_TRANSITION_ON, CONF_DEFAULT_TRANSITION_OFF)
DEFAULT_KEYS = (CONF_DEFAULT_BRIGHTNESS, CONF_DEFAULT_COLOR_TEMP, *TRANSITION_KEYS)

# Standardwerte auch anwenden, wenn die Gruppe schon an ist.
# Standardmäßig an; in entry.options steht nur ein abgeschalteter Schalter (False).
CONF_APPLY_WHEN_ON = "apply_defaults_when_on"
DEFAULT_APPLY_WHEN_ON = True

# Wertebereiche für die Einstellungen
MIN_BRIGHTNESS_PCT = 1
MAX_BRIGHTNESS_PCT = 100
MIN_COLOR_TEMP_KELVIN = 2000
MAX_COLOR_TEMP_KELVIN = 6500
MIN_TRANSITION = 0.0
MAX_TRANSITION = 10.0
TRANSITION_STEP = 0.1

# Startwerte der Slider, solange kein Standardwert gespeichert ist
FALLBACK_BRIGHTNESS_PCT = 100
FALLBACK_COLOR_TEMP_KELVIN = 3000
FALLBACK_TRANSITION = 0.5
