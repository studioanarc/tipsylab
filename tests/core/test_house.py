"""Hauswerte und Nachkalkulation."""

from datetime import datetime, timedelta
import random

import pytest

from core.house import PRIORS, crossing_time, forecast_check, house_values

T0 = datetime(2026, 9, 1, 8, 0)


def test_without_observations_the_start_values_hold():
    values = house_values({})
    for name, (mean, sigma, _) in PRIORS.items():
        assert values[name].mean == pytest.approx(mean)
        assert values[name].sigma == pytest.approx(sigma)
        assert values[name].n == 0


def test_observations_pull_the_value_and_shrink_the_uncertainty():
    values = house_values({"saturation": [(1.0, 0.1), (1.0, 0.1)]})
    assert 0.95 < values["saturation"].mean < 1.0  # Startwert 0,8 zählt noch ein wenig
    assert values["saturation"].sigma < 0.08
    assert values["saturation"].n == 2


def test_a_very_sure_observation_is_capped():
    """Eine einzelne Messflasche darf den Hauswert nicht festnageln."""
    values = house_values({"saturation": [(1.2, 0.001)]})
    assert values["saturation"].sigma >= 0.045


def test_crossing_time_ignores_single_noisy_dips():
    rng = random.Random(3)
    series = []
    for h in range(110):
        s = 30.0 - 0.25 * h + rng.gauss(0, 0.3)
        if h == 20:
            s = 4.0  # einzelner Ausreißer weit unter dem Ziel
        series.append((T0 + timedelta(hours=h), s, 1.0))
    crossing = crossing_time(series, 6.5)
    assert abs(crossing - (T0 + timedelta(hours=94))) <= timedelta(hours=3)


def test_no_crossing_when_bottled_early():
    series = [(T0 + timedelta(hours=h), 30.0 - 0.1 * h, 1.0) for h in range(48)]
    assert crossing_time(series, 6.5) is None


def test_forecast_check_compares_48_24_12_hours_before():
    crossing = T0 + timedelta(days=5)
    snaps = []
    for h in range(0, 120, 2):
        t = T0 + timedelta(hours=h)
        best = crossing + timedelta(hours=6) * (1 - h / 120)  # anfangs 6 h zu spät, dann besser
        snaps.append((t, best, best - timedelta(hours=10), best + timedelta(hours=10)))
    check = forecast_check(snaps, crossing)
    assert set(check) == {48, 24, 12}
    assert check[48]["error_h"] == pytest.approx(2.4, abs=0.2)
    assert check[12]["error_h"] < check[48]["error_h"]
    assert all(c["inside"] for c in check.values())


def test_forecast_check_skips_missing_snapshots():
    crossing = T0 + timedelta(days=5)
    snaps = [(crossing - timedelta(hours=12), crossing, None, None)]
    check = forecast_check(snaps, crossing)
    assert set(check) == {12}
    assert check[12]["inside"] is False
