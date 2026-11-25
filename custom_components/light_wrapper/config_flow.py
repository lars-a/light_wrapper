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
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    DOMAIN,
    FALLBACK_BRIGHTNESS_PCT,
    FALLBACK_COLOR_TEMP_KELVIN,
    MAX_BRIGHTNESS_PCT,
    MAX_COLOR_TEMP_KELVIN,
    MIN_BRIGHTNESS_PCT,
    MIN_COLOR_TEMP_KELVIN,
)


# Schalter, ob ein Standardwert verwendet wird (werden nicht gespeichert)
CONF_USE_DEFAULT_BRIGHTNESS = "use_default_brightness"
CONF_USE_DEFAULT_COLOR_TEMP = "use_default_color_temp"

# Schalter -> Wert, mit Startwert für den Slider, solange noch nichts gespeichert ist
_TOGGLES: dict[str, tuple[str, int]] = {
    CONF_USE_DEFAULT_BRIGHTNESS: (CONF_DEFAULT_BRIGHTNESS, FALLBACK_BRIGHTNESS_PCT),
    CONF_USE_DEFAULT_COLOR_TEMP: (CONF_DEFAULT_COLOR_TEMP, FALLBACK_COLOR_TEMP_KELVIN),
}


def _options_schema(exclude_entities: list[str]) -> vol.Schema:
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
                    min=MIN_COLOR_TEMP_KELVIN,
                    max=MAX_COLOR_TEMP_KELVIN,
                    step=50,
                    unit_of_measurement="K",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


def _form_values(options: Mapping[str, Any]) -> dict[str, Any]:
    """Gespeicherte Optionen in Formularwerte (Schalter + Slider) umwandeln."""
    values: dict[str, Any] = {CONF_ENTITIES: list(options.get(CONF_ENTITIES, []))}
    for toggle, (key, fallback) in _TOGGLES.items():
        values[toggle] = options.get(key) is not None
        values[key] = options[key] if options.get(key) is not None else fallback
    return values


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Formularwerte in Optionen umwandeln; abgeschaltete Standardwerte entfallen."""
    options: dict[str, Any] = {CONF_ENTITIES: list(user_input.get(CONF_ENTITIES, []))}
    for toggle, (key, fallback) in _TOGGLES.items():
        if user_input.get(toggle):
            value = user_input.get(key)
            options[key] = int(round(value if value is not None else fallback))
    return options


class LightWrapperConfigFlow(ConfigFlow, domain=DOMAIN):
    """Neuen Wrapper anlegen."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return LightWrapperOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            options = _clean(user_input)
            if not options[CONF_ENTITIES]:
                errors[CONF_ENTITIES] = "no_entities"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data={}, options=options
                )

        schema = vol.Schema({vol.Required(CONF_NAME): selector.TextSelector()}).extend(
            _options_schema([]).schema
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or _form_values({})
            ),
            errors=errors,
        )


class LightWrapperOptionsFlow(OptionsFlow):
    """Lichter und Standardwerte nachträglich ändern."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            options = _clean(user_input)
            if not options[CONF_ENTITIES]:
                errors[CONF_ENTITIES] = "no_entities"
            else:
                return self.async_create_entry(data=options)

        # Die eigene Lichtentität nicht zur Auswahl anbieten (Schleife vermeiden)
        own_entity = er.async_get(self.hass).async_get_entity_id(
            LIGHT_DOMAIN, DOMAIN, self.config_entry.entry_id
        )
        schema = _options_schema([own_entity] if own_entity else [])
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or _form_values(self.config_entry.options)
            ),
            errors=errors,
        )
