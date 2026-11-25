"""Number-Plattform: Standardwerte direkt in der Oberfläche und in Automationen einstellen."""

from __future__ import annotations

from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import LightWrapperConfigEntry
from .const import (
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    MAX_BRIGHTNESS_PCT,
    MAX_COLOR_TEMP_KELVIN,
    MIN_BRIGHTNESS_PCT,
    MIN_COLOR_TEMP_KELVIN,
)
from .entity import color_temp_range, device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LightWrapperConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Nur für aktivierte Standardwerte eine Number-Entität anlegen."""
    defaults = entry.runtime_data.defaults
    entities: list[NumberEntity] = []
    if CONF_DEFAULT_BRIGHTNESS in defaults:
        entities.append(DefaultBrightnessNumber(entry))
    if CONF_DEFAULT_COLOR_TEMP in defaults:
        entities.append(DefaultColorTempNumber(entry))
    async_add_entities(entities)


class _DefaultValueNumber(NumberEntity):
    """Basisklasse: Wert liegt in entry.options, Änderungen werden dort gespeichert."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _option_key: str

    def __init__(self, entry: LightWrapperConfigEntry) -> None:
        self._entry = entry
        self._data = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{self._option_key}"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> float | None:
        return self._data.defaults.get(self._option_key)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._data.async_add_listener(self.async_write_ha_state))

    async def async_set_native_value(self, value: float) -> None:
        self.hass.config_entries.async_update_entry(
            self._entry,
            options={**self._entry.options, self._option_key: int(round(value))},
        )


class DefaultBrightnessNumber(_DefaultValueNumber):
    _option_key = CONF_DEFAULT_BRIGHTNESS
    _attr_translation_key = "default_brightness"
    _attr_icon = "mdi:brightness-6"
    _attr_native_min_value = MIN_BRIGHTNESS_PCT
    _attr_native_max_value = MAX_BRIGHTNESS_PCT
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE


class DefaultColorTempNumber(_DefaultValueNumber):
    """Nur verfügbar, wenn mindestens ein Mitglied Farbtemperatur unterstützt.

    Der Bereich ist der gemeinsame Bereich aller Mitglieder mit Farbtemperatur
    und wird bei jeder Zustandsänderung eines Mitglieds neu bestimmt.
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
