import pytest

from core import units as u
from core.composition import WineModel


@pytest.mark.parametrize("brix", [0, 5, 12.5, 20, 24])
def test_brix_sg_roundtrip(brix):
    assert u.sg_to_brix(u.brix_to_sg(brix)) == pytest.approx(brix, abs=1e-6)


def test_known_values():
    assert u.brix_to_sg(20) == pytest.approx(1.083, abs=0.001)
    assert u.to_sg(83, "oe") == pytest.approx(1.083)
    assert u.sg_to_baume(u.baume_to_sg(11.5)) == pytest.approx(11.5)
    assert u.to_sg(0.99820, "gcm3") == pytest.approx(1.0)
    assert u.brix_from_solids(u.solids_from_brix(18.0)) == pytest.approx(18.0, abs=1e-6)
    with pytest.raises(ValueError):
        u.to_sg(1.0, "plato")


@pytest.fixture
def model():
    return WineModel.from_must(brix0=20.5)


def test_must_numbers(model):
    assert 195 < model.s0 < 215
    assert 11.5 < model.potential_abv < 13.0


@pytest.mark.parametrize("sugar", [190, 120, 40, 16, 6, 1])
def test_roundtrips(model, sugar):
    r, sg = model.refractometer_reading(sugar), model.density(sugar)
    assert model.sugar_from_refractometer(r) == pytest.approx(sugar, abs=1e-4)
    assert model.sugar_from_density(sg) == pytest.approx(sugar, abs=1e-4)
    s, abv = model.sugar_and_abv_from_pair(r, sg)
    assert s == pytest.approx(sugar, abs=1e-3)
    assert abv == pytest.approx(model.abv(sugar), abs=1e-4)


def test_dry_wine_is_plausible(model):
    # Trockener Wein: Refraktometer zeigt wegen Alkohol und Extrakt noch 5–8 °Bx, Dichte 0,990–0,997
    assert 5.5 < model.refractometer_reading(0.5) < 8.0
    assert 0.990 < model.density(0.5) < 0.997


def test_readings_increase_with_sugar(model):
    readings = [model.refractometer_reading(s) for s in range(0, 200, 10)]
    densities = [model.density(s) for s in range(0, 200, 10)]
    assert readings == sorted(readings)
    assert densities == sorted(densities)


def test_must_density_offset_is_respected():
    m = WineModel.from_must(brix0=20.5, sg0=1.0870)
    assert m.density(m.s0 * 0.999) == pytest.approx(1.0870, abs=0.0005)
