"""Alkohol in der Flasche: Schätzer gegen Weine mit bekannter Wahrheit."""

from datetime import timedelta
import random
import statistics

import pytest

from core.composition import (
    ABV_PARAM_SIGMA,
    DSG_ETHANOL,
    K_ETHANOL_BRIX,
    PAIR_SIGMA_BRIX,
    PAIR_SIGMA_SG,
    WineModel,
    abv_label,
    bottle_abv,
    label_within,
)
from core.fermentation import Anchor, Settings, estimate
from simulator import SimConfig, simulate

DRY = 2.0


def _pairs(sim, days, seed=3):
    """Messpaare: Refraktometer und Hydrometer an derselben Probe."""
    rng = random.Random(seed)
    out = []
    for d in days:
        t = sim.start + timedelta(days=d)
        out.append((sim.refractometer(t, rng, PAIR_SIGMA_BRIX), sim.hydrometer(t, rng, PAIR_SIGMA_SG)))
    return out


@pytest.mark.parametrize(("value", "label"), [(11.24, 11.0), (11.26, 11.5), (11.74, 11.5), (11.76, 12.0), (12.0, 12.0)])
def test_label_rounds_to_half_percent(value, label):
    assert abv_label(value) == label


def test_label_within_tolerance():
    assert label_within(12.0, 12.0, 0.35, 0.8)
    assert not label_within(12.0, 12.0, 0.46, 0.8)  # ohne Messpaar zu unsicher für Pet Nat
    assert not label_within(12.0, 12.0, 0.31, 0.5)  # Stillwein braucht ein Labor
    assert not label_within(11.5, 11.74, 0.35, 0.8)  # die Rundung frisst Spielraum


def test_default_truth_without_pairs():
    sim = simulate()
    b = bottle_abv(WineModel.from_must(brix0=20.5), DRY)
    assert b.value == pytest.approx(sim.bottle_abv(DRY), abs=0.1)
    assert 0.35 < b.sigma < 0.6
    assert b.pairs == 0
    assert not b.label_ok


def test_early_pairs_change_nothing():
    sim = simulate()
    model = WineModel.from_must(brix0=20.5)
    assert all(sim.sugar_at(sim.start + timedelta(days=d)) > 0.5 * model.s0 for d in (1, 2, 3))
    assert bottle_abv(model, DRY, _pairs(sim, [1, 2, 3])) == bottle_abv(model, DRY)


@pytest.mark.parametrize("coeff", [1.02, 0.98])
def test_pairs_pull_toward_a_deviating_truth(coeff):
    sim = simulate(
        SimConfig(
            g_sugar_per_abv=17.6,
            fermentable_fraction=0.90,
            k_ethanol_brix=K_ETHANOL_BRIX * coeff,
            dsg_ethanol=DSG_ETHANOL / coeff,
        )
    )
    model = WineModel.from_must(brix0=20.5)
    truth = sim.bottle_abv(DRY)
    alone = bottle_abv(model, DRY)
    paired = bottle_abv(model, DRY, _pairs(sim, [8, 9, 10]))
    assert paired.pairs == 3
    assert abs(paired.value - truth) < abs(alone.value - truth)
    assert paired.sigma < alone.sigma
    assert abs(paired.value - truth) <= 2 * paired.sigma


@pytest.mark.parametrize("with_pairs", [False, True])
def test_uncertainty_is_honest(with_pairs):
    """Streut die Wahrheit so, wie der Schätzer annimmt, liegt sie in mindestens 90 % der Fälle in 2σ."""
    rng = random.Random(11)
    defaults = WineModel.from_must(brix0=20.0)
    hits, errors, n = 0, [], 200
    for _ in range(n):
        brix = rng.uniform(17, 24)
        truth = WineModel.from_must(
            brix0=brix,
            **{k: rng.gauss(getattr(defaults, k), s) for k, s in ABV_PARAM_SIGMA.items() if k != "brix0"},
        )
        model = WineModel.from_must(brix0=brix + rng.gauss(0, ABV_PARAM_SIGMA["brix0"]))
        pairs = []
        if with_pairs:  # Pet Nat kurz vor dem Abfüllen
            for frac in (0.15, 0.08):
                s = frac * truth.s0
                pairs.append(
                    (
                        truth.refractometer_reading(s) + rng.gauss(0, PAIR_SIGMA_BRIX),
                        truth.density(s) + rng.gauss(0, PAIR_SIGMA_SG),
                    )
                )
        b = bottle_abv(model, DRY, pairs)
        error = abs(b.value - truth.abv(DRY))
        errors.append(error)
        hits += error <= 2 * b.sigma
    assert hits / n >= 0.9
    rms = statistics.fmean(e * e for e in errors) ** 0.5
    assert rms < (0.4 if with_pairs else 0.5)


def test_estimate_has_bottle_abv_from_the_start():
    sim = simulate()
    e = estimate(WineModel.from_must(brix0=20.5), Settings(), sim.start, sim.start + timedelta(days=2))
    assert e.status == "waiting"
    assert e.abv_end == pytest.approx(sim.bottle_abv(DRY), abs=0.1)
    assert e.abv_label is not None
    assert e.abv_pairs == 0


def _paired_estimate(settings):
    sim = simulate()
    model = WineModel.from_must(brix0=20.5)
    now = sim.start + timedelta(days=10)
    anchors = []
    for d, (r, sg) in zip((8, 9, 10), _pairs(sim, [8, 9, 10])):
        sugar, _ = model.sugar_and_abv_from_pair(r, sg)
        anchors.append(Anchor(sim.start + timedelta(days=d), sugar, 1.2, "brix_density", (r, sg)))
    anchors.append(Anchor(now, 12.0, 2.5, "brix"))  # ohne Paar: zählt nicht für den Alkohol
    return estimate(model, settings, sim.start, now, anchors)


def test_estimate_counts_pairs_and_uses_the_right_tolerance():
    petnat = _paired_estimate(Settings(mode="petnat", target_bar_20c=2.5))
    assert petnat.abv_pairs == 3
    assert petnat.abv_label_ok  # Perlwein: ±0,8 % vol
    assert not _paired_estimate(Settings(mode="still")).abv_label_ok  # Stillwein: ±0,5 % vol
    assert not _paired_estimate(Settings(mode="petnat", target_bar_20c=0.8)).abv_label_ok  # unter 1 bar still


def test_drier_than_assumed_ends_there():
    """Ist der Wein schon trockener als der angenommene Endzucker, steigt der Alkohol nicht mehr."""
    sim = simulate(SimConfig(days=16, cool_at_sugar=None))
    model = WineModel.from_must(brix0=20.5)
    now = sim.start + timedelta(days=15)
    assert sim.sugar_at(now) < DRY
    r = sim.refractometer(now, random.Random(5), 0.0)
    e = estimate(model, Settings(mode="still"), sim.start, now, [Anchor(now, model.sugar_from_refractometer(r), 0.5)])
    assert e.abv_end == pytest.approx(e.abv, abs=0.01)
