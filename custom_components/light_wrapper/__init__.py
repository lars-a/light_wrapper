"""Light Wrapper: combines several lights into one light entity with defaults.

There is exactly one config entry. Its options are the global settings
(default transitions for all groups); each light group is a subentry.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_ENTITIES, Platform
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_APPLY_WHEN_ON,
    DEFAULT_APPLY_WHEN_ON,
    DEFAULT_KEYS,
    MAX_TRANSITION,
    MIN_TRANSITION,
    SUBENTRY_TYPE_GROUP,
    TRANSITION_KEYS,
    TRANSITION_STEP,
)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.NUMBER, Platform.SWITCH]


@dataclass
class LightWrapperData:
    """Settings of a light group or the global settings."""

    entities: list[str]
    defaults: dict[str, float]
    apply_when_on: bool = DEFAULT_APPLY_WHEN_ON
    _listeners: list[Callable[[], None]] = field(default_factory=list)

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Register a callback that is called when the settings change."""
        self._listeners.append(update_callback)

        @callback
        def _remove() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return _remove

    @callback
    def async_set_settings(self, defaults: dict[str, float], apply_when_on: bool) -> None:
        """Replace the defaults and the behavior when on, then notify listeners."""
        self.defaults = defaults
        self.apply_when_on = apply_when_on
        for update_callback in list(self._listeners):
            update_callback()


@dataclass
class LightWrapperRuntime:
    """Runtime data of the config entry."""

    global_settings: LightWrapperData
    groups: dict[str, LightWrapperData]  # subentry_id -> settings
    structure: Hashable


type LightWrapperConfigEntry = ConfigEntry[LightWrapperRuntime]


def normalize_default(key: str, value: Any) -> float | int:
    """Convert a default value to its stored format.

    Transitions: seconds, rounded to 0.1 s and limited to 0–10 s.
    Everything else: integer.
    """
    if key in TRANSITION_KEYS:
        seconds = round(round(float(value) / TRANSITION_STEP) * TRANSITION_STEP, 1)
        return max(MIN_TRANSITION, min(MAX_TRANSITION, seconds))
    return int(round(value))


def defaults_from_options(options: Mapping[str, Any]) -> dict[str, float]:
    """Take over only the defaults that are set."""
    return {
        key: normalize_default(key, options[key])
        for key in DEFAULT_KEYS
        if options.get(key) is not None
    }


def apply_when_on_from_options(options: Mapping[str, Any]) -> bool:
    """The "apply when on" switch; if it is missing, the default (on) applies."""
    return bool(options.get(CONF_APPLY_WHEN_ON, DEFAULT_APPLY_WHEN_ON))


def group_subentries(entry: ConfigEntry) -> dict[str, ConfigSubentry]:
    """All light groups of the entry."""
    return {
        subentry_id: subentry
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_GROUP
    }


def _group_settings(subentry: ConfigSubentry) -> LightWrapperData:
    return LightWrapperData(
        entities=list(subentry.data.get(CONF_ENTITIES, [])),
        defaults=defaults_from_options(subentry.data),
        apply_when_on=apply_when_on_from_options(subentry.data),
    )


def _structure(entry: ConfigEntry) -> Hashable:
    """Everything that requires a reload when it changes.

    That is: which groups exist, their names and lights, and which defaults
    are enabled (the number entities depend on that).
    Pure value changes are not part of it.
    """
    return (
        frozenset(defaults_from_options(entry.options)),
        tuple(
            (
                subentry_id,
                subentry.title,
                tuple(subentry.data.get(CONF_ENTITIES, [])),
                frozenset(defaults_from_options(subentry.data)),
            )
            for subentry_id, subentry in group_subentries(entry).items()
        ),
    )


async def async_setup_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Set up the config entry."""
    entry.runtime_data = LightWrapperRuntime(
        global_settings=LightWrapperData(entities=[], defaults=defaults_from_options(entry.options)),
        groups={
            subentry_id: _group_settings(subentry)
            for subentry_id, subentry in group_subentries(entry).items()
        },
        structure=_structure(entry),
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> None:
    """React to changed settings.

    If only values change (e.g. via the number entities or the "apply when on"
    switch), nothing is reloaded, so the light entities do not disappear briefly.
    If a group is added, removed or renamed, its lights change, or a default is
    enabled or disabled, the entry is reloaded.
    """
    runtime = entry.runtime_data
    if _structure(entry) != runtime.structure:
        await hass.config_entries.async_reload(entry.entry_id)
        return

    runtime.global_settings.async_set_settings(
        defaults_from_options(entry.options), DEFAULT_APPLY_WHEN_ON
    )
    for subentry_id, subentry in group_subentries(entry).items():
        runtime.groups[subentry_id].async_set_settings(
            defaults_from_options(subentry.data), apply_when_on_from_options(subentry.data)
        )


async def async_unload_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
