"""Tests für die Number-Entitäten (Standardwerte)."""

from __future__ import annotations

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.light_wrapper.const import (
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
)

from .conftest import WRAPPER_ID, number_entity_id, set_member, setup_wrapper

CT_LIGHT = "light.decke"
DIM_LIGHT = "light.stehlampe"


async def test_numbers_only_for_enabled_defaults(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60})

    brightness_id = number_entity_id(hass, entry, CONF_DEFAULT_BRIGHTNESS)
    assert brightness_id is not None
    assert float(hass.states.get(brightness_id).state) == 60
    assert number_entity_id(hass, entry, CONF_DEFAULT_COLOR_TEMP) is None


async def test_set_value_updates_options_without_reload(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )
    runtime_before = entry.runtime_data
    brightness_id = number_entity_id(hass, entry, CONF_DEFAULT_BRIGHTNESS)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: brightness_id, ATTR_VALUE: 35},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_DEFAULT_BRIGHTNESS] == 35
    assert entry.options[CONF_DEFAULT_COLOR_TEMP] == 2700
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is runtime_before  # kein Reload
    assert float(hass.states.get(brightness_id).state) == 35
    assert hass.states.get(WRAPPER_ID).attributes[CONF_DEFAULT_BRIGHTNESS] == 35


async def test_color_temp_number_unavailable_without_capable_member(hass: HomeAssistant) -> None:
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    entry = await setup_wrapper(hass, [DIM_LIGHT], **{CONF_DEFAULT_COLOR_TEMP: 2700})
    ct_id = number_entity_id(hass, entry, CONF_DEFAULT_COLOR_TEMP)
    assert hass.states.get(ct_id).state == STATE_UNAVAILABLE


async def test_color_temp_number_becomes_available(hass: HomeAssistant) -> None:
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_COLOR_TEMP: 2700})
    ct_id = number_entity_id(hass, entry, CONF_DEFAULT_COLOR_TEMP)
    assert hass.states.get(ct_id).state == STATE_UNAVAILABLE  # Mitglied noch nicht da

    set_member(hass, CT_LIGHT, "off")
    await hass.async_block_till_done()
    assert float(hass.states.get(ct_id).state) == 2700


async def test_color_temp_number_range_is_intersection(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2200, max_kelvin=6500)
    set_member(hass, "light.spot", "off", min_kelvin=2700, max_kelvin=5000)
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))  # zählt nicht mit
    entry = await setup_wrapper(
        hass, [CT_LIGHT, "light.spot", DIM_LIGHT], **{CONF_DEFAULT_COLOR_TEMP: 3000}
    )
    attrs = hass.states.get(number_entity_id(hass, entry, CONF_DEFAULT_COLOR_TEMP)).attributes
    assert attrs["min"] == 2700
    assert attrs["max"] == 5000


async def test_color_temp_number_range_follows_members(hass: HomeAssistant) -> None:
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_COLOR_TEMP: 3000})
    ct_id = number_entity_id(hass, entry, CONF_DEFAULT_COLOR_TEMP)
    # Mitglied noch nicht geladen: fester Bereich
    assert hass.states.get(ct_id).attributes["min"] == 2000
    assert hass.states.get(ct_id).attributes["max"] == 6500

    set_member(hass, CT_LIGHT, "off", min_kelvin=2500, max_kelvin=6000)
    await hass.async_block_till_done()
    assert hass.states.get(ct_id).attributes["min"] == 2500
    assert hass.states.get(ct_id).attributes["max"] == 6000


async def test_color_temp_number_range_without_overlap_uses_union(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2000, max_kelvin=3000)
    set_member(hass, "light.spot", "off", min_kelvin=4000, max_kelvin=6500)
    entry = await setup_wrapper(hass, [CT_LIGHT, "light.spot"], **{CONF_DEFAULT_COLOR_TEMP: 3000})
    attrs = hass.states.get(number_entity_id(hass, entry, CONF_DEFAULT_COLOR_TEMP)).attributes
    assert (attrs["min"], attrs["max"]) == (2000, 6500)
