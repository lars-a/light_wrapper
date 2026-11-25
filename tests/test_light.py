"""Tests für die Lichtentität des Wrappers."""

from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    LightEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from custom_components.light_wrapper.const import (
    CONF_APPLY_WHEN_ON,
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
)

from .conftest import WRAPPER_ID, calls_by_entity, set_member, setup_wrapper

CT_LIGHT = "light.decke"  # kann Farbtemperatur (2200–6500 K)
DIM_LIGHT = "light.stehlampe"  # nur dimmbar


async def _turn_on(hass: HomeAssistant, **data) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: WRAPPER_ID, **data}, blocking=True
    )


# --------------------------------------------------------------------------- Zustand


async def test_state_aggregation(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "on", brightness=200, kelvin=3000)
    set_member(hass, DIM_LIGHT, "on", modes=("brightness",), brightness=100)
    await setup_wrapper(hass, [CT_LIGHT, DIM_LIGHT])

    state = hass.states.get(WRAPPER_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 150
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 3000
    assert state.attributes["supported_color_modes"] == ["color_temp"]
    assert state.attributes["color_mode"] == "color_temp"
    assert state.attributes[ATTR_ENTITY_ID] == [CT_LIGHT, DIM_LIGHT]


async def test_on_if_any_member_on(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    await setup_wrapper(hass, [CT_LIGHT, DIM_LIGHT])
    assert hass.states.get(WRAPPER_ID).state == STATE_OFF

    set_member(hass, DIM_LIGHT, "on", modes=("brightness",), brightness=50)
    await hass.async_block_till_done()
    state = hass.states.get(WRAPPER_ID)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 50


async def test_unavailable_if_all_members_unavailable(hass: HomeAssistant) -> None:
    hass.states.async_set(CT_LIGHT, STATE_UNAVAILABLE)
    hass.states.async_set(DIM_LIGHT, STATE_UNAVAILABLE)
    await setup_wrapper(hass, [CT_LIGHT, DIM_LIGHT])
    assert hass.states.get(WRAPPER_ID).state == STATE_UNAVAILABLE

    set_member(hass, CT_LIGHT, "off")
    await hass.async_block_till_done()
    assert hass.states.get(WRAPPER_ID).state == STATE_OFF


async def test_color_modes_union(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, "light.strip", "off", modes=("hs",))
    await setup_wrapper(hass, [CT_LIGHT, "light.strip"])
    modes = hass.states.get(WRAPPER_ID).attributes["supported_color_modes"]
    assert sorted(modes) == ["color_temp", "hs"]


async def test_defaults_shown_as_attributes(hass: HomeAssistant) -> None:
    set_member(hass, CT_LIGHT, "off")
    await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )
    attrs = hass.states.get(WRAPPER_ID).attributes
    assert attrs[CONF_DEFAULT_BRIGHTNESS] == 60
    assert attrs[CONF_DEFAULT_COLOR_TEMP] == 2700


# --------------------------------------------------------------------------- Einschalten


async def test_turn_on_without_params_uses_defaults(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    await setup_wrapper(
        hass, [CT_LIGHT, DIM_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )

    await _turn_on(hass)

    calls = calls_by_entity(member_calls)
    assert calls[CT_LIGHT] == (
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS_PCT: 60, ATTR_COLOR_TEMP_KELVIN: 2700},
    )
    # Nur dimmbares Licht bekommt keine Farbtemperatur
    assert calls[DIM_LIGHT] == (SERVICE_TURN_ON, {ATTR_BRIGHTNESS_PCT: 60})


async def test_default_color_temp_clamped_to_member_range(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off", min_kelvin=2700, max_kelvin=5000)
    await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_COLOR_TEMP: 2000})

    await _turn_on(hass)

    assert calls_by_entity(member_calls)[CT_LIGHT][1][ATTR_COLOR_TEMP_KELVIN] == 2700


async def test_given_brightness_wins_but_color_default_applies(
    hass: HomeAssistant, member_calls
) -> None:
    set_member(hass, CT_LIGHT, "off")
    await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )

    await _turn_on(hass, brightness_pct=30)

    _service, data = calls_by_entity(member_calls)[CT_LIGHT]
    assert ATTR_BRIGHTNESS_PCT not in data  # Standard nicht angewendet
    assert data[ATTR_BRIGHTNESS] in (76, 77)  # 30 % von HA in 0–255 umgerechnet
    assert data[ATTR_COLOR_TEMP_KELVIN] == 2700


async def test_given_color_wins_but_brightness_default_applies(
    hass: HomeAssistant, member_calls
) -> None:
    set_member(hass, CT_LIGHT, "off")
    await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )

    await _turn_on(hass, color_temp_kelvin=4000)

    _service, data = calls_by_entity(member_calls)[CT_LIGHT]
    assert data[ATTR_COLOR_TEMP_KELVIN] == 4000
    assert data[ATTR_BRIGHTNESS_PCT] == 60


