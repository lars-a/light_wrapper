"""Config- und Options-Flow für Light Wrapper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ENTITIES, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, selector

from . import apply_when_on_from_options, is_global, normalize_default
from .const import (
    CONF_APPLY_WHEN_ON,
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    CONF_DEFAULT_TRANSITION_OFF,
    CONF_DEFAULT_TRANSITION_ON,
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_GLOBAL,
    FALLBACK_BRIGHTNESS_PCT,
    FALLBACK_COLOR_TEMP_KELVIN,
    FALLBACK_TRANSITION,
    GLOBAL_UNIQUE_ID,
    MAX_BRIGHTNESS_PCT,
    MAX_TRANSITION,
    MIN_BRIGHTNESS_PCT,
    MIN_TRANSITION,
    TRANSITION_STEP,
)
from .entity import clamp, color_temp_range

GLOBAL_TITLE = "Globale Einstellungen"

# Schalter, ob ein Standardwert verwendet wird (werden nicht gespeichert)
CONF_USE_DEFAULT_BRIGHTNESS = "use_default_brightness"
CONF_USE_DEFAULT_COLOR_TEMP = "use_default_color_temp"
CONF_USE_DEFAULT_TRANSITION_ON = "use_default_transition_on"
CONF_USE_DEFAULT_TRANSITION_OFF = "use_default_transition_off"

# Schalter -> Wert, mit Startwert für den Slider, solange noch nichts gespeichert ist
_TRANSITION_TOGGLES: dict[str, tuple[str, float]] = {
    CONF_USE_DEFAULT_TRANSITION_ON: (CONF_DEFAULT_TRANSITION_ON, FALLBACK_TRANSITION),
    CONF_USE_DEFAULT_TRANSITION_OFF: (CONF_DEFAULT_TRANSITION_OFF, FALLBACK_TRANSITION),
}
_GROUP_TOGGLES: dict[str, tuple[str, float]] = {
    CONF_USE_DEFAULT_BRIGHTNESS: (CONF_DEFAULT_BRIGHTNESS, FALLBACK_BRIGHTNESS_PCT),
    CONF_USE_DEFAULT_COLOR_TEMP: (CONF_DEFAULT_COLOR_TEMP, FALLBACK_COLOR_TEMP_KELVIN),
    **_TRANSITION_TOGGLES,
}


def _transition_fields() -> dict[vol.Marker, Any]:
    """Schalter + Slider (0–10 s in 0,1-s-Schritten) für Ein- und Ausschalten."""
    slider = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=MIN_TRANSITION,
            max=MAX_TRANSITION,
            step=TRANSITION_STEP,
            unit_of_measurement="s",
            mode=selector.NumberSelectorMode.SLIDER,
        )
    )
    return {
        vol.Optional(CONF_USE_DEFAULT_TRANSITION_ON): selector.BooleanSelector(),
        vol.Optional(CONF_DEFAULT_TRANSITION_ON): slider,
        vol.Optional(CONF_USE_DEFAULT_TRANSITION_OFF): selector.BooleanSelector(),
        vol.Optional(CONF_DEFAULT_TRANSITION_OFF): slider,
    }


def _group_schema(
    exclude_entities: list[str], color_temp_bounds: tuple[int, int]
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ENTITIES): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=LIGHT_DOMAIN,
                    multiple=True,
                    exclude_entities=exclude_entities,
                )
            ),
            vol.Optional(CONF_USE_DEFAULT_BRIGHTNESS): selector.BooleanSelector(),
            vol.Optional(CONF_DEFAULT_BRIGHTNESS): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_BRIGHTNESS_PCT,
                    max=MAX_BRIGHTNESS_PCT,
                    step=1,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(CONF_USE_DEFAULT_COLOR_TEMP): selector.BooleanSelector(),
            vol.Optional(CONF_DEFAULT_COLOR_TEMP): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=color_temp_bounds[0],
                    max=color_temp_bounds[1],
                    step=50,
                    unit_of_measurement="K",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            **_transition_fields(),
            vol.Optional(CONF_APPLY_WHEN_ON): selector.BooleanSelector(),
        }
    )


def _global_schema() -> vol.Schema:
    return vol.Schema(_transition_fields())


def _toggle_values(
    options: Mapping[str, Any], toggles: Mapping[str, tuple[str, float]]
) -> dict[str, Any]:
    """Gespeicherte Standardwerte als Schalter + Slider vorbelegen."""
    values: dict[str, Any] = {}
    for toggle, (key, fallback) in toggles.items():
        values[toggle] = options.get(key) is not None
        values[key] = options[key] if options.get(key) is not None else fallback
    return values


def _toggle_options(
    user_input: Mapping[str, Any], toggles: Mapping[str, tuple[str, float]]
) -> dict[str, Any]:
    """Nur Standardwerte mit aktivem Schalter übernehmen."""
    options: dict[str, Any] = {}
    for toggle, (key, fallback) in toggles.items():
        if user_input.get(toggle):
            value = user_input.get(key)
            options[key] = normalize_default(key, value if value is not None else fallback)
    return options


def _group_form_values(
    options: Mapping[str, Any], color_temp_bounds: tuple[int, int]
) -> dict[str, Any]:
    """Gespeicherte Optionen einer Gruppe in Formularwerte umwandeln.

    Die Farbtemperatur wird auf den Bereich des Sliders begrenzt, sonst ließe
    sich das Formular mit dem vorbelegten Wert nicht absenden.
    """
    values: dict[str, Any] = {CONF_ENTITIES: list(options.get(CONF_ENTITIES, []))}
    values.update(_toggle_values(options, _GROUP_TOGGLES))
    values[CONF_DEFAULT_COLOR_TEMP] = clamp(values[CONF_DEFAULT_COLOR_TEMP], color_temp_bounds)
    values[CONF_APPLY_WHEN_ON] = apply_when_on_from_options(options)
    return values


def _group_options(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, Any]:
    """Formularwerte einer Gruppe in Optionen umwandeln; abgeschaltete Standardwerte entfallen.

    Der Schalter „auch wenn an“ wird nur gespeichert, wenn er abgeschaltet ist.

    Die Farbtemperatur wird auf den gemeinsamen Bereich der gewählten Lichter
    begrenzt (die Lichtauswahl kann sich im selben Formular geändert haben).
    """
    options: dict[str, Any] = {CONF_ENTITIES: list(user_input.get(CONF_ENTITIES, []))}
    options.update(_toggle_options(user_input, _GROUP_TOGGLES))
    if not apply_when_on_from_options(user_input):
        options[CONF_APPLY_WHEN_ON] = False
    if CONF_DEFAULT_COLOR_TEMP in options:
        options[CONF_DEFAULT_COLOR_TEMP] = clamp(
            options[CONF_DEFAULT_COLOR_TEMP],
            color_temp_range(hass, options[CONF_ENTITIES]),
        )
    return options


class LightWrapperConfigFlow(ConfigFlow, domain=DOMAIN):
    """Neue Lichtgruppe oder die globalen Einstellungen anlegen."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return LightWrapperOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Auswahl anbieten, solange es noch keine globalen Einstellungen gibt."""
        if any(is_global(entry) for entry in self._async_current_entries()):
            return await self.async_step_group()
        return self.async_show_menu(step_id="user", menu_options=["group", "global"])

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            options = _group_options(self.hass, user_input)
            if not options[CONF_ENTITIES]:
                errors[CONF_ENTITIES] = "no_entities"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data={}, options=options
                )

        # Die Lichter sind hier noch nicht gewählt: fester Bereich für den Slider
        bounds = color_temp_range(self.hass, [])
        schema = vol.Schema({vol.Required(CONF_NAME): selector.TextSelector()}).extend(
            _group_schema([], bounds).schema
        )
        return self.async_show_form(
            step_id="group",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or _group_form_values({}, bounds)
            ),
            errors=errors,
        )

    async def async_step_global(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(GLOBAL_UNIQUE_ID)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(
                title=GLOBAL_TITLE,
                data={CONF_ENTRY_TYPE: ENTRY_TYPE_GLOBAL},
                options=_toggle_options(user_input, _TRANSITION_TOGGLES),
            )
        return self.async_show_form(
            step_id="global",
            data_schema=self.add_suggested_values_to_schema(
                _global_schema(), _toggle_values({}, _TRANSITION_TOGGLES)
            ),
        )


class LightWrapperOptionsFlow(OptionsFlow):
    """Einstellungen einer Lichtgruppe oder die globalen Einstellungen ändern."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if is_global(self.config_entry):
            return await self.async_step_global(user_input)

        errors: dict[str, str] = {}
        if user_input is not None:
            options = _group_options(self.hass, user_input)
            if not options[CONF_ENTITIES]:
                errors[CONF_ENTITIES] = "no_entities"
            else:
                return self.async_create_entry(data=options)

        # Die eigene Lichtentität nicht zur Auswahl anbieten (Schleife vermeiden)
        own_entity = er.async_get(self.hass).async_get_entity_id(
            LIGHT_DOMAIN, DOMAIN, self.config_entry.entry_id
        )
        # Slider-Bereich: gemeinsamer Bereich der aktuell gespeicherten Lichter
        bounds = color_temp_range(self.hass, self.config_entry.options.get(CONF_ENTITIES, []))
        schema = _group_schema([own_entity] if own_entity else [], bounds)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or _group_form_values(self.config_entry.options, bounds)
            ),
            errors=errors,
        )

    async def async_step_global(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data=_toggle_options(user_input, _TRANSITION_TOGGLES)
            )
        return self.async_show_form(
            step_id="global",
            data_schema=self.add_suggested_values_to_schema(
                _global_schema(),
                _toggle_values(self.config_entry.options, _TRANSITION_TOGGLES),
            ),
        )
