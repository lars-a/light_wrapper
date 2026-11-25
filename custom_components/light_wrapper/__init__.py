"""Light Wrapper: fasst mehrere Lichter zu einer Lichtentität mit Standardwerten zusammen.

Es gibt genau einen Config Entry. Seine Optionen sind die globalen Einstellungen
(Standard-Übergangszeiten für alle Gruppen); jede Lichtgruppe ist ein Untereintrag.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_ENTITIES, Platform
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_APPLY_WHEN_ON,
    DEFAULT_APPLY_WHEN_ON,
    DEFAULT_KEYS,
    MAX_TRANSITION,
    MIN_TRANSITION,
    SUBENTRY_TYPE_GROUP,
    TRANSITION_KEYS,
    TRANSITION_STEP,
)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.NUMBER, Platform.SWITCH]


@dataclass
class LightWrapperData:
    """Einstellungen einer Lichtgruppe oder die globalen Einstellungen."""

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


@dataclass
class LightWrapperRuntime:
    """Laufzeitdaten des Config Entries."""

    global_settings: LightWrapperData
    groups: dict[str, LightWrapperData]  # subentry_id -> Einstellungen
    structure: Hashable


type LightWrapperConfigEntry = ConfigEntry[LightWrapperRuntime]


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
    """Nur gesetzte Standardwerte übernehmen."""
    return {
        key: normalize_default(key, options[key])
        for key in DEFAULT_KEYS
        if options.get(key) is not None
    }


def apply_when_on_from_options(options: Mapping[str, Any]) -> bool:
    """Schalter „auch wenn an“; fehlt er, gilt der Standard (an)."""
    return bool(options.get(CONF_APPLY_WHEN_ON, DEFAULT_APPLY_WHEN_ON))


def group_subentries(entry: ConfigEntry) -> dict[str, ConfigSubentry]:
    """Alle Lichtgruppen des Eintrags."""
    return {
        subentry_id: subentry
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_GROUP
    }


def _group_settings(subentry: ConfigSubentry) -> LightWrapperData:
    return LightWrapperData(
        entities=list(subentry.data.get(CONF_ENTITIES, [])),
        defaults=defaults_from_options(subentry.data),
        apply_when_on=apply_when_on_from_options(subentry.data),
    )


def _structure(entry: ConfigEntry) -> Hashable:
    """Alles, was beim Ändern ein Neuladen erfordert.

    Das sind: welche Gruppen es gibt, ihre Namen und Lichter sowie welche
    Standardwerte aktiv sind (davon hängen die Number-Entitäten ab).
    Reine Wertänderungen gehören nicht dazu.
    """
    return (
        frozenset(defaults_from_options(entry.options)),
        tuple(
            (
                subentry_id,
                subentry.title,
                tuple(subentry.data.get(CONF_ENTITIES, [])),
                frozenset(defaults_from_options(subentry.data)),
            )
            for subentry_id, subentry in group_subentries(entry).items()
        ),
    )


async def async_setup_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Config Entry einrichten."""
    entry.runtime_data = LightWrapperRuntime(
        global_settings=LightWrapperData(entities=[], defaults=defaults_from_options(entry.options)),
        groups={
            subentry_id: _group_settings(subentry)
            for subentry_id, subentry in group_subentries(entry).items()
        },
        structure=_structure(entry),
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> None:
    """Auf geänderte Einstellungen reagieren.

    Ändern sich nur Werte (z. B. über die Number-Entitäten oder den Schalter
    „auch wenn an“), wird nicht neu geladen, damit die Lichtentitäten nicht kurz
    verschwinden. Wird eine Gruppe angelegt, gelöscht oder umbenannt, ändern sich
    ihre Lichter oder wird ein Standardwert an- bzw. abgeschaltet, wird neu geladen.
    """
    runtime = entry.runtime_data
    if _structure(entry) != runtime.structure:
        await hass.config_entries.async_reload(entry.entry_id)
        return

    runtime.global_settings.async_set_settings(
        defaults_from_options(entry.options), DEFAULT_APPLY_WHEN_ON
    )
    for subentry_id, subentry in group_subentries(entry).items():
        runtime.groups[subentry_id].async_set_settings(
            defaults_from_options(subentry.data), apply_when_on_from_options(subentry.data)
        )


async def async_unload_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Config Entry entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
