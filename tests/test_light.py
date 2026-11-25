"""Tests for the wrapper's light entity."""

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
    CONF_DEFAULT_TRANSITION_OFF,
    CONF_DEFAULT_TRANSITION_ON,
)

from .conftest import (
    WRAPPER_ID,
    calls_by_entity,
    set_member,
    setup_integration,
    setup_wrapper,
)

CT_LIGHT = "light.decke"  # supports color temperature (2200–6500 K)
DIM_LIGHT = "light.stehlampe"  # dimmable only


async def _turn_on(hass: HomeAssistant, **data) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: WRAPPER_ID, **data}, blocking=True
    )


# --------------------------------------------------------------------------- State


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


# --------------------------------------------------------------------------- Turning on


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
    # The dimmable-only light gets no color temperature
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
    assert ATTR_BRIGHTNESS_PCT not in data  # default not applied
    assert data[ATTR_BRIGHTNESS] in (76, 77)  # 30 % converted to 0–255 by HA
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
    # switch not stored -> default (on)
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

    # Change only the brightness: color temperature stays as it is
    await _turn_on(hass, brightness=100)

    assert calls_by_entity(member_calls)[CT_LIGHT] == (SERVICE_TURN_ON, {ATTR_BRIGHTNESS: 100})


async def test_turn_on_without_defaults_passes_through(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    await setup_wrapper(hass, [CT_LIGHT, DIM_LIGHT])

    await _turn_on(hass)

    assert member_calls.call_count == 1  # one shared call for all
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


# --------------------------------------------------------------------------- Turning off


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


# --------------------------------------------------------------------------- Transitions

TRANSITION = int(LightEntityFeature.TRANSITION)


async def _turn_off(hass: HomeAssistant, **data) -> None:
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: WRAPPER_ID, **data}, blocking=True
    )


async def test_own_transitions_for_on_and_off(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off", features=TRANSITION)
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))  # no transition support
    await setup_wrapper(
        hass,
        [CT_LIGHT, DIM_LIGHT],
        **{CONF_DEFAULT_TRANSITION_ON: 1.5, CONF_DEFAULT_TRANSITION_OFF: 3.0},
    )

    await _turn_on(hass)
    calls = calls_by_entity(member_calls)
    assert calls[CT_LIGHT] == (SERVICE_TURN_ON, {ATTR_TRANSITION: 1.5})
    assert calls[DIM_LIGHT] == (SERVICE_TURN_ON, {})

    member_calls.reset_mock()
    await _turn_off(hass)
    calls = calls_by_entity(member_calls)
    assert calls[CT_LIGHT] == (SERVICE_TURN_OFF, {ATTR_TRANSITION: 3.0})
    assert calls[DIM_LIGHT] == (SERVICE_TURN_OFF, {})


async def test_global_transition_applies_without_own(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off", features=TRANSITION)
    await setup_wrapper(
        hass,
        [CT_LIGHT],
        global_options={CONF_DEFAULT_TRANSITION_ON: 0.5, CONF_DEFAULT_TRANSITION_OFF: 2.0},
        **{CONF_DEFAULT_TRANSITION_OFF: 4.0},
    )

    await _turn_on(hass)
    assert calls_by_entity(member_calls)[CT_LIGHT] == (SERVICE_TURN_ON, {ATTR_TRANSITION: 0.5})

    member_calls.reset_mock()
    await _turn_off(hass)
    # The group's own value takes precedence
    assert calls_by_entity(member_calls)[CT_LIGHT] == (SERVICE_TURN_OFF, {ATTR_TRANSITION: 4.0})


async def test_given_transition_wins(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off", features=TRANSITION)
    await setup_wrapper(hass, [CT_LIGHT], global_options={CONF_DEFAULT_TRANSITION_ON: 0.5})

    await _turn_on(hass, transition=7)

    assert calls_by_entity(member_calls)[CT_LIGHT] == (SERVICE_TURN_ON, {ATTR_TRANSITION: 7})


async def test_no_default_transition_with_flash(hass: HomeAssistant, member_calls) -> None:
    features = TRANSITION | int(LightEntityFeature.FLASH)
    set_member(hass, CT_LIGHT, "off", features=features)
    await setup_wrapper(hass, [CT_LIGHT], **{CONF_DEFAULT_TRANSITION_ON: 1.0})

    await _turn_on(hass, flash="short")

    assert ATTR_TRANSITION not in calls_by_entity(member_calls)[CT_LIGHT][1]


async def test_transition_combined_with_defaults(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off", features=TRANSITION)
    await setup_wrapper(
        hass, [CT_LIGHT], **{CONF_DEFAULT_BRIGHTNESS: 60, CONF_DEFAULT_TRANSITION_ON: 2.0}
    )

    await _turn_on(hass)

    assert calls_by_entity(member_calls)[CT_LIGHT] == (
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS_PCT: 60, ATTR_TRANSITION: 2.0},
    )


async def test_global_transition_change_applies_without_reload(
    hass: HomeAssistant, member_calls
) -> None:
    set_member(hass, CT_LIGHT, "off", features=TRANSITION)
    entry = await setup_wrapper(
        hass, [CT_LIGHT], global_options={CONF_DEFAULT_TRANSITION_ON: 0.5}
    )
    runtime_before = entry.runtime_data

    hass.config_entries.async_update_entry(entry, options={CONF_DEFAULT_TRANSITION_ON: 3.0})
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime_before  # no reload

    await _turn_on(hass)
    assert calls_by_entity(member_calls)[CT_LIGHT] == (SERVICE_TURN_ON, {ATTR_TRANSITION: 3.0})


async def test_several_groups(hass: HomeAssistant, member_calls) -> None:
    set_member(hass, CT_LIGHT, "off")
    set_member(hass, DIM_LIGHT, "off", modes=("brightness",))
    await setup_integration(
        hass,
        groups={
            "Wohnzimmer": {"entities": [CT_LIGHT], CONF_DEFAULT_BRIGHTNESS: 60},
            "Flur": {"entities": [DIM_LIGHT], CONF_DEFAULT_BRIGHTNESS: 20},
        },
    )
    assert hass.states.get("light.wohnzimmer") is not None
    assert hass.states.get("light.flur") is not None

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "light.flur"}, blocking=True
    )
    assert calls_by_entity(member_calls) == {DIM_LIGHT: (SERVICE_TURN_ON, {ATTR_BRIGHTNESS_PCT: 20})}
