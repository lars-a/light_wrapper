"""Light Wrapper: fasst mehrere Lichter zu einer Lichtentität mit Standardwerten zusammen."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES, Platform
from homeassistant.core import HomeAssistant, callback

from .const import CONF_APPLY_WHEN_ON, DEFAULT_APPLY_WHEN_ON, DEFAULT_KEYS

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.NUMBER, Platform.SWITCH]


@dataclass
class LightWrapperData:
    """Laufzeitdaten eines Config Entries."""

    entities: list[str]
    defaults: dict[str, int]
    apply_when_on: bool = DEFAULT_APPLY_WHEN_ON
    _listeners: list[Callable[[], None]] = field(default_factory=list)

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Callback registrieren, der bei geänderten Einstellungen aufgerufen wird."""
        self._listeners.append(update_callback)

        @callback
        def _remove() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return _remove

    @callback
    def async_set_settings(self, defaults: dict[str, int], apply_when_on: bool) -> None:
        """Standardwerte und Verhalten bei eingeschalteter Gruppe ersetzen, Listener informieren."""
        self.defaults = defaults
        self.apply_when_on = apply_when_on
        for update_callback in list(self._listeners):
            update_callback()


type LightWrapperConfigEntry = ConfigEntry[LightWrapperData]


def defaults_from_options(options: Mapping[str, Any]) -> dict[str, int]:
    """Nur gesetzte Standardwerte aus den Optionen übernehmen."""
    return {
        key: int(options[key]) for key in DEFAULT_KEYS if options.get(key) is not None
    }


def apply_when_on_from_options(options: Mapping[str, Any]) -> bool:
    """Schalter „auch wenn an“; fehlt er in den Optionen, gilt der Standard (an)."""
    return bool(options.get(CONF_APPLY_WHEN_ON, DEFAULT_APPLY_WHEN_ON))


async def async_setup_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Config Entry einrichten."""
    entry.runtime_data = LightWrapperData(
        entities=list(entry.options.get(CONF_ENTITIES, [])),
        defaults=defaults_from_options(entry.options),
        apply_when_on=apply_when_on_from_options(entry.options),
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> None:
    """Auf geänderte Optionen reagieren.

    Ändern sich nur die Werte der Standardwerte (z. B. über die Number-Entitäten)
    oder der Schalter „auch wenn an“,
    wird nicht neu geladen, damit die Lichtentität nicht kurz verschwindet.
    Ändern sich die Lichter oder wird ein Standardwert an- bzw. abgeschaltet,
    wird der Entry neu geladen.
    """
    data = entry.runtime_data
    new_entities = list(entry.options.get(CONF_ENTITIES, []))
    new_defaults = defaults_from_options(entry.options)

    if new_entities == data.entities and new_defaults.keys() == data.defaults.keys():
        data.async_set_settings(new_defaults, apply_when_on_from_options(entry.options))
        return

    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Config Entry entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
