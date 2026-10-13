"""Sensoren eines Ansatzes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TipsylabConfigEntry
from .const import STATUS_OPTIONS
from .coordinator import BatchResult
from .core.display import format_dub
from .entity import TipsylabEntity

G_L = "g/L"
G_L_DAY = "g/L/d"


@dataclass(frozen=True, kw_only=True)
class TipsylabSensorDescription(SensorEntityDescription):
    value_fn: Callable[[BatchResult], Any]
    attrs_fn: Callable[[BatchResult], dict[str, Any]] | None = None
    modes: tuple[str, ...] = ("petnat", "still")


def _est(attr: str, digits: int | None = None) -> Callable[[BatchResult], Any]:
    def get(res: BatchResult) -> Any:
        if res.estimate is None:
            return None
        value = getattr(res.estimate, attr)
        return round(value, digits) if digits is not None and isinstance(value, float) else value

    return get


def _charm(attr: str, digits: int = 2) -> Callable[[BatchResult], Any]:
    def get(res: BatchResult) -> Any:
        value = getattr(res.charmat, attr, None) if res.charmat else None
        return round(value, digits) if isinstance(value, float) else value

    return get


SENSORS: tuple[TipsylabSensorDescription, ...] = (
    TipsylabSensorDescription(
        key="restzucker",
        translation_key="restzucker",
        native_unit_of_measurement=G_L,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:cube-outline",
        value_fn=_est("sugar", 2),
        attrs_fn=lambda r: {
            "unsicherheit": round(r.estimate.sigma, 2) if r.estimate and r.estimate.sigma else None,
            "spindel_versatz": r.estimate.spindle_offset if r.estimate else None,
            "hinweise": r.estimate.notes if r.estimate else [],
        },
    ),
    TipsylabSensorDescription(
        key="alkohol",
        translation_key="alkohol",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:glass-wine",
        value_fn=_est("abv", 2),
    ),
    TipsylabSensorDescription(
        key="alkohol_flasche",
        translation_key="alkohol_flasche",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:bottle-wine",
        value_fn=_est("abv_end", 2),
        attrs_fn=lambda r: {
            "unsicherheit": round(r.estimate.abv_end_sigma, 2) if r.estimate and r.estimate.abv_end_sigma else None,
            "etikett": r.estimate.abv_label if r.estimate else None,
            "etikett_sicher": r.estimate.abv_label_ok if r.estimate else None,
            "messpaare": r.estimate.abv_pairs if r.estimate else 0,
            "laborwerte": r.estimate.abv_labs if r.estimate else 0,
        },
    ),
    TipsylabSensorDescription(
        key="gaergeschwindigkeit",
        translation_key="gaergeschwindigkeit",
        native_unit_of_measurement=G_L_DAY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:speedometer",
        value_fn=_est("rate_g_l_day", 2),
    ),
    TipsylabSensorDescription(
        key="zielzucker",
        translation_key="zielzucker",
        native_unit_of_measurement=G_L,
        suggested_display_precision=1,
        icon="mdi:bullseye-arrow",
        value_fn=_est("target_sugar", 2),
    ),
    TipsylabSensorDescription(
        key="dub",
        translation_key="dub",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        icon="mdi:timer-sand",
        value_fn=_est("dub_hours", 1),
        attrs_fn=lambda r: {
            "anzeige": format_dub(r.estimate.dub_hours if r.estimate else None),
            "farbe": r.estimate.display_state if r.estimate else "none",
        },
    ),
    TipsylabSensorDescription(
        key="abfuellen",
        translation_key="abfuellen",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:bottle-wine",
        value_fn=_est("best"),
    ),
    TipsylabSensorDescription(
        key="fenster_beginn",
        translation_key="fenster_beginn",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_est("start"),
    ),
    TipsylabSensorDescription(
        key="fenster_ende",
        translation_key="fenster_ende",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_est("end"),
    ),
    TipsylabSensorDescription(
        key="druck_jetzt_10",
        translation_key="druck_jetzt_10",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        value_fn=_est("p_now_10", 2),
        modes=("petnat",),
    ),
    TipsylabSensorDescription(
        key="druck_jetzt_20",
        translation_key="druck_jetzt_20",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=1,
        value_fn=_est("p_now_20", 2),
        modes=("petnat",),
    ),
    TipsylabSensorDescription(
        key="solltemperatur",
        translation_key="solltemperatur",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=_est("planned_temp", 1),
    ),
    TipsylabSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_OPTIONS,
        icon="mdi:list-status",
        value_fn=lambda r: r.estimate.status if r.estimate else ("charmat" if r.charmat else "waiting"),
        modes=("petnat", "still", "charmat"),
    ),
    TipsylabSensorDescription(
        key="tank_sollwert",
        translation_key="tank_sollwert",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=2,
        value_fn=_charm("setpoint"),
        attrs_fn=lambda r: {"tabelle": r.charmat.table if r.charmat else {}},
        modes=("charmat",),
    ),
    TipsylabSensorDescription(
        key="co2_ziel",
        translation_key="co2_ziel",
        native_unit_of_measurement=G_L,
        suggested_display_precision=2,
        icon="mdi:molecule-co2",
        value_fn=_charm("co2_target"),
        modes=("charmat",),
    ),
    TipsylabSensorDescription(
        key="co2_geloest",
        translation_key="co2_geloest",
        native_unit_of_measurement=G_L,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:molecule-co2",
        value_fn=_charm("dissolved"),
        modes=("charmat",),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: TipsylabConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        TipsylabSensor(coordinator, desc) for desc in SENSORS if coordinator.mode in desc.modes
    )


class TipsylabSensor(TipsylabEntity, SensorEntity):
    entity_description: TipsylabSensorDescription

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None or self.coordinator.data is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
