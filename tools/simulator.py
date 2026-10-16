"""Simulierte Pet-Nat-Gärung mit bekannter Wahrheit (für Tests und zum Ausprobieren).

Bildet ab: logistische Gärung mit nachlassender Hefe, Temperaturplan, Spindel mit Versatz,
Drift und Rauschen, Blasenzähler mit Leck, Sättigung (max. ~6 Blasen/s) und CO2-Rücklösung
beim Kühlen, Refraktometer-Messungen mit Ablesefehler sowie eine Waage (ganzes Gefäß oder
ein Bein von dreien) mit Rauschen, Drift und Probenahmen.

Aufruf:  python3 tools/simulator.py      (druckt einen Verlauf und die Prognose)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "custom_components", "tipsylab"))

from core.bottling import fill_conditions, pressure_from_co2
from core.composition import (
    DSG_ETHANOL,
    FERMENTABLE_FRACTION,
    G_SUGAR_PER_ABV,
    K_ETHANOL_BRIX,
    WineModel,
)
from core.fermentation import thermal_factor
from core.physics import BOTTLES, YIELD_CO2_MALIC, YIELD_CO2_SUGAR, henry


@dataclass
class SimConfig:
    brix0: float = 20.5
    # Wahrheit des Weins; der Schätzer kennt nur die Startwerte aus core.composition
    g_sugar_per_abv: float = G_SUGAR_PER_ABV
    fermentable_fraction: float = FERMENTABLE_FRACTION
    k_ethanol_brix: float = K_ETHANOL_BRIX
    dsg_ethanol: float = DSG_ETHANOL
    volume_l: float = 50.0
    mu: float = 0.75  # Wachstumsrate je thermischem Tag (logistisch)
    decline: float = 0.03  # Hefe lässt je Tag nach (macht das Ende träger als ein reiner Zerfall)
    lag_days: float = 1.0
    q10: float = 2.2
    temp_start: float = 17.0
    cool_at_sugar: float | None = 30.0  # ab diesem Restzucker kühlen
    temp_cool: float = 12.0
    stuck_at_sugar: float | None = None  # Gärung bleibt hier stehen
    spindle_offset: float = 0.0025  # SG-Versatz der Spindel
    spindle_drift_per_day: float = 0.0003
    spindle_noise: float = 0.0005
    refr_noise: float = 0.1  # °Bx
    ml_per_bubble: float = 2.0
    leak_fraction: float = 0.1
    max_bubbles_per_min: float = 360.0
    vessel_kg: float = 15.0  # Leergewicht des Gefäßes (Ballon ~15 kg, 750-L-Tank ~100 kg)
    scale_fraction: float = 1.0  # Anteil, den die Waage sieht: 1 = ganzes Gefäß, 1/3 = ein Bein von dreien
    scale_noise_kg: float = 0.002
    scale_drift_kg_per_day: float = 0.0
    samples: tuple[tuple[float, float], ...] = ()  # Probenahmen: (Tag, Liter)
    days: float = 14.0
    step_min: int = 15
    seed: int = 7


@dataclass
class SimResult:
    start: datetime
    model: WineModel
    config: SimConfig = field(default_factory=SimConfig)
    truth: list[tuple[datetime, float]] = field(default_factory=list)  # (t, Zucker g/L)
    temps: list[tuple[datetime, float]] = field(default_factory=list)
    gravity: list[tuple[datetime, float]] = field(default_factory=list)
    bubbles: list[tuple[datetime, float]] = field(default_factory=list)  # kumuliert
    saturated: list[datetime] = field(default_factory=list)  # Zähler an der Grenze: zählt zu wenig
    weight: list[tuple[datetime, float]] = field(default_factory=list)  # Anzeige der Waage, kg

    def bubbles_per_g(self, t_c: float) -> float:
        """Wahre Blasen je g entweichendes CO2 dieses Röhrchens bei t_c (Gasvolumen, Leck, Blasengröße)."""
        cfg = self.config
        return 22414 * (t_c + 273.15) / 273.15 / 44.01 * (1 - cfg.leak_fraction) / cfg.ml_per_bubble

    def sugar_at(self, t: datetime) -> float:
        best = min(self.truth, key=lambda p: abs((p[0] - t).total_seconds()))
        return best[1]

    def crossing(self, sugar: float) -> datetime | None:
        for t, s in self.truth:
            if s <= sugar:
                return t
        return None

    def refractometer(self, t: datetime, rng: random.Random, noise: float) -> float:
        return self.model.refractometer_reading(self.sugar_at(t)) + rng.gauss(0, noise)

    def hydrometer(self, t: datetime, rng: random.Random, noise: float) -> float:
        """Relative Dichte einer entgasten Probe (Hydrometer oder Dichtemeter)."""
        return self.model.density(self.sugar_at(t)) + rng.gauss(0, noise)

    def abv_at(self, t: datetime) -> float:
        return self.model.abv(self.sugar_at(t))

    def lab(self, t: datetime, rng: random.Random, sugar_noise: float = 0.5, abv_noise: float = 0.1) -> tuple[float, float]:
        """Laborbefund einer Probe: Restzucker (g/L) und Alkohol (% vol)."""
        return self.sugar_at(t) + rng.gauss(0, sugar_noise), self.abv_at(t) + rng.gauss(0, abv_noise)

    def bottle_abv(self, dry_sugar: float) -> float:
        """Wahrer Alkohol nach vollständiger Vergärung bis dry_sugar."""
        return self.model.abv(dry_sugar)


def simulate(cfg: SimConfig | None = None, start: datetime | None = None) -> SimResult:
    cfg = cfg or SimConfig()
    rng = random.Random(cfg.seed)
    start = start or datetime(2026, 9, 1, 8, 0)
    model = WineModel.from_must(
        brix0=cfg.brix0,
        g_sugar_per_abv=cfg.g_sugar_per_abv,
        fermentable_fraction=cfg.fermentable_fraction,
        k_ethanol_brix=cfg.k_ethanol_brix,
        dsg_ethanol=cfg.dsg_ethanol,
    )
    res = SimResult(start=start, model=model, config=cfg)
    s0 = model.s0
    s = s0 * 0.995
    step = timedelta(minutes=cfg.step_min)
    dt_days = cfg.step_min / 1440.0
    n_steps = int(cfg.days * 1440 / cfg.step_min)
    temp = cfg.temp_start
    bubbles = 0.0
    dissolved = 0.0  # g/L CO2 gelöst
    wine_kg = cfg.volume_l * model.density(s) * 0.998  # Most, kg
    pending_samples = sorted(cfg.samples)
    for i in range(n_steps + 1):
        t = start + step * i
        age = i * dt_days
        if cfg.cool_at_sugar is not None and s <= cfg.cool_at_sugar:
            temp = cfg.temp_cool
        res.truth.append((t, s))
        res.temps.append((t, temp + rng.gauss(0, 0.1)))
        sg = model.density(s) + cfg.spindle_offset + cfg.spindle_drift_per_day * age + rng.gauss(0, cfg.spindle_noise)
        res.gravity.append((t, sg))
        res.bubbles.append((t, bubbles))
        while pending_samples and pending_samples[0][0] <= age:
            _, liters = pending_samples.pop(0)
            wine_kg -= liters * model.density(s) * 0.998
        scale = cfg.scale_fraction * (cfg.vessel_kg + wine_kg) + cfg.scale_drift_kg_per_day * age
        res.weight.append((t, scale + rng.gauss(0, cfg.scale_noise_kg)))
        if i == n_steps:
            break
        # Gärung
        f = thermal_factor(temp, cfg.q10)
        mu = cfg.mu * math.exp(-cfg.decline * age) if age >= cfg.lag_days else cfg.mu * 0.05
        ds = mu * s * (1 - s / s0 + 0.02) * f * dt_days
        if cfg.stuck_at_sugar is not None and s <= cfg.stuck_at_sugar:
            ds = 0.0
        s = max(0.0, s - ds)
        # CO2: erst lösen bis zur Sättigung, dann ausgasen; Kühlen löst zurück
        produced = YIELD_CO2_SUGAR * ds  # g/L
        sat = henry(temp)  # g/L bei 1 bar
        dissolved += produced
        out = max(0.0, dissolved - sat)
        dissolved = min(dissolved, sat)
        wine_kg -= out * cfg.volume_l / 1000.0  # entwichenes CO2 verlässt das Gefäß
        gas_ml = out * cfg.volume_l / 44.01 * 22414 * (temp + 273.15) / 273.15
        n = gas_ml * (1 - cfg.leak_fraction) / cfg.ml_per_bubble
        cap = cfg.max_bubbles_per_min * cfg.step_min
        if n > cap:
            res.saturated.append(t + step)  # wie die Gärbox: "saturated" in der nächsten Meldung
        n = min(n, cap)
        bubbles += max(0.0, n)
    return res


def simulate_bottle(
    sugar: float,
    saturation: float = 0.8,
    start: datetime | None = None,
    days: tuple[float, ...] = (3, 7, 14, 21, 28, 35),
    temp_c: float | tuple[float, ...] = 14.0,
    bottle: str = "750",
    malic: float = 0.0,
    t_bottling_c: float = 12.0,
    half_life_days: float = 4.0,
    noise_bar: float = 0.05,
    seed: int = 7,
) -> list[tuple[datetime, float, float]]:
    """Messflasche mit bekannter Wahrheit: Der Restzucker vergärt in der Flasche mit erster Ordnung.

    Liefert Ablesungen (Zeit, Überdruck bar, Temperatur °C) an den gegebenen Tagen nach dem Abfüllen.
    """
    rng = random.Random(seed)
    start = start or datetime(2026, 9, 20, 10, 0)
    fill = fill_conditions(saturation, t_bottling_c)[0]
    temps = temp_c if isinstance(temp_c, tuple) else (temp_c,) * len(days)
    out = []
    for d, t_c in zip(days, temps):
        done = 1.0 - 0.5 ** (d / half_life_days)
        co2 = saturation * henry(t_bottling_c) + done * (YIELD_CO2_SUGAR * sugar + YIELD_CO2_MALIC * malic)
        p = pressure_from_co2(co2, t_c, BOTTLES[bottle], fill) + rng.gauss(0, noise_bar)
        out.append((start + timedelta(days=d), p, t_c))
    return out


if __name__ == "__main__":
    from core.fermentation import Anchor, Settings, estimate

    sim = simulate()
    rng = random.Random(1)
    settings = Settings(target_bar_20c=2.5, temp_plan=((None, 17.0), (30.0, 12.0)))
    target = settings.target_sugar()
    cross = sim.crossing(target)
    print(f"Zielzucker {target:.1f} g/L, wahrer Durchgang {cross:%a %d.%m. %H:%M}")
    anchors: list[Anchor] = []
    for day in range(1, 14):
        now = sim.start + timedelta(days=day)
        if now > sim.truth[-1][0]:
            break
        r = sim.refractometer(now, rng, 0.1)
        anchors.append(Anchor(now, sim.model.sugar_from_refractometer(r), 2.5, "brix"))
        e = estimate(sim.model, settings, sim.start, now, anchors,
                     [g for g in sim.gravity if g[0] <= now], [b for b in sim.bubbles if b[0] <= now],
                     [x for x in sim.temps if x[0] <= now])
        best = f"{e.best:%a %d.%m. %H:%M}" if e.best else "–"
        print(f"Tag {day:2d}: wahr {sim.sugar_at(now):6.1f}  geschätzt {e.sugar or 0:6.1f} ± {e.sigma or 0:4.1f}  "
              f"beste Zeit {best}  Status {e.status}")

    # Alkohol in der Flasche: Die Wahrheit weicht von den Startwerten ab, der Schätzer kennt sie nicht.
    # Jeden Tag ein Messpaar (Refraktometer und Hydrometer an derselben Probe).
    cfg = SimConfig(g_sugar_per_abv=17.4, fermentable_fraction=0.90)
    sim = simulate(cfg)
    model = WineModel.from_must(brix0=cfg.brix0)
    print(f"\nAlkohol in der Flasche: wahr {sim.bottle_abv(settings.dry_sugar_g_l):.2f} % vol "
          f"(Wahrheit {cfg.g_sugar_per_abv} g/L je % vol, {cfg.fermentable_fraction:.0%} vergärbar)")
    anchors = []
    for day in range(1, 14):
        now = sim.start + timedelta(days=day)
        if now > sim.truth[-1][0]:
            break
        r, sg = sim.refractometer(now, rng, 0.1), sim.hydrometer(now, rng, 0.0005)
        anchors.append(Anchor(now, model.sugar_and_abv_from_pair(r, sg)[0], 1.2, "brix_density", (r, sg)))
        e = estimate(model, settings, sim.start, now, anchors)
        print(f"Tag {day:2d}: jetzt wahr {sim.abv_at(now):5.2f}  Flasche {e.abv_end:5.2f} ± {e.abv_end_sigma:4.2f}  "
              f"Etikett {e.abv_label:4.1f} {'ok' if e.abv_label_ok else 'unsicher'}  Messpaare {e.abv_pairs}")
