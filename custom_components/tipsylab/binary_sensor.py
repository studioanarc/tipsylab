"""Binäre Sensoren: im Fenster, Messung empfohlen, Flaschengrenze, Sicherheitsabstand, Messflasche,
Quelle stumm, Akku schwach. Handlungen in der Sprache des Servers (texts.py)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TipsylabConfigEntry
from .const import BATTERY_LOW_PCT, MODES, SILENT_AFTER_H
from .coordinator import BatchResult
from .entity import TipsylabEntity
from .texts import say

ALL_MODES = tuple(MODES)


@dataclass(frozen=True, kw_only=True)
class TipsylabBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[BatchResult], bool | None]
    attrs_fn: Callable[[BatchResult], dict[str, Any]] | None = None
    modes: tuple[str, ...] = ("petnat", "still")


BINARY_SENSORS: tuple[TipsylabBinaryDescription, ...] = (
    TipsylabBinaryDescription(
        key="im_fenster",
        translation_key="im_fenster",
        icon="mdi:bottle-wine-outline",
        value_fn=lambda r: r.estimate.display_state == "now" if r.estimate else None,
    ),
    TipsylabBinaryDescription(
        key="messung_empfohlen",
        translation_key="messung_empfohlen",
        icon="mdi:test-tube",
        value_fn=lambda r: r.estimate.measurement_recommended if r.estimate else None,
        attrs_fn=lambda r: {
            "fenster_h": round(r.estimate.window_h, 1) if r.estimate and r.estimate.window_h is not None else None,
            "fenster_nach_messung_h": round(r.estimate.window_h_measured, 1)
            if r.estimate and r.estimate.window_h_measured is not None
            else None,
        },
    ),
    TipsylabBinaryDescription(
        key="flaschengrenze",
        translation_key="flaschengrenze",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda r: (not r.estimate.limit_ok) if r.estimate else None,
        modes=("petnat",),
    ),
    TipsylabBinaryDescription(
        key="sicherheitsabstand",
        translation_key="sicherheitsabstand",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda r: (not r.charmat.margin_ok) if r.charmat else None,
        modes=("charmat",),
    ),
    TipsylabBinaryDescription(
        key="flaschendruck_alarm",
        translation_key="flaschendruck_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda r: bool(r.bottle and r.bottle.alarm),
        attrs_fn=lambda r: {
            "handlung": say(f"bottle_{r.bottle.state}", r.lang) if r.bottle and r.bottle.alarm else "",
            "stufe": r.bottle.state if r.bottle else None,
        },
        modes=("petnat",),
    ),
    TipsylabBinaryDescription(
        key="quelle_stumm",
        translation_key="quelle_stumm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda r: bool(r.silent),
        attrs_fn=lambda r: {
            "quellen": r.silent,
            "handlung": say(
                "silent", r.lang, hours=SILENT_AFTER_H, sources=", ".join(say(f"source_{c}", r.lang) for c in r.silent)
            )
            if r.silent
            else "",
        },
        modes=ALL_MODES,
    ),
    TipsylabBinaryDescription(
        key="akku_schwach",
        translation_key="akku_schwach",
        device_class=BinarySensorDeviceClass.BATTERY,
        value_fn=lambda r: r.battery is not None and r.battery[1] <= BATTERY_LOW_PCT,
        attrs_fn=lambda r: {
            "geraet": r.battery[0] if r.battery else None,
            "akku": r.battery[1] if r.battery else None,
            "handlung": say("battery", r.lang, device=r.battery[0], pct=round(r.battery[1]))
            if r.battery and r.battery[1] <= BATTERY_LOW_PCT
            else "",
        },
        modes=ALL_MODES,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: TipsylabConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        TipsylabBinarySensor(coordinator, desc) for desc in BINARY_SENSORS if coordinator.mode in desc.modes
    )


class TipsylabBinarySensor(TipsylabEntity, BinarySensorEntity):
    entity_description: TipsylabBinaryDescription

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None or self.coordinator.data is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
