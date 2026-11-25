"""Switch-Plattform: Standardwerte auch bei schon eingeschalteter Gruppe anwenden."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LightWrapperConfigEntry
from .const import CONF_APPLY_WHEN_ON
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LightWrapperConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Schalter anlegen."""
    async_add_entities([ApplyWhenOnSwitch(entry)])


class ApplyWhenOnSwitch(SwitchEntity):
    """An: ein turn_on ohne Parameter setzt auch bei eingeschalteter Gruppe die Standardwerte.

    Der Wert liegt in entry.options und wird dort nur gespeichert, wenn er aktiv ist.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "apply_defaults_when_on"
    _attr_icon = "mdi:lightbulb-auto"

    def __init__(self, entry: LightWrapperConfigEntry) -> None:
        self._entry = entry
        self._data = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{CONF_APPLY_WHEN_ON}"
        self._attr_device_info = device_info(entry)

    @property
    def is_on(self) -> bool:
        return self._data.apply_when_on

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._data.async_add_listener(self.async_write_ha_state))

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set(False)

    def _set(self, value: bool) -> None:
        options = {k: v for k, v in self._entry.options.items() if k != CONF_APPLY_WHEN_ON}
        if value:
            options[CONF_APPLY_WHEN_ON] = True
        self.hass.config_entries.async_update_entry(self._entry, options=options)
