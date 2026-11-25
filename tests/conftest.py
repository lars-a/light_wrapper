"""Shared fixtures and helpers for the tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigSubentryData

from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.light_wrapper import LightWrapperData, group_subentries
from custom_components.light_wrapper.const import DOMAIN, ENTRY_TITLE, SUBENTRY_TYPE_GROUP
from custom_components.light_wrapper.light import LightWrapperLight

WRAPPER_ID = "light.wohnzimmer"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom integrations in all tests."""
    return


def set_member(
    hass: HomeAssistant,
    entity_id: str,
    state: str = "off",
    *,
    modes: tuple[str, ...] = ("color_temp",),
    color_mode: str | None = None,
    brightness: int | None = None,
    kelvin: int | None = None,
    min_kelvin: int = 2200,
    max_kelvin: int = 6500,
    features: int = 0,
    **extra: Any,
) -> None:
    """Set the state of a (simulated) physical light."""
    attrs: dict[str, Any] = {"supported_color_modes": list(modes), "supported_features": features}
    if "color_temp" in modes:
        attrs["min_color_temp_kelvin"] = min_kelvin
        attrs["max_color_temp_kelvin"] = max_kelvin
    if state == "on":
        attrs["color_mode"] = color_mode or modes[0]
        if brightness is not None:
            attrs["brightness"] = brightness
        if kelvin is not None:
            attrs["color_temp_kelvin"] = kelvin
    attrs.update(extra)
    hass.states.async_set(entity_id, state, attrs)


async def setup_integration(
    hass: HomeAssistant,
    groups: dict[str, dict[str, Any]] | None = None,
    global_options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Load the "Light Wrapper" entry with global settings and light groups.

    groups: {name: group data}
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=ENTRY_TITLE,
        data={},
        options=global_options or {},
        subentries_data=[
            ConfigSubentryData(
                data=data, subentry_type=SUBENTRY_TYPE_GROUP, title=title, unique_id=None
            )
            for title, data in (groups or {}).items()
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def setup_wrapper(
    hass: HomeAssistant,
    entities: list[str],
    *,
    global_options: dict[str, Any] | None = None,
    **defaults: float | bool,
) -> MockConfigEntry:
    """Create and load a light group 'Wohnzimmer'."""
    return await setup_integration(
        hass,
        groups={"Wohnzimmer": {CONF_ENTITIES: entities, **defaults}},
        global_options=global_options,
    )


async def setup_global(hass: HomeAssistant, **options: float) -> MockConfigEntry:
    """Load only the entry with global settings (no groups)."""
    return await setup_integration(hass, global_options=options)


def group_id(entry: MockConfigEntry) -> str:
    """subentry_id of the only light group."""
    (subentry_id,) = group_subentries(entry)
    return subentry_id


def group_data(entry: MockConfigEntry) -> dict[str, Any]:
    """Stored data of the only light group."""
    return dict(entry.subentries[group_id(entry)].data)


def group_settings(entry: MockConfigEntry) -> LightWrapperData:
    """Runtime settings of the only light group."""
    return entry.runtime_data.groups[group_id(entry)]


def number_entity_id(hass: HomeAssistant, entry: MockConfigEntry, option_key: str) -> str | None:
    """Entity ID of a number entity of the only light group."""
    return er.async_get(hass).async_get_entity_id(
        "number", DOMAIN, f"{group_id(entry)}_{option_key}"
    )


def global_number_entity_id(
    hass: HomeAssistant, entry: MockConfigEntry, option_key: str
) -> str | None:
    """Entity ID of a global number entity."""
    return er.async_get(hass).async_get_entity_id(
        "number", DOMAIN, f"{entry.entry_id}_{option_key}"
    )


def switch_entity_id(hass: HomeAssistant, entry: MockConfigEntry, option_key: str) -> str | None:
    """Entity ID of a switch entity of the only light group."""
    return er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{group_id(entry)}_{option_key}"
    )


@pytest.fixture
def member_calls():
    """Intercept service calls to the members instead of executing them.

    Result: a mock whose calls contain (self, service, entity_ids, data).
    """
    with patch.object(LightWrapperLight, "_async_call", autospec=True) as mock:
        yield mock


def calls_by_entity(mock) -> dict[str, tuple[str, dict[str, Any]]]:
    """Calls per member: {entity_id: (service, data)}."""
    result: dict[str, tuple[str, dict[str, Any]]] = {}
    for call in mock.call_args_list:
        _self, service, entity_ids, data = call.args
        for entity_id in entity_ids:
            assert entity_id not in result, f"{entity_id} was called more than once"
            result[entity_id] = (service, dict(data))
    return result
