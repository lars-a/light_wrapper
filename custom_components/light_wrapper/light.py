"""Licht-Plattform: Gruppe mehrerer Lichter mit Standardwerten beim Einschalten."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Iterable
import itertools
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
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

from . import LightWrapperConfigEntry
from .const import CONF_DEFAULT_BRIGHTNESS, CONF_DEFAULT_COLOR_TEMP
from .entity import device_info

# Parameter, die eine Helligkeit vorgeben -> Standardhelligkeit wird nicht angewendet
BRIGHTNESS_PARAMS = {ATTR_BRIGHTNESS, ATTR_WHITE}
# Parameter, die eine Farbe/Farbtemperatur vorgeben -> Standard-Farbtemperatur wird nicht angewendet
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

SUPPORTED_FEATURES_MASK = (
    LightEntityFeature.EFFECT | LightEntityFeature.FLASH | LightEntityFeature.TRANSITION
)

# Reihenfolge, falls kein Mitglied einen passenden Farbmodus meldet
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
    """Lichtentität anlegen."""
    async_add_entities([LightWrapperLight(entry)])


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
    """ONOFF/BRIGHTNESS dürfen nicht mit reicheren Modi kombiniert werden."""
    simple = {ColorMode.ONOFF, ColorMode.BRIGHTNESS}
    if modes - simple:
        return modes - simple
    if ColorMode.BRIGHTNESS in modes:
        return {ColorMode.BRIGHTNESS}
    return modes


# --------------------------------------------------------------------------- entity


class LightWrapperLight(LightEntity):
    """Lichtgruppe, die sich wie ein normales Licht verhält."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_icon = "mdi:lightbulb-group"

    def __init__(self, entry: LightWrapperConfigEntry) -> None:
        self._data = entry.runtime_data
        self._entity_ids: list[str] = list(self._data.entities)
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = device_info(entry)
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
        self.async_on_remove(self._data.async_add_listener(self.async_write_ha_state))
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
        self._attr_is_on = bool(on_states) if valid else None

        # Werte der eingeschalteten Mitglieder mitteln
        self._attr_brightness = _mean_int(_values(on_states, ATTR_BRIGHTNESS))
        self._attr_color_temp_kelvin = _mean_int(_values(on_states, ATTR_COLOR_TEMP_KELVIN))
        self._attr_hs_color = _mean_tuple(_values(on_states, ATTR_HS_COLOR))
        self._attr_xy_color = _mean_tuple(_values(on_states, ATTR_XY_COLOR))
        self._attr_rgb_color = _mean_tuple(_values(on_states, ATTR_RGB_COLOR), as_int=True)
        self._attr_rgbw_color = _mean_tuple(_values(on_states, ATTR_RGBW_COLOR), as_int=True)
        self._attr_rgbww_color = _mean_tuple(_values(on_states, ATTR_RGBWW_COLOR), as_int=True)

        # Farbtemperatur-Bereich über alle Mitglieder
        if mins := _values(states, ATTR_MIN_COLOR_TEMP_KELVIN):
            self._attr_min_color_temp_kelvin = min(mins)
        if maxs := _values(states, ATTR_MAX_COLOR_TEMP_KELVIN):
            self._attr_max_color_temp_kelvin = max(maxs)

        # Effekte
        effect_lists = _values(states, ATTR_EFFECT_LIST)
        self._attr_effect_list = (
            list(dict.fromkeys(itertools.chain.from_iterable(effect_lists))) or None
        )
        effects = _values(on_states, ATTR_EFFECT)
        self._attr_effect = Counter(effects).most_common(1)[0][0] if effects else None

        # Farbmodi
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

        # Features (Effekt, Flash, Transition)
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
        """Einschalten; Standardwerte nur, wenn die Gruppe aus war und nichts vorgegeben ist."""
        defaults = self._data.defaults
        switching_on = self.is_on is not True

        brightness_pct = (
            defaults.get(CONF_DEFAULT_BRIGHTNESS)
            if switching_on and not kwargs.keys() & BRIGHTNESS_PARAMS
            else None
        )
        color_temp = (
            defaults.get(CONF_DEFAULT_COLOR_TEMP)
            if switching_on and not kwargs.keys() & COLOR_PARAMS
            else None
        )

        if brightness_pct is None and color_temp is None:
            await self._async_call(SERVICE_TURN_ON, self._entity_ids, kwargs)
            return

        # Mitglieder mit identischem Payload in einem Aufruf zusammenfassen
        batches: dict[str, tuple[dict[str, Any], list[str]]] = {}
        for entity_id in self._entity_ids:
            payload = dict(kwargs)
            if brightness_pct is not None:
                payload[ATTR_BRIGHTNESS_PCT] = brightness_pct
            if color_temp is not None and (
                kelvin := self._member_color_temp(entity_id, color_temp)
            ) is not None:
                payload[ATTR_COLOR_TEMP_KELVIN] = kelvin
            key = repr(sorted(payload.items()))
            batches.setdefault(key, (payload, []))[1].append(entity_id)

        await asyncio.gather(
            *(
                self._async_call(SERVICE_TURN_ON, entity_ids, payload)
                for payload, entity_ids in batches.values()
            )
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_call(SERVICE_TURN_OFF, self._entity_ids, kwargs)

    def _member_color_temp(self, entity_id: str, kelvin: int) -> int | None:
        """Farbtemperatur nur für Mitglieder, die sie unterstützen; auf deren Bereich begrenzt."""
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
