"""Tests für den Schalter „Standardwerte auch wenn an“."""

from __future__ import annotations

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from custom_components.light_wrapper.const import CONF_APPLY_WHEN_ON, CONF_DEFAULT_BRIGHTNESS

from .conftest import set_member, setup_wrapper, switch_entity_id

CT_LIGHT = "light.decke"


async def _switch(hass: HomeAssistant, service: str, entity_id: str) -> None:
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def test_switch_defaults_to_off(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60})
    switch_id = switch_entity_id(hass, entry, CONF_APPLY_WHEN_ON)
    assert switch_id is not None
    assert hass.states.get(switch_id).state == STATE_OFF


async def test_switch_updates_options_without_reload(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60})
    runtime_before = entry.runtime_data
    switch_id = switch_entity_id(hass, entry, CONF_APPLY_WHEN_ON)

    await _switch(hass, SERVICE_TURN_ON, switch_id)

    assert entry.options[CONF_APPLY_WHEN_ON] is True
    assert entry.options[CONF_DEFAULT_BRIGHTNESS] == 60
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is runtime_before  # kein Reload
    assert entry.runtime_data.apply_when_on is True
    assert hass.states.get(switch_id).state == STATE_ON

    await _switch(hass, SERVICE_TURN_OFF, switch_id)

    assert CONF_APPLY_WHEN_ON not in entry.options  # nur gespeichert, wenn aktiv
    assert entry.runtime_data is runtime_before
    assert entry.runtime_data.apply_when_on is False
    assert hass.states.get(switch_id).state == STATE_OFF
