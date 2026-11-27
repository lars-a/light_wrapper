"""Tests for the optional icons of the group light."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import ATTR_ICON, CONF_ENTITIES
from homeassistant.core import HomeAssistant

from custom_components.light_wrapper.const import (
    CONF_ICON_OFF,
    CONF_ICON_ON,
    SUBENTRY_TYPE_GROUP,
)

from .conftest import WRAPPER_ID, group_data, group_id, set_member, setup_wrapper

LIGHT = "light.decke"


def _icon(hass: HomeAssistant) -> str:
    return hass.states.get(WRAPPER_ID).attributes[ATTR_ICON]


async def test_default_icon(hass: HomeAssistant) -> None:
    set_member(hass, LIGHT, "off")
    await setup_wrapper(hass, [LIGHT])
    assert _icon(hass) == "mdi:lightbulb-group"

    set_member(hass, LIGHT, "on")
    await hass.async_block_till_done()
    assert _icon(hass) == "mdi:lightbulb-group"


async def test_icons_for_on_and_off(hass: HomeAssistant) -> None:
    set_member(hass, LIGHT, "off")
    await setup_wrapper(
        hass, [LIGHT], **{CONF_ICON_ON: "mdi:ceiling-light", CONF_ICON_OFF: "mdi:ceiling-light-outline"}
    )
    assert _icon(hass) == "mdi:ceiling-light-outline"

    set_member(hass, LIGHT, "on")
    await hass.async_block_till_done()
    assert _icon(hass) == "mdi:ceiling-light"


async def test_only_one_icon_set(hass: HomeAssistant) -> None:
    set_member(hass, LIGHT, "on")
    await setup_wrapper(hass, [LIGHT], **{CONF_ICON_OFF: "mdi:lightbulb-off"})
    assert _icon(hass) == "mdi:lightbulb-group"

    set_member(hass, LIGHT, "off")
    await hass.async_block_till_done()
    assert _icon(hass) == "mdi:lightbulb-off"


async def test_icons_in_edit_dialog(hass: HomeAssistant) -> None:
    set_member(hass, LIGHT, "off")
    entry = await setup_wrapper(hass, [LIGHT])

    async def _reconfigure(user_input: dict[str, Any]) -> dict[str, Any]:
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

    suggested = await _reconfigure(
        {CONF_ENTITIES: [LIGHT], CONF_ICON_ON: "mdi:lamp", CONF_ICON_OFF: " "}
    )
    assert CONF_ICON_ON not in suggested
    # Blank values are not stored; the change applies without a reload
    assert group_data(entry) == {CONF_ENTITIES: [LIGHT], CONF_ICON_ON: "mdi:lamp"}
    set_member(hass, LIGHT, "on")
    await hass.async_block_till_done()
    assert _icon(hass) == "mdi:lamp"

    # Prefilled when editing again; clearing it brings back the default icon
    suggested = await _reconfigure({CONF_ENTITIES: [LIGHT]})
    assert suggested[CONF_ICON_ON] == "mdi:lamp"
    assert group_data(entry) == {CONF_ENTITIES: [LIGHT]}
    assert _icon(hass) == "mdi:lightbulb-group"


async def test_icon_fields_follow_the_lights(hass: HomeAssistant) -> None:
    set_member(hass, LIGHT, "off")
    entry = await setup_wrapper(hass, [LIGHT])

    for context in (
        {"source": config_entries.SOURCE_USER},
        {"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": group_id(entry)},
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_GROUP), context=context
        )
        keys = [str(key) for key in result["data_schema"].schema]
        position = keys.index(CONF_ENTITIES)
        assert keys[position + 1 : position + 3] == [CONF_ICON_ON, CONF_ICON_OFF]
