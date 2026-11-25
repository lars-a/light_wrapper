"""Gemeinsame Helfer für Entitäten."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from homeassistant.components.light import (
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import LightWrapperConfigEntry, LightWrapperData
from .const import DOMAIN, MAX_COLOR_TEMP_KELVIN, MIN_COLOR_TEMP_KELVIN


def device_info(entry: ConfigEntry, subentry: ConfigSubentry | None) -> DeviceInfo:
    """Virtuelles Gerät: eines pro Lichtgruppe und eines für die globalen Einstellungen."""
    if subentry is None:
        return DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            translation_key="global",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Light Wrapper",
            model="Globale Einstellungen",
        )
    return DeviceInfo(
        identifiers={(DOMAIN, subentry.subentry_id)},
        name=subentry.title,
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Light Wrapper",
        model="Lichtgruppe",
    )


class LightWrapperSettingEntity(Entity):
    """Basis für Einstellungs-Entitäten (Number, Switch) einer Gruppe oder der globalen Einstellungen.

    Gespeichert wird bei Gruppen in subentry.data, global in entry.options.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _option_key: str

    def __init__(self, entry: LightWrapperConfigEntry, subentry_id: str | None) -> None:
        runtime = entry.runtime_data
        self._entry = entry
        self._subentry_id = subentry_id
        self._data: LightWrapperData = (
            runtime.groups[subentry_id] if subentry_id else runtime.global_settings
        )
        self._attr_unique_id = f"{subentry_id or entry.entry_id}_{self._option_key}"
        self._attr_device_info = device_info(
            entry, entry.subentries[subentry_id] if subentry_id else None
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._data.async_add_listener(self.async_write_ha_state))

    def _store(self, value: Any) -> None:
        """Einstellung speichern; None entfernt den Schlüssel."""
        config_entries = self.hass.config_entries
        if self._subentry_id is None:
            config_entries.async_update_entry(
                self._entry, options=_with_value(self._entry.options, self._option_key, value)
            )
            return
        subentry = self._entry.subentries[self._subentry_id]
        config_entries.async_update_subentry(
            self._entry, subentry, data=_with_value(subentry.data, self._option_key, value)
        )


def _with_value(mapping: Mapping[str, Any], key: str, value: Any) -> dict[str, Any]:
    result = {k: v for k, v in mapping.items() if k != key}
    if value is not None:
        result[key] = value
    return result


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
