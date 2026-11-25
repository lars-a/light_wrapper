"""Config- und Options-Flow für Light Wrapper."""

from __future__ import annotations

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
    MAX_BRIGHTNESS_PCT,
    MAX_COLOR_TEMP_KELVIN,
    MIN_BRIGHTNESS_PCT,
    MIN_COLOR_TEMP_KELVIN,
)


def _options_schema(exclude_entities: list[str]) -> vol.Schema:
    # BOX statt SLIDER, damit optionale Felder geleert (= Standardwert deaktiviert) werden können
    return vol.Schema(
        {
            vol.Required(CONF_ENTITIES): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=LIGHT_DOMAIN,
                    multiple=True,
                    exclude_entities=exclude_entities,
                )
            ),
            vol.Optional(CONF_DEFAULT_BRIGHTNESS): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_BRIGHTNESS_PCT,
                    max=MAX_BRIGHTNESS_PCT,
                    step=1,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(CONF_DEFAULT_COLOR_TEMP): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_COLOR_TEMP_KELVIN,
                    max=MAX_COLOR_TEMP_KELVIN,
                    step=50,
                    unit_of_measurement="K",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    options: dict[str, Any] = {CONF_ENTITIES: list(user_input.get(CONF_ENTITIES, []))}
    for key in (CONF_DEFAULT_BRIGHTNESS, CONF_DEFAULT_COLOR_TEMP):
        if user_input.get(key) is not None:
            options[key] = int(round(user_input[key]))
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
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
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
                schema, user_input or dict(self.config_entry.options)
            ),
            errors=errors,
        )
