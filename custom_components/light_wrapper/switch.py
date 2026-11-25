"""Switch-Plattform: Standardwerte auch bei schon eingeschalteter Gruppe anwenden."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LightWrapperConfigEntry
from .const import CONF_APPLY_WHEN_ON, DEFAULT_APPLY_WHEN_ON
from .entity import LightWrapperSettingEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LightWrapperConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Einen Schalter pro Lichtgruppe anlegen."""
    for subentry_id in entry.runtime_data.groups:
        async_add_entities(
            [ApplyWhenOnSwitch(entry, subentry_id)], config_subentry_id=subentry_id
        )


class ApplyWhenOnSwitch(LightWrapperSettingEntity, SwitchEntity):
    """An: ein turn_on ohne Parameter setzt auch bei eingeschalteter Gruppe die Standardwerte.

    Standardmäßig an. Der Wert steht nur in den Einstellungen der Gruppe,
    wenn der Schalter aus ist.
    """

    _option_key = CONF_APPLY_WHEN_ON
    _attr_translation_key = "apply_defaults_when_on"
    _attr_icon = "mdi:lightbulb-auto"

    @property
    def is_on(self) -> bool:
        return self._data.apply_when_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._store(None if DEFAULT_APPLY_WHEN_ON else True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._store(False if DEFAULT_APPLY_WHEN_ON else None)
