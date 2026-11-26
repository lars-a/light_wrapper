"""Tests for the area chosen when adding a light group."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_ENTITIES, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from custom_components.light_wrapper.const import CONF_AREA, DOMAIN, SUBENTRY_TYPE_GROUP

from .conftest import group_id, set_member, setup_groups

LIGHT = "light.decke"


async def _add_group(hass: HomeAssistant, entry, **extra):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_GROUP),
        context={"source": config_entries.SOURCE_USER},
    )
    assert CONF_AREA in {str(key) for key in result["data_schema"].schema}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Deckenlicht", CONF_ENTITIES: [LIGHT], **extra}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    return result


def _device(hass: HomeAssistant, entry):
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, group_id(entry))})


async def test_new_group_gets_area(hass: HomeAssistant) -> None:
    area = ar.async_get(hass).async_create("Küche")
    set_member(hass, LIGHT, "off", modes=("brightness",))
    entry = await setup_groups(hass)

    result = await _add_group(hass, entry, **{CONF_AREA: area.id})

    assert result["data"][CONF_AREA] == area.id
    assert _device(hass, entry).area_id == area.id
    # The entity ID is built with the area right away
    entity_id = er.async_get(hass).async_get_entity_id("light", DOMAIN, group_id(entry))
    assert entity_id == "light.kuche_deckenlicht"


async def test_new_group_without_area(hass: HomeAssistant) -> None:
    set_member(hass, LIGHT, "off", modes=("brightness",))
    entry = await setup_groups(hass)

    result = await _add_group(hass, entry)

    assert CONF_AREA not in result["data"]
    assert _device(hass, entry).area_id is None


async def test_area_changed_on_device_is_kept(hass: HomeAssistant) -> None:
    areas = ar.async_get(hass)
    kitchen = areas.async_create("Küche")
    hallway = areas.async_create("Flur")
    set_member(hass, LIGHT, "off", modes=("brightness",))
    entry = await setup_groups(hass)
    await _add_group(hass, entry, **{CONF_AREA: kitchen.id})

    device_registry = dr.async_get(hass)
    device_registry.async_update_device(_device(hass, entry).id, area_id=hallway.id)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert _device(hass, entry).area_id == hallway.id


async def test_reconfigure_has_no_area_field(hass: HomeAssistant) -> None:
    set_member(hass, LIGHT, "off", modes=("brightness",))
    entry = await setup_groups(hass)
    await _add_group(hass, entry)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_GROUP),
        context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": group_id(entry)},
    )
    assert CONF_AREA not in {str(key) for key in result["data_schema"].schema}
