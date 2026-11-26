"""Tests for the "hide members" group setting."""

from __future__ import annotations

from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.light_wrapper.const import CONF_HIDE_MEMBERS

from .conftest import group_id, set_member, setup_integration, setup_wrapper

CT_LIGHT = "light.decke"
DIM_LIGHT = "light.stehlampe"


def _register(hass: HomeAssistant, entity_id: str) -> None:
    """Create a registry entry for a (simulated) member light."""
    object_id = entity_id.split(".", 1)[1]
    er.async_get(hass).async_get_or_create(
        "light", "test", object_id, suggested_object_id=object_id
    )
    set_member(hass, entity_id, "off")


def _hidden_by(hass: HomeAssistant, entity_id: str) -> er.RegistryEntryHider | None:
    return er.async_get(hass).async_get(entity_id).hidden_by


async def test_members_hidden_and_shown_again(hass: HomeAssistant) -> None:
    _register(hass, CT_LIGHT)
    _register(hass, DIM_LIGHT)
    entry = await setup_wrapper(hass, [CT_LIGHT, DIM_LIGHT], **{CONF_HIDE_MEMBERS: True})
    assert _hidden_by(hass, CT_LIGHT) is er.RegistryEntryHider.INTEGRATION
    assert _hidden_by(hass, DIM_LIGHT) is er.RegistryEntryHider.INTEGRATION

    # Removing a light from the group shows it again
    subentry = entry.subentries[group_id(entry)]
    hass.config_entries.async_update_subentry(
        entry, subentry, data={**subentry.data, CONF_ENTITIES: [CT_LIGHT]}
    )
    await hass.async_block_till_done()
    assert _hidden_by(hass, CT_LIGHT) is er.RegistryEntryHider.INTEGRATION
    assert _hidden_by(hass, DIM_LIGHT) is None

    # Turning the setting off shows the rest again, without a reload
    runtime_before = entry.runtime_data
    subentry = entry.subentries[group_id(entry)]
    hass.config_entries.async_update_subentry(entry, subentry, data={CONF_ENTITIES: [CT_LIGHT]})
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime_before
    assert _hidden_by(hass, CT_LIGHT) is None


async def test_members_shown_again_when_group_removed(hass: HomeAssistant) -> None:
    _register(hass, CT_LIGHT)
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_HIDE_MEMBERS: True})
    assert _hidden_by(hass, CT_LIGHT) is er.RegistryEntryHider.INTEGRATION

    hass.config_entries.async_remove_subentry(entry, group_id(entry))
    await hass.async_block_till_done()
    assert _hidden_by(hass, CT_LIGHT) is None


async def test_members_shown_again_when_entry_removed(hass: HomeAssistant) -> None:
    _register(hass, CT_LIGHT)
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_HIDE_MEMBERS: True})
    assert _hidden_by(hass, CT_LIGHT) is er.RegistryEntryHider.INTEGRATION

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert _hidden_by(hass, CT_LIGHT) is None


async def test_user_hidden_member_stays_hidden(hass: HomeAssistant) -> None:
    _register(hass, CT_LIGHT)
    er.async_get(hass).async_update_entity(CT_LIGHT, hidden_by=er.RegistryEntryHider.USER)
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_HIDE_MEMBERS: True})
    assert _hidden_by(hass, CT_LIGHT) is er.RegistryEntryHider.USER

    hass.config_entries.async_remove_subentry(entry, group_id(entry))
    await hass.async_block_till_done()
    assert _hidden_by(hass, CT_LIGHT) is er.RegistryEntryHider.USER


async def test_member_of_two_groups_stays_hidden(hass: HomeAssistant) -> None:
    _register(hass, CT_LIGHT)
    _global, entry = await setup_integration(
        hass,
        groups={
            "Wohnzimmer": {CONF_ENTITIES: [CT_LIGHT], CONF_HIDE_MEMBERS: True},
            "Alle": {CONF_ENTITIES: [CT_LIGHT]},
        },
    )
    assert _hidden_by(hass, CT_LIGHT) is er.RegistryEntryHider.INTEGRATION

    # The other group does not hide it, so removing that one changes nothing
    other = next(s for s in entry.subentries.values() if s.title == "Alle")
    hass.config_entries.async_remove_subentry(entry, other.subentry_id)
    await hass.async_block_till_done()
    assert _hidden_by(hass, CT_LIGHT) is er.RegistryEntryHider.INTEGRATION


async def test_members_not_hidden_by_default(hass: HomeAssistant) -> None:
    _register(hass, CT_LIGHT)
    await setup_wrapper(hass, [CT_LIGHT])
    assert _hidden_by(hass, CT_LIGHT) is None
