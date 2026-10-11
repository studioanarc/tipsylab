"""Gärschätzung und Prognose gegen den Simulator (bekannte Wahrheit)."""

from datetime import timedelta
import random

import pytest
from simulator import SimConfig, simulate

from core.fermentation import Anchor, Settings, estimate

PLAN = ((None, 17.0), (30.0, 12.0))


def run(sim, day, settings, spindle=True, bubbles=True, anchors_every=1.0, seed=1):
    rng = random.Random(seed)
    now = sim.start + timedelta(days=day)
    anchors = []
    d = anchors_every
    while d <= day + 1e-9:
        t = sim.start + timedelta(days=d)
        r = sim.refractometer(t, rng, 0.1)
        anchors.append(Anchor(t, sim.model.sugar_from_refractometer(r), 2.5, "brix"))
        d += anchors_every
    upto = lambda xs: [x for x in xs if x[0] <= now]  # noqa: E731
    return estimate(
        sim.model,
        settings,
        sim.start,
        now,
        anchors,
        upto(sim.gravity) if spindle else None,
        upto(sim.bubbles) if bubbles else None,
        upto(sim.temps),
    )


@pytest.fixture(scope="module")
def sim():
    return simulate(SimConfig())


@pytest.mark.parametrize("day", [9, 10, 11])
def test_window_contains_true_crossing(sim, day):
    settings = Settings(target_bar_20c=2.5, temp_plan=PLAN)
    est = run(sim, day, settings)
    truth = sim.crossing(settings.target_sugar())
    assert est.best is not None
    assert abs((est.best - truth).total_seconds()) <= 12 * 3600
    assert est.start - timedelta(hours=6) <= truth <= est.end + timedelta(hours=6)


def test_sugar_estimate_tracks_truth(sim):
    settings = Settings(temp_plan=PLAN)
    for day in (6, 8, 10):
        est = run(sim, day, settings)
        assert est.sugar == pytest.approx(sim.sugar_at(sim.start + timedelta(days=day)), abs=4.0)


def test_anchors_only_still_forecasts(sim):
    settings = Settings(temp_plan=PLAN)
    est = run(sim, 9, settings, spindle=False, bubbles=False)
    truth = sim.crossing(settings.target_sugar())
    assert est.best is not None
    assert abs((est.best - truth).total_seconds()) <= 24 * 3600


def test_cooler_plan_moves_window_later(sim):
    warm = run(sim, 8, Settings(temp_plan=((None, 17.0),)))
    cold = run(sim, 8, Settings(temp_plan=((None, 17.0), (30.0, 10.0))))
    assert cold.best > warm.best


def test_display_state_and_pressures(sim):
    settings = Settings(target_bar_20c=2.5, temp_plan=PLAN)
    early = run(sim, 6, settings)
    assert early.display_state == "ok"
    late = run(sim, 12.5, settings)
    assert late.display_state == "late"
    assert late.status == "past"
    mid = run(sim, 10, settings)
    assert mid.display_state in ("soon", "now")
    assert mid.p_now_20 > mid.p_target_20
    assert mid.p_target_20 == pytest.approx(2.5, abs=0.01)
    assert mid.limit_ok


def test_malo_option_lowers_target_sugar():
    plain = Settings(target_bar_20c=2.5)
    malo = Settings(target_bar_20c=2.5, malo_in_bottle=True, malic_g_l=2.0)
    assert plain.target_sugar() - malo.target_sugar() == pytest.approx(1.4, abs=0.05)


def test_stuck_fermentation_is_detected():
    sim = simulate(SimConfig(stuck_at_sugar=20.0, cool_at_sugar=None))
    est = run(sim, 11, Settings(target_bar_20c=2.5), anchors_every=0.5)
    assert est.status == "stuck"
    assert est.measurement_recommended


def test_still_wine_reaches_dry():
    sim = simulate(SimConfig(days=16, cool_at_sugar=None))
    est = run(sim, 15.5, Settings(mode="still", dry_sugar_g_l=2.0), anchors_every=0.5)
    assert est.status == "dry"


def test_waiting_without_data(sim):
    est = estimate(sim.model, Settings(), sim.start, sim.start + timedelta(days=2))
    assert est.status == "waiting"
    assert est.best is None


@pytest.mark.parametrize("seed", [7, 11])
def test_no_false_stuck_in_healthy_fermentation(seed):
    sim = simulate(SimConfig(seed=seed))
    for d10 in range(20, 130, 5):
        est = run(sim, d10 / 10, Settings(target_bar_20c=2.5, temp_plan=PLAN), anchors_every=0.5, seed=seed)
        assert est.status != "stuck", d10 / 10


def test_forecast_curve_matches_window(sim):
    settings = Settings(target_bar_20c=2.5, temp_plan=PLAN)
    est = run(sim, 9, settings)
    assert est.forecast and est.forecast[0][0] == est.now
    times = [p[0] for p in est.forecast]
    assert times == sorted(times)
    assert times[-1] >= est.end
    for _, s, hi, lo in est.forecast:
        assert lo <= s <= hi
    mids = [p[1] for p in est.forecast]
    assert all(b <= a for a, b in zip(mids, mids[1:]))
    # Die Mittellinie kreuzt den Zielzucker dort, wo best liegt (± ein Rechenschritt)
    crossing = next(t for t, s, _, _ in est.forecast if s <= est.target_sugar)
    assert abs((crossing - est.best).total_seconds()) <= 3600


def test_forecast_empty_without_fit(sim):
    est = estimate(sim.model, Settings(), sim.start, sim.start + timedelta(days=2))
    assert est.forecast == []