async def test_given_hs_color_blocks_color_temp_default(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, "light.strip", "off", modes=("hs", "color_temp"))
    await setup_wrapper(hass, ["light.strip"], **{CONF_DEFAULT_COLOR_TEMP: 2700})

    await _turn_on(hass, hs_color=(120, 100))

    _service, data = calls_by_entity(member_calls)["light.strip"]
    assert ATTR_COLOR_TEMP_KELVIN not in data
    assert tuple(data[ATTR_HS_COLOR]) == (120, 100)


async def test_no_defaults_when_already_on_with_switch_off(
    hass: HomeAssistant, member_calls
) -> None:
    set_member(hass, CT_LIGHT, "on", brightness=20, kelvin=5000)
    await setup_wrapper(
        hass,
        [CT_LIGHT],
        **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700, CONF_APPLY_WHEN_ON: False},
    )

    await _turn_on(hass)

    assert calls_by_entity(member_calls)[CT_LIGHT] == (SERVICE_TURN_ON, {})


async def test_defaults_when_already_on_by_default(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "on", brightness=20, kelvin=5000)
    set_member(hass, DIM_LIGHT, "on", modes=("brightness",), brightness=20)
    # Schalter nicht gespeichert -> Standard (an)
    await setup_wrapper(
        hass, [CT_LIGHT, DIM_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700}
    )

    await _turn_on(hass)

    calls = calls_by_entity(member_calls)
    assert calls[CT_LIGHT] == (
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS_PCT: 60, ATTR_COLOR_TEMP_KELVIN: 2700},
    )
    assert calls[DIM_LIGHT] == (SERVICE_TURN_ON, {ATTR_BRIGHTNESS_PCT: 60})


async def test_defaults_when_already_on_with_switch_keep_transition(
    hass: HomeAssistant, member_calls
) -> None:
    features = int(LightEntityFeature.TRANSITION)
    set_member(hass, CT_LIGHT, "on", brightness=20, kelvin=5000, features=features)
    await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_APPLY_WHEN_ON: True}
    )

    await _turn_on(hass, transition=2)

    assert calls_by_entity(member_calls)[CT_LIGHT] == (
        SERVICE_TURN_ON,
        {ATTR_TRANSITION: 2, ATTR_BRIGHTNESS_PCT: 60},
    )


async def test_already_on_with_switch_but_params_given(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "on", brightness=20, kelvin=5000)
    await setup_wrapper(
        hass,
        [CT_LIGHT],
        **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700, CONF_APPLY_WHEN_ON: True},
    )

    # Nur die Helligkeit ändern: Farbtemperatur bleibt, wie sie ist
    await _turn_on(hass, brightness=100)

    assert calls_by_entity(member_calls)[CT_LIGHT] == (SERVICE_TURN_ON, {ATTR_BRIGHTNESS: 100})


async def test_turn_on_without_defaults_passes_through(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    await setup_wrapper(hass, [CT_LIGHT, DIM_LIGHT])

    await _turn_on(hass)

    assert member_calls.call_count == 1  # ein gemeinsamer Aufruf für alle
    calls = calls_by_entity(member_calls)
    assert calls[CT_LIGHT] == (SERVICE_TURN_ON, {})
    assert calls[DIM_LIGHT] == (SERVICE_TURN_ON, {})


async def test_members_with_same_payload_share_one_call(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, "light.a", "off")
    set_member(hass, "light.b", "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    await setup_wrapper(
        hass,
        ["light.a", "light.b", DIM_LIGHT],
        **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_COLOR_TEMP: 2700},
    )

    await _turn_on(hass)

    assert member_calls.call_count == 2


# --------------------------------------------------------------------------- Ausschalten


async def test_turn_off_passes_transition(hass: HomeAssistant, member_calls) -> None:
    features = int(LightEntityFeature.TRANSITION)
    set_member(hass, CT_LIGHT, "on", brightness=100, kelvin=3000, features=features)
    set_member(hass, DIM_LIGHT, "on", modes=("brightness",), brightness=100, features=features)
    await setup_wrapper(hass, [CT_LIGHT, DIM_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60})

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: WRAPPER_ID, ATTR_TRANSITION: 2},
        blocking=True,
    )

    calls = calls_by_entity(member_calls)
    assert calls[CT_LIGHT] == (SERVICE_TURN_OFF, {ATTR_TRANSITION: 2})
    assert calls[DIM_LIGHT] == (SERVICE_TURN_OFF, {ATTR_TRANSITION: 2})
