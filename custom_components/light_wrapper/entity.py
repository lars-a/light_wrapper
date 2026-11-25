"""Gemeinsame Helfer für Entitäten."""

from __future__ import annotations

from collections.abc import Iterable

from homeassistant.components.light import (
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import (
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_GLOBAL,
    MAX_COLOR_TEMP_KELVIN,
    MIN_COLOR_TEMP_KELVIN,
)


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """Ein virtuelles Gerät pro Eintrag, damit Licht und Einstellungen zusammen erscheinen."""
    global_entry = entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_GLOBAL
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Light Wrapper",
        model="Globale Einstellungen" if global_entry else "Lichtgruppe",
    )


def color_temp_range(hass: HomeAssistant, entity_ids: Iterable[str]) -> tuple[int, int]:
    """Farbtemperaturbereich, den alle Mitglieder mit Farbtemperatur gemeinsam haben.

    Berücksichtigt werden nur Mitglieder, die Farbtemperatur unterstützen und
    ihren Bereich melden. Ist keines bekannt (z. B. weil die Lichter noch nicht
    geladen sind), gilt der feste Bereich. Überschneiden sich die Bereiche nicht,
    wird ersatzweise der Gesamtbereich verwendet, damit der Slider bedienbar bleibt.
    """
    lows: list[int] = []
    highs: list[int] = []
    for entity_id in entity_ids:
        if (state := hass.states.get(entity_id)) is None:
            continue
        if ColorMode.COLOR_TEMP not in (state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) or []):
            continue
        low = state.attributes.get(ATTR_MIN_COLOR_TEMP_KELVIN)
        high = state.attributes.get(ATTR_MAX_COLOR_TEMP_KELVIN)
        if low is None or high is None:
            continue
        lows.append(int(low))
        highs.append(int(high))

    if not lows:
        return MIN_COLOR_TEMP_KELVIN, MAX_COLOR_TEMP_KELVIN
    if max(lows) <= min(highs):
        return max(lows), min(highs)
    return min(lows), max(highs)


def clamp(value: int, value_range: tuple[int, int]) -> int:
    """Wert auf einen Bereich begrenzen."""
    low, high = value_range
    return max(low, min(high, value))
