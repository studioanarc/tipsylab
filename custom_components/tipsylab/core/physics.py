"""CO2-Physik für Pet Nat und Charmat.

Henry-Konstante und Flaschendruck nach Liger-Belair et al. (2013), J. Food Eng. 116, 78–85
(Henry-Konstante für Champagner aus den Daten von Agabaliantz 1963). Die Konstanten sind
Startwerte; Messflaschen eichen die Annahmen zum Abfüllen (Sättigung, Kopfraum) pro Haus.

Alle Drücke in bar Überdruck, wenn nicht anders angegeben.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

R = 8.314  # J/(mol K)
P_ATM = 1.013  # bar
K298 = 1.21  # g/(L bar), Henry-Konstante CO2 in Champagner bei 25 °C
DH_DISS = 24_800.0  # J/mol, Lösungsenthalpie CO2
YIELD_CO2_SUGAR = 0.47  # g CO2 je g vergorenem Zucker (theoretisch 0,489)
YIELD_CO2_MALIC = 0.328  # g CO2 je g abgebauter Äpfelsäure (C4H6O5 -> C3H6O3 + CO2)


def henry(t_c: float, k298: float = K298) -> float:
    """Henry-Konstante in g/(L·bar) bei t_c °C (Van-'t-Hoff-Form)."""
    t_k = t_c + 273.15
    return k298 * math.exp(DH_DISS / R * (1.0 / t_k - 1.0 / 298.15))


@dataclass(frozen=True)
class Bottle:
    """Flasche: Weinvolumen und Kopfraum in Litern, Belastungsgrenze in bar."""

    wine_l: float
    headspace_l: float
    limit_bar: float


BOTTLES: dict[str, Bottle] = {
    "330": Bottle(0.318, 0.012, 4.5),
    "750": Bottle(0.730, 0.020, 6.0),
}


@dataclass(frozen=True)
class FillConditions:
    """Zustand beim Abfüllen.

    saturation:   gelöstes CO2 relativ zur Sättigung bei 1 bar CO2 (frisch gärend ~0,8–1,2)
    air_fraction: Anteil Luft (N2) im Kopfraum beim Verschließen, relativ zu 1 atm
    t_bottling_c: Weintemperatur beim Abfüllen
    """

    saturation: float = 0.8
    air_fraction: float = 0.4
    t_bottling_c: float = 12.0


FILL_MID = FillConditions()
FILL_WORST = FillConditions(saturation=1.0, air_fraction=0.79)
FILL_MILD = FillConditions(saturation=0.6, air_fraction=0.0)


def bottle_pressure(
    sugar_g_l: float,
    t_c: float,
    bottle: Bottle = BOTTLES["750"],
    fill: FillConditions = FILL_MID,
    malic_g_l: float = 0.0,
    *,
    k298: float = K298,
    yield_sugar: float = YIELD_CO2_SUGAR,
) -> float:
    """Überdruck (bar) bei t_c, wenn der vergärbare Restzucker vollständig vergärt.

    malic_g_l: Äpfelsäure, die erst in der Flasche abgebaut wird (Malo nach dem Abfüllen).
    """
    c0 = fill.saturation * henry(fill.t_bottling_c, k298)  # g/L CO2 beim Abfüllen
    m = bottle.wine_l * (c0 + yield_sugar * max(0.0, sugar_g_l) + YIELD_CO2_MALIC * max(0.0, malic_g_l))
    t_k = t_c + 273.15
    p_co2 = m * R * t_k / (4.4e3 * bottle.headspace_l + henry(t_c, k298) * R * t_k * bottle.wine_l)
    p_air = fill.air_fraction * P_ATM * t_k / (fill.t_bottling_c + 273.15)
    return p_co2 + p_air - P_ATM


def sugar_for_pressure(
    target_bar: float,
    t_c: float = 20.0,
    bottle: Bottle = BOTTLES["750"],
    fill: FillConditions = FILL_MID,
    malic_g_l: float = 0.0,
) -> float:
    """Vergärbarer Restzucker (g/L) beim Abfüllen, der bei t_c den Ziel-Überdruck ergibt."""
    lo, hi = 0.0, 120.0
    if bottle_pressure(lo, t_c, bottle, fill, malic_g_l) >= target_bar:
        return 0.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if bottle_pressure(mid, t_c, bottle, fill, malic_g_l) > target_bar:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def malo_sugar_offset(malic_g_l: float) -> float:
    """Wie viel weniger Restzucker (g/L) die Malo in der Flasche ausgleicht."""
    return YIELD_CO2_MALIC * max(0.0, malic_g_l) / YIELD_CO2_SUGAR


def eu_category(p20_bar: float) -> str:
    """EU-Kategorie nach Überdruck bei 20 °C (VO 1308/2013, Anhang VII Teil II)."""
    if p20_bar < 1.0:
        return "still"
    if p20_bar <= 2.5:
        return "semi_sparkling"  # frisante / pétillant / Perlwein
    if p20_bar < 3.0:
        return "gap"  # keine Kategorie
    if p20_bar < 3.5:
        return "sparkling"  # espumante / mousseux / Schaumwein
    return "quality_sparkling"


def dissolved_co2(p_gauge_bar: float, t_c: float) -> float:
    """Gelöstes CO2 (g/L) im Gleichgewicht mit reinem CO2 im Kopfraum."""
    return henry(t_c) * max(0.0, p_gauge_bar + P_ATM)


def solubility_change(t_from_c: float, t_to_c: float) -> float:
    """Wie viel CO2 (g/L) ein gesättigter Wein beim Temperaturwechsel aufnimmt (+) oder abgibt (−)."""
    return henry(t_to_c) - henry(t_from_c)


def charmat_co2_target(target_bar_20c: float, filling_loss: float = 0.08) -> float:
    """CO2-Gehalt (g/L) im Tank, der nach isobarer Abfüllung den Zieldruck bei 20 °C ergibt."""
    return henry(20.0) * (target_bar_20c + P_ATM) / (1.0 - filling_loss)


def charmat_setpoint(co2_target_g_l: float, tank_c: float) -> float:
    """Tank-Sollwert (bar Überdruck) für einen CO2-Gehalt bei Tanktemperatur.

    Annahmen: Kopfraum mit Gär-CO2 gespült, Gleichgewicht zwischen Gas und Wein.
    """
    return co2_target_g_l / henry(tank_c) - P_ATM


def co2_in_tank(p_gauge_bar: float, t_c: float, wine_l: float, headspace_l: float) -> float:
    """CO2-Masse (g) in einem geschlossenen Tank im Gleichgewicht (gelöst + Gasraum)."""
    p_abs = max(0.0, p_gauge_bar + P_ATM)
    t_k = t_c + 273.15
    dissolved = henry(t_c) * p_abs * wine_l
    gas = p_abs * 1e5 * headspace_l * 1e-3 * 44.01 / (R * t_k)
    return dissolved + gas
