"""Tests for the workaround that sends the color temperature again after turning on."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_ENTITIES, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from custom_components.light_wrapper.const import (
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    CONF_RESEND_COLOR_TEMP,
    SUBENTRY_TYPE_GROUP,
)

from .conftest import WRAPPER_ID, group_data, group_id, set_member, setup_wrapper

CT_LIGHT = "light.decke"
CT_LIGHT_2 = "light.spot"
DIM_LIGHT = "light.stehlampe"
ON = {CONF_RESEND_COLOR_TEMP: True}


@pytest.fixture(autouse=True)
def no_delay():
    with patch("custom_components.light_wrapper.light.RESEND_COLOR_TEMP_DELAY", 0):
        yield


def _calls(mock) -> list[tuple[list[str], dict[str, Any]]]:
    """All member calls in order: (entity_ids, data)."""
    result = []
    for call in mock.call_args_list:
        _self, service, entity_ids, data = call.args
        assert service == SERVICE_TURN_ON
        result.append((sorted(entity_ids), dict(data)))
    return result


async def _turn_on(hass: HomeAssistant, **data) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: WRAPPER_ID, **data}, blocking=True
    )


async def test_resends_color_temp_to_lights_switched_on(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, CT_LIGHT_2, "off")
    await setup_wrapper(
        hass,
        [CT_LIGHT, CT_LIGHT_2],
        **{CONF_DEFAULT_COLOR_TEMP: 2700, CONF_DEFAULT_BRIGHTNESS: 40, **ON},
    )

    await _turn_on(hass)

    assert _calls(member_calls) == [
        ([CT_LIGHT, CT_LIGHT_2], {ATTR_BRIGHTNESS_PCT: 40, ATTR_COLOR_TEMP_KELVIN: 2700}),
        ([CT_LIGHT, CT_LIGHT_2], {ATTR_COLOR_TEMP_KELVIN: 2700}),
    ]


async def test_resends_given_color_temp(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off")
    await setup_wrapper(hass, [CT_LIGHT], **ON)

    await _turn_on(hass, color_temp_kelvin=4000)

    assert _calls(member_calls) == [
        ([CT_LIGHT], {ATTR_COLOR_TEMP_KELVIN: 4000}),
        ([CT_LIGHT], {ATTR_COLOR_TEMP_KELVIN: 4000}),
    ]


async def test_no_resend_when_disabled(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off")
    await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_COLOR_TEMP: 2700})

    await _turn_on(hass)

    assert len(member_calls.call_args_list) == 1


async def test_no_resend_to_lights_already_on(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "on", kelvin=3000)
    set_member(hass, CT_LIGHT_2, "off")
    await setup_wrapper(hass, [CT_LIGHT, CT_LIGHT_2], **{CONF_DEFAULT_COLOR_TEMP: 2700, **ON})

    await _turn_on(hass)

    assert _calls(member_calls) == [
        ([CT_LIGHT, CT_LIGHT_2], {ATTR_COLOR_TEMP_KELVIN: 2700}),
        ([CT_LIGHT_2], {ATTR_COLOR_TEMP_KELVIN: 2700}),
    ]


async def test_no_resend_without_color_temp(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    await setup_wrapper(hass, [CT_LIGHT, DIM_LIGHT], **{CONF_DEFAULT_COLOR_TEMP: 2700, **ON})

    await _turn_on(hass)
    calls = _calls(member_calls)
    # Only the light with color temperature gets the second command
    assert calls[-1] == ([CT_LIGHT], {ATTR_COLOR_TEMP_KELVIN: 2700})
    assert len(calls) == 3


async def test_setting_in_edit_dialog(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT])

    async def _reconfigure(user_input: dict[str, Any]):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_GROUP),
            context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": group_id(entry)},
        )
        suggested = {
            str(key): key.description["suggested_value"]
            for key in result["data_schema"].schema
            if key.description and "suggested_value" in key.description
        }
        await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)
        await hass.async_block_till_done()
        return suggested

    suggested = await _reconfigure({CONF_ENTITIES: [CT_LIGHT], CONF_RESEND_COLOR_TEMP: True})
    assert suggested[CONF_RESEND_COLOR_TEMP] is False
    assert group_data(entry) == {CONF_ENTITIES: [CT_LIGHT], CONF_RESEND_COLOR_TEMP: True}

    suggested = await _reconfigure({CONF_ENTITIES: [CT_LIGHT], CONF_RESEND_COLOR_TEMP: False})
    assert suggested[CONF_RESEND_COLOR_TEMP] is True
    assert group_data(entry) == {CONF_ENTITIES: [CT_LIGHT]}
