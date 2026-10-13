"""TIPSYLAB: Abfüllfenster für Pet Nat, Charmat-Druckregelung und Gärüberwachung für Naturwein."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ENTRY_ID,
    BOTTLES,
    DENSITY_UNITS,
    DOMAIN,
    EVENT_KINDS,
    MEASUREMENT_KINDS,
    OPT_BOTTLE,
    OPT_DRY_SUGAR,
    OPT_FILLING_LOSS,
    OPT_MALIC,
    OPT_MALO,
    OPT_PRV_BAR,
    OPT_Q10,
    OPT_TARGET_BAR,
    OPT_TEMP_LATE,
    OPT_TEMP_START,
    OPT_TEMP_SWITCH_SUGAR,
    PANEL_URL,
    SERVICE_ADD_EVENT,
    SERVICE_ADD_MEASUREMENT,
    SERVICE_REMOVE_ENTRY,
    SERVICE_UPDATE_SETTINGS,
    STATIC_URL,
    VERSION,
)
from .coordinator import TipsylabCoordinator
from .house import House
from .websocket import async_register_websocket

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type TipsylabConfigEntry = ConfigEntry[TipsylabCoordinator]

MEASUREMENT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Required("kind"): vol.In(MEASUREMENT_KINDS),
        vol.Required("value"): vol.Coerce(float),
        vol.Optional("value2"): vol.Coerce(float),
        vol.Optional("unit"): vol.In(DENSITY_UNITS),
        vol.Optional("temperature"): vol.Coerce(float),
        vol.Optional("time"): cv.datetime,
        vol.Optional("note"): cv.string,
    }
)
EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Required("kind"): vol.In(EVENT_KINDS),
        vol.Optional("value"): vol.Coerce(float),
        vol.Optional("note"): cv.string,
    }
)
REMOVE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Required("kind"): cv.string,
        vol.Required("time"): cv.string,
    }
)
SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Optional(OPT_TARGET_BAR): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=6.0)),
        vol.Optional(OPT_BOTTLE): vol.In(BOTTLES),
        vol.Optional(OPT_MALO): cv.boolean,
        vol.Optional(OPT_MALIC): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        vol.Optional(OPT_Q10): vol.All(vol.Coerce(float), vol.Range(min=1.2, max=4.0)),
        vol.Optional(OPT_DRY_SUGAR): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        vol.Optional(OPT_TEMP_START): vol.Any(None, vol.Coerce(float)),
        vol.Optional(OPT_TEMP_LATE): vol.Any(None, vol.Coerce(float)),
        vol.Optional(OPT_TEMP_SWITCH_SUGAR): vol.Any(None, vol.Coerce(float)),
        vol.Optional(OPT_FILLING_LOSS): vol.All(vol.Coerce(float), vol.Range(min=0, max=0.5)),
        vol.Optional(OPT_PRV_BAR): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=12)),
        vol.Optional("volume_l"): vol.All(vol.Coerce(float), vol.Range(min=1, max=100000)),
    }
)


def _coordinator(hass: HomeAssistant, entry_id: str) -> TipsylabCoordinator:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or not hasattr(entry, "runtime_data"):
        raise ServiceValidationError(f"Kein TIPSYLAB-Ansatz mit der ID {entry_id}")
    return entry.runtime_data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Hauswerte laden, Services, WebSocket und Panel einmalig anmelden."""
    house = House(hass)
    await house.async_load()
    hass.data.setdefault(DOMAIN, {})["house"] = house

    async def add_measurement(call: ServiceCall) -> None:
        data = dict(call.data)
        coord = _coordinator(hass, data.pop(ATTR_ENTRY_ID))
        await coord.async_add_measurement(**data)

    async def add_event(call: ServiceCall) -> None:
        data = dict(call.data)
        coord = _coordinator(hass, data.pop(ATTR_ENTRY_ID))
        await coord.async_add_event(**data)

    async def update_settings(call: ServiceCall) -> None:
        data = dict(call.data)
        coord = _coordinator(hass, data.pop(ATTR_ENTRY_ID))
        await coord.async_update_settings(data)

    async def remove_entry(call: ServiceCall) -> None:
        coord = _coordinator(hass, call.data[ATTR_ENTRY_ID])
        await coord.async_remove_entry(call.data["kind"], call.data["time"])

    hass.services.async_register(DOMAIN, SERVICE_ADD_MEASUREMENT, add_measurement, schema=MEASUREMENT_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADD_EVENT, add_event, schema=EVENT_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_SETTINGS, update_settings, schema=SETTINGS_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_ENTRY, remove_entry, schema=REMOVE_SCHEMA)
    async_register_websocket(hass)
    await _async_register_panel(hass)
    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Panel „TIPSYLAB“ in der Seitenleiste, nur wenn Frontend und HTTP laufen."""
    if "frontend" not in hass.config.components or getattr(hass, "http", None) is None:
        _LOGGER.debug("Frontend nicht geladen, Panel wird nicht angemeldet")
        return
    from homeassistant.components import panel_custom
    from homeassistant.components.http import StaticPathConfig

    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths([StaticPathConfig(STATIC_URL, str(frontend_dir), False)])
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name="tipsylab-panel",
        sidebar_title="TIPSYLAB",
        sidebar_icon="mdi:glass-wine",
        module_url=f"{STATIC_URL}/tipsylab-panel.js?v={VERSION}",
        config={"static": STATIC_URL},
        require_admin=False,
    )


async def async_setup_entry(hass: HomeAssistant, entry: TipsylabConfigEntry) -> bool:
    coordinator = TipsylabCoordinator(hass, entry)
    await coordinator.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TipsylabConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_unload()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Gespeicherte Messungen eines gelöschten Ansatzes entfernen."""
    from homeassistant.helpers.storage import Store

    from .const import STORAGE_VERSION

    store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
    await store.async_remove()
