"""Config, options and subentry flows for Light Wrapper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_ENTITIES, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, selector

from . import (
    apply_when_on_from_options,
    is_global,
    normalize_default,
    on_when_all_on_from_options,
)
from .const import (
    CONF_APPLY_WHEN_ON,
    CONF_AREA,
    CONF_HIDE_MEMBERS,
    CONF_ON_WHEN_ALL_ON,
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    CONF_DEFAULT_TRANSITION_OFF,
    CONF_DEFAULT_TRANSITION_ON,
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TITLES,
    ENTRY_TYPE_GROUPS,
    ENTRY_TYPES,
    IMPORT_OPTIONS,
    IMPORT_TITLE,
    FALLBACK_BRIGHTNESS_PCT,
    FALLBACK_COLOR_TEMP_KELVIN,
    FALLBACK_TRANSITION,
    MAX_BRIGHTNESS_PCT,
    MAX_TRANSITION,
    MIN_BRIGHTNESS_PCT,
    MIN_TRANSITION,
    SUBENTRY_TYPE_GROUP,
    TRANSITION_STEP,
)
from .entity import clamp, color_temp_range

# Toggles that decide whether a default is used (they are not stored)
CONF_USE_DEFAULT_BRIGHTNESS = "use_default_brightness"
CONF_USE_DEFAULT_COLOR_TEMP = "use_default_color_temp"
CONF_USE_DEFAULT_TRANSITION_ON = "use_default_transition_on"
CONF_USE_DEFAULT_TRANSITION_OFF = "use_default_transition_off"

# Toggle -> value, with the slider's start value while nothing is stored yet
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
    """Toggle + slider (0–10 s in 0.1 s steps) for turning on and off."""
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
            vol.Optional(CONF_ON_WHEN_ALL_ON): selector.BooleanSelector(),
            vol.Optional(CONF_HIDE_MEMBERS): selector.BooleanSelector(),
        }
    )


def _global_schema() -> vol.Schema:
    return vol.Schema(_transition_fields())


def _toggle_values(
    options: Mapping[str, Any], toggles: Mapping[str, tuple[str, float]]
) -> dict[str, Any]:
    """Prefill stored defaults as toggle + slider."""
    values: dict[str, Any] = {}
    for toggle, (key, fallback) in toggles.items():
        values[toggle] = options.get(key) is not None
        values[key] = options[key] if options.get(key) is not None else fallback
    return values


def _toggle_options(
    user_input: Mapping[str, Any], toggles: Mapping[str, tuple[str, float]]
) -> dict[str, Any]:
    """Take over only defaults whose toggle is on."""
    options: dict[str, Any] = {}
    for toggle, (key, fallback) in toggles.items():
        if user_input.get(toggle):
            value = user_input.get(key)
            options[key] = normalize_default(key, value if value is not None else fallback)
    return options


def _group_form_values(
    options: Mapping[str, Any], color_temp_bounds: tuple[int, int]
) -> dict[str, Any]:
    """Convert a group's stored settings to form values.

    The color temperature is limited to the slider's range; otherwise the form
    could not be submitted with the prefilled value.
    """
    values: dict[str, Any] = {CONF_ENTITIES: list(options.get(CONF_ENTITIES, []))}
    values.update(_toggle_values(options, _GROUP_TOGGLES))
    values[CONF_DEFAULT_COLOR_TEMP] = clamp(values[CONF_DEFAULT_COLOR_TEMP], color_temp_bounds)
    values[CONF_APPLY_WHEN_ON] = apply_when_on_from_options(options)
    values[CONF_ON_WHEN_ALL_ON] = on_when_all_on_from_options(options)
    values[CONF_HIDE_MEMBERS] = bool(options.get(CONF_HIDE_MEMBERS))
    return values


def _group_options(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert a group's form values to settings; disabled defaults are dropped.

    The "apply when on" switch is only stored when it is off, the "on only when
    all are on" and "hide members" settings only when they are on (all only
    when not the default).

    The color temperature is limited to the common range of the selected lights
    (the selection may have changed in the same form).
    """
    options: dict[str, Any] = {CONF_ENTITIES: list(user_input.get(CONF_ENTITIES, []))}
    options.update(_toggle_options(user_input, _GROUP_TOGGLES))
    if not apply_when_on_from_options(user_input):
        options[CONF_APPLY_WHEN_ON] = False
    if on_when_all_on_from_options(user_input):
        options[CONF_ON_WHEN_ALL_ON] = True
    if user_input.get(CONF_HIDE_MEMBERS):
        options[CONF_HIDE_MEMBERS] = True
    if CONF_DEFAULT_COLOR_TEMP in options:
        options[CONF_DEFAULT_COLOR_TEMP] = clamp(
            options[CONF_DEFAULT_COLOR_TEMP],
            color_temp_range(hass, options[CONF_ENTITIES]),
        )
    return options


