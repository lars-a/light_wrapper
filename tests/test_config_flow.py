"""Tests für Config- und Options-Flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_ENTITIES, CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.light_wrapper.const import (
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    DOMAIN,
)
from custom_components.light_wrapper.config_flow import (
    CONF_USE_DEFAULT_BRIGHTNESS,
    CONF_USE_DEFAULT_COLOR_TEMP,
)

from .conftest import number_entity_id, set_member, setup_wrapper

CT_LIGHT = "light.decke"
DIM_LIGHT = "light.stehlampe"


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Wohnzimmer",
            CONF_ENTITIES: [CT_LIGHT, DIM_LIGHT],
            CONF_USE_DEFAULT_BRIGHTNESS: True,
            CONF_DEFAULT_BRIGHTNESS: 60,
            CONF_USE_DEFAULT_COLOR_TEMP: True,
            CONF_DEFAULT_COLOR_TEMP: 2700,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Wohnzimmer"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_ENTITIES: [CT_LIGHT, DIM_LIGHT],
        CONF_DEFAULT_BRIGHTNESS: 60,
        CONF_DEFAULT_COLOR_TEMP: 2700,
    }
    assert hass.states.get("light.wohnzimmer") is not None


async def test_user_flow_without_defaults(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Slider haben immer einen Wert; ausschlaggebend sind die Schalter
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Flur",
            CONF_ENTITIES: [CT_LIGHT],
            CONF_USE_DEFAULT_BRIGHTNESS: False,
            CONF_DEFAULT_BRIGHTNESS: 80,
            CONF_USE_DEFAULT_COLOR_TEMP: False,
            CONF_DEFAULT_COLOR_TEMP: 4000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_ENTITIES: [CT_LIGHT]}


async def test_user_flow_requires_lights(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Leer", CONF_ENTITIES: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENTITIES: "no_entities"}


async def test_options_flow_changes_members_and_disables_default(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    entry = await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )
    brightness_id = number_entity_id(hass, entry, CONF_DEFAULT_BRIGHTNESS)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    # Gespeicherte Werte werden als Schalter + Slider vorbelegt
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested[CONF_USE_DEFAULT_BRIGHTNESS] is True
    assert suggested[CONF_DEFAULT_BRIGHTNESS] == 60
    assert suggested[CONF_USE_DEFAULT_COLOR_TEMP] is True
    assert suggested[CONF_DEFAULT_COLOR_TEMP] == 2700

    # Helligkeit abschalten, Stehlampe hinzufügen
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENTITIES: [CT_LIGHT, DIM_LIGHT],
            CONF_USE_DEFAULT_BRIGHTNESS: False,
            CONF_DEFAULT_BRIGHTNESS: 60,
            CONF_USE_DEFAULT_COLOR_TEMP: True,
            CONF_DEFAULT_COLOR_TEMP: 3000,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_ENTITIES: [CT_LIGHT, DIM_LIGHT], CONF_DEFAULT_COLOR_TEMP: 3000}

    wrapper = hass.states.get("light.wohnzimmer")
    assert wrapper.attributes["entity_id"] == [CT_LIGHT, DIM_LIGHT]
    assert CONF_DEFAULT_BRIGHTNESS not in wrapper.attributes

    # Number-Entität für die Helligkeit gibt es nach dem Reload nicht mehr
    old_number = hass.states.get(brightness_id)
    assert old_number is None or old_number.state == STATE_UNAVAILABLE


async def test_options_flow_requires_lights(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT])

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ENTITIES: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENTITIES: "no_entities"}


async def test_options_flow_enables_default_with_slider_fallback(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    entry = await setup_wrapper(hass, [CT_LIGHT])

    result = await hass.config_entries.options.async_init(entry.entry_id)
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested[CONF_USE_DEFAULT_BRIGHTNESS] is False
    assert suggested[CONF_DEFAULT_BRIGHTNESS] == 100

    # Schalter an, Slider nicht angefasst -> Startwert wird übernommen
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ENTITIES: [CT_LIGHT], CONF_USE_DEFAULT_BRIGHTNESS: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_ENTITIES: [CT_LIGHT], CONF_DEFAULT_BRIGHTNESS: 100}
