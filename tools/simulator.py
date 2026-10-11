"""Simulierte Pet-Nat-Gärung mit bekannter Wahrheit (für Tests und zum Ausprobieren).

Bildet ab: logistische Gärung mit nachlassender Hefe, Temperaturplan, Spindel mit Versatz,
Drift und Rauschen, Blasenzähler mit Leck, Sättigung (max. ~6 Blasen/s) und CO2-Rücklösung
beim Kühlen sowie Refraktometer-Messungen mit Ablesefehler.

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

from core.composition import WineModel  # noqa: E402
from core.fermentation import T_REF, thermal_factor  # noqa: E402
from core.physics import YIELD_CO2_SUGAR, henry  # noqa: E402


@dataclass
class SimConfig:
    brix0: float = 20.5
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
    days: float = 14.0
    step_min: int = 15
    seed: int = 7


@dataclass
class SimResult:
    start: datetime
    model: WineModel
    truth: list[tuple[datetime, float]] = field(default_factory=list)  # (t, Zucker g/L)
    temps: list[tuple[datetime, float]] = field(default_factory=list)
    gravity: list[tuple[datetime, float]] = field(default_factory=list)
    bubbles: list[tuple[datetime, float]] = field(default_factory=list)  # kumuliert

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


def simulate(cfg: SimConfig | None = None, start: datetime | None = None) -> SimResult:
    cfg = cfg or SimConfig()
    rng = random.Random(cfg.seed)
    start = start or datetime(2026, 9, 1, 8, 0)
    model = WineModel.from_must(brix0=cfg.brix0)
    res = SimResult(start=start, model=model)
    s0 = model.s0
    s = s0 * 0.995
    step = timedelta(minutes=cfg.step_min)
    dt_days = cfg.step_min / 1440.0
    n_steps = int(cfg.days * 1440 / cfg.step_min)
    temp = cfg.temp_start
    bubbles = 0.0
    dissolved = 0.0  # g/L CO2 gelöst
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
        gas_ml = out * cfg.volume_l / 44.01 * 22414 * (temp + 273.15) / 273.15
        n = gas_ml * (1 - cfg.leak_fraction) / cfg.ml_per_bubble
        n = min(n, cfg.max_bubbles_per_min * cfg.step_min)
        bubbles += max(0.0, n)
    return res


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