def _with_name(name: str | None, schema: vol.Schema, *, area: bool = False) -> vol.Schema:
    """Put the name (and, when adding a group, the area) in front of the form."""
    fields: dict[vol.Marker, Any] = {
        vol.Required(CONF_NAME, default=name or vol.UNDEFINED): selector.TextSelector()
    }
    if area:
        fields[vol.Optional(CONF_AREA)] = selector.AreaSelector()
    return vol.Schema(fields).extend(schema.schema)


class LightWrapperConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the integration: creates the "Light groups" and "Global settings" entries.

    Both are created right away without questions. Light groups are added
    afterwards as subentries of "Light groups".
    """

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return LightWrapperOptionsFlow()

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ConfigEntry) -> bool:
        # Only the global entry has a "Configure" dialog
        return is_global(config_entry)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        # "Add light group" only on the groups entry
        if config_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_GROUPS:
            return {SUBENTRY_TYPE_GROUP: LightGroupSubentryFlow}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create the missing entries; the second one via its own flow."""
        existing = {
            entry.data.get(CONF_ENTRY_TYPE) for entry in self._async_current_entries()
        }
        missing = [entry_type for entry_type in ENTRY_TYPES if entry_type not in existing]
        if not missing:
            return self.async_abort(reason="already_configured")

        first, *others = missing
        for entry_type in others:
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    # Not SOURCE_SYSTEM: the UI hides "Delete" for system entries
                    context={"source": SOURCE_IMPORT},
                    data={CONF_ENTRY_TYPE: entry_type},
                )
            )
        return await self._async_create(first)

    async def async_step_import(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry started by async_step_user or async_setup.

        Title and options are optional (used when an old entry is replaced).
        """
        return await self._async_create(
            data[CONF_ENTRY_TYPE], data.get(IMPORT_TITLE), data.get(IMPORT_OPTIONS)
        )

    async def _async_create(
        self,
        entry_type: str,
        title: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(entry_type)
        self._abort_if_unique_id_configured()
        if title is None:
            titles = ENTRY_TITLES[entry_type]
            language = (self.hass.config.language or "en").split("-")[0]
            title = titles.get(language, titles["en"])
        return self.async_create_entry(
            title=title, data={CONF_ENTRY_TYPE: entry_type}, options=options or {}
        )


class LightWrapperOptionsFlow(OptionsFlow):
    """Change the global settings (default transitions for all groups)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data=_toggle_options(user_input, _TRANSITION_TOGGLES)
            )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _global_schema(),
                _toggle_values(self.config_entry.options, _TRANSITION_TOGGLES),
            ),
        )


class LightGroupSubentryFlow(ConfigSubentryFlow):
    """Add or edit a light group."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            options = _group_options(self.hass, user_input)
            if not options[CONF_ENTITIES]:
                errors[CONF_ENTITIES] = "no_entities"
            else:
                # Only needed to create the device; changed later on the device itself
                if user_input.get(CONF_AREA):
                    options[CONF_AREA] = user_input[CONF_AREA]
                return self.async_create_entry(title=user_input[CONF_NAME], data=options)

        # No lights are selected yet: fixed range for the slider
        bounds = color_temp_range(self.hass, [])
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _with_name(None, _group_schema([], bounds), area=True),
                user_input or _group_form_values({}, bounds),
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            options = _group_options(self.hass, user_input)
            if not options[CONF_ENTITIES]:
                errors[CONF_ENTITIES] = "no_entities"
            else:
                return self.async_update_and_abort(
                    entry, subentry, title=user_input[CONF_NAME], data=options
                )

        # Do not offer the group's own light entity (avoid loops)
        own_entity = er.async_get(self.hass).async_get_entity_id(
            LIGHT_DOMAIN, DOMAIN, subentry.subentry_id
        )
        # Slider range: common range of the currently stored lights
        bounds = color_temp_range(self.hass, subentry.data.get(CONF_ENTITIES, []))
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _with_name(subentry.title, _group_schema([own_entity] if own_entity else [], bounds)),
                user_input or _group_form_values(subentry.data, bounds),
            ),
            errors=errors,
        )
