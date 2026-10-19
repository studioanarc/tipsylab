"""Gärschätzung und Prognose gegen den Simulator (bekannte Wahrheit)."""

from datetime import datetime, timedelta
from itertools import pairwise
import random

import pytest

from core.composition import WineModel
from core.fermentation import Anchor, Settings, estimate, remove_steps
from simulator import SimConfig, simulate

PLAN = ((None, 17.0), (30.0, 12.0))
MODEL = WineModel.from_must(brix0=20.5)


def run(sim, day, settings, spindle=True, bubbles=True, anchors_every=1.0, seed=1, weight=False):
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
        upto(sim.weight) if weight else None,
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
    assert all(b <= a for a, b in pairwise(mids))
    # Die Mittellinie kreuzt den Zielzucker dort, wo best liegt (± ein Rechenschritt)
    crossing = next(t for t, s, _, _ in est.forecast if s <= est.target_sugar)
    assert abs((crossing - est.best).total_seconds()) <= 3600


def test_forecast_empty_without_fit(sim):
    est = estimate(sim.model, Settings(), sim.start, sim.start + timedelta(days=2))
    assert est.forecast == []


# --- Waage ---------------------------------------------------------------------------------------

def test_remove_steps_takes_out_a_sample():
    t0 = datetime(2026, 10, 1)
    pts = [(t0 + timedelta(minutes=15 * i), 70.0 - 0.001 * i) for i in range(20)]
    pts = pts[:10] + [(t, v - 0.25) for t, v in pts[10:]]  # 250 mL Probe nach dem zehnten Wert
    cleaned, steps = remove_steps(pts, max_kg_per_min=0.0005, noise_kg=0.002)
    assert steps == 1
    # der Sprung nimmt die Gärung dieses einen Intervalls (1 g) mit heraus
    assert cleaned[-1][1] == pytest.approx(70.0 - 0.019 + 0.001, abs=1e-9)


@pytest.mark.parametrize("day", [6, 8, 10])
def test_weight_alone_tracks_sugar_from_volume(day):
    sim = simulate(SimConfig())  # 50-L-Ballon auf einer Plattformwaage
    est = run(sim, day, Settings(temp_plan=PLAN, volume_l=50.0), spindle=False, bubbles=False,
              anchors_every=99, weight=True)
    assert est.weight_g_l_per_kg == pytest.approx(1000 / (0.47 * 50), rel=1e-9)
    assert not est.weight_calibrated
    assert est.sugar == pytest.approx(sim.sugar_at(sim.start + timedelta(days=day)), abs=3.0)


def test_weight_alone_finds_the_window():
    # Ohne jede Messung, nur Volumen und Waage. Die Prognose der Stufe 1 liegt in der Simulation
    # bei allen Quellen etwas spät (Phase 3 im Plan); hier kommt der Startwert des Mosts dazu.
    sim = simulate(SimConfig())
    settings = Settings(target_bar_20c=2.5, temp_plan=PLAN, volume_l=50.0)
    est = run(sim, 9.5, settings, spindle=False, bubbles=False, anchors_every=99, weight=True)
    truth = sim.crossing(settings.target_sugar())
    assert est.best is not None
    assert abs((est.best - truth).total_seconds()) <= 18 * 3600


@pytest.mark.parametrize("day", [9, 10])
def test_weight_with_measurements_finds_the_window(day):
    sim = simulate(SimConfig())
    settings = Settings(target_bar_20c=2.5, temp_plan=PLAN, volume_l=50.0)
    est = run(sim, day, settings, spindle=False, bubbles=False, anchors_every=1.0, weight=True)
    truth = sim.crossing(settings.target_sugar())
    assert est.weight_calibrated
    assert abs((est.best - truth).total_seconds()) <= 12 * 3600


def test_one_leg_of_three_is_calibrated_by_anchors():
    cfg = SimConfig(volume_l=700.0, vessel_kg=100.0, scale_fraction=1 / 3, scale_noise_kg=0.02)
    sim = simulate(cfg)
    est = run(sim, 9, Settings(temp_plan=PLAN, volume_l=700.0), spindle=False, bubbles=False,
              anchors_every=1.0, weight=True)
    k_theo = 1000 / (0.47 * 700)
    assert est.weight_calibrated
    assert est.weight_g_l_per_kg == pytest.approx(3 * k_theo, rel=0.2)
    assert "weight_third" in est.notes
    assert est.sugar == pytest.approx(sim.sugar_at(sim.start + timedelta(days=9)), abs=3.0)


def test_sample_does_not_look_like_fermentation():
    sim = simulate(SimConfig(samples=((7.0, 0.25),)))  # 250 mL aus 50 L: ohne Filter ~11 g/L Fehler
    est = run(sim, 9, Settings(temp_plan=PLAN, volume_l=50.0), spindle=False, bubbles=False,
              anchors_every=99, weight=True)
    assert est.weight_steps >= 1
    assert est.sugar == pytest.approx(sim.sugar_at(sim.start + timedelta(days=9)), abs=3.0)


def test_weight_with_all_sources_stays_on_truth():
    sim = simulate(SimConfig())
    est = run(sim, 9, Settings(temp_plan=PLAN, volume_l=50.0), weight=True)
    assert est.sugar == pytest.approx(sim.sugar_at(sim.start + timedelta(days=9)), abs=2.5)


