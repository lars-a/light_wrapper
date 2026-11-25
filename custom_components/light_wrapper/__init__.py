"""Light Wrapper: fasst mehrere Lichter zu einer Lichtentität mit Standardwerten zusammen."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ENTITIES, Platform
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_APPLY_WHEN_ON,
    CONF_ENTRY_TYPE,
    DEFAULT_APPLY_WHEN_ON,
    DEFAULT_KEYS,
    DOMAIN,
    ENTRY_TYPE_GLOBAL,
    MAX_TRANSITION,
    MIN_TRANSITION,
    TRANSITION_KEYS,
    TRANSITION_STEP,
)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.NUMBER, Platform.SWITCH]
# Der Eintrag „Globale Einstellungen“ hat nur Number-Entitäten
GLOBAL_PLATFORMS: list[Platform] = [Platform.NUMBER]


@dataclass
class LightWrapperData:
    """Laufzeitdaten eines Config Entries (Lichtgruppe oder globale Einstellungen)."""

    entities: list[str]
    defaults: dict[str, float]
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
    def async_set_settings(self, defaults: dict[str, float], apply_when_on: bool) -> None:
        """Standardwerte und Verhalten bei eingeschalteter Gruppe ersetzen, Listener informieren."""
        self.defaults = defaults
        self.apply_when_on = apply_when_on
        for update_callback in list(self._listeners):
            update_callback()


type LightWrapperConfigEntry = ConfigEntry[LightWrapperData]


def is_global(entry: ConfigEntry) -> bool:
    """True für den Eintrag „Globale Einstellungen“."""
    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_GLOBAL


def normalize_default(key: str, value: Any) -> float | int:
    """Standardwert ins gespeicherte Format bringen.

    Übergangszeiten: Sekunden, auf 0,1 s gerundet und auf 0–10 s begrenzt.
    Alles andere: ganze Zahl.
    """
    if key in TRANSITION_KEYS:
        seconds = round(round(float(value) / TRANSITION_STEP) * TRANSITION_STEP, 1)
        return max(MIN_TRANSITION, min(MAX_TRANSITION, seconds))
    return int(round(value))


def defaults_from_options(options: Mapping[str, Any]) -> dict[str, float]:
    """Nur gesetzte Standardwerte aus den Optionen übernehmen."""
    return {
        key: normalize_default(key, options[key])
        for key in DEFAULT_KEYS
        if options.get(key) is not None
    }


def apply_when_on_from_options(options: Mapping[str, Any]) -> bool:
    """Schalter „auch wenn an“; fehlt er in den Optionen, gilt der Standard (an)."""
    return bool(options.get(CONF_APPLY_WHEN_ON, DEFAULT_APPLY_WHEN_ON))


@callback
def global_defaults(hass: HomeAssistant) -> dict[str, float]:
    """Standardwerte des geladenen Eintrags „Globale Einstellungen“ (leer, wenn es keinen gibt)."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if is_global(entry) and entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data.defaults
    return {}


def _platforms(entry: ConfigEntry) -> list[Platform]:
    return GLOBAL_PLATFORMS if is_global(entry) else PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Config Entry einrichten."""
    entry.runtime_data = LightWrapperData(
        entities=list(entry.options.get(CONF_ENTITIES, [])),
        defaults=defaults_from_options(entry.options),
        apply_when_on=apply_when_on_from_options(entry.options),
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> None:
    """Auf geänderte Optionen reagieren.

    Ändern sich nur die Werte der Standardwerte (z. B. über die Number-Entitäten)
    oder der Schalter „auch wenn an“, wird nicht neu geladen, damit die
    Lichtentität nicht kurz verschwindet. Ändern sich die Lichter oder wird ein
    Standardwert an- bzw. abgeschaltet, wird der Entry neu geladen.
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
    return await hass.config_entries.async_unload_platforms(entry, _platforms(entry))
