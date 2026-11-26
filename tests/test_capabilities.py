"""Tests for lights that only report their capabilities while on."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.components.light import (
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    LightEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.light_wrapper.capabilities import STORAGE_KEY, STORAGE_VERSION
from custom_components.light_wrapper.const import (
    CONF_DEFAULT_COLOR_TEMP,
    CONF_DEFAULT_TRANSITION_ON,
)

from .conftest import WRAPPER_ID, calls_by_entity, set_member, setup_wrapper

LIGHT = "light.decke"
DEFAULTS = {CONF_DEFAULT_COLOR_TEMP: 2500, CONF_DEFAULT_TRANSITION_ON: 1.0}
TRANSITION = int(LightEntityFeature.TRANSITION)


def _off_without_capabilities(hass: HomeAssistant) -> None:
    """Off, reporting neither color modes, color temperature range nor features."""
    set_member(hass, LIGHT, "off", modes=())


async def _turn_on(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: WRAPPER_ID}, blocking=True
    )


async def test_off_member_uses_capabilities_seen_while_on(
    hass: HomeAssistant, member_calls
) -> None:
    set_member(hass, LIGHT, "on", min_kelvin=2700, max_kelvin=5000, features=TRANSITION)
    await setup_wrapper(hass, [LIGHT], **DEFAULTS)
    _off_without_capabilities(hass)
    await hass.async_block_till_done()

    state = hass.states.get(WRAPPER_ID)
    assert state.state == "off"
    assert "color_temp" in state.attributes[ATTR_SUPPORTED_COLOR_MODES]

    await _turn_on(hass)
    _service, data = calls_by_entity(member_calls)[LIGHT]
    # Clamped to the remembered range; transition from the remembered features
    assert data[ATTR_COLOR_TEMP_KELVIN] == 2700
    assert data[ATTR_TRANSITION] == 1.0


async def test_unknown_capabilities_are_not_guessed(hass: HomeAssistant, member_calls) -> None:
    _off_without_capabilities(hass)
    await setup_wrapper(hass, [LIGHT], **DEFAULTS)

    await _turn_on(hass)
    _service, data = calls_by_entity(member_calls)[LIGHT]
    assert ATTR_COLOR_TEMP_KELVIN not in data
    assert ATTR_TRANSITION not in data


async def test_capabilities_are_restored_after_restart(
    hass: HomeAssistant, hass_storage: dict[str, Any], member_calls
) -> None:
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {
            LIGHT: {
                ATTR_SUPPORTED_COLOR_MODES: ["color_temp"],
                "min_color_temp_kelvin": 2200,
                "max_color_temp_kelvin": 6500,
                "supported_features": TRANSITION,
            }
        },
    }
    _off_without_capabilities(hass)
    await setup_wrapper(hass, [LIGHT], **DEFAULTS)

    await _turn_on(hass)
    _service, data = calls_by_entity(member_calls)[LIGHT]
    assert data[ATTR_COLOR_TEMP_KELVIN] == 2500
    assert data[ATTR_TRANSITION] == 1.0


async def test_capabilities_are_stored(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    set_member(hass, LIGHT, "on", min_kelvin=2700, max_kelvin=5000)
    await setup_wrapper(hass, [LIGHT])

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    stored = hass_storage[STORAGE_KEY]["data"][LIGHT]
    assert stored[ATTR_SUPPORTED_COLOR_MODES] == ["color_temp"]
    assert stored["min_color_temp_kelvin"] == 2700
    assert stored["max_color_temp_kelvin"] == 5000


async def test_turning_on_without_capabilities_keeps_them(hass: HomeAssistant) -> None:
    """The first state after turning on often lacks the capabilities."""
    set_member(hass, LIGHT, "on", min_kelvin=2700, max_kelvin=5000)
    await setup_wrapper(hass, [LIGHT])
    _off_without_capabilities(hass)
    await hass.async_block_till_done()

    set_member(hass, LIGHT, "on", modes=())
    await hass.async_block_till_done()

    state = hass.states.get(WRAPPER_ID)
    assert state.state == "on"
    assert "color_temp" in state.attributes[ATTR_SUPPORTED_COLOR_MODES]
    assert state.attributes["min_color_temp_kelvin"] == 2700
    assert state.attributes["max_color_temp_kelvin"] == 5000


async def test_lights_outside_groups_are_forgotten(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {
            LIGHT: {ATTR_SUPPORTED_COLOR_MODES: ["color_temp"]},
            "light.old": {ATTR_SUPPORTED_COLOR_MODES: ["color_temp"]},
        },
    }
    _off_without_capabilities(hass)
    await setup_wrapper(hass, [LIGHT])

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()

    assert set(hass_storage[STORAGE_KEY]["data"]) == {LIGHT}
