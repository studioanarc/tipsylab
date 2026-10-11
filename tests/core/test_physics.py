import importlib.util
import os

import pytest

from core import physics as ph

_spec = importlib.util.spec_from_file_location(
    "druckmodell", os.path.join(os.path.dirname(__file__), "..", "..", "tools", "druckmodell.py")
)
dm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dm)


def test_henry_values_match_plan():
    assert ph.henry(10) == pytest.approx(2.06, abs=0.01)
    assert ph.henry(12) == pytest.approx(1.91, abs=0.01)
    assert ph.henry(20) == pytest.approx(1.44, abs=0.01)


def test_henry_reproduces_independent_literature_value():
    # 8,4 g/L CO2 entsprechen laut Winegrowers 5,9 bar bei 20 °C
    assert 8.4 / ph.henry(20) == pytest.approx(5.9, rel=0.02)


@pytest.mark.parametrize("bottle", ["330", "750"])
@pytest.mark.parametrize("case", ["mittel", "unguenstig", "guenstig"])
@pytest.mark.parametrize("t_c", [10, 12, 20, 30])
@pytest.mark.parametrize("sugar", [0, 4, 8, 12, 20])
def test_bottle_pressure_matches_druckmodell(bottle, case, t_c, sugar):
    fill = {"mittel": ph.FILL_MID, "unguenstig": ph.FILL_WORST, "guenstig": ph.FILL_MILD}[case]
    ours = ph.bottle_pressure(sugar, t_c, ph.BOTTLES[bottle], fill)
    ref = dm.pet_nat_gauge(sugar, t_c, bottle=f"{bottle} ml", case=case)
    assert ours == pytest.approx(ref, abs=1e-9)


def test_plan_table_values():
    # Tabelle 2.3: 10 g/L -> 4,3 bar bei 20 °C (ungünstig), 2,5 bar laut Add-on
    assert ph.bottle_pressure(10, 20, fill=ph.FILL_WORST) == pytest.approx(4.26, abs=0.02)
    assert ph.sugar_for_pressure(2.5) == pytest.approx(6.5, abs=0.1)
    assert ph.sugar_for_pressure(2.5, fill=ph.FILL_WORST) == pytest.approx(4.4, abs=0.1)


def test_sugar_for_pressure_inverts_bottle_pressure():
    for target in (1.5, 2.5, 3.5):
        s = ph.sugar_for_pressure(target)
        assert ph.bottle_pressure(s, 20) == pytest.approx(target, abs=1e-6)


def test_malo_offset_and_extra_pressure():
    assert ph.malo_sugar_offset(1.0) == pytest.approx(0.7, abs=0.01)
    s = ph.sugar_for_pressure(2.5)
    extra = ph.bottle_pressure(s, 20, malic_g_l=2.0) - ph.bottle_pressure(s, 20)
    assert extra == pytest.approx(0.44, abs=0.02)


def test_charmat_setpoints_match_plan_table():
    co2 = ph.charmat_co2_target(2.5)
    assert ph.charmat_setpoint(co2, 12) == pytest.approx(1.86, abs=0.01)
    assert ph.charmat_setpoint(co2, 18) == pytest.approx(2.55, abs=0.01)
    for target in (2.0, 3.0, 4.0):
        for t_c in (8, 12, 18):
            assert ph.charmat_setpoint(ph.charmat_co2_target(target), t_c) == pytest.approx(
                dm.charmat_setpoint(target, t_c), abs=1e-9
            )


@pytest.mark.parametrize(
    ("p20", "cat"),
    [(0.5, "still"), (2.5, "semi_sparkling"), (2.7, "gap"), (3.2, "sparkling"), (4.0, "quality_sparkling")],
)
def test_eu_category(p20, cat):
    assert ph.eu_category(p20) == cat


def test_cooling_dissolves_co2():
    assert ph.solubility_change(15, 10) == pytest.approx(0.34, abs=0.01)
