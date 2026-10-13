"""Probabilistische Prognose (Stufe 2, docs/PLAN 3.4 und Phase 3): Monte Carlo auf der Stufe-1-Schätzung.

Gestreut werden der Restzucker jetzt, die Gärrate und ihre Drift, Q10 und die Kellertemperatur.
Jeder Zug rechnet analytisch, wann der Zielzucker erreicht ist; die Quantile ergeben das Fenster
P10–P90 und die beste Zeit P50. Die Streuungen sind im Simulator geeicht (tests/core/test_forecast.py):
Das Fenster aus Prognosen 48, 24 und 12 h vor dem Durchgang enthält ihn in mindestens 80 % der Fälle.

Die Rate darf sich ändern: k(τ) = k·exp(βτ) in thermischer Zeit τ. Gegen Ende gären manche Ansätze
schneller (die Hefe hat mehr Zucker pro Zelle übrig), andere langsamer (müde Hefe, Alkohol).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import pairwise
import math
import random

MC_SAMPLES = 300
MC_SEED = 7  # feste Züge: gleiche Eingaben ergeben dieselbe Prognose
RATE_REL_FLOOR = 0.25  # geeicht: ln(k_fit / k_wahr) streut im Simulator um 0,25–0,3
RATE_DRIFT_SIGMA = 0.1  # relative Änderung der Rate je thermischem Tag
SUGAR_SIGMA_FACTOR = 1.3  # Quellen hängen am selben Anker: der gemittelte Restzucker ist unsicherer, als σ sagt
Q10_SIGMA = 0.3
TEMP_SIGMA = 0.5  # °C, so weit weicht der Keller vom Plan ab
Q_LOW, Q_MID, Q_HIGH = 0.1, 0.5, 0.9
GAIN_MIN_HOURS = 4.0  # ab so viel engerem Fenster lohnt eine Messung
GAIN_MIN_FRACTION = 0.25


@dataclass(frozen=True)
class Draw:
    sugar: float
    k: float  # je thermischem Tag
    beta: float  # Drift der Rate je thermischem Tag
    q10: float
    d_temp: float


@dataclass
class Forecast:
    p10: datetime | None = None
    p50: datetime | None = None
    p90: datetime | None = None
    band: list[tuple[datetime, float, float, float]] = field(default_factory=list)  # (t, P50, P90, P10)


def draws(
    s_now: float, sigma: float, k: float, rel: float, q10: float, n: int = MC_SAMPLES, seed: int = MC_SEED
) -> list[Draw]:
    rng = random.Random(seed)
    rel_total = math.hypot(rel, RATE_REL_FLOOR)
    out = []
    for _ in range(n):
        out.append(
            Draw(
                sugar=max(0.1, rng.gauss(s_now, sigma * SUGAR_SIGMA_FACTOR)),
                k=k * math.exp(rng.gauss(0.0, rel_total)),
                beta=rng.gauss(0.0, RATE_DRIFT_SIGMA),
                q10=max(1.2, rng.gauss(q10, Q10_SIGMA)),
                d_temp=rng.gauss(0.0, TEMP_SIGMA),
            )
        )
    return out


def tau_to(s0: float, s: float, k: float, beta: float) -> float:
    """Thermische Tage, bis S von s0 auf s fällt, wenn k(τ) = k·exp(βτ); unendlich, wenn nie."""
    if s >= s0:
        return 0.0
    log_ratio = math.log(s0 / max(s, 1e-6))
    if abs(beta) < 1e-9:
        return log_ratio / k
    arg = 1.0 + beta * log_ratio / k
    return math.log(arg) / beta if arg > 0 else math.inf


def sugar_after(s0: float, tau: float, k: float, beta: float) -> float:
    """Restzucker nach τ thermischen Tagen (Umkehrung von tau_to)."""
    if abs(beta) < 1e-9:
        return s0 * math.exp(-k * tau)
    return s0 * math.exp(-k * (math.exp(beta * tau) - 1.0) / beta)


def _factor(draw: Draw, temp: float | None, temp_now: float | None, q10: float) -> float:
    """Thermischer Faktor eines Zugs bei einer geplanten Temperatur.

    Die Rate ist bei temp_now gemessen; weicht Q10 ab, stimmt sie bei anderen Temperaturen um
    (q10_zug / q10) ** ((temp − temp_now) / 10) nicht.
    """
    if temp is None:
        return 1.0
    f = q10 ** ((temp + draw.d_temp - 15.0) / 10.0)
    if temp_now is not None:
        f *= (draw.q10 / q10) ** ((temp - temp_now) / 10.0)
    return f


def days_to(draw: Draw, target: float, plan_temp, temp_now: float | None, q10: float, thresholds: list[float]) -> float:
    """Kalendertage, bis ein Zug den Zielzucker erreicht: Temperaturplan stückweise, Zeit analytisch."""
    if target >= draw.sugar:
        return 0.0
    cuts = sorted((th for th in thresholds if target < th < draw.sugar), reverse=True)
    days, tau_prev = 0.0, 0.0
    for a, b in pairwise([draw.sugar, *cuts, target]):
        tau_b = tau_to(draw.sugar, b, draw.k, draw.beta)
        if math.isinf(tau_b):
            return math.inf
        days += (tau_b - tau_prev) / _factor(draw, plan_temp((a + b) / 2), temp_now, q10)
        tau_prev = tau_b
    return days


def _quantile(sorted_vals: list[float], p: float) -> float:
    return sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))]


def crossing_quantiles(
    sample: list[Draw], target: float, plan_temp, temp_now: float | None, q10: float, thresholds: list[float]
) -> tuple[float, float, float]:
    """P10, P50, P90 der Tage bis zum Zielzucker (unendlich, wenn nie)."""
    days = sorted(days_to(d, target, plan_temp, temp_now, q10, thresholds) for d in sample)
    return _quantile(days, Q_LOW), _quantile(days, Q_MID), _quantile(days, Q_HIGH)


def forecast(
    now: datetime,
    s_now: float,
    sigma: float,
    k: float,
    rel: float,
    target: float,
    plan_temp,
    temp_now: float | None,
    q10: float,
    thresholds: list[float],
    horizon: timedelta,
    until: datetime | None = None,
    step: timedelta = timedelta(hours=1),
) -> Forecast:
    """Fenster P10–P90, beste Zeit P50 und das Band des Restzuckers bis `until`."""
    sample = draws(s_now, sigma, k, rel, q10)
    q = crossing_quantiles(sample, target, plan_temp, temp_now, q10, thresholds)
    out = Forecast(*(now + timedelta(days=d) if d * 86400 <= horizon.total_seconds() else None for d in q))
    if until is None:
        return out
    # Band: jeder Zug stündlich vorwärts, Temperatur nach Plan und dem eigenen Restzucker
    step_days = step.total_seconds() / 86400.0
    n_steps = max(1, math.ceil((until - now) / step))
    paths = []
    for d in sample:
        tau, s, path = 0.0, d.sugar, [d.sugar]
        for _ in range(n_steps):
            tau += _factor(d, plan_temp(s), temp_now, q10) * step_days
            s = sugar_after(d.sugar, tau, d.k, d.beta)
            path.append(s)
        paths.append(path)
    for i in range(n_steps + 1):
        col = sorted(p[i] for p in paths)
        out.band.append((now + step * i, _quantile(col, Q_MID), _quantile(col, Q_HIGH), _quantile(col, Q_LOW)))
    return out


def window_hours(p10: datetime | None, p90: datetime | None) -> float | None:
    if p10 is None or p90 is None:
        return None
    return (p90 - p10).total_seconds() / 3600.0


def measurement_gain(
    s_now: float,
    sigma: float,
    sigma_measure: float,
    k: float,
    rel: float,
    target: float,
    plan_temp,
    temp_now: float | None,
    q10: float,
    thresholds: list[float],
) -> tuple[float, float] | None:
    """Halbe Fensterbreite (h) jetzt und nach einer Messung mit sigma_measure (erwarteter Gewinn)."""
    after = 1.0 / math.sqrt(1.0 / sigma**2 + 1.0 / sigma_measure**2)
    widths = []
    for sig in (sigma, after):
        p10, _, p90 = crossing_quantiles(draws(s_now, sig, k, rel, q10), target, plan_temp, temp_now, q10, thresholds)
        if math.isinf(p90):
            return None
        widths.append((p90 - p10) * 12.0)  # Tage → halbe Breite in Stunden
    return widths[0], widths[1]


def worth_measuring(gain: tuple[float, float] | None) -> bool:
    if gain is None:
        return False
    before, after = gain
    return before - after >= GAIN_MIN_HOURS and (before - after) >= GAIN_MIN_FRACTION * before


def chance_above(s_now: float, sigma: float, sugar_limit: float) -> float:
    """Wahrscheinlichkeit, dass der wahre Restzucker über sugar_limit liegt (Normalverteilung)."""
    sig = sigma * SUGAR_SIGMA_FACTOR
    return 0.5 * (1.0 - math.erf((sugar_limit - s_now) / (sig * math.sqrt(2.0))))
