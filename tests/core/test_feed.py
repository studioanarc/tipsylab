"""DataWein-Feed: nur öffentliche, gerundete Zahlen."""

from datetime import timedelta
import json
import random

from core.composition import WineModel
from core.feed import HISTORY_POINTS, feed, feed_entry
from core.fermentation import Anchor, Settings, estimate
from simulator import SimConfig, simulate


def _est(day: float = 8.0):
    sim = simulate(SimConfig())
    now = sim.start + timedelta(days=day)
    rng = random.Random(1)
    anchors = [
        Anchor(sim.start + timedelta(days=d), sim.model.sugar_from_refractometer(sim.refractometer(sim.start + timedelta(days=d), rng, 0.1)), 2.5)
        for d in range(1, int(day) + 1)
    ]
    upto = lambda xs: [x for x in xs if x[0] <= now]  # noqa: E731
    est = estimate(sim.model, Settings(), sim.start, now, anchors, upto(sim.gravity), upto(sim.bubbles), upto(sim.temps))
    return sim, now, est


def test_entry_has_the_numbers_of_the_page():
    sim, now, est = _est()
    entry = feed_entry("DATA Rosé 2026", "petnat", sim.start, now, est, sim.model, 12.4, 12.06)
    assert entry["day"] == 8
    assert entry["bpm"] == 12
    assert entry["temp"] == 12.1
    assert entry["sugar"] == round(est.sugar, 1)
    assert 0.99 < entry["sg"] < 1.05
    assert len(entry["history"]) <= HISTORY_POINTS
    assert entry["history"][-1][1] < entry["history"][0][1]  # Dichte fällt


def test_nothing_private_leaks():
    sim, now, est = _est()
    entry = feed_entry("x" * 200, "petnat", sim.start, now, est, sim.model, None, None)
    text = json.dumps(feed([entry], now))
    assert len(entry["name"]) == 60
    for word in ("entity", "sensor.", "tipsy-", "192.168", "device", "host"):
        assert word not in text


def test_without_estimate_only_the_basics():
    model = WineModel.from_must(brix0=20.5)
    sim, now, _ = _est()
    entry = feed_entry("Branco", "still", sim.start, now, None, model, None, 14.0)
    assert entry["status"] == "waiting"
    assert "sugar" not in entry
