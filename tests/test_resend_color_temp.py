"""Tests for the second color temperature command for lights that hide it while off."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.components.light import (
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.light_wrapper.const import CONF_DEFAULT_COLOR_TEMP

from .conftest import WRAPPER_ID, set_member, setup_wrapper

LIGHT = "light.decke"
DEFAULTS = {CONF_DEFAULT_COLOR_TEMP: 2700}
SECOND = (SERVICE_TURN_ON, [LIGHT], {ATTR_COLOR_TEMP_KELVIN: 2700})


def _calls(mock) -> list[tuple[str, list[str], dict[str, Any]]]:
    """All member calls in order: (service, entity_ids, data)."""
    return [
        (call.args[1], sorted(call.args[2]), dict(call.args[3])) for call in mock.call_args_list
    ]


async def _call(hass: HomeAssistant, service: str, **data) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN, service, {ATTR_ENTITY_ID: WRAPPER_ID, **data}, blocking=True
    )


async def _setup_hiding_light(hass: HomeAssistant) -> None:
    """A light that was seen on with color temperature and now hides it while off."""
    set_member(hass, LIGHT, "on", kelvin=4000)
    await setup_wrapper(hass, [LIGHT], **DEFAULTS)
    set_member(hass, LIGHT, "off", modes=())
    await hass.async_block_till_done()


async def _reports_again(hass: HomeAssistant, kelvin: int = 4000) -> None:
    set_member(hass, LIGHT, "on", kelvin=kelvin)
    await hass.async_block_till_done()


async def test_sends_color_temp_once_the_light_reports_it(
    hass: HomeAssistant, member_calls
) -> None:
    await _setup_hiding_light(hass)

    await _call(hass, SERVICE_TURN_ON)
    assert len(member_calls.call_args_list) == 1

    # On, but still without capabilities: keep waiting
    set_member(hass, LIGHT, "on", modes=(), color_mode="unknown")
    await hass.async_block_till_done()
    assert len(member_calls.call_args_list) == 1

    # Reports color temperature again, but ignored the requested one
    await _reports_again(hass)
    assert _calls(member_calls)[1:] == [SECOND]

    # Only once
    await _reports_again(hass, kelvin=3500)
    assert len(member_calls.call_args_list) == 2


async def test_nothing_sent_if_the_color_temp_was_applied(
    hass: HomeAssistant, member_calls
) -> None:
    await _setup_hiding_light(hass)

    await _call(hass, SERVICE_TURN_ON)
    await _reports_again(hass, kelvin=2710)

    assert len(member_calls.call_args_list) == 1


async def test_lights_reporting_while_off_are_not_affected(
    hass: HomeAssistant, member_calls
) -> None:
    set_member(hass, LIGHT, "off")
    await setup_wrapper(hass, [LIGHT], **DEFAULTS)

    await _call(hass, SERVICE_TURN_ON)
    await _reports_again(hass)

    assert len(member_calls.call_args_list) == 1


async def test_gives_up_after_timeout(hass: HomeAssistant, member_calls) -> None:
    await _setup_hiding_light(hass)

    await _call(hass, SERVICE_TURN_ON)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()
    await _reports_again(hass)

    assert len(member_calls.call_args_list) == 1


async def test_turning_off_cancels(hass: HomeAssistant, member_calls) -> None:
    await _setup_hiding_light(hass)

    await _call(hass, SERVICE_TURN_ON)
    await _call(hass, SERVICE_TURN_OFF)
    await _reports_again(hass)

    assert [service for service, _ids, _data in _calls(member_calls)] == [
        SERVICE_TURN_ON,
        SERVICE_TURN_OFF,
    ]


async def test_latest_color_temp_is_sent(hass: HomeAssistant, member_calls) -> None:
    await _setup_hiding_light(hass)

    await _call(hass, SERVICE_TURN_ON)
    await _call(hass, SERVICE_TURN_ON, color_temp_kelvin=3300)
    await _reports_again(hass)

    assert _calls(member_calls)[2:] == [
        (SERVICE_TURN_ON, [LIGHT], {ATTR_COLOR_TEMP_KELVIN: 3300})
    ]
