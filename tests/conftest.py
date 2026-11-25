"""Gemeinsame Fixtures und Helfer für die Tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.light_wrapper.const import (
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_GLOBAL,
    GLOBAL_UNIQUE_ID,
)
from custom_components.light_wrapper.light import LightWrapperLight

WRAPPER_ID = "light.wohnzimmer"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Custom Integrations in allen Tests laden dürfen."""
    return


def set_member(
    hass: HomeAssistant,
    entity_id: str,
    state: str = "off",
    *,
    modes: tuple[str, ...] = ("color_temp",),
    color_mode: str | None = None,
    brightness: int | None = None,
    kelvin: int | None = None,
    min_kelvin: int = 2200,
    max_kelvin: int = 6500,
    features: int = 0,
    **extra: Any,
) -> None:
    """Zustand eines (simulierten) physischen Lichts setzen."""
    attrs: dict[str, Any] = {"supported_color_modes": list(modes), "supported_features": features}
    if "color_temp" in modes:
        attrs["min_color_temp_kelvin"] = min_kelvin
        attrs["max_color_temp_kelvin"] = max_kelvin
    if state == "on":
        attrs["color_mode"] = color_mode or modes[0]
        if brightness is not None:
            attrs["brightness"] = brightness
        if kelvin is not None:
            attrs["color_temp_kelvin"] = kelvin
    attrs.update(extra)
    hass.states.async_set(entity_id, state, attrs)


async def setup_wrapper(
    hass: HomeAssistant, entities: list[str], **defaults: float | bool
) -> MockConfigEntry:
    """Einen Wrapper 'Wohnzimmer' anlegen und laden."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Wohnzimmer",
        data={},
        options={CONF_ENTITIES: entities, **defaults},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def setup_global(hass: HomeAssistant, **options: float) -> MockConfigEntry:
    """Den Eintrag „Globale Einstellungen“ anlegen und laden."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Globale Einstellungen",
        unique_id=GLOBAL_UNIQUE_ID,
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_GLOBAL},
        options=options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def number_entity_id(hass: HomeAssistant, entry: MockConfigEntry, option_key: str) -> str | None:
    """Entity-ID einer Number-Entität über ihre unique_id finden."""
    return er.async_get(hass).async_get_entity_id(
        "number", DOMAIN, f"{entry.entry_id}_{option_key}"
    )


def switch_entity_id(hass: HomeAssistant, entry: MockConfigEntry, option_key: str) -> str | None:
    """Entity-ID einer Switch-Entität über ihre unique_id finden."""
    return er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_{option_key}"
    )


@pytest.fixture
def member_calls():
    """Service-Aufrufe an die Mitglieder abfangen statt sie auszuführen.

    Ergebnis: Mock, dessen Aufrufe (self, service, entity_ids, data) enthalten.
    """
    with patch.object(LightWrapperLight, "_async_call", autospec=True) as mock:
        yield mock


def calls_by_entity(mock) -> dict[str, tuple[str, dict[str, Any]]]:
    """Aufrufe pro Mitglied: {entity_id: (service, data)}."""
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    for call in mock.call_args_list:
        _self, service, entity_ids, data = call.args
        for entity_id in entity_ids:
            assert entity_id not in result, f"{entity_id} wurde mehrfach angesprochen"
            result[entity_id] = (service, dict(data))
    return result
