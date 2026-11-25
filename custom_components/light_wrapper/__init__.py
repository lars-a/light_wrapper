"""Light Wrapper: fasst mehrere Lichter zu einer Lichtentität mit Standardwerten zusammen."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES, Platform
from homeassistant.core import HomeAssistant, callback

from .const import DEFAULT_KEYS

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.NUMBER]


@dataclass
class LightWrapperData:
    """Laufzeitdaten eines Config Entries."""

    entities: list[str]
    defaults: dict[str, int]
    _listeners: list[Callable[[], None]] = field(default_factory=list)

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Callback registrieren, der bei geänderten Standardwerten aufgerufen wird."""
        self._listeners.append(update_callback)

        @callback
        def _remove() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return _remove

    @callback
    def async_set_defaults(self, defaults: dict[str, int]) -> None:
        """Standardwerte ersetzen und Listener informieren."""
        self.defaults = defaults
        for update_callback in list(self._listeners):
            update_callback()


type LightWrapperConfigEntry = ConfigEntry[LightWrapperData]


def defaults_from_options(options: Mapping[str, Any]) -> dict[str, int]:
    """Nur gesetzte Standardwerte aus den Optionen übernehmen."""
    return {
        key: int(options[key]) for key in DEFAULT_KEYS if options.get(key) is not None
    }


async def async_setup_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Config Entry einrichten."""
    entry.runtime_data = LightWrapperData(
        entities=list(entry.options.get(CONF_ENTITIES, [])),
        defaults=defaults_from_options(entry.options),
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> None:
    """Auf geänderte Optionen reagieren.

    Ändern sich nur die Werte der Standardwerte (z. B. über die Number-Entitäten),
    wird nicht neu geladen, damit die Lichtentität nicht kurz verschwindet.
    Ändern sich die Lichter oder wird ein Standardwert an- bzw. abgeschaltet,
    wird der Entry neu geladen.
    """
    data = entry.runtime_data
    new_entities = list(entry.options.get(CONF_ENTITIES, []))
    new_defaults = defaults_from_options(entry.options)

    if new_entities == data.entities and new_defaults.keys() == data.defaults.keys():
        data.async_set_defaults(new_defaults)
        return

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Config Entry entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
