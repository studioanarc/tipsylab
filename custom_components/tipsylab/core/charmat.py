"""Charmat: Sollwert für den Tankdruck und Gärfortschritt aus der Druckbilanz (PLAN 3.9)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .physics import YIELD_CO2_SUGAR, charmat_co2_target, charmat_setpoint, co2_in_tank, dissolved_co2

SAFETY_MARGIN_BAR = 0.3


@dataclass(frozen=True)
class CharmatStatus:
    co2_target: float  # g/L im Tank
    setpoint: float  # bar Überdruck bei aktueller Tanktemperatur
    dissolved: float | None  # g/L, aus Ist-Druck und Temperatur
    margin_ok: bool  # Sollwert mindestens 0,3 bar unter dem Sicherheitsventil
    table: dict[int, float] = field(default_factory=dict)  # Sollwert je Tanktemperatur


def charmat_status(
    target_bar_20c: float,
    tank_c: float,
    p_tank: float | None = None,
    prv_bar: float | None = None,
    filling_loss: float = 0.08,
) -> CharmatStatus:
    co2 = charmat_co2_target(target_bar_20c, filling_loss)
    sp = charmat_setpoint(co2, tank_c)
    return CharmatStatus(
        co2_target=co2,
        setpoint=sp,
        dissolved=None if p_tank is None else dissolved_co2(p_tank, tank_c),
        margin_ok=prv_bar is None or sp <= prv_bar - SAFETY_MARGIN_BAR,
        table={t: round(charmat_setpoint(co2, t), 2) for t in (8, 10, 12, 15, 18)},
    )


def sugar_consumed(
    p_start: float,
    t_start: float,
    p_now: float,
    t_now: float,
    vented_g: float,
    wine_l: float,
    headspace_l: float,
) -> float:
    """Vergorener Zucker (g/L) seit dem Schließen des Tanks, aus der CO2-Bilanz.

    vented_g: CO2, das durch das Ventil entwichen ist (Summe der Druckabfälle je Puls).
    """
    produced = co2_in_tank(p_now, t_now, wine_l, headspace_l) - co2_in_tank(p_start, t_start, wine_l, headspace_l)
    produced += max(0.0, vented_g)
    return max(0.0, produced) / YIELD_CO2_SUGAR / wine_l
