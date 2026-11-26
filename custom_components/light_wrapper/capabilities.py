"""Remember the capabilities of member lights.

Some lights only report their capabilities (color modes, color temperature
range, features, effects) while they are on. While such a light is off, the
group would not know that it supports color temperature, so the default color
temperature or transition would not be sent when turning it on.

While a member is on, its reported capabilities are taken as they are and
remembered (stored across restarts). While it is off or unavailable, the
remembered capabilities fill in what its state lacks.
"""

from __future__ import annotations

from collections.abc import Mapping
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
    """Last capabilities seen per member light while it was on."""

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
        self._store.async_delay_save(lambda: self._data, SAVE_DELAY)


async def async_setup_capabilities(hass: HomeAssistant) -> None:
    """Load the remembered capabilities (once per start)."""
    if DATA_CAPABILITIES in hass.data:
        return
    cache = CapabilityCache(hass)
    await cache.async_load()
    hass.data[DATA_CAPABILITIES] = cache


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
    if state is not None and state.state == STATE_ON:
        cache.async_remember(entity_id, current)
        return current

    remembered = cache.get(entity_id)
    merged = {**remembered, **current}
    modes = set(remembered.get(ATTR_SUPPORTED_COLOR_MODES, [])) | set(
        current.get(ATTR_SUPPORTED_COLOR_MODES, [])
    )
    if modes:
        merged[ATTR_SUPPORTED_COLOR_MODES] = sorted(modes)
    features = remembered.get(ATTR_SUPPORTED_FEATURES, 0) | current.get(
        ATTR_SUPPORTED_FEATURES, 0
    )
    if features:
        merged[ATTR_SUPPORTED_FEATURES] = features
    return merged
