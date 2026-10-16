"""Was über die Ansätze hinweg gelernt wird: Hauswerte und Nachkalkulation (docs/PLAN 3.4, Phase 5).

Jeder abgeschlossene Ansatz bringt Beobachtungen mit Unsicherheit mit. Der Hauswert ist das
Bayes-Mittel aus Startwert und allen Beobachtungen (Normalverteilungen, inverse Varianzen). Er wird
immer neu aus dem Archiv gerechnet: Ein gelöschter Ansatz nimmt seinen Beitrag mit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise
from statistics import median

from .composition import ABV_PARAM_SIGMA, G_SUGAR_PER_ABV
from .physics import FILL_MID

# Startwert und Unsicherheit (1σ) jedes Hauswerts, dazu die kleinste Unsicherheit einer Beobachtung
PRIORS: dict[str, tuple[float, float, float]] = {
    "saturation": (FILL_MID.saturation, 0.2, 0.05),  # gelöstes CO2 beim Abfüllen, aus Messflaschen
    "g_sugar_per_abv": (G_SUGAR_PER_ABV, ABV_PARAM_SIGMA["g_sugar_per_abv"], 0.1),  # aus Laborwerten
}
# Gerätewerte je Gärbox bzw. Spindel: Startwert, Unsicherheit und kleinste Unsicherheit einer Beobachtung.
# Genutzt werden sie erst, wenn mindestens ein Ansatz beigetragen hat (nie der reine Startwert).
DEVICE_PRIORS: dict[str, tuple[float, float, float]] = {
    "bubbles_per_g": (240.0, 240.0, 0.0),  # Blasen je g CO2; Röhrchen sind sehr verschieden
    "spindle_offset": (0.0, 0.005, 0.0005),  # relative Dichte
}
BUBBLES_REL_FLOOR = 0.15  # eine Gärbox-Eichung ist mindestens so unsicher (Röhrchen, Schaum, Kühlen)
HORIZONS_H = (48, 24, 12)  # Nachkalkulation: Prognosen so lange vor dem Durchgang
HORIZON_SLACK = timedelta(hours=4)  # so weit darf ein gespeicherter Prognose-Stand danebenliegen


@dataclass(frozen=True)
class HouseValue:
    mean: float
    sigma: float
    n: int  # Anzahl Ansätze, die beigetragen haben


def house_values(observations: dict[str, list[tuple[float, float]]]) -> dict[str, HouseValue]:
    """Bayes-Mittel je Hauswert aus Startwert und Beobachtungen (Wert, σ)."""
    out = {}
    for name, (m0, s0, floor) in PRIORS.items():
        w = 1.0 / s0**2
        acc = m0 * w
        obs = observations.get(name, [])
        for value, sigma in obs:
            wi = 1.0 / max(sigma, floor) ** 2
            w += wi
            acc += value * wi
        out[name] = HouseValue(acc / w, w**-0.5, len(obs))
    return out


def device_values(kind: str, observations: dict[str, list[tuple[float, float]]]) -> dict[str, HouseValue]:
    """Bayes-Mittel je Gerät (Gärbox-ID oder Spindel-Entität) aus Startwert und Beobachtungen."""
    m0, s0, floor = DEVICE_PRIORS[kind]
    out = {}
    for device, obs in observations.items():
        if not obs:
            continue
        w, acc = 1.0 / s0**2, m0 / s0**2
        for value, sigma in obs:
            sig = max(sigma, floor, BUBBLES_REL_FLOOR * abs(value) if kind == "bubbles_per_g" else 0.0)
            w += 1.0 / sig**2
            acc += value / sig**2
        out[device] = HouseValue(acc / w, w**-0.5, len(obs))
    return out


def crossing_time(series: list[tuple[datetime, float, float]], target: float) -> datetime | None:
    """Wann der Restzucker den Zielzucker unterschritten hat (Median über fünf Punkte gegen Rauschen)."""
    pts = sorted(series, key=lambda p: p[0])
    if len(pts) < 5:
        return None
    smooth = [(pts[i][0], median(p[1] for p in pts[i - 2 : i + 3])) for i in range(2, len(pts) - 2)]
    for (t0, s0), (t1, s1) in pairwise(smooth):
        if s0 > target >= s1:
            return t0 + (t1 - t0) * ((s0 - target) / (s0 - s1))
    return None


def forecast_check(
    snapshots: list[tuple[datetime, datetime, datetime | None, datetime | None]], crossing: datetime
) -> dict[int, dict[str, float | bool]]:
    """Nachkalkulation: Wie gut lag die Prognose 48, 24 und 12 h vor dem tatsächlichen Durchgang?

    snapshots: gespeicherte Prognose-Stände (Zeitpunkt, beste Zeit, Fensterbeginn, Fensterende).
    Ergebnis je Stunde: Fehler in Stunden (+ = Prognose zu spät) und ob das Fenster den Durchgang
    enthielt.
    """
    out: dict[int, dict[str, float | bool]] = {}
    for hours in HORIZONS_H:
        when = crossing - timedelta(hours=hours)
        near = [s for s in snapshots if abs(s[0] - when) <= HORIZON_SLACK and s[0] < crossing]
        if not near:
            continue
        _, best, start, end = min(near, key=lambda s: abs(s[0] - when))
        out[hours] = {
            "error_h": (best - crossing).total_seconds() / 3600.0,
            "inside": start is not None and end is not None and start <= crossing <= end,
        }
    return out
