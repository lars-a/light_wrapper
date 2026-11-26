"""Remember the capabilities of member lights.

Some lights only report their capabilities (color modes, color temperature
range, features, effects) while they are on, and often not yet in the first
state after turning on. While such a light does not report them, the group
would not know that it supports color temperature: the default color
temperature or transition would not be sent, and the group's color
temperature controls would disappear for a moment.

What a member reports while it is on is remembered (stored across restarts)
and always combined with what it currently reports. Remembered capabilities are
dropped when the light is no longer a member of any group, so removing and
re-adding a light resets them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from homeassistant.components.light import (
    ATTR_EFFECT_LIST,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_SUPPORTED_COLOR_MODES,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_KEY = f"{DOMAIN}.capabilities"
STORAGE_VERSION = 1
SAVE_DELAY = 10
DATA_CAPABILITIES = f"{DOMAIN}_capabilities"


class CapabilityCache:
    """Capabilities seen per member light while it was on."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, dict[str, Any]]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._data: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        self._data = await self._store.async_load() or {}

    def get(self, entity_id: str) -> dict[str, Any]:
        return self._data.get(entity_id, {})

    @callback
    def async_remember(self, entity_id: str, capabilities: dict[str, Any]) -> None:
        if not capabilities or self._data.get(entity_id) == capabilities:
            return
        self._data[entity_id] = capabilities
        self._save()

    @callback
    def async_keep_only(self, entity_ids: Iterable[str]) -> None:
        """Forget lights that are no longer a member of any group."""
        keep = set(entity_ids)
        if stale := self._data.keys() - keep:
            for entity_id in stale:
                del self._data[entity_id]
            self._save()

    def _save(self) -> None:
        self._store.async_delay_save(lambda: self._data, SAVE_DELAY)


async def async_setup_capabilities(hass: HomeAssistant) -> None:
    """Load the remembered capabilities (once per start)."""
    if DATA_CAPABILITIES in hass.data:
        return
    cache = CapabilityCache(hass)
    await cache.async_load()
    hass.data[DATA_CAPABILITIES] = cache


@callback
def async_keep_capabilities(hass: HomeAssistant, entity_ids: Iterable[str]) -> None:
    """Forget the capabilities of all lights except these."""
    if (cache := hass.data.get(DATA_CAPABILITIES)) is not None:
        cache.async_keep_only(entity_ids)


def _capabilities(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """The capability attributes a state reports (empty values left out)."""
    result: dict[str, Any] = {}
    if modes := attributes.get(ATTR_SUPPORTED_COLOR_MODES):
        result[ATTR_SUPPORTED_COLOR_MODES] = sorted(str(mode) for mode in modes)
    for key in (ATTR_MIN_COLOR_TEMP_KELVIN, ATTR_MAX_COLOR_TEMP_KELVIN):
        if (value := attributes.get(key)) is not None:
            result[key] = int(value)
    if features := int(attributes.get(ATTR_SUPPORTED_FEATURES) or 0):
        result[ATTR_SUPPORTED_FEATURES] = features
    if effects := attributes.get(ATTR_EFFECT_LIST):
        result[ATTR_EFFECT_LIST] = list(effects)
    return result


def _combine(remembered: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Current values win; color modes, features and effects are added up."""
    combined = {**remembered, **current}
    if modes := set(remembered.get(ATTR_SUPPORTED_COLOR_MODES, [])) | set(
        current.get(ATTR_SUPPORTED_COLOR_MODES, [])
    ):
        combined[ATTR_SUPPORTED_COLOR_MODES] = sorted(modes)
    if features := remembered.get(ATTR_SUPPORTED_FEATURES, 0) | current.get(
        ATTR_SUPPORTED_FEATURES, 0
    ):
        combined[ATTR_SUPPORTED_FEATURES] = features
    if effects := list(
        dict.fromkeys([*remembered.get(ATTR_EFFECT_LIST, []), *current.get(ATTR_EFFECT_LIST, [])])
    ):
        combined[ATTR_EFFECT_LIST] = effects
    return combined


@callback
def member_capabilities(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    """Capabilities of a member light (empty if none are known).

    Keys: supported_color_modes (list), min/max_color_temp_kelvin,
    supported_features, effect_list; missing if unknown.
    """
    state = hass.states.get(entity_id)
    current = _capabilities(state.attributes) if state is not None else {}
    cache: CapabilityCache | None = hass.data.get(DATA_CAPABILITIES)
    if cache is None:
        return current
    combined = _combine(cache.get(entity_id), current)
    if state is not None and state.state == STATE_ON:
        cache.async_remember(entity_id, combined)
    return combined
