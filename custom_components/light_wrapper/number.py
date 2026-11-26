"""Number platform: set defaults directly in the UI and in automations."""

from __future__ import annotations

from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import LightWrapperConfigEntry, is_global, normalize_default
from .const import (
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    CONF_DEFAULT_TRANSITION_OFF,
    CONF_DEFAULT_TRANSITION_ON,
    MAX_BRIGHTNESS_PCT,
    MAX_COLOR_TEMP_KELVIN,
    MAX_TRANSITION,
    MIN_BRIGHTNESS_PCT,
    MIN_COLOR_TEMP_KELVIN,
    MIN_TRANSITION,
    TRANSITION_KEYS,
    TRANSITION_STEP,
)
from .entity import LightWrapperSettingEntity, color_temp_range


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LightWrapperConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a number entity only for enabled defaults.

    The global entry only has the transitions; groups have all defaults.
    """
    runtime = entry.runtime_data
    if is_global(entry):
        async_add_entities(
            _NUMBER_CLASSES[key](entry, None)
            for key in TRANSITION_KEYS
            if key in runtime.global_settings.defaults
        )
        return
    for subentry_id, data in runtime.groups.items():
        async_add_entities(
            (
                number_class(entry, subentry_id)
                for key, number_class in _NUMBER_CLASSES.items()
                if key in data.defaults
            ),
            config_subentry_id=subentry_id,
        )


class _DefaultValueNumber(LightWrapperSettingEntity, NumberEntity):
    """Default value as a slider; changes are stored in the settings."""

    _attr_mode = NumberMode.SLIDER

    @property
    def native_value(self) -> float | None:
        return self._data.defaults.get(self._option_key)

    async def async_set_native_value(self, value: float) -> None:
        self._store(normalize_default(self._option_key, value))


class DefaultBrightnessNumber(_DefaultValueNumber):
    _option_key = CONF_DEFAULT_BRIGHTNESS
    _attr_translation_key = "default_brightness"
    _attr_icon = "mdi:brightness-6"
    _attr_native_min_value = MIN_BRIGHTNESS_PCT
    _attr_native_max_value = MAX_BRIGHTNESS_PCT
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE


class DefaultColorTempNumber(_DefaultValueNumber):
    """Only available if at least one member supports color temperature.

    The range is the common range of all members with color temperature and
    is recalculated on every state change of a member.
    """

    _option_key = CONF_DEFAULT_COLOR_TEMP
    _attr_translation_key = "default_color_temp"
    _attr_icon = "mdi:thermometer"
    _attr_native_min_value = MIN_COLOR_TEMP_KELVIN
    _attr_native_max_value = MAX_COLOR_TEMP_KELVIN
    _attr_native_step = 50
    _attr_native_unit_of_measurement = UnitOfTemperature.KELVIN

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _member_changed(event: Event[EventStateChangedData]) -> None:
            self._update_from_members()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(self.hass, self._data.entities, _member_changed)
        )
        self._update_from_members()

    @callback
    def _update_from_members(self) -> None:
        low, high = color_temp_range(self.hass, self._data.entities)
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        self._attr_available = any(
            ColorMode.COLOR_TEMP in (state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) or [])
            for entity_id in self._data.entities
            if (state := self.hass.states.get(entity_id)) is not None
        )


class _DefaultTransitionNumber(_DefaultValueNumber):
    """Default transition in seconds (0–10 s, 0.1 s steps)."""

    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = MIN_TRANSITION
    _attr_native_max_value = MAX_TRANSITION
    _attr_native_step = TRANSITION_STEP
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS


class DefaultTransitionOnNumber(_DefaultTransitionNumber):
    _option_key = CONF_DEFAULT_TRANSITION_ON
    _attr_translation_key = "default_transition_on"


class DefaultTransitionOffNumber(_DefaultTransitionNumber):
    _option_key = CONF_DEFAULT_TRANSITION_OFF
    _attr_translation_key = "default_transition_off"


_NUMBER_CLASSES: dict[str, type[_DefaultValueNumber]] = {
    CONF_DEFAULT_BRIGHTNESS: DefaultBrightnessNumber,
    CONF_DEFAULT_COLOR_TEMP: DefaultColorTempNumber,
    CONF_DEFAULT_TRANSITION_ON: DefaultTransitionOnNumber,
    CONF_DEFAULT_TRANSITION_OFF: DefaultTransitionOffNumber,
}
