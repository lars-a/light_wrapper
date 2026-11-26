"""Tests for the config flow, options flow (global) and subentry flow (light groups)."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_ENTITIES, CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.light_wrapper.config_flow import (
    CONF_USE_DEFAULT_BRIGHTNESS,
    CONF_USE_DEFAULT_COLOR_TEMP,
    CONF_USE_DEFAULT_TRANSITION_OFF,
    CONF_USE_DEFAULT_TRANSITION_ON,
)
from custom_components.light_wrapper.const import (
    CONF_APPLY_WHEN_ON,
    CONF_HIDE_MEMBERS,
    CONF_ON_WHEN_ALL_ON,
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    CONF_DEFAULT_TRANSITION_OFF,
    CONF_DEFAULT_TRANSITION_ON,
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_GLOBAL,
    ENTRY_TYPE_GROUPS,
    SUBENTRY_TYPE_GROUP,
)

from .conftest import (
    global_number_entity_id,
    group_data,
    group_id,
    number_entity_id,
    set_member,
    setup_global,
    setup_groups,
    setup_wrapper,
)

CT_LIGHT = "light.decke"
DIM_LIGHT = "light.stehlampe"


def _suggested(result) -> dict:
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


def _color_temp_selector_config(result) -> dict:
    for key, value in result["data_schema"].schema.items():
        if str(key) == CONF_DEFAULT_COLOR_TEMP:
            return value.config
    raise AssertionError("No color temperature slider in the form")


async def _add_group_flow(hass: HomeAssistant, entry):
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_GROUP),
        context={"source": config_entries.SOURCE_USER},
    )


async def _reconfigure_flow(hass: HomeAssistant, entry):
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_GROUP),
        context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": group_id(entry)},
    )


# --------------------------------------------------------------------------- Setup


async def test_setup_creates_both_entries_without_questions(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Light groups"
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_GROUPS}

    entries = {
        entry.data[CONF_ENTRY_TYPE]: entry for entry in hass.config_entries.async_entries(DOMAIN)
    }
    assert set(entries) == {ENTRY_TYPE_GLOBAL, ENTRY_TYPE_GROUPS}
    global_settings = entries[ENTRY_TYPE_GLOBAL]
    groups = entries[ENTRY_TYPE_GROUPS]
    assert global_settings.title == "Global settings"
    assert global_settings.unique_id == ENTRY_TYPE_GLOBAL
    assert groups.unique_id == ENTRY_TYPE_GROUPS
    # Not created as a system entry, otherwise the UI offers no "Delete"
    assert global_settings.source == config_entries.SOURCE_IMPORT

    # "Configure" only on the global entry, "Add light group" only on the groups entry
    assert global_settings.supports_options is True
    assert groups.supports_options is False
    assert global_settings.supported_subentry_types == {}
    assert set(groups.supported_subentry_types) == {SUBENTRY_TYPE_GROUP}

    # Global number entities only exist once one is enabled
    assert global_number_entity_id(hass, global_settings, CONF_DEFAULT_TRANSITION_ON) is None

    # Both entries exist only once
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_setup_recreates_missing_entry(hass: HomeAssistant) -> None:
    groups = await setup_groups(hass)
    global_id = next(
        entry.entry_id
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != groups.entry_id
    )
    await hass.config_entries.async_remove(global_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_GLOBAL}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert len(groups.subentries) == 0  # groups entry untouched


async def test_old_system_global_entry_is_replaced(hass: HomeAssistant) -> None:
    """A global entry created with SOURCE_SYSTEM (up to 0.7.1) is replaced once."""
    old = MockConfigEntry(
        domain=DOMAIN,
        title="Meine Einstellungen",
        unique_id=ENTRY_TYPE_GLOBAL,
        source=config_entries.SOURCE_SYSTEM,
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_GLOBAL},
        options={CONF_DEFAULT_TRANSITION_ON: 1.5},
    )
    old.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    new = entries[0]
    assert new.entry_id != old.entry_id
    assert new.source == config_entries.SOURCE_IMPORT
    assert new.title == "Meine Einstellungen"
    assert new.data == {CONF_ENTRY_TYPE: ENTRY_TYPE_GLOBAL}
    assert dict(new.options) == {CONF_DEFAULT_TRANSITION_ON: 1.5}
    assert new.state is config_entries.ConfigEntryState.LOADED
    assert global_number_entity_id(hass, new, CONF_DEFAULT_TRANSITION_ON) is not None


# --------------------------------------------------------------------------- Add group


async def test_add_group(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    entry = await setup_groups(hass)

    result = await _add_group_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    suggested = _suggested(result)
    assert suggested[CONF_USE_DEFAULT_BRIGHTNESS] is False
    assert suggested[CONF_DEFAULT_TRANSITION_ON] == 0.5
    assert suggested[CONF_APPLY_WHEN_ON] is True

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Wohnzimmer",
            CONF_ENTITIES: [CT_LIGHT, DIM_LIGHT],
            CONF_USE_DEFAULT_BRIGHTNESS: True,
            CONF_DEFAULT_BRIGHTNESS: 60,
            CONF_USE_DEFAULT_COLOR_TEMP: True,
            CONF_DEFAULT_COLOR_TEMP: 2700,
            CONF_USE_DEFAULT_TRANSITION_ON: True,
            CONF_DEFAULT_TRANSITION_ON: 1.5,
            CONF_USE_DEFAULT_TRANSITION_OFF: False,
            CONF_DEFAULT_TRANSITION_OFF: 3,
            CONF_APPLY_WHEN_ON: True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Wohnzimmer"
    assert group_data(entry) == {
        CONF_ENTITIES: [CT_LIGHT, DIM_LIGHT],
        CONF_DEFAULT_BRIGHTNESS: 60,
        CONF_DEFAULT_COLOR_TEMP: 2700,
        CONF_DEFAULT_TRANSITION_ON: 1.5,
    }  # "apply when on" switch = default, not stored

    state = hass.states.get("light.wohnzimmer")
    assert state is not None
    assert state.attributes["entity_id"] == [CT_LIGHT, DIM_LIGHT]
    assert number_entity_id(hass, entry, CONF_DEFAULT_BRIGHTNESS) is not None

    # The group has its own device that belongs to the subentry
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, group_id(entry))})
    assert device is not None
    assert device.name == "Wohnzimmer"
    assert group_id(entry) in device.config_entries_subentries[entry.entry_id]


async def test_add_group_without_defaults(hass: HomeAssistant) -> None:
    entry = await setup_groups(hass)
    result = await _add_group_flow(hass, entry)
    # Sliders always have a value; the toggles decide
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Flur",
            CONF_ENTITIES: [CT_LIGHT],
            CONF_USE_DEFAULT_BRIGHTNESS: False,
            CONF_DEFAULT_BRIGHTNESS: 80,
            CONF_USE_DEFAULT_COLOR_TEMP: False,
            CONF_DEFAULT_COLOR_TEMP: 4000,
            CONF_APPLY_WHEN_ON: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert group_data(entry) == {CONF_ENTITIES: [CT_LIGHT], CONF_APPLY_WHEN_ON: False}


async def test_add_group_requires_lights(hass: HomeAssistant) -> None:
    entry = await setup_groups(hass)
    result = await _add_group_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Leer", CONF_ENTITIES: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENTITIES: "no_entities"}


async def test_add_group_clamps_color_temp_to_selected_lights(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2700, max_kelvin=5000)
    entry = await setup_groups(hass)

    result = await _add_group_flow(hass, entry)
    config = _color_temp_selector_config(result)
    assert (config["min"], config["max"]) == (2000, 6500)  # no lights selected yet

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Flur",
            CONF_ENTITIES: [CT_LIGHT],
            CONF_USE_DEFAULT_COLOR_TEMP: True,
            CONF_DEFAULT_COLOR_TEMP: 6500,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert group_data(entry)[CONF_DEFAULT_COLOR_TEMP] == 5000


# --------------------------------------------------------------------------- Edit group


async def test_reconfigure_group(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    entry = await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )
    brightness_id = number_entity_id(hass, entry, CONF_DEFAULT_BRIGHTNESS)

    result = await _reconfigure_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Stored values are prefilled as toggle + slider
    suggested = _suggested(result)
    assert suggested[CONF_USE_DEFAULT_BRIGHTNESS] is True
    assert suggested[CONF_DEFAULT_BRIGHTNESS] == 60
    assert suggested[CONF_USE_DEFAULT_COLOR_TEMP] is True
    assert suggested[CONF_DEFAULT_COLOR_TEMP] == 2700
    assert suggested[CONF_USE_DEFAULT_TRANSITION_ON] is False
    assert suggested[CONF_APPLY_WHEN_ON] is True  # default
    assert suggested[CONF_ON_WHEN_ALL_ON] is False  # default
    assert suggested[CONF_HIDE_MEMBERS] is False  # default

    # Rename, disable brightness, add the floor lamp
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Stube",
            CONF_ENTITIES: [CT_LIGHT, DIM_LIGHT],
            CONF_USE_DEFAULT_BRIGHTNESS: False,
            CONF_DEFAULT_BRIGHTNESS: 60,
            CONF_USE_DEFAULT_COLOR_TEMP: True,
            CONF_DEFAULT_COLOR_TEMP: 3000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[group_id(entry)].title == "Stube"
    assert group_data(entry) == {
        CONF_ENTITIES: [CT_LIGHT, DIM_LIGHT],
        CONF_DEFAULT_COLOR_TEMP: 3000,
    }

    # Entity ID stays, members are updated
    wrapper = hass.states.get("light.wohnzimmer")
    assert wrapper.attributes["entity_id"] == [CT_LIGHT, DIM_LIGHT]
    assert CONF_DEFAULT_BRIGHTNESS not in wrapper.attributes

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, group_id(entry))})
    assert device.name == "Stube"

    # The brightness number entity is gone after the reload
    old_number = hass.states.get(brightness_id)
    assert old_number is None or old_number.state == STATE_UNAVAILABLE


async def test_reconfigure_requires_lights(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT])

    result = await _reconfigure_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Wohnzimmer", CONF_ENTITIES: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENTITIES: "no_entities"}


async def test_reconfigure_enables_default_with_slider_fallback(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT])

    result = await _reconfigure_flow(hass, entry)
    suggested = _suggested(result)
    assert suggested[CONF_USE_DEFAULT_BRIGHTNESS] is False
    assert suggested[CONF_DEFAULT_BRIGHTNESS] == 100

    # Toggle on, slider untouched -> start value is used
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ENTITIES: [CT_LIGHT], CONF_USE_DEFAULT_BRIGHTNESS: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert group_data(entry) == {CONF_ENTITIES: [CT_LIGHT], CONF_DEFAULT_BRIGHTNESS: 100}
    assert entry.subentries[group_id(entry)].title == "Wohnzimmer"  # name unchanged


async def test_reconfigure_color_temp_slider_uses_common_range(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2200, max_kelvin=6500)
    set_member(hass, "light.spot", "off", min_kelvin=2700, max_kelvin=5000)
    entry = await setup_wrapper(hass, [CT_LIGHT, "light.spot"], **{CONF_DEFAULT_COLOR_TEMP: 2000})

    result = await _reconfigure_flow(hass, entry)
    config = _color_temp_selector_config(result)
    assert (config["min"], config["max"]) == (2700, 5000)

    # A stored value outside the range is limited for the slider
    assert _suggested(result)[CONF_DEFAULT_COLOR_TEMP] == 2700


async def test_remove_group(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60})
    subentry_id = group_id(entry)
    assert hass.states.get("light.wohnzimmer") is not None

    hass.config_entries.async_remove_subentry(entry, subentry_id)
    await hass.async_block_till_done()

    assert not entry.subentries
    state = hass.states.get("light.wohnzimmer")
    assert state is None or state.state == STATE_UNAVAILABLE
    assert dr.async_get(hass).async_get_device(identifiers={(DOMAIN, subentry_id)}) is None


# --------------------------------------------------------------------------- Global settings


async def test_global_options_flow(hass: HomeAssistant) -> None:
    entry = await setup_global(hass, **{CONF_DEFAULT_TRANSITION_ON: 1.0})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    suggested = _suggested(result)
    assert suggested[CONF_USE_DEFAULT_TRANSITION_ON] is True
    assert suggested[CONF_DEFAULT_TRANSITION_ON] == 1.0
    assert suggested[CONF_USE_DEFAULT_TRANSITION_OFF] is False
    assert suggested[CONF_DEFAULT_TRANSITION_OFF] == 0.5  # slider start value

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_USE_DEFAULT_TRANSITION_ON: False,
            CONF_DEFAULT_TRANSITION_ON: 1.0,
            CONF_USE_DEFAULT_TRANSITION_OFF: True,
            CONF_DEFAULT_TRANSITION_OFF: 2.04,  # rounded to 0.1 s
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_DEFAULT_TRANSITION_OFF: 2.0}
    assert global_number_entity_id(hass, entry, CONF_DEFAULT_TRANSITION_OFF) is not None

    # The "Global settings" device belongs to the main entry, not to a group
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.config_entries_subentries[entry.entry_id] == {None}


async def test_reconfigure_on_when_all_on(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT])

    result = await _reconfigure_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ENTITIES: [CT_LIGHT], CONF_ON_WHEN_ALL_ON: True}
    )
    await hass.async_block_till_done()
    assert group_data(entry) == {CONF_ENTITIES: [CT_LIGHT], CONF_ON_WHEN_ALL_ON: True}

    # Prefilled when editing again; switching it off removes it (default)
    result = await _reconfigure_flow(hass, entry)
    assert _suggested(result)[CONF_ON_WHEN_ALL_ON] is True
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_ENTITIES: [CT_LIGHT], CONF_ON_WHEN_ALL_ON: False}
    )
    await hass.async_block_till_done()
    assert group_data(entry) == {CONF_ENTITIES: [CT_LIGHT]}
