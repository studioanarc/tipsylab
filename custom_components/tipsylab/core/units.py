"""Umrechnungen für Most und Wein: Brix, Dichte, Oechsle, Baumé."""

from __future__ import annotations

WATER_DENSITY_20C = 0.99820  # g/cm³


def brix_to_sg(brix: float) -> float:
    """Relative Dichte (20/20 °C) einer Saccharoselösung (NBS-Näherung)."""
    return 1.0 + brix / (258.6 - (brix / 258.2) * 227.1)


def sg_to_brix(sg: float) -> float:
    """Umkehrung von brix_to_sg (Newton-Verfahren)."""
    brix = (sg - 1.0) * 250.0
    for _ in range(30):
        f = brix_to_sg(brix) - sg
        d = (brix_to_sg(brix + 1e-3) - brix_to_sg(brix - 1e-3)) / 2e-3
        if d == 0:
            break
        step = f / d
        brix -= step
        if abs(step) < 1e-9:
            break
    return brix


def solids_from_brix(brix: float) -> float:
    """Gelöste Stoffe in g/L für eine Lösung mit gegebenem Brix (Brix = Massenprozent)."""
    return brix * 10.0 * brix_to_sg(brix)


def brix_from_solids(solids_g_l: float) -> float:
    """Brix einer Lösung mit solids_g_l gelösten Stoffen (Umkehrung von solids_from_brix)."""
    if solids_g_l <= 0:
        return 0.0
    lo, hi = 0.0, 80.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if solids_from_brix(mid) > solids_g_l:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def oechsle_to_sg(oechsle: float) -> float:
    return 1.0 + oechsle / 1000.0


def sg_to_oechsle(sg: float) -> float:
    return (sg - 1.0) * 1000.0


def baume_to_sg(baume: float) -> float:
    """Baumé-Skala für Flüssigkeiten schwerer als Wasser (°Bé = 145 − 145/SG)."""
    return 145.0 / (145.0 - baume)


def sg_to_baume(sg: float) -> float:
    return 145.0 - 145.0 / sg


def density_to_sg(g_per_cm3: float) -> float:
    """Dichte bei 20 °C (g/cm³) in relative Dichte 20/20."""
    return g_per_cm3 / WATER_DENSITY_20C


def to_sg(value: float, unit: str) -> float:
    """Dichteangabe in relative Dichte umrechnen. unit: sg | oe | baume | gcm3."""
    unit = unit.lower()
    if unit == "sg":
        return value
    if unit in ("oe", "oechsle"):
        return oechsle_to_sg(value)
    if unit in ("baume", "be"):
        return baume_to_sg(value)
    if unit in ("gcm3", "g/cm3", "density"):
        return density_to_sg(value)
    raise ValueError(f"Unbekannte Dichte-Einheit: {unit}")
