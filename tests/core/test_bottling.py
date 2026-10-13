"""Nach dem Abfüllen: Messflasche gegen eine simulierte Flaschengärung mit bekannter Wahrheit."""

from datetime import datetime, timedelta

import pytest

from core.bottling import (
    ACTION_DANGER,
    ACTION_HIGH,
    Bottling,
    bottle_status,
    co2_in_bottle,
    fill_conditions,
    observed_saturation,
    pressure_at_20,
    pressure_from_co2,
)
from core.physics import BOTTLES, FILL_MID, FILL_MILD, FILL_WORST, bottle_pressure, sugar_for_pressure
from simulator import simulate_bottle

START = datetime(2026, 9, 20, 10, 0)
TARGET_SUGAR = sugar_for_pressure(2.5, 20.0, BOTTLES["750"], FILL_MID)


def _bottling(sugar=TARGET_SUGAR, sigma=1.0, saturation=0.8, malic=0.0):
    return Bottling(START, sugar, sigma, "750", malic, 12.0, saturation)


@pytest.mark.parametrize("p", [0.0, 1.2, 2.5, 4.0])
@pytest.mark.parametrize("t_c", [4.0, 10.0, 20.0, 28.0])
def test_co2_and_pressure_are_inverse(p, t_c):
    b = BOTTLES["750"]
    assert pressure_from_co2(co2_in_bottle(p, t_c, b, FILL_MID), t_c, b, FILL_MID) == pytest.approx(p, abs=1e-9)


def test_pressure_model_matches_physics():
    """Volle Vergärung über bottle_pressure und über die CO2-Bilanz ergibt denselben Druck."""
    b = _bottling(sugar=8.0)
    co2 = b.co2_start + b.co2_to_come
    for t_c in (10.0, 20.0):
        assert pressure_from_co2(co2, t_c, b.flask, b.fill) == pytest.approx(b.expected(t_c), abs=1e-9)
        assert b.expected(t_c) == pytest.approx(bottle_pressure(8.0, t_c, BOTTLES["750"], FILL_MID), abs=1e-9)


def test_cold_reading_is_higher_at_20():
    b = BOTTLES["750"]
    assert pressure_at_20(2.0, 10.0, b, FILL_MID) > 2.0
    assert pressure_at_20(2.0, 20.0, b, FILL_MID) == pytest.approx(2.0, abs=1e-9)


def test_learned_saturation_never_softens_the_worst_case():
    assert fill_conditions() == (FILL_MID, FILL_WORST, FILL_MILD)
    mid, worst, mild = fill_conditions(1.1)
    assert mid.saturation == 1.1
    assert worst.saturation == pytest.approx(1.3)  # immer über dem gelernten Wert
    assert mild.saturation <= mid.saturation
    assert fill_conditions(0.5)[1].saturation == FILL_WORST.saturation  # nie milder als FILL_WORST


def test_as_expected_is_ok_and_finishes():
    status = bottle_status(_bottling(), simulate_bottle(TARGET_SUGAR, start=START), START + timedelta(days=36))
    assert status.state == "ok"
    assert not status.alarm
    assert status.latest.p20 == pytest.approx(status.expected_20, abs=0.15)
    assert status.progress == pytest.approx(1.0, abs=0.1)
    assert status.done


def test_progress_grows_and_is_not_done_early():
    readings = simulate_bottle(TARGET_SUGAR, start=START, days=(3, 7))
    status = bottle_status(_bottling(), readings, START + timedelta(days=8))
    assert 0.5 < status.progress < 0.9
    assert not status.done


def test_more_sugar_than_estimated_raises_the_alarm():
    readings = simulate_bottle(TARGET_SUGAR + 3.0, start=START)
    status = bottle_status(_bottling(), readings, START + timedelta(days=36))
    assert status.state == "high"
    assert status.alarm
    assert status.action == ACTION_HIGH
    # früh genug: schon nach einer Woche über dem erwarteten Enddruck
    early = bottle_status(_bottling(), readings[:3], START + timedelta(days=15))
    assert early.alarm


def test_near_the_bottle_limit_is_danger():
    status = bottle_status(_bottling(), simulate_bottle(TARGET_SUGAR + 12.0, start=START), START + timedelta(days=36))
    assert status.state == "danger"
    assert status.action == ACTION_DANGER


def test_missing_temperature_counts_as_cold():
    b = _bottling()
    t = START + timedelta(days=10)
    with_temp = bottle_status(b, [(t, 2.0, 20.0)], t)
    without = bottle_status(b, [(t, 2.0, None)], t)
    assert without.latest.p20 > with_temp.latest.p20


def test_readings_before_bottling_are_ignored():
    status = bottle_status(_bottling(), [(START - timedelta(days=1), 5.0, 20.0)], START + timedelta(days=1))
    assert status.latest is None
    assert status.state == "wait"


@pytest.mark.parametrize("true_saturation", [0.6, 0.8, 1.05])
def test_measurement_bottle_learns_the_saturation(true_saturation):
    """Am Ende eicht die Messflasche die Sättigung beim Abfüllen (bekannte Wahrheit)."""
    readings = simulate_bottle(TARGET_SUGAR, saturation=true_saturation, start=START, noise_bar=0.02)
    status = bottle_status(_bottling(), readings, START + timedelta(days=36))
    value, sigma = observed_saturation(status)
    assert value == pytest.approx(true_saturation, abs=0.05)  # Zucker beim Abfüllen hier exakt bekannt
    assert 0.05 < sigma < 0.5


def test_no_saturation_before_the_end():
    status = bottle_status(_bottling(), simulate_bottle(TARGET_SUGAR, start=START, days=(3, 7)), START + timedelta(days=8))
    assert observed_saturation(status) is None


@pytest.mark.parametrize("extra_sugar", [-5.0, 6.0])
def test_implausible_bottles_teach_nothing(extra_sugar):
    """Steckt die Flaschengärung oder war viel mehr Zucker drin, lernt der Hauswert nichts daraus."""
    readings = simulate_bottle(TARGET_SUGAR + extra_sugar, start=START, noise_bar=0.02)
    status = bottle_status(_bottling(), readings, START + timedelta(days=36))
    assert status.done
    assert observed_saturation(status) is None
