"""Tests for the light_wrapper.set_defaults action."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_ENTITIES
from homeassistant.core import HomeAssistant

from custom_components.light_wrapper.const import (
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    CONF_DEFAULT_TRANSITION_OFF,
    CONF_DEFAULT_TRANSITION_ON,
    DOMAIN,
    SERVICE_SET_DEFAULTS,
)

from .conftest import WRAPPER_ID, group_data, number_entity_id, set_member, setup_integration, setup_wrapper

CT_LIGHT = "light.decke"


async def _set_defaults(hass: HomeAssistant, entity_id: str | list[str], **data) -> None:
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DEFAULTS,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_set_existing_defaults_without_reload(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )
    runtime_before = entry.runtime_data

    await _set_defaults(
        hass, WRAPPER_ID, **{CONF_DEFAULT_BRIGHTNESS: 35, CONF_DEFAULT_COLOR_TEMP: 4000}
    )

    assert group_data(entry)[CONF_DEFAULT_BRIGHTNESS] == 35
    assert group_data(entry)[CONF_DEFAULT_COLOR_TEMP] == 4000
    assert entry.runtime_data is runtime_before  # no reload
    attrs = hass.states.get(WRAPPER_ID).attributes
    assert attrs[CONF_DEFAULT_BRIGHTNESS] == 35
    assert attrs[CONF_DEFAULT_COLOR_TEMP] == 4000
    brightness_id = number_entity_id(hass, entry, CONF_DEFAULT_BRIGHTNESS)
    assert float(hass.states.get(brightness_id).state) == 35


async def test_set_new_defaults_enables_them(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT])

    await _set_defaults(
        hass,
        WRAPPER_ID,
        **{CONF_DEFAULT_TRANSITION_ON: 1.25, CONF_DEFAULT_TRANSITION_OFF: 3},
    )

    assert group_data(entry) == {
        CONF_ENTITIES: [CT_LIGHT],
        CONF_DEFAULT_TRANSITION_ON: 1.2,  # rounded to 0.1 s
        CONF_DEFAULT_TRANSITION_OFF: 3.0,
    }
    # Enabling a default reloads the group and creates its number entity
    assert number_entity_id(hass, entry, CONF_DEFAULT_TRANSITION_ON) is not None
    assert hass.states.get(WRAPPER_ID).attributes[CONF_DEFAULT_TRANSITION_OFF] == 3.0


async def test_null_disables_default(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )

    await _set_defaults(hass, WRAPPER_ID, **{CONF_DEFAULT_BRIGHTNESS: None})

    assert group_data(entry) == {CONF_ENTITIES: [CT_LIGHT], CONF_DEFAULT_COLOR_TEMP: 2700}
    assert CONF_DEFAULT_BRIGHTNESS not in hass.states.get(WRAPPER_ID).attributes


async def test_color_temp_limited_to_group_range(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2700, max_kelvin=5000)
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_COLOR_TEMP: 3000})

    await _set_defaults(hass, WRAPPER_ID, **{CONF_DEFAULT_COLOR_TEMP: 6500})

    assert group_data(entry)[CONF_DEFAULT_COLOR_TEMP] == 5000


async def test_several_groups_at_once(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, "light.flurlampe", "off")
    _global, entry = await setup_integration(
        hass,
        groups={
            "Wohnzimmer": {CONF_ENTITIES: [CT_LIGHT], CONF_DEFAULT_BRIGHTNESS: 60},
            "Flur": {CONF_ENTITIES: ["light.flurlampe"], CONF_DEFAULT_BRIGHTNESS: 20},
        },
    )

    await _set_defaults(hass, ["light.wohnzimmer", "light.flur"], **{CONF_DEFAULT_BRIGHTNESS: 50})

    assert all(s.data[CONF_DEFAULT_BRIGHTNESS] == 50 for s in entry.subentries.values())


async def test_requires_a_value_and_valid_ranges(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    await setup_wrapper(hass, [CT_LIGHT])

    with pytest.raises(vol.Invalid):
        await _set_defaults(hass, WRAPPER_ID)
    with pytest.raises(vol.Invalid):
        await _set_defaults(hass, WRAPPER_ID, **{CONF_DEFAULT_BRIGHTNESS: 0})
    with pytest.raises(vol.Invalid):
        await _set_defaults(hass, WRAPPER_ID, **{CONF_DEFAULT_TRANSITION_ON: 11})
