"""Light Wrapper: combines several lights into one light entity with defaults.

There are two config entries: "Global settings" (its options are the default
transitions for all groups) and "Light groups" (each light group is a subentry).
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_SYSTEM,
    ConfigEntry,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.const import CONF_ENTITIES, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_APPLY_WHEN_ON,
    CONF_ENTRY_TYPE,
    CONF_HIDE_MEMBERS,
    CONF_ON_WHEN_ALL_ON,
    DEFAULT_APPLY_WHEN_ON,
    DEFAULT_ON_WHEN_ALL_ON,
    DEFAULT_KEYS,
    DOMAIN,
    ENTRY_TYPE_GLOBAL,
    IMPORT_OPTIONS,
    IMPORT_TITLE,
    MAX_TRANSITION,
    MIN_TRANSITION,
    SUBENTRY_TYPE_GROUP,
    TRANSITION_KEYS,
    TRANSITION_STEP,
)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.NUMBER, Platform.SWITCH]
# The "Global settings" entry only has number entities
GLOBAL_PLATFORMS: list[Platform] = [Platform.NUMBER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class LightWrapperData:
    """Settings of a light group or the global settings."""

    entities: list[str]
    defaults: dict[str, float]
    apply_when_on: bool = DEFAULT_APPLY_WHEN_ON
    on_when_all_on: bool = DEFAULT_ON_WHEN_ALL_ON
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
    def async_set_settings(
        self,
        defaults: dict[str, float],
        apply_when_on: bool = DEFAULT_APPLY_WHEN_ON,
        on_when_all_on: bool = DEFAULT_ON_WHEN_ALL_ON,
    ) -> None:
        """Replace the defaults and the behavior when on, then notify listeners."""
        self.defaults = defaults
        self.apply_when_on = apply_when_on
        self.on_when_all_on = on_when_all_on
        for update_callback in list(self._listeners):
            update_callback()


@dataclass
class LightWrapperRuntime:
    """Runtime data of a config entry.

    Global entry: global_settings holds the settings, groups is empty.
    Groups entry: groups holds one entry per light group, global_settings is unused.
    """

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


def on_when_all_on_from_options(options: Mapping[str, Any]) -> bool:
    """The "on only when all are on" setting; if it is missing, the default (off) applies."""
    return bool(options.get(CONF_ON_WHEN_ALL_ON, DEFAULT_ON_WHEN_ALL_ON))


def apply_when_on_from_options(options: Mapping[str, Any]) -> bool:
    """The "apply when on" switch; if it is missing, the default (on) applies."""
    return bool(options.get(CONF_APPLY_WHEN_ON, DEFAULT_APPLY_WHEN_ON))


def is_global(entry: ConfigEntry) -> bool:
    """True for the "Global settings" entry."""
    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_GLOBAL


@callback
def global_defaults(hass: HomeAssistant) -> dict[str, float]:
    """Defaults of the loaded "Global settings" entry (empty if there is none)."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if is_global(entry) and entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data.global_settings.defaults
    return {}


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
        on_when_all_on=on_when_all_on_from_options(subentry.data),
    )


def _members(entry: ConfigEntry, *, hidden_only: bool = False) -> set[str]:
    """Member lights of all groups (only of groups that hide them, if hidden_only)."""
    return {
        entity_id
        for subentry in group_subentries(entry).values()
        if not hidden_only or subentry.data.get(CONF_HIDE_MEMBERS)
        for entity_id in subentry.data.get(CONF_ENTITIES, [])
    }


@callback
def _async_update_hidden_members(
    hass: HomeAssistant, hide: set[str], candidates: set[str]
) -> None:
    """Hide the lights in `hide`, show the other candidates again.

    Only entities hidden by an integration are shown again; lights the user
    hid themselves stay hidden. Lights without a registry entry are skipped.
    """
    registry = er.async_get(hass)
    for entity_id in candidates | hide:
        if (registry_entry := registry.async_get(entity_id)) is None:
            continue
        if entity_id in hide:
            if registry_entry.hidden_by is None:
                registry.async_update_entity(
                    entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
                )
        elif registry_entry.hidden_by is er.RegistryEntryHider.INTEGRATION:
            registry.async_update_entity(entity_id, hidden_by=None)


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Replace a global entry created by 0.7.x once.

    Up to 0.7.1 the global entry was created with SOURCE_SYSTEM, for which the UI
    offers no "Delete". The source cannot be changed afterwards, so the entry is
    replaced by a new one (same title and options) created with SOURCE_IMPORT.
    """
    for entry in hass.config_entries.async_entries(DOMAIN):
        if not (is_global(entry) and entry.source == SOURCE_SYSTEM):
            continue
        data = {
            CONF_ENTRY_TYPE: ENTRY_TYPE_GLOBAL,
            IMPORT_TITLE: entry.title,
            IMPORT_OPTIONS: dict(entry.options),
        }
        await hass.config_entries.async_remove(entry.entry_id)
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=data
            )
        )
    return True


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
    if not is_global(entry):
        _async_update_hidden_members(hass, _members(entry, hidden_only=True), set())
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, _platforms(entry))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> None:
    """React to changed settings.

    If only values change (e.g. via the number entities or the "apply when on"
    switch), nothing is reloaded, so the light entities do not disappear briefly.
    If a group is added, removed or renamed, its lights change, or a default is
    enabled or disabled, the entry is reloaded.
    """
    runtime = entry.runtime_data
    if not is_global(entry):
        # Lights that left a group (or whose group was removed) are candidates too
        previous = {eid for group in runtime.groups.values() for eid in group.entities}
        _async_update_hidden_members(
            hass, _members(entry, hidden_only=True), previous | _members(entry)
        )

    if _structure(entry) != runtime.structure:
        await hass.config_entries.async_reload(entry.entry_id)
        return

    runtime.global_settings.async_set_settings(
        defaults_from_options(entry.options), DEFAULT_APPLY_WHEN_ON
    )
    for subentry_id, subentry in group_subentries(entry).items():
        runtime.groups[subentry_id].async_set_settings(
            defaults_from_options(subentry.data),
            apply_when_on_from_options(subentry.data),
            on_when_all_on_from_options(subentry.data),
        )


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Show the member lights again when the groups entry is deleted."""
    if not is_global(entry):
        _async_update_hidden_members(hass, set(), _members(entry))


async def async_unload_entry(hass: HomeAssistant, entry: LightWrapperConfigEntry) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _platforms(entry))


def _platforms(entry: ConfigEntry) -> list[Platform]:
    return GLOBAL_PLATFORMS if is_global(entry) else PLATFORMS
