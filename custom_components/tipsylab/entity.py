"""Gemeinsame Basis: ein Gerät „TIPSYLAB ‹Ansatz›“ je Config-Entry."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION
from .coordinator import TipsylabCoordinator


class TipsylabEntity(CoordinatorEntity[TipsylabCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TipsylabCoordinator, description: EntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"TIPSYLAB {entry.title}",
            manufacturer="Tipsy Wines",
            model={"petnat": "Pet Nat", "still": "Naturwein", "charmat": "Charmat"}.get(coordinator.mode, "Ansatz"),
            sw_version=VERSION,
        )
