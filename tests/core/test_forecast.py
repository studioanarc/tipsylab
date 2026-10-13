"""Probabilistische Prognose (Phase 3): Bausteine und das Kriterium aus dem Plan im Simulator."""

from datetime import datetime, timedelta
import math
import random

import pytest

from core.fermentation import Anchor, Settings, estimate
from core.forecast import (
    chance_above,
    crossing_quantiles,
    days_to,
    draws,
    forecast,
    measurement_gain,
    sugar_after,
    tau_to,
    worth_measuring,
)
from simulator import SimConfig, simulate

NOW = datetime(2026, 9, 10, 8, 0)


@pytest.mark.parametrize("beta", [-0.2, 0.0, 0.15])
def test_tau_and_sugar_are_inverse(beta):
    tau = tau_to(40.0, 6.5, 0.4, beta)
    assert sugar_after(40.0, tau, 0.4, beta) == pytest.approx(6.5, rel=1e-9)


def test_strong_slowdown_never_arrives():
    assert math.isinf(tau_to(40.0, 1.0, 0.1, -0.5))


def test_days_follow_the_temperature_plan():
    """Kühler Abschnitt dauert länger: Thermische Zeit wird über den Plan in Kalendertage umgerechnet."""
    d = draws(30.0, 0.0001, 0.5, 0.0, 2.2, n=1)[0]
    flat = days_to(d, 6.5, lambda s: 15.0, 15.0, 2.2, [])
    cooled = days_to(d, 6.5, lambda s: 15.0 if s > 20 else 10.0, 15.0, 2.2, [20.0])
    assert cooled > flat


def test_quantiles_are_ordered_and_honest_about_sigma():
    sample = draws(20.0, 1.5, 0.45, 0.1, 2.2)
    p10, p50, p90 = crossing_quantiles(sample, 6.5, lambda s: 12.0, 12.0, 2.2, [])
    assert 0 < p10 < p50 < p90
    wide = crossing_quantiles(draws(20.0, 4.0, 0.45, 0.1, 2.2), 6.5, lambda s: 12.0, 12.0, 2.2, [])
    assert wide[2] - wide[0] > p90 - p10


def test_band_matches_the_quantiles():
    fc = forecast(NOW, 20.0, 1.5, 0.45, 0.1, 6.5, lambda s: 12.0, 12.0, 2.2, [], timedelta(days=30),
                  until=NOW + timedelta(days=6))
    for _, mid, hi, lo in fc.band:
        assert lo <= mid <= hi
    crossing = next(t for t, mid, _, _ in fc.band if mid <= 6.5)
    assert abs(crossing - fc.p50) <= timedelta(hours=1)


def test_a_measurement_narrows_the_window_when_the_sugar_is_unsure():
    before, after = measurement_gain(12.0, 4.0, 2.5, 0.45, 0.1, 6.5, lambda s: 12.0, 12.0, 2.2, [])
    assert worth_measuring((before, after))
    # Weit vor dem Ziel bestimmt die Rate das Fenster; eine Messung bringt dann wenig
    far = measurement_gain(14.0, 2.0, 2.5, 0.45, 0.1, 6.5, lambda s: 12.0, 12.0, 2.2, [])
    assert far[1] < far[0]
    assert not worth_measuring(far)


def test_chance_above():
    assert chance_above(6.5, 1.0, 6.5) == pytest.approx(0.5)
    assert chance_above(4.0, 1.0, 6.5) < 0.1
    assert chance_above(9.0, 1.0, 6.5) > 0.9


# --- Das Kriterium aus dem Plan (Phase 3) ------------------------------------------------------------


def _scenario(i: int) -> SimConfig:
    """Zufällige Ansätze: Kinetik, müde Hefe, Q10, Temperatur und Kühlplan, Spindel-Versatz."""
    r = random.Random(1000 + i)
    return SimConfig(
        brix0=r.uniform(19.0, 22.5),
        mu=r.uniform(0.5, 1.0),
        decline=r.uniform(0.0, 0.1),
        lag_days=r.uniform(0.5, 2.0),
        q10=r.uniform(1.8, 2.7),
        temp_start=r.uniform(14.0, 19.0),
        cool_at_sugar=r.choice([None, 25.0, 30.0, 35.0]),
        temp_cool=r.uniform(9.0, 13.0),
        spindle_offset=r.uniform(-0.004, 0.004),
        spindle_drift_per_day=r.uniform(0.0, 0.0005),
        days=24.0,
        step_min=30,
        seed=i,
    )


def _forecast_before(cfg: SimConfig, hours: float) -> tuple[bool, float] | None:
    """Prognose `hours` vor dem wahren Durchgang mit täglichem Refraktometer, Spindel und Blasen."""
    sim = simulate(cfg)
    plan = ((None, cfg.temp_start),) + (((cfg.cool_at_sugar, cfg.temp_cool),) if cfg.cool_at_sugar else ())
    settings = Settings(target_bar_20c=2.5, temp_plan=plan)
    crossing = sim.crossing(settings.target_sugar())
    if crossing is None:
        return None
    now = crossing - timedelta(hours=hours)
    if now <= sim.start + timedelta(days=2):
        return None
    rng = random.Random(cfg.seed * 7 + int(hours))
    anchors = []
    d = 1.0
    while sim.start + timedelta(days=d) <= now:
        t = sim.start + timedelta(days=d)
        anchors.append(Anchor(t, sim.model.sugar_from_refractometer(sim.refractometer(t, rng, 0.1)), 2.5, "brix"))
        d += 1.0
    upto = lambda xs: [x for x in xs if x[0] <= now]  # noqa: E731
    est = estimate(sim.model, settings, sim.start, now, anchors, upto(sim.gravity), upto(sim.bubbles), upto(sim.temps))
    if est.start is None or est.end is None:
        return None
    return est.start <= crossing <= est.end, (est.best - crossing).total_seconds() / 3600


@pytest.mark.parametrize("hours", [48, 24])
def test_window_p10_p90_contains_the_crossing_in_80_percent(hours):
    """Plan, Phase 3: Das Fenster P10–P90 aus Prognosen 48 h (und 24 h) vor dem Durchgang enthält
    ihn in mindestens 80 % der Fälle. Ein Kalibrierungstest, kein Genauigkeitsversprechen."""
    results = [r for r in (_forecast_before(_scenario(i), hours) for i in range(36)) if r is not None]
    assert len(results) >= 25
    coverage = sum(inside for inside, _ in results) / len(results)
    assert coverage >= 0.8, f"{coverage:.0%} von {len(results)}"
    errors = sorted(err for _, err in results)
    assert abs(errors[len(errors) // 2]) <= 10.0  # Median der besten Zeit: höchstens 10 h daneben
