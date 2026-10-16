"""Ein Ansatz in Home Assistant: Sensoren einsammeln, speichern, rechnen, ausgeben."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from functools import partial
import json
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    BUBBLE_TOPIC,
    CONF_BOTTLE_PRESSURE_ENTITY,
    CONF_BOTTLE_TEMP_ENTITY,
    CONF_BRIX0,
    CONF_BUBBLE_DEVICE,
    CONF_CO2_TARGET_ENTITY,
    CONF_GRAVITY_ENTITY,
    CONF_GRAVITY_UNIT,
    CONF_HEATER_HOST,
    CONF_MODE,
    CONF_PRESSURE_ENTITY,
    CONF_SG0,
    CONF_START,
    CONF_TEMP_ENTITY,
    CONF_VOLUME,
    CONF_WEIGHT_ENTITY,
    DEFAULT_OPTIONS,
    DISPLAY_TOPIC,
    DOMAIN,
    FORECAST_SNAPSHOT_MAX,
    FORECAST_SNAPSHOT_MINUTES,
    HEATER_KVS_KEY,
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
    READING_INTERVAL_S,
    READING_RETENTION_DAYS,
    STORAGE_VERSION,
)
from .core.bottling import BottleStatus, Bottling, bottle_status, observed_saturation
from .core.bubbles import BubbleAccumulator
from .core.charmat import CharmatStatus, charmat_status
from .core.composition import LAB_SIGMA_ABV, LAB_SIGMA_SUGAR, WineModel
from .core.display import display_payload, format_dub
from .core.feed import feed_entry
from .core.fermentation import SIGMA, Anchor, Estimate, Series, Settings, estimate
from .core.house import crossing_time, forecast_check
from .core.physics import FILL_MID, YIELD_CO2_SUGAR
from .core.units import brix_to_sg, to_sg
from .house import get_house

_LOGGER = logging.getLogger(__name__)

SERIES = ("gravity", "temps", "bubbles", "pressure", "weight", "bottle_pressure", "bottle_temp", "bubbles_saturated")
DISPLAY_REFRESH = timedelta(minutes=15)
HEATER_REFRESH = timedelta(minutes=30)
HISTORY_DAYS = {"gravity": 7, "temps": 7, "pressure": 3, "weight": 7}
WEIGHT_UNITS = {"kg": 1.0, "g": 0.001, "lb": 0.45359237}
HISTORY_POINTS = 300


@dataclass
class BatchResult:
    estimate: Estimate | None = None
    charmat: CharmatStatus | None = None
    bottle: BottleStatus | None = None  # Messflasche nach dem Abfüllen (Pet Nat)


def _bottle_dict(bottle: BottleStatus | None) -> dict[str, Any] | None:
    """Messflasche fürs Panel und fürs Archiv."""
    if bottle is None:
        return None
    return {
        "days": bottle.days,
        "expected_10": bottle.expected_10,
        "expected_20": bottle.expected_20,
        "expected_sigma_20": bottle.expected_sigma_20,
        "worst_20": bottle.worst_20,
        "limit": bottle.limit,
        "readings": [[_iso(r.t), r.p, r.temp_c, r.p20] for r in bottle.readings[-60:]],
        "progress": bottle.progress,
        "done": bottle.done,
        "state": bottle.state,
        "alarm": bottle.alarm,
        "action": bottle.action,
    }


def _iso(t: datetime) -> str:
    return dt_util.as_utc(t).isoformat()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    t = dt_util.parse_datetime(value)
    if t is None:
        return None
    return dt_util.as_utc(t) if t.tzinfo else t.replace(tzinfo=dt_util.UTC)


def _float_state(state: Any) -> float | None:
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


class TipsylabCoordinator(DataUpdateCoordinator[BatchResult]):
    """Rechnet einen Ansatz neu, sobald neue Werte kommen (höchstens alle 30 s) und alle 5 min."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            config_entry=entry,
            update_interval=timedelta(minutes=5),
            request_refresh_debouncer=Debouncer(hass, _LOGGER, cooldown=30, immediate=False),
        )
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.store_data: dict[str, Any] = {
            "measurements": [],
            "events": [],
            "readings": {name: [] for name in SERIES},
            "bubble_acc": {},
        }
        self._acc = BubbleAccumulator()
        self._unsubs: list[Any] = []
        self._last_display: tuple[str, datetime] | None = None
        self._last_heater: tuple[float, datetime] | None = None
        self._last_co2: float | None = None
        self._display_off_sent = False

    # --- Lebenszyklus ------------------------------------------------------------------------
    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.store_data.update(stored)
            for name in SERIES:
                self.store_data["readings"].setdefault(name, [])
        self._acc = BubbleAccumulator.from_dict(self.store_data.get("bubble_acc"))

        entities = [e for e in (self._conf(CONF_GRAVITY_ENTITY), self._conf(CONF_TEMP_ENTITY),
                                self._conf(CONF_PRESSURE_ENTITY), self._conf(CONF_WEIGHT_ENTITY),
                                self._conf(CONF_BOTTLE_PRESSURE_ENTITY), self._conf(CONF_BOTTLE_TEMP_ENTITY)) if e]
        if entities:
            self._unsubs.append(async_track_state_change_event(self.hass, entities, self._on_state))
            for entity_id in entities:  # aktuellen Wert gleich mitnehmen
                self._record_entity(entity_id, self.hass.states.get(entity_id))

        device = self._conf(CONF_BUBBLE_DEVICE)
        if device and "mqtt" in self.hass.config.components:
            try:
                self._unsubs.append(
                    await mqtt.async_subscribe(self.hass, BUBBLE_TOPIC.format(device=device), self._on_bubbles)
                )
            except HomeAssistantError as err:
                _LOGGER.warning("Blasenzähler %s: MQTT nicht verfügbar (%s)", device, err)

    async def async_unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self.store_data["bubble_acc"] = self._acc.to_dict()
        await self._store.async_save(self.store_data)

    def _save(self) -> None:
        self.store_data["bubble_acc"] = self._acc.to_dict()
        self._store.async_delay_save(lambda: self.store_data, 30)

    # --- Konfiguration -----------------------------------------------------------------------
    def _conf(self, key: str) -> Any:
        return self.config_entry.data.get(key)

    def _opt(self, key: str) -> Any:
        return self.config_entry.options.get(key, DEFAULT_OPTIONS.get(key))

    @property
    def mode(self) -> str:
        return self._conf(CONF_MODE) or "petnat"

    @property
    def start(self) -> datetime:
        return _parse(self._conf(CONF_START)) or dt_util.utcnow()

    @property
    def volume_l(self) -> float | None:
        return self.store_data.get("volume_l") or self._conf(CONF_VOLUME)

    def model(self) -> WineModel:
        house = get_house(self.hass)
        g = house.values["g_sugar_per_abv"].mean if house else None
        extra = {"g_sugar_per_abv": g} if g is not None else {}
        return WineModel.from_must(brix0=self._conf(CONF_BRIX0), sg0=self._conf(CONF_SG0), **extra)

    def _model_or_none(self) -> WineModel | None:
        """Charmat-Ansätze haben oft keinen Most-Wert; dann gibt es kein Zuckermodell."""
        try:
            return self.model()
        except ValueError:
            return None

    def settings(self) -> Settings:
        plan: list[tuple[float | None, float]] = []
        if self._opt(OPT_TEMP_START) is not None:
            plan.append((None, float(self._opt(OPT_TEMP_START))))
        if self._opt(OPT_TEMP_LATE) is not None and self._opt(OPT_TEMP_SWITCH_SUGAR) is not None:
            plan.append((float(self._opt(OPT_TEMP_SWITCH_SUGAR)), float(self._opt(OPT_TEMP_LATE))))
        malic = float(self._opt(OPT_MALIC) or 0.0)
        measured = [m for m in self.store_data["measurements"] if m["kind"] == "malic"]
        if measured:
            malic = float(measured[-1]["value"])
        house = get_house(self.hass)
        learned: dict[str, float] = {}
        if house:
            learned = {
                "saturation": house.values["saturation"].mean,
                "g_sugar_per_abv_sigma": house.values["g_sugar_per_abv"].sigma,
            }
            if bubbles := house.device("bubbles_per_g", self._conf(CONF_BUBBLE_DEVICE)):
                learned["bubbles_per_g"] = bubbles.mean
                learned["bubbles_per_g_rel"] = bubbles.sigma / bubbles.mean
            if spindle := house.device("spindle_offset", self._conf(CONF_GRAVITY_ENTITY)):
                learned["spindle_offset_prior"] = spindle.mean
                learned["spindle_offset_prior_sigma"] = spindle.sigma
        return Settings(
            **learned,
            mode=self.mode,
            target_bar_20c=float(self._opt(OPT_TARGET_BAR)),
            bottle=str(self._opt(OPT_BOTTLE)),
            malo_in_bottle=bool(self._opt(OPT_MALO)),
            malic_g_l=malic,
            q10=float(self._opt(OPT_Q10)),
            dry_sugar_g_l=float(self._opt(OPT_DRY_SUGAR)),
            volume_l=float(self.volume_l) if self.volume_l else None,
            temp_plan=tuple(plan),
        )

    # --- Eingang -----------------------------------------------------------------------------
    def _record(self, name: str, t: datetime, value: float) -> None:
        """Höchstens ein Wert je 5 min; der letzte Punkt trägt immer den jüngsten Wert mit seiner Zeit."""
        series: list[list[Any]] = self.store_data["readings"][name]
        if len(series) >= 2:
            prev_t = _parse(series[-2][0])
            if prev_t is not None and (t - prev_t).total_seconds() < READING_INTERVAL_S:
                series[-1] = [_iso(t), value]
                return
        series.append([_iso(t), value])
        cutoff = t - timedelta(days=READING_RETENTION_DAYS)
        while series and (_parse(series[0][0]) or t) < cutoff:
            series.pop(0)

    def _record_entity(self, entity_id: str, state: Any) -> bool:
        value = _float_state(state)
        if value is None:
            return False
        t = dt_util.as_utc(state.last_updated) if state is not None else dt_util.utcnow()
        if entity_id == self._conf(CONF_GRAVITY_ENTITY):
            unit = self._conf(CONF_GRAVITY_UNIT) or "sg"
            sg = brix_to_sg(value) if unit == "plato" else to_sg(value, unit)
            self._record("gravity", t, sg)
        elif entity_id == self._conf(CONF_TEMP_ENTITY):
            self._record("temps", t, value)
        elif entity_id == self._conf(CONF_PRESSURE_ENTITY):
            self._record("pressure", t, value)
        elif entity_id == self._conf(CONF_BOTTLE_PRESSURE_ENTITY):
            self._record("bottle_pressure", t, value)
        elif entity_id == self._conf(CONF_BOTTLE_TEMP_ENTITY):
            self._record("bottle_temp", t, value)
        elif entity_id == self._conf(CONF_WEIGHT_ENTITY):
            unit = (state.attributes.get("unit_of_measurement") or "kg") if state is not None else "kg"
            if unit not in WEIGHT_UNITS:
                _LOGGER.warning("Waage %s: Einheit %s unbekannt, erwartet kg oder g", entity_id, unit)
                return False
            self._record("weight", t, value * WEIGHT_UNITS[unit])
        else:
            return False
        return True

    @callback
    def _on_state(self, event: Event[EventStateChangedData]) -> None:
        if self._record_entity(event.data["entity_id"], event.data["new_state"]):
            self._save()
            self.hass.async_create_task(self.async_request_refresh())

    @callback
    def _on_bubbles(self, msg: Any) -> None:
        try:
            payload = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        if not isinstance(payload, dict):
            return
        self._acc.add(payload)
        now = dt_util.utcnow()
        self._record("bubbles", now, self._acc.total)
        if payload.get("saturated"):  # Zähler an der Grenze: zählt zu wenig (Phase 3)
            self._record("bubbles_saturated", now, 1.0)
        if not self._conf(CONF_TEMP_ENTITY) and isinstance(payload.get("temperature"), (int, float)):
            self._record("temps", now, float(payload["temperature"]))
        if not self._conf(CONF_WEIGHT_ENTITY) and isinstance(payload.get("weight_kg"), (int, float)):
            self._record("weight", now, float(payload["weight_kg"]))  # Gärbox mit Waage
        self._save()
        self.hass.async_create_task(self.async_request_refresh())

    # --- Messungen und Ereignisse ----------------------------------------------------------
    async def async_add_measurement(
        self,
        kind: str,
        value: float,
        value2: float | None = None,
        unit: str | None = None,
        temperature: float | None = None,
        time: datetime | None = None,
        note: str | None = None,
    ) -> None:
        entry = {"kind": kind, "value": float(value), "time": _iso(time or dt_util.utcnow())}
        if value2 is not None:
            entry["value2"] = float(value2)
        if unit:
            entry["unit"] = unit
        if temperature is not None:
            entry["temperature"] = float(temperature)
        if note:
            entry["note"] = note
        self._anchor(entry)  # prüft, ob sich die Messung auswerten lässt
        self.store_data["measurements"].append(entry)
        self.store_data["measurements"].sort(key=lambda m: m["time"])
        self._save()
        await self.async_refresh()

    async def async_add_event(self, kind: str, value: float | None = None, note: str | None = None) -> None:
        now = dt_util.utcnow()
        entry: dict[str, Any] = {"kind": kind, "time": _iso(now)}
        if value is not None:
            entry["value"] = float(value)
            if kind == "volume":
                self.store_data["volume_l"] = float(value)
        if note:
            entry["note"] = note
        if kind == "bottled":
            self.store_data["bottling"] = self._bottling_snapshot(now)
            self._display_off_sent = False
        self.store_data["events"].append(entry)
        self._save()
        await self.async_refresh()
        if kind == "closed":
            await self._archive(now)

    async def async_remove_entry(self, kind: str, time: str) -> None:
        """Eine Messung oder ein Ereignis löschen, etwa ein versehentliches „Abgefüllt“."""
        for key in ("measurements", "events"):
            items = self.store_data[key]
            keep = [x for x in items if not (x.get("kind") == kind and x.get("time") == time)]
            if len(keep) != len(items):
                self.store_data[key] = keep
                break
        else:
            raise HomeAssistantError(f"Kein Eintrag {kind} um {time}")
        if kind == "bottled" and not any(e["kind"] == "bottled" for e in self.store_data["events"]):
            self.store_data.pop("bottling", None)
        if kind == "closed":
            house = get_house(self.hass)
            if house:
                await house.async_drop(self.config_entry.entry_id)
                self._refresh_others()
        self._save()
        await self.async_refresh()

    @property
    def bottling(self) -> Bottling | None:
        data = self.store_data.get("bottling")
        return Bottling.from_dict(data) if data else None

    def _bottling_snapshot(self, now: datetime) -> dict[str, Any]:
        """Stand beim Abfüllen festhalten: Restzucker, Temperatur, Flasche, Nachkalkulation der Prognose."""
        est = self.data.estimate if self.data else None
        if self.mode == "charmat" or est is None or est.sugar is None:
            raise HomeAssistantError("Zum Abfüllen braucht es einen aktuellen Restzucker: erst messen, dann abfüllen.")
        settings = self.settings()
        temps = self._series("temps")
        temp = temps[-1][1] if temps and now - temps[-1][0] <= timedelta(hours=6) else FILL_MID.t_bottling_c
        bottling = Bottling(
            now, est.sugar, est.sigma or SIGMA["brix"], settings.bottle, settings.malic(), temp, settings.saturation
        )
        snap: dict[str, Any] = bottling.to_dict()
        snap["time"] = _iso(now)
        snap["target_sugar"] = est.target_sugar
        crossing = crossing_time(est.series, est.target_sugar) if est.target_sugar is not None else None
        if crossing is not None:
            snaps = [
                (_parse(s[0]), _parse(s[1]), _parse(s[2]), _parse(s[3]))
                for s in self.store_data.get("forecasts", [])
            ]
            snaps = [s for s in snaps if s[0] is not None and s[1] is not None]
            snap["crossing"] = _iso(crossing)
            snap["forecast_check"] = {str(h): v for h, v in forecast_check(snaps, crossing).items()}
        return snap

    def _refresh_others(self) -> None:
        """Hauswerte haben sich geändert: alle anderen Ansätze neu rechnen."""
        for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            coord = getattr(entry, "runtime_data", None)
            if coord is not None and coord is not self:
                self.hass.async_create_task(coord.async_request_refresh())

    def _observed_sugar_per_abv(self, anchors: list[Anchor]) -> list[float] | None:
        """Umrechnungsfaktor aus dem jüngsten Laborwert (Zucker je % vol, im Maßstab des Modells)."""
        labs = [a for a in anchors if a.abv is not None and a.abv >= 3.0]
        if not labs:
            return None
        model, lab = self.model(), labs[-1]
        consumed = model.s0 - lab.sugar
        value = consumed / lab.abv
        dbrix = WineModel.from_must(brix0=model.brix0 + 0.2, sg0=model.sg0).s0 - model.s0
        sigma = (
            (consumed * LAB_SIGMA_ABV / lab.abv**2) ** 2 + (LAB_SIGMA_SUGAR / lab.abv) ** 2 + (dbrix / lab.abv) ** 2
        ) ** 0.5
        return [value, sigma]

    async def _archive(self, now: datetime) -> None:
        """Ansatz abschließen: Archiv-Eintrag mit Nachkalkulation, daraus lernen die Hauswerte."""
        house = get_house(self.hass)
        if house is None:
            return
        est = self.data.estimate if self.data else None
        bottle = self.data.bottle if self.data else None
        _, anchors = self._estimate_inputs()
        observed: dict[str, list[float] | None] = {"g_sugar_per_abv": self._observed_sugar_per_abv(anchors)}
        if bottle is not None and (sat := observed_saturation(bottle)) is not None:
            observed["saturation"] = [sat[0], sat[1]]
        devices: dict[str, dict[str, list[float]]] = {}
        device, volume = self._conf(CONF_BUBBLE_DEVICE), self.volume_l
        if est is not None and device and volume and est.bubble_g_l_per_bubble:
            per_g = 1.0 / (est.bubble_g_l_per_bubble * YIELD_CO2_SUGAR * float(volume))
            devices["bubbles_per_g"] = {device: [per_g, per_g * (est.bubble_rel_sigma or 0.3)]}
        spindle = self._conf(CONF_GRAVITY_ENTITY)
        if est is not None and spindle and est.spindle_offset is not None and est.spindle_offset_sigma is not None:
            devices["spindle_offset"] = {spindle: [est.spindle_offset, est.spindle_offset_sigma]}
        series = est.series if est else []
        step = max(1, len(series) // 120)
        record: dict[str, Any] = {
            "entry_id": self.config_entry.entry_id,
            "name": self.config_entry.title,
            "mode": self.mode,
            "start": _iso(self.start),
            "closed": _iso(now),
            "bottling": self.store_data.get("bottling"),
            "target_bar_20c": self.settings().target_bar_20c,
            "bottle": _bottle_dict(bottle),
            "abv": None
            if est is None or est.abv_end is None
            else {
                "value": est.abv_end,
                "sigma": est.abv_end_sigma,
                "label": est.abv_label,
                "pairs": est.abv_pairs,
                "labs": est.abv_labs,
            },
            "series": [[_iso(t), round(s, 2)] for t, s, _ in series[::step]],
            "observed": observed,
            "observed_devices": devices,
        }
        await house.async_put(record)
        self._refresh_others()
        await self.async_refresh()

    def _bottle_readings(self) -> list[tuple[datetime, float, float | None]]:
        """Messflasche: Eingaben im Panel und, falls verbunden, die Flaschenbox."""
        out: list[tuple[datetime, float, float | None]] = []
        for m in self.store_data["measurements"]:
            if m["kind"] == "bottle_pressure" and (t := _parse(m["time"])) is not None:
                temp = m.get("temperature")
                out.append((t, float(m["value"]), float(temp) if temp is not None else None))
        temps = Series(self._series("bottle_temp"))
        for t, p in self._series("bottle_pressure"):
            out.append((t, p, temps.at(t) if temps else None))
        return out

    async def async_update_settings(self, changes: dict[str, Any]) -> None:
        if OPT_MALIC in changes:  # als Messung speichern: die jüngste Äpfelsäure gilt
            self.store_data["measurements"].append(
                {"kind": "malic", "value": float(changes.pop(OPT_MALIC)), "time": _iso(dt_util.utcnow()),
                 "note": "Eingabe im Panel"}
            )
        if "volume_l" in changes:
            self.store_data["volume_l"] = float(changes.pop("volume_l"))
            self._save()
        if changes:
            self.hass.config_entries.async_update_entry(
                self.config_entry, options={**self.config_entry.options, **changes}
            )
        await self.async_refresh()

    def _anchor(self, m: dict[str, Any], model: WineModel | None = None) -> Anchor | None:
        kind = m["kind"]
        if kind not in ("brix", "density", "brix_density", "sugar"):
            return None
        model = model or self._model_or_none()
        if model is None:
            return None
        t = _parse(m["time"]) or dt_util.utcnow()
        if kind == "brix":
            return Anchor(t, model.sugar_from_refractometer(m["value"]), SIGMA["brix"], kind)
        if kind == "density":
            sg = to_sg(m["value"], m.get("unit", "sg"))
            return Anchor(t, model.sugar_from_density(sg), SIGMA["sg"], kind)
        if kind == "brix_density":
            if "value2" not in m:
                raise HomeAssistantError("Für Refraktometer + Dichte braucht es beide Werte")
            sg = to_sg(m["value2"], m.get("unit", "sg"))
            sugar, _ = model.sugar_and_abv_from_pair(m["value"], sg)
            return Anchor(t, sugar, SIGMA["brix_sg"], kind, (float(m["value"]), sg))
        lab_abv = m.get("value2")  # Laborbefund: Alkohol derselben Probe, % vol
        return Anchor(t, float(m["value"]), SIGMA["sugar"], kind, abv=float(lab_abv) if lab_abv is not None else None)

    def _series(self, name: str) -> list[tuple[datetime, float]]:
        out = []
        for t, v in self.store_data["readings"][name]:
            parsed = _parse(t)
            if parsed is not None:
                out.append((parsed, float(v)))
        return out

    def _estimate_inputs(self) -> tuple[WineModel, list[Anchor]]:
        model = self.model()
        return model, [a for a in (self._anchor(m, model) for m in self.store_data["measurements"]) if a]

    # --- Rechnen ------------------------------------------------------------------------------
    async def _async_update_data(self) -> BatchResult:
        now = dt_util.utcnow()
        if self.mode == "charmat":
            return BatchResult(charmat=await self._update_charmat())
        model, anchors = self._estimate_inputs()
        bottling = self.bottling
        est = await self.hass.async_add_executor_job(
            partial(
                estimate,
                model,
                self.settings(),
                self.start,
                bottling.time if bottling else now,  # nach dem Abfüllen: Stand beim Abfüllen
                anchors,
                self._series("gravity"),
                self._series("bubbles"),
                self._series("temps"),
                self._series("weight"),
                abv_now=now,  # Laborwerte aus der Flasche zählen für den Alkohol weiter
                saturated=[t for t, _ in self._series("bubbles_saturated")],
            )
        )
        if bottling is not None:
            est.status = "bottled"
            est.display_state, est.dub_hours, est.measurement_recommended = "none", None, False
            bottle = bottle_status(bottling, self._bottle_readings(), now) if self.mode == "petnat" else None
            await self._display_off(now)
            await self._push_heater(None, now)
            return BatchResult(estimate=est, bottle=bottle)
        self._remember_forecast(est, now)
        await self._publish_display(est, now)
        await self._push_heater(est.planned_temp, now)
        return BatchResult(estimate=est)

    def _remember_forecast(self, est: Estimate, now: datetime) -> None:
        """Prognose-Stand für die Nachkalkulation, höchstens stündlich."""
        if est.best is None:
            return
        snaps: list[list[Any]] = self.store_data.setdefault("forecasts", [])
        last = _parse(snaps[-1][0]) if snaps else None
        if last is not None and now - last < timedelta(minutes=FORECAST_SNAPSHOT_MINUTES):
            return
        snaps.append([_iso(now), _iso(est.best), _iso(est.start) if est.start else None, _iso(est.end) if est.end else None])
        del snaps[:-FORECAST_SNAPSHOT_MAX]
        self._save()

    async def _update_charmat(self) -> CharmatStatus | None:
        temps, pressure = self._series("temps"), self._series("pressure")
        if not temps:
            return None
        status = charmat_status(
            float(self._opt(OPT_TARGET_BAR)),
            temps[-1][1],
            pressure[-1][1] if pressure else None,
            self._opt(OPT_PRV_BAR),
            float(self._opt(OPT_FILLING_LOSS)),
        )
        target_entity = self._conf(CONF_CO2_TARGET_ENTITY)
        if target_entity and (self._last_co2 is None or abs(status.co2_target - self._last_co2) > 0.05):
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": target_entity, "value": round(status.co2_target, 2)}
            )
            self._last_co2 = status.co2_target
        return status

    async def _publish_display(self, est: Estimate, now: datetime) -> None:
        device = self._conf(CONF_BUBBLE_DEVICE)
        if not device or "mqtt" not in self.hass.config.components:
            return
        payload = json.dumps(display_payload(est, self.mode), separators=(",", ":"))
        if self._last_display and self._last_display[0] == payload and now - self._last_display[1] < DISPLAY_REFRESH:
            return
        try:
            await mqtt.async_publish(self.hass, DISPLAY_TOPIC.format(device=device), payload, qos=0, retain=True)
            self._last_display = (payload, now)
        except HomeAssistantError as err:
            _LOGGER.debug("Display-Wert nicht gesendet: %s", err)

    async def _display_off(self, now: datetime) -> None:
        """Nach dem Abfüllen einmal „keine Prognose“ ans Display, danach nichts mehr."""
        device = self._conf(CONF_BUBBLE_DEVICE)
        if self._display_off_sent or not device or "mqtt" not in self.hass.config.components:
            return
        payload = json.dumps(
            {"dub_h": None, "state": "none", "mode": self.mode, "status": "bottled", "measure": False},
            separators=(",", ":"),
        )
        try:
            await mqtt.async_publish(self.hass, DISPLAY_TOPIC.format(device=device), payload, qos=0, retain=True)
            self._display_off_sent = True
        except HomeAssistantError as err:
            _LOGGER.debug("Display-Wert nicht gesendet: %s", err)

    async def _push_heater(self, planned: float | None, now: datetime) -> None:
        """Solltemperatur an den Shelly. Nach dem Abfüllen 0: Das Skript sieht keinen gültigen
        Sollwert (unter 5 °C) und schaltet die Heizung aus."""
        host = self._conf(CONF_HEATER_HOST)
        if not host or (planned is None and self.bottling is None):
            return
        temp = 0.0 if self.bottling is not None else round(planned, 1)
        if self._last_heater and self._last_heater[0] == temp and now - self._last_heater[1] < HEATER_REFRESH:
            return
        body = {"id": 1, "method": "KVS.Set", "params": {"key": HEATER_KVS_KEY, "value": temp}}
        try:
            async with async_get_clientsession(self.hass).post(f"http://{host}/rpc", json=body, timeout=5) as resp:
                resp.raise_for_status()
            self._last_heater = (temp, now)
        except Exception as err:  # noqa: BLE001 - Heizung darf das Rechnen nie aufhalten
            _LOGGER.warning("Solltemperatur %.1f °C nicht an %s gesendet: %s", temp, host, err)

    # --- Für Panel und WebSocket ----------------------------------------------------------
    async def async_preview(
        self, kind: str, value: float, value2: float | None = None, unit: str | None = None
    ) -> dict[str, Any]:
        """Was eine Messung ändern würde, ohne sie zu speichern."""
        current = self.data.estimate if self.data else None
        out: dict[str, Any] = {
            "prev_sugar": current.sugar if current else None,
            "prev_abv_end_sigma": current.abv_end_sigma if current else None,
        }
        if kind == "malic":
            settings = replace(self.settings(), malic_g_l=float(value))
            out["target_sugar"] = settings.target_sugar()
            return out
        m: dict[str, Any] = {"kind": kind, "value": float(value), "time": _iso(dt_util.utcnow())}
        if value2 is not None:
            m["value2"] = float(value2)
        if unit:
            m["unit"] = unit
        model = self._model_or_none()
        if model is None:
            return out
        anchors = [a for a in (self._anchor(x, model) for x in self.store_data["measurements"]) if a]
        try:
            anchor = self._anchor(m, model)
        except (HomeAssistantError, ValueError, ZeroDivisionError) as err:
            return {**out, "error": str(err)}
        if anchor is None:
            return out
        out["sugar"] = anchor.sugar
        out["abv"] = model.abv(max(0.0, anchor.sugar))
        if anchor.pair is not None:
            out["abv_measured"] = model.sugar_and_abv_from_pair(*anchor.pair)[1]
        elif anchor.abv is not None:
            out["abv_measured"] = anchor.abv
        out["plausible"] = -1.0 <= anchor.sugar <= model.s0 + 5.0
        if self.mode == "charmat" or not out["plausible"]:
            return out
        est = await self.hass.async_add_executor_job(
            estimate,
            model,
            self.settings(),
            self.start,
            dt_util.utcnow(),
            [*anchors, anchor],
            self._series("gravity"),
            self._series("bubbles"),
            self._series("temps"),
            self._series("weight"),
            None,
            [t for t, _ in self._series("bubbles_saturated")],
        )
        out.update(
            {
                "now_sugar": est.sugar,
                "spindle_offset": est.spindle_offset,
                "best": _iso(est.best) if est.best else None,
                "start": _iso(est.start) if est.start else None,
                "end": _iso(est.end) if est.end else None,
                "status": est.status,
                "display_state": est.display_state,
                "abv_end": est.abv_end,
                "abv_end_sigma": est.abv_end_sigma,
                "abv_label": est.abv_label,
                "abv_label_ok": est.abv_label_ok,
                "abv_pairs": est.abv_pairs,
                "abv_labs": est.abv_labs,
            }
        )
        return out

    def _history(self, now: datetime) -> dict[str, Any]:
        """Verläufe fürs Diagramm, auf höchstens HISTORY_POINTS Punkte ausgedünnt."""
        out: dict[str, Any] = {}
        for name, days in HISTORY_DAYS.items():
            pts = [p for p in self.store_data["readings"][name] if (_parse(p[0]) or now) >= now - timedelta(days=days)]
            out[name] = pts[:: max(1, len(pts) // HISTORY_POINTS)]
        out["bubbles_bpm"], out["bpm_now"] = self._bubble_rates(now)
        return out

    def _bubble_rates(self, now: datetime) -> tuple[list[list[Any]], float | None]:
        """Blasen pro Minute: stündlich über 7 Tage und über die letzten 15 Minuten."""
        pts = self._series("bubbles")
        if len(pts) < 2:
            return [], None
        totals = Series(pts)
        first, last = pts[0][0], pts[-1][0]
        hour = timedelta(hours=1)
        t = max(first, now - timedelta(days=7)).replace(minute=0, second=0, microsecond=0) + hour
        hourly: list[list[Any]] = []
        while t + hour <= last:
            n0, n1 = totals.interpolate(t), totals.interpolate(t + hour)
            hourly.append([_iso(t), round(max(0.0, (n1 or 0.0) - (n0 or 0.0)) / 60.0, 2)])
            t += hour
        bpm = None
        a = max(first, last - timedelta(minutes=15))
        minutes = (last - a).total_seconds() / 60.0
        if minutes >= 4 and now - last <= timedelta(minutes=20):
            bpm = round(max(0.0, (totals.interpolate(last) or 0.0) - (totals.interpolate(a) or 0.0)) / minutes, 1)
        return hourly, bpm

    def public_entry(self) -> dict[str, Any] | None:
        """Öffentliche Zahlen dieses Ansatzes für den DataWein-Feed (nur gerundete Werte, keine Geräte)."""
        if self.mode == "charmat":
            return None
        now = dt_util.utcnow()
        temps = self._series("temps")
        temp = temps[-1][1] if temps and now - temps[-1][0] <= timedelta(hours=1) else None
        _, bpm = self._bubble_rates(now)
        est = self.data.estimate if self.data else None
        return feed_entry(self.config_entry.title, self.mode, self.start, now, est, self._model_or_none(), bpm, temp)

    def panel_data(self) -> dict[str, Any]:
        est = self.data.estimate if self.data else None
        charm = self.data.charmat if self.data else None
        settings = self.settings()
        model = self._model_or_none()
        anchors = [a for a in (self._anchor(m, model) for m in self.store_data["measurements"]) if a] if model else []
        out: dict[str, Any] = {
            "entry_id": self.config_entry.entry_id,
            "name": self.config_entry.title,
            "mode": self.mode,
            "start": _iso(self.start),
            "volume_l": self.volume_l,
            "bubble_device": self._conf(CONF_BUBBLE_DEVICE),
            "brix0": self._conf(CONF_BRIX0),
            "sg0": self._conf(CONF_SG0),
            "s0": model.s0 if model else None,
            "anchors": [[_iso(a.t), a.sugar, a.kind] for a in anchors[-40:]],
            "has_heater": bool(self._conf(CONF_HEATER_HOST)),
            "has_gravity": bool(self._conf(CONF_GRAVITY_ENTITY)),
            "has_weight": bool(self._conf(CONF_WEIGHT_ENTITY) or self.store_data["readings"]["weight"]),
            "has_bottle_sensor": bool(self._conf(CONF_BOTTLE_PRESSURE_ENTITY)),
            "bottling": self.store_data.get("bottling"),
            "bottle": _bottle_dict(self.data.bottle if self.data else None),
            "closed": any(e["kind"] == "closed" for e in self.store_data["events"]),
            "settings": {
                "target_bar_20c": settings.target_bar_20c,
                "bottle": settings.bottle,
                "malo_in_bottle": settings.malo_in_bottle,
                "malic_g_l": settings.malic_g_l,
                "q10": settings.q10,
                "dry_sugar_g_l": settings.dry_sugar_g_l,
                "saturation": settings.saturation,
                "temp_plan": [list(step) for step in settings.temp_plan],
                "temp_start": self._opt(OPT_TEMP_START),
                "temp_switch_sugar": self._opt(OPT_TEMP_SWITCH_SUGAR),
                "temp_late": self._opt(OPT_TEMP_LATE),
                "prv_bar": self._opt(OPT_PRV_BAR),
                "filling_loss": self._opt(OPT_FILLING_LOSS),
            },
            "measurements": self.store_data["measurements"][-30:],
            "events": self.store_data["events"][-30:],
            "latest": {
                name: (self.store_data["readings"][name][-1] if self.store_data["readings"][name] else None)
                for name in SERIES
            },
            "history": self._history(dt_util.utcnow()),
        }
        if est is not None:
            cutoff = est.now - timedelta(days=7)
            series = [p for p in est.series if p[0] >= cutoff]
            step = max(1, len(series) // 300)
            out["estimate"] = {
                "now": _iso(est.now),
                "sugar": est.sugar,
                "sigma": est.sigma,
                "abv": est.abv,
                "abv_end": est.abv_end,
                "abv_end_sigma": est.abv_end_sigma,
                "abv_label": est.abv_label,
                "abv_label_ok": est.abv_label_ok,
                "abv_pairs": est.abv_pairs,
                "abv_labs": est.abv_labs,
                "rate": est.rate_g_l_day,
                "target_sugar": est.target_sugar,
                "best": _iso(est.best) if est.best else None,
                "start": _iso(est.start) if est.start else None,
                "end": _iso(est.end) if est.end else None,
                "dub_h": est.dub_hours,
                "dub": format_dub(est.dub_hours),
                "display_state": est.display_state,
                "status": est.status,
                "p_now_10": est.p_now_10,
                "p_now_20": est.p_now_20,
                "p_target_10": est.p_target_10,
                "p_target_20": est.p_target_20,
                "p_worst_20": est.p_worst_20,
                "limit_ok": est.limit_ok,
                "category": est.category,
                "planned_temp": est.planned_temp,
                "measurement_recommended": est.measurement_recommended,
                "window_h": est.window_h,
                "window_h_measured": est.window_h_measured,
                "p_over_target": est.p_over_target,
                "p_over_limit": est.p_over_limit,
                "spindle_offset": est.spindle_offset,
                "fit_k": est.fit_k,
                "fit_rel": est.fit_rel,
                "weight_g_l_per_kg": est.weight_g_l_per_kg,
                "weight_calibrated": est.weight_calibrated,
                "notes": est.notes,
                "series": [[_iso(t), s, sig] for t, s, sig in series[::step]],
                "forecast": [[_iso(t), s, hi, lo] for t, s, hi, lo in est.forecast[:: max(1, len(est.forecast) // 120)]],
            }
        if charm is not None:
            out["charmat"] = {
                "co2_target": charm.co2_target,
                "setpoint": charm.setpoint,
                "dissolved": charm.dissolved,
                "margin_ok": charm.margin_ok,
                "table": charm.table,
            }
        return out
