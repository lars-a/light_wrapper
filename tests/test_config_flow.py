"""Tests für Config-Flow, Options-Flow (global) und Untereintrags-Flow (Lichtgruppen)."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_ENTITIES, CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from custom_components.light_wrapper.config_flow import (
    CONF_USE_DEFAULT_BRIGHTNESS,
    CONF_USE_DEFAULT_COLOR_TEMP,
    CONF_USE_DEFAULT_TRANSITION_OFF,
    CONF_USE_DEFAULT_TRANSITION_ON,
)
from custom_components.light_wrapper.const import (
    CONF_APPLY_WHEN_ON,
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    CONF_DEFAULT_TRANSITION_OFF,
    CONF_DEFAULT_TRANSITION_ON,
    DOMAIN,
    ENTRY_TITLE,
    SUBENTRY_TYPE_GROUP,
)

from .conftest import (
    global_number_entity_id,
    group_data,
    group_id,
    number_entity_id,
    set_member,
    setup_global,
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
    raise AssertionError("Kein Farbtemperatur-Slider im Formular")


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


# --------------------------------------------------------------------------- Einrichten


async def test_setup_creates_single_entry_without_questions(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ENTRY_TITLE
    assert result["data"] == {}
    assert result["options"] == {}

    # Number-Entitäten der globalen Einstellungen gibt es erst, wenn eine aktiv ist
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert global_number_entity_id(hass, entry, CONF_DEFAULT_TRANSITION_ON) is None

    # Nur ein Eintrag erlaubt
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


# --------------------------------------------------------------------------- Gruppe hinzufügen


async def test_add_group(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    entry = await setup_global(hass)

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
    }  # Schalter „auch wenn an“ = Standard, wird nicht gespeichert

    state = hass.states.get("light.wohnzimmer")
    assert state is not None
    assert state.attributes["entity_id"] == [CT_LIGHT, DIM_LIGHT]
    assert number_entity_id(hass, entry, CONF_DEFAULT_BRIGHTNESS) is not None

    # Die Gruppe hat ein eigenes Gerät, das zum Untereintrag gehört
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, group_id(entry))})
    assert device is not None
    assert device.name == "Wohnzimmer"
    assert group_id(entry) in device.config_entries_subentries[entry.entry_id]


async def test_add_group_without_defaults(hass: HomeAssistant) -> None:
    entry = await setup_global(hass)
    result = await _add_group_flow(hass, entry)
    # Slider haben immer einen Wert; ausschlaggebend sind die Schalter
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
    entry = await setup_global(hass)
    result = await _add_group_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Leer", CONF_ENTITIES: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENTITIES: "no_entities"}


async def test_add_group_clamps_color_temp_to_selected_lights(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2700, max_kelvin=5000)
    entry = await setup_global(hass)

    result = await _add_group_flow(hass, entry)
    config = _color_temp_selector_config(result)
    assert (config["min"], config["max"]) == (2000, 6500)  # Lichter noch nicht gewählt

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


# --------------------------------------------------------------------------- Gruppe bearbeiten


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

    # Gespeicherte Werte werden als Schalter + Slider vorbelegt
    suggested = _suggested(result)
    assert suggested[CONF_USE_DEFAULT_BRIGHTNESS] is True
    assert suggested[CONF_DEFAULT_BRIGHTNESS] == 60
    assert suggested[CONF_USE_DEFAULT_COLOR_TEMP] is True
    assert suggested[CONF_DEFAULT_COLOR_TEMP] == 2700
    assert suggested[CONF_USE_DEFAULT_TRANSITION_ON] is False
    assert suggested[CONF_APPLY_WHEN_ON] is True  # Standard

    # Umbenennen, Helligkeit abschalten, Stehlampe hinzufügen
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

    # Entity-ID bleibt, die Mitglieder sind aktualisiert
    wrapper = hass.states.get("light.wohnzimmer")
    assert wrapper.attributes["entity_id"] == [CT_LIGHT, DIM_LIGHT]
    assert CONF_DEFAULT_BRIGHTNESS not in wrapper.attributes

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, group_id(entry))})
    assert device.name == "Stube"

    # Number-Entität für die Helligkeit gibt es nach dem Neuladen nicht mehr
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

    # Schalter an, Slider nicht angefasst -> Startwert wird übernommen
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ENTITIES: [CT_LIGHT], CONF_USE_DEFAULT_BRIGHTNESS: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert group_data(entry) == {CONF_ENTITIES: [CT_LIGHT], CONF_DEFAULT_BRIGHTNESS: 100}
    assert entry.subentries[group_id(entry)].title == "Wohnzimmer"  # Name unverändert


async def test_reconfigure_color_temp_slider_uses_common_range(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2200, max_kelvin=6500)
    set_member(hass, "light.spot", "off", min_kelvin=2700, max_kelvin=5000)
    entry = await setup_wrapper(hass, [CT_LIGHT, "light.spot"], **{CONF_DEFAULT_COLOR_TEMP: 2000})

    result = await _reconfigure_flow(hass, entry)
    config = _color_temp_selector_config(result)
    assert (config["min"], config["max"]) == (2700, 5000)

    # Gespeicherter Wert außerhalb des Bereichs wird für den Slider begrenzt
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


# --------------------------------------------------------------------------- Globale Einstellungen


async def test_global_options_flow(hass: HomeAssistant) -> None:
    entry = await setup_global(hass, **{CONF_DEFAULT_TRANSITION_ON: 1.0})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    suggested = _suggested(result)
    assert suggested[CONF_USE_DEFAULT_TRANSITION_ON] is True
    assert suggested[CONF_DEFAULT_TRANSITION_ON] == 1.0
    assert suggested[CONF_USE_DEFAULT_TRANSITION_OFF] is False
    assert suggested[CONF_DEFAULT_TRANSITION_OFF] == 0.5  # Startwert des Sliders

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_USE_DEFAULT_TRANSITION_ON: False,
            CONF_DEFAULT_TRANSITION_ON: 1.0,
            CONF_USE_DEFAULT_TRANSITION_OFF: True,
            CONF_DEFAULT_TRANSITION_OFF: 2.04,  # wird auf 0,1 s gerundet
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_DEFAULT_TRANSITION_OFF: 2.0}
    assert global_number_entity_id(hass, entry, CONF_DEFAULT_TRANSITION_OFF) is not None

    # Gerät „Globale Einstellungen“ hängt am Haupteintrag, nicht an einer Gruppe
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.config_entries_subentries[entry.entry_id] == {None}
