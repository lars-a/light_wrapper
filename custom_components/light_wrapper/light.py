"""Light platform: group of several lights with defaults when turning on."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable, Iterable
import itertools
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ATTR_XY_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import LightWrapperConfigEntry, global_defaults
from .const import (
    CONF_DEFAULT_BRIGHTNESS,
    CONF_DEFAULT_COLOR_TEMP,
    CONF_DEFAULT_TRANSITION_OFF,
    CONF_DEFAULT_TRANSITION_ON,
)
from .entity import device_info

# Parameters that set a brightness -> default brightness is not applied
BRIGHTNESS_PARAMS = {ATTR_BRIGHTNESS, ATTR_WHITE}
# Parameters that set a color/color temperature -> default color temperature is not applied
COLOR_PARAMS = {
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_XY_COLOR,
    ATTR_WHITE,
    ATTR_EFFECT,
}

# Parameters that still count as "no parameters" when the group is already on
PASSIVE_PARAMS = {ATTR_TRANSITION}
# Parameters for which no default transition is added
TRANSITION_PARAMS = {ATTR_TRANSITION, ATTR_FLASH}

SUPPORTED_FEATURES_MASK = (
    LightEntityFeature.EFFECT | LightEntityFeature.FLASH | LightEntityFeature.TRANSITION
)

# Order used if no member reports a matching color mode
COLOR_MODE_FALLBACK_ORDER = (
    ColorMode.COLOR_TEMP,
    ColorMode.HS,
    ColorMode.XY,
    ColorMode.RGB,
    ColorMode.RGBW,
    ColorMode.RGBWW,
    ColorMode.WHITE,
    ColorMode.BRIGHTNESS,
    ColorMode.ONOFF,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LightWrapperConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one light entity per light group."""
    for subentry_id in entry.runtime_data.groups:
        async_add_entities(
            [LightWrapperLight(entry, subentry_id)], config_subentry_id=subentry_id
        )


# --------------------------------------------------------------------------- helpers


def _values(states: Iterable[State], key: str) -> list[Any]:
    return [value for state in states if (value := state.attributes.get(key)) is not None]


def _mean_int(values: list[Any]) -> int | None:
    if not values:
        return None
    return round(sum(values) / len(values))


def _mean_tuple(values: list[Any], as_int: bool = False) -> tuple | None:
    if not values:
        return None
    means = (sum(component) / len(values) for component in zip(*values, strict=False))
    if as_int:
        return tuple(round(m) for m in means)
    return tuple(means)


def _to_color_mode(value: Any) -> ColorMode | None:
    try:
        mode = ColorMode(value)
    except ValueError:
        return None
    return None if mode == ColorMode.UNKNOWN else mode


def _filter_color_modes(modes: set[ColorMode]) -> set[ColorMode]:
    """ONOFF/BRIGHTNESS must not be combined with richer modes."""
    simple = {ColorMode.ONOFF, ColorMode.BRIGHTNESS}
    if modes - simple:
        return modes - simple
    if ColorMode.BRIGHTNESS in modes:
        return {ColorMode.BRIGHTNESS}
    return modes


# --------------------------------------------------------------------------- entity


