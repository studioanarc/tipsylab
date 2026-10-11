"""WebSocket-Befehle für das Panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DENSITY_UNITS, DOMAIN, MEASUREMENT_KINDS


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_batches)
    websocket_api.async_register_command(hass, ws_preview)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/batches"})
@callback
def ws_batches(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Alle Ansätze mit Schätzung, Verlauf und Einstellungen."""
    batches = [
        entry.runtime_data.panel_data()
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if getattr(entry, "runtime_data", None) is not None
    ]
    connection.send_result(msg["id"], {"batches": batches})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/preview",
        vol.Required("entry_id"): str,
        vol.Required("kind"): vol.In(MEASUREMENT_KINDS),
        vol.Required("value"): vol.Coerce(float),
        vol.Optional("value2"): vol.Coerce(float),
        vol.Optional("unit"): vol.In(DENSITY_UNITS),
    }
)
@websocket_api.async_response
async def ws_preview(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Was eine Messung ändern würde, bevor sie gespeichert wird."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    coordinator = getattr(entry, "runtime_data", None) if entry and entry.domain == DOMAIN else None
    if coordinator is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Ansatz nicht gefunden")
        return
    result = await coordinator.async_preview(msg["kind"], msg["value"], msg.get("value2"), msg.get("unit"))
    connection.send_result(msg["id"], result)