def test_before_the_start_there_is_nothing_to_estimate(sim):
    e = estimate(sim.model, Settings(), sim.start, sim.start - timedelta(days=1))
    assert e.status == "waiting"
    assert e.sugar is None


def test_saturated_counter_is_not_used_for_calibration():
    """Läuft der Zähler an der Grenze, wird über diese Strecke nicht geeicht (Simulator mit Zählgrenze)."""
    sim = simulate(SimConfig(max_bubbles_per_min=120))
    assert sim.saturated
    now = sim.start + timedelta(days=9)
    rng = random.Random(2)
    anchors = [
        Anchor(sim.start + timedelta(days=d), sim.model.sugar_from_refractometer(sim.refractometer(sim.start + timedelta(days=d), rng, 0.1)), 2.5)
        for d in (3, 5)
    ]
    upto = lambda xs: [x for x in xs if x[0] <= now]  # noqa: E731
    args = (sim.model, Settings(temp_plan=PLAN), sim.start, now, anchors, None, upto(sim.bubbles), upto(sim.temps))
    assert estimate(*args).bubble_g_l_per_bubble is not None  # ohne die Meldung würde geeicht
    flagged = estimate(*args, saturated=[t for t in sim.saturated if t <= now])
    assert flagged.bubble_g_l_per_bubble is None
    assert "bubbles_saturated" in flagged.notes


def test_bubbles_stop_counting_at_saturation_after_the_anchor():
    start = datetime(2026, 9, 1, 8, 0)
    a1, a2 = start + timedelta(days=4), start + timedelta(days=5)
    bubbles = [(start + timedelta(hours=h), 1000.0 * h) for h in range(24 * 7)]
    anchors = [Anchor(a1, 60.0, 1.0), Anchor(a2, 40.0, 1.0)]
    now = start + timedelta(days=6)
    stop = a2 + timedelta(hours=6)
    est = estimate(MODEL, Settings(), start, now, anchors, None, bubbles, None, saturated=[stop])
    assert est.bubble_g_l_per_bubble is not None
    late = [t for t, _, _ in est.series if a2 < t < now and t >= stop]
    assert not late  # nach der gesättigten Meldung keine Blasen-Punkte mehr


@pytest.mark.parametrize("day", [3, 5])
def test_learned_bubbles_estimate_before_the_first_measurement(day):
    """Hauswert der Gärbox (Blasen je g CO2): Schätzung ab dem Start, ohne eine einzige Messung."""
    sim = simulate(SimConfig(volume_l=50))
    now = sim.start + timedelta(days=day)
    upto = lambda xs: [x for x in xs if x[0] <= now]  # noqa: E731
    learned = Settings(temp_plan=PLAN, volume_l=50, bubbles_per_g=sim.bubbles_per_g(17.0), bubbles_per_g_rel=0.15)
    est = estimate(sim.model, learned, sim.start, now, [], None, upto(sim.bubbles), upto(sim.temps))
    truth = sim.sugar_at(now)
    assert est.sugar is not None
    assert abs(est.sugar - truth) <= max(6.0, 2 * est.sigma)
    assert "bubbles_house" in est.notes
    without = estimate(sim.model, Settings(temp_plan=PLAN, volume_l=50), sim.start, now, [], None,
                       upto(sim.bubbles), upto(sim.temps))
    assert without.sugar is None  # ohne Hauswert und ohne Messung weiß die App nichts


def test_wrong_learned_bubbles_stay_honest():
    sim = simulate(SimConfig(volume_l=50))
    now = sim.start + timedelta(days=4)
    upto = lambda xs: [x for x in xs if x[0] <= now]  # noqa: E731
    off = Settings(temp_plan=PLAN, volume_l=50, bubbles_per_g=sim.bubbles_per_g(17.0) * 1.3, bubbles_per_g_rel=0.1)
    est = estimate(sim.model, off, sim.start, now, [], None, upto(sim.bubbles), upto(sim.temps))
    assert abs(est.sugar - sim.sugar_at(now)) <= 2 * est.sigma  # mindestens 30 % Unsicherheit


def test_learned_spindle_offset_until_the_first_match():
    """Typischer Versatz der Spindel aus dem Archiv, solange kein Anker einen eigenen liefert."""
    sim = simulate(SimConfig(spindle_offset=0.003, spindle_drift_per_day=0.0))
    now = sim.start + timedelta(days=3)
    gravity = [g for g in sim.gravity if sim.start + timedelta(hours=8) <= g[0] <= now]  # Spindel kam später
    upto = lambda xs: [x for x in xs if x[0] <= now]  # noqa: E731
    truth = sim.sugar_at(now)
    raw = estimate(sim.model, Settings(temp_plan=PLAN), sim.start, now, [], gravity, None, upto(sim.temps))
    learned = Settings(temp_plan=PLAN, spindle_offset_prior=0.003, spindle_offset_prior_sigma=0.0005)
    est = estimate(sim.model, learned, sim.start, now, [], gravity, None, upto(sim.temps))
    assert abs(est.sugar - truth) < abs(raw.sugar - truth)
    assert abs(est.sugar - truth) <= 3.0
