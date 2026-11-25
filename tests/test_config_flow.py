"""Tests für Config- und Options-Flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_ENTITIES, CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.light_wrapper.const import (
    CONF_APPLY_WHEN_ON,
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    CONF_DEFAULT_TRANSITION_OFF,
    CONF_DEFAULT_TRANSITION_ON,
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_GLOBAL,
)
from custom_components.light_wrapper.config_flow import (
    CONF_USE_DEFAULT_BRIGHTNESS,
    CONF_USE_DEFAULT_COLOR_TEMP,
    CONF_USE_DEFAULT_TRANSITION_OFF,
    CONF_USE_DEFAULT_TRANSITION_ON,
)

from .conftest import number_entity_id, set_member, setup_global, setup_wrapper

CT_LIGHT = "light.decke"
DIM_LIGHT = "light.stehlampe"


async def _group_flow(hass: HomeAssistant):
    """Config-Flow starten und im Menü „Lichtgruppe“ wählen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["group", "global"]
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "group"}
    )


def _suggested(result) -> dict:
    return {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))

    result = await _group_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "group"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Wohnzimmer",
            CONF_ENTITIES: [CT_LIGHT, DIM_LIGHT],
            CONF_USE_DEFAULT_BRIGHTNESS: True,
            CONF_DEFAULT_BRIGHTNESS: 60,
            CONF_USE_DEFAULT_COLOR_TEMP: True,
            CONF_DEFAULT_COLOR_TEMP: 2700,
            CONF_APPLY_WHEN_ON: True,
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
    }  # Schalter an = Standard, wird nicht gespeichert
    assert hass.states.get("light.wohnzimmer") is not None


async def test_user_flow_without_defaults(hass: HomeAssistant) -> None:
    result = await _group_flow(hass)
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
            CONF_APPLY_WHEN_ON: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_ENTITIES: [CT_LIGHT], CONF_APPLY_WHEN_ON: False}


async def test_user_flow_requires_lights(hass: HomeAssistant) -> None:
    result = await _group_flow(hass)
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
    assert suggested[CONF_APPLY_WHEN_ON] is True  # Standard

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


def _color_temp_selector_config(result) -> dict:
    for key, value in result["data_schema"].schema.items():
        if str(key) == CONF_DEFAULT_COLOR_TEMP:
            return value.config
    raise AssertionError("Kein Farbtemperatur-Slider im Formular")


async def test_options_flow_color_temp_slider_uses_common_range(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2200, max_kelvin=6500)
    set_member(hass, "light.spot", "off", min_kelvin=2700, max_kelvin=5000)
    entry = await setup_wrapper(
        hass, [CT_LIGHT, "light.spot"], **{CONF_DEFAULT_COLOR_TEMP: 2000}
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    config = _color_temp_selector_config(result)
    assert (config["min"], config["max"]) == (2700, 5000)

    # Gespeicherter Wert außerhalb des Bereichs wird für den Slider begrenzt
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested[CONF_DEFAULT_COLOR_TEMP] == 2700
    assert suggested[CONF_APPLY_WHEN_ON] is True  # Standard


async def test_user_flow_clamps_color_temp_to_selected_lights(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2700, max_kelvin=5000)

    result = await _group_flow(hass)
    config = _color_temp_selector_config(result)
    assert (config["min"], config["max"]) == (2000, 6500)  # Lichter noch nicht gewählt

    result = await hass.config_entries.flow.async_configure(
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
    assert result["options"][CONF_DEFAULT_COLOR_TEMP] == 5000


# --------------------------------------------------------------------------- Übergangszeiten


async def test_group_flow_stores_own_transitions(hass: HomeAssistant) -> None:
    result = await _group_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Flur",
            CONF_ENTITIES: [CT_LIGHT],
            CONF_USE_DEFAULT_TRANSITION_ON: True,
            CONF_DEFAULT_TRANSITION_ON: 1.5,
            CONF_USE_DEFAULT_TRANSITION_OFF: False,
            CONF_DEFAULT_TRANSITION_OFF: 3,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_ENTITIES: [CT_LIGHT], CONF_DEFAULT_TRANSITION_ON: 1.5}


async def test_global_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "global"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "global"
    suggested = _suggested(result)
    assert suggested[CONF_USE_DEFAULT_TRANSITION_ON] is False
    assert suggested[CONF_DEFAULT_TRANSITION_ON] == 0.5  # Startwert des Sliders
    assert suggested[CONF_DEFAULT_TRANSITION_OFF] == 0.5

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USE_DEFAULT_TRANSITION_ON: True,
            CONF_DEFAULT_TRANSITION_ON: 0.8,
            CONF_USE_DEFAULT_TRANSITION_OFF: True,
            CONF_DEFAULT_TRANSITION_OFF: 2.04,  # wird auf 0,1 s gerundet
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_GLOBAL}
    assert result["options"] == {
        CONF_DEFAULT_TRANSITION_ON: 0.8,
        CONF_DEFAULT_TRANSITION_OFF: 2.0,
    }
    entry = hass.config_entries.async_get_entry(result["result"].entry_id)
    assert number_entity_id(hass, entry, CONF_DEFAULT_TRANSITION_ON) is not None
    assert hass.states.get("light.globale_einstellungen") is None  # kein Licht


async def test_menu_skipped_when_global_exists(hass: HomeAssistant) -> None:
    await setup_global(hass, **{CONF_DEFAULT_TRANSITION_ON: 1.0})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "group"


async def test_global_options_flow(hass: HomeAssistant) -> None:
    entry = await setup_global(hass, **{CONF_DEFAULT_TRANSITION_ON: 1.0})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "global"
    suggested = _suggested(result)
    assert suggested[CONF_USE_DEFAULT_TRANSITION_ON] is True
    assert suggested[CONF_DEFAULT_TRANSITION_ON] == 1.0
    assert suggested[CONF_USE_DEFAULT_TRANSITION_OFF] is False

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_USE_DEFAULT_TRANSITION_ON: False,
            CONF_DEFAULT_TRANSITION_ON: 1.0,
            CONF_USE_DEFAULT_TRANSITION_OFF: True,
            CONF_DEFAULT_TRANSITION_OFF: 4.5,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_DEFAULT_TRANSITION_OFF: 4.5}