class LightWrapperLight(LightEntity):
    """Light group that behaves like a regular light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_icon = "mdi:lightbulb-group"

    def __init__(self, entry: LightWrapperConfigEntry, subentry_id: str) -> None:
        self._data = entry.runtime_data.groups[subentry_id]
        self._entity_ids: list[str] = list(self._data.entities)
        self._attr_unique_id = subentry_id
        self._attr_device_info = device_info(entry, entry.subentries[subentry_id])
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = None
        self._attr_is_on = None

    # ----------------------------------------------------------------- lifecycle

    async def async_added_to_hass(self) -> None:
        @callback
        def _member_changed(event: Event[EventStateChangedData]) -> None:
            self._async_update_group_state()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(self.hass, self._entity_ids, _member_changed)
        )
        @callback
        def _settings_changed() -> None:
            # "on only when all are on" changes the state without a reload
            self._async_update_group_state()
            self.async_write_ha_state()

        self.async_on_remove(self._data.async_add_listener(_settings_changed))
        self._async_update_group_state()

    # ----------------------------------------------------------------- state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {ATTR_ENTITY_ID: self._entity_ids}
        attrs.update(self._data.defaults)
        return attrs

    @callback
    def _async_update_group_state(self) -> None:
        states = [s for eid in self._entity_ids if (s := self.hass.states.get(eid)) is not None]
        valid = [s for s in states if s.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)]
        on_states = [s for s in valid if s.state == STATE_ON]

        self._attr_available = any(s.state != STATE_UNAVAILABLE for s in states)
        # On when any member is on, or only when all are (members that are
        # unavailable or unknown are not counted)
        if not valid:
            self._attr_is_on = None
        elif self._data.on_when_all_on:
            self._attr_is_on = len(on_states) == len(valid)
        else:
            self._attr_is_on = bool(on_states)

        # Average the values of the members that are on
        self._attr_brightness = _mean_int(_values(on_states, ATTR_BRIGHTNESS))
        self._attr_color_temp_kelvin = _mean_int(_values(on_states, ATTR_COLOR_TEMP_KELVIN))
        self._attr_hs_color = _mean_tuple(_values(on_states, ATTR_HS_COLOR))
        self._attr_xy_color = _mean_tuple(_values(on_states, ATTR_XY_COLOR))
        self._attr_rgb_color = _mean_tuple(_values(on_states, ATTR_RGB_COLOR), as_int=True)
        self._attr_rgbw_color = _mean_tuple(_values(on_states, ATTR_RGBW_COLOR), as_int=True)
        self._attr_rgbww_color = _mean_tuple(_values(on_states, ATTR_RGBWW_COLOR), as_int=True)

        # Color temperature range across all members
        if mins := _values(states, ATTR_MIN_COLOR_TEMP_KELVIN):
            self._attr_min_color_temp_kelvin = min(mins)
        if maxs := _values(states, ATTR_MAX_COLOR_TEMP_KELVIN):
            self._attr_max_color_temp_kelvin = max(maxs)

        # Effects
        effect_lists = _values(states, ATTR_EFFECT_LIST)
        self._attr_effect_list = (
            list(dict.fromkeys(itertools.chain.from_iterable(effect_lists))) or None
        )
        effects = _values(on_states, ATTR_EFFECT)
        self._attr_effect = Counter(effects).most_common(1)[0][0] if effects else None

        # Color modes
        modes: set[ColorMode] = set()
        for state in states:
            for raw in state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) or []:
                if (mode := _to_color_mode(raw)) is not None:
                    modes.add(mode)
        supported = _filter_color_modes(modes) or {ColorMode.ONOFF}
        self._attr_supported_color_modes = supported
        self._attr_color_mode = (
            self._pick_color_mode(on_states, supported) if self._attr_is_on else None
        )

        # Features (effect, flash, transition)
        features = 0
        for state in states:
            features |= int(state.attributes.get(ATTR_SUPPORTED_FEATURES, 0))
        self._attr_supported_features = LightEntityFeature(features) & SUPPORTED_FEATURES_MASK

    @staticmethod
    def _pick_color_mode(on_states: list[State], supported: set[ColorMode]) -> ColorMode:
        counts = Counter(
            mode
            for raw in _values(on_states, ATTR_COLOR_MODE)
            if (mode := _to_color_mode(raw)) is not None and mode in supported
        )
        ranked = [mode for mode, _ in counts.most_common()]
        rich = [m for m in ranked if m not in (ColorMode.ONOFF, ColorMode.BRIGHTNESS)]
        if rich:
            return rich[0]
        if ranked:
            return ranked[0]
        for mode in COLOR_MODE_FALLBACK_ORDER:
            if mode in supported:
                return mode
        return next(iter(supported))

    # ----------------------------------------------------------------- actions

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on with defaults.

        If the group was off, every default whose quantity is not given applies.
        If it is already on, the defaults only apply if the "apply when on" switch
        is on and no parameters except a transition are given.
        The default transition applies to every turn-on without transition/flash.
        """
        defaults = self._data.defaults
        apply_defaults = self.is_on is not True or (
            self._data.apply_when_on and not kwargs.keys() - PASSIVE_PARAMS
        )

        brightness_pct = (
            defaults.get(CONF_DEFAULT_BRIGHTNESS)
            if apply_defaults and not kwargs.keys() & BRIGHTNESS_PARAMS
            else None
        )
        color_temp = (
            defaults.get(CONF_DEFAULT_COLOR_TEMP)
            if apply_defaults and not kwargs.keys() & COLOR_PARAMS
            else None
        )
        transition = self._default_transition(CONF_DEFAULT_TRANSITION_ON, kwargs)

        def payload(entity_id: str) -> dict[str, Any]:
            data = self._with_transition(entity_id, kwargs, transition)
            if brightness_pct is not None:
                data[ATTR_BRIGHTNESS_PCT] = brightness_pct
            if color_temp is not None and (
                kelvin := self._member_color_temp(entity_id, color_temp)
            ) is not None:
                data[ATTR_COLOR_TEMP_KELVIN] = kelvin
            return data

        await self._async_call_members(SERVICE_TURN_ON, payload)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off; without transition/flash, use the default transition."""
        transition = self._default_transition(CONF_DEFAULT_TRANSITION_OFF, kwargs)
        await self._async_call_members(
            SERVICE_TURN_OFF,
            lambda entity_id: self._with_transition(entity_id, kwargs, transition),
        )

    def _default_transition(self, key: str, kwargs: dict[str, Any]) -> float | None:
        """The group's own default transition, otherwise the global one.

        None if the call already contains transition or flash.
        """
        if kwargs.keys() & TRANSITION_PARAMS:
            return None
        if key in self._data.defaults:
            return self._data.defaults[key]
        return global_defaults(self.hass).get(key)

    def _with_transition(
        self, entity_id: str, kwargs: dict[str, Any], transition: float | None
    ) -> dict[str, Any]:
        """Call data for a member; transition only if it supports transitions."""
        data = dict(kwargs)
        if transition is not None and self._member_supports_transition(entity_id):
            data[ATTR_TRANSITION] = transition
        return data

    def _member_supports_transition(self, entity_id: str) -> bool:
        if (state := self.hass.states.get(entity_id)) is None:
            return False
        features = int(state.attributes.get(ATTR_SUPPORTED_FEATURES, 0))
        return bool(features & LightEntityFeature.TRANSITION)

    async def _async_call_members(
        self, service: str, payload: Callable[[str], dict[str, Any]]
    ) -> None:
        """Combine members with an identical payload into one call."""
        batches: dict[str, tuple[dict[str, Any], list[str]]] = {}
        for entity_id in self._entity_ids:
            data = payload(entity_id)
            key = repr(sorted(data.items()))
            batches.setdefault(key, (data, []))[1].append(entity_id)

        await asyncio.gather(
            *(
                self._async_call(service, entity_ids, data)
                for data, entity_ids in batches.values()
            )
        )

    def _member_color_temp(self, entity_id: str, kelvin: int) -> int | None:
        """Color temperature only for members that support it, limited to their range."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        if ColorMode.COLOR_TEMP not in (state.attributes.get(ATTR_SUPPORTED_COLOR_MODES) or []):
            return None
        low = state.attributes.get(ATTR_MIN_COLOR_TEMP_KELVIN)
        high = state.attributes.get(ATTR_MAX_COLOR_TEMP_KELVIN)
        if low is not None:
            kelvin = max(kelvin, int(low))
        if high is not None:
            kelvin = min(kelvin, int(high))
        return kelvin

    async def _async_call(self, service: str, entity_ids: list[str], data: dict[str, Any]) -> None:
        await self.hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_ids, **data},
            blocking=True,
            context=self._context,
        )
