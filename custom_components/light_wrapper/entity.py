"""Gemeinsame Helfer für Entitäten."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """Ein virtuelles Gerät pro Wrapper, damit Licht und Einstellungen zusammen erscheinen."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Light Wrapper",
        model="Lichtgruppe",
    )
