"""Gärschätzung und Abfüllprognose (Stufe 1, siehe docs/PLAN Abschnitt 3.4).

Vorgehen
1. Anker: Messungen (Refraktometer, Dichte, Labor) und der Start-Brix setzen Zucker S und σ.
2. Spindel: Ihr Versatz wird an jedem Anker neu bestimmt; dazwischen liefert sie S(t).
3. Blasen: Zwischen den letzten beiden Ankern wird geeicht, wie viel Zucker eine Blase
   bedeutet; danach liefern die Blasen S(t).
4. Waage: Gewichtsverlust ist entwichenes CO2. Mit dem Volumen ergibt das den vergorenen Zucker
   direkt (0,47 g CO2 je g Zucker); liegen zwei Anker im Verlauf, wird stattdessen zwischen ihnen
   geeicht. Gelöstes CO2 (Sättigung, Rücklösung beim Kühlen) wird mitgerechnet, Sprünge durch
   Proben oder Abstiche herausgerechnet.
5. Jetzt-Wert: gewichteter Mittelwert der verfügbaren Schätzungen (inverse Varianz).
6. Prognose: S fällt in der späten Phase etwa exponentiell. Gerechnet wird in thermischer
   Zeit (Q10-Skalierung), damit Temperatur und Temperaturplan die Prognose verschieben.
7. Fenster: Zeitpunkte, an denen S den Zielzucker ± Unsicherheit erreicht.

Alles ohne numpy und ohne Home Assistant, damit es direkt testbar ist.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
from statistics import median

from .composition import ABV_TOLERANCE_SPARKLING, ABV_TOLERANCE_STILL, BottleAbv, WineModel, bottle_abv
from .physics import (
    BOTTLES,
    FILL_MID,
    FILL_WORST,
    YIELD_CO2_SUGAR,
    bottle_pressure,
    eu_category,
    henry,
    sugar_for_pressure,
)

T_REF = 15.0  # °C, Bezug der thermischen Zeit
SIGMA = {"start": 1.0, "brix": 2.5, "sg": 1.5, "brix_sg": 1.2, "sugar": 0.5}
SPINDLE_SIGMA = 2.0  # g/L direkt nach dem Abgleich an einem Anker
SPINDLE_SIGMA_UNCALIBRATED = 4.0
SPINDLE_DRIFT_PER_DAY = 0.5  # g/L Zuwachs je Tag seit dem Abgleich
BUBBLE_REL_SIGMA = 0.25  # relative Unsicherheit der geeichten Blasen
FRESH = timedelta(hours=3)  # so alt darf ein Sensorwert für den Jetzt-Wert sein
MAX_FORECAST = timedelta(days=30)
SOON = timedelta(hours=72)
DECLINE_FRACTION = 0.5  # Prognose nur aus Punkten unter 50 % des Startzuckers
FIT_HALF_LIFE = 1.0  # thermische Tage: jüngere Punkte zählen mehr (die Hefe ändert ihr Tempo)
FIT_HORIZON = 4.0  # thermische Tage zurück
WEIGHT_NOISE = 2e-5  # Rauschen der Waage, Anteil der Anzeige (500-kg-Zelle: ~10 g)
WEIGHT_DRIFT_PER_DAY = 5e-5  # Drift der Waage je Tag, Anteil der Anzeige
WEIGHT_REL_SIGMA_THEO = 0.07  # Volumen (±3 %), CO2-Ausbeute (±3 %), Eichung und Verdunstung
WEIGHT_REL_SIGMA_CAL = 0.10  # zwischen zwei Ankern geeicht
WEIGHT_DISSOLVED_SIGMA = 0.3  # g/L Zucker: wie weit die CO2-Sättigung danebenliegen kann
PEAK_SUGAR_RATE = 30.0  # g/L am Tag: schneller vergärt kein Ansatz; schnellere Gewichtsänderung ist ein Sprung
FORECAST_TAIL = timedelta(hours=12)  # so weit reicht die Kurve über das Fensterende hinaus
FORECAST_MAX = timedelta(days=10)


@dataclass(frozen=True)
class Anchor:
    """Zuckerwert aus einer Messung."""

    t: datetime
    sugar: float
    sigma: float
    kind: str = "brix"
    pair: tuple[float, float] | None = None  # Refraktometer °Bx und relative Dichte derselben Probe


@dataclass(frozen=True)
class Settings:
    mode: str = "petnat"  # petnat | still | charmat
    target_bar_20c: float = 2.5
    bottle: str = "750"
    malo_in_bottle: bool = False
    malic_g_l: float = 0.0
    q10: float = 2.2
    dry_sugar_g_l: float = 2.0
    volume_l: float | None = None  # für die Waage: Gewichtsverlust je Liter
    # Temperaturplan: Schritte (ab Restzucker g/L oder None für den Start, °C), z. B.
    # ((None, 20.0), (25.0, 14.0)) = 20 °C, ab 25 g/L 14 °C
    temp_plan: tuple[tuple[float | None, float], ...] = ()

    def malic(self) -> float:
        return self.malic_g_l if self.malo_in_bottle else 0.0

    def target_sugar(self) -> float:
        if self.mode == "still":
            return self.dry_sugar_g_l
        return sugar_for_pressure(self.target_bar_20c, 20.0, BOTTLES[self.bottle], FILL_MID, self.malic())

    def planned_temp(self, sugar: float, default: float | None) -> float | None:
        temp = default
        for threshold, t_c in self.temp_plan:
            if threshold is None or sugar <= threshold:
                temp = t_c
        return temp


def thermal_factor(t_c: float | None, q10: float) -> float:
    if t_c is None:
        return 1.0
    return q10 ** ((t_c - T_REF) / 10.0)


class Series:
    """Zeitreihe (t, Wert), stückweise konstant."""

    def __init__(self, points: list[tuple[datetime, float]] | None = None):
        pts = sorted(points or [], key=lambda p: p[0])
        self.t = [p[0] for p in pts]
        self.v = [p[1] for p in pts]

    def __bool__(self) -> bool:
        return bool(self.t)

    def at(self, t: datetime) -> float | None:
        if not self.t:
            return None
        i = bisect_right(self.t, t) - 1
        return self.v[max(i, 0)]

    def latest(self) -> tuple[datetime, float] | None:
        return (self.t[-1], self.v[-1]) if self.t else None

    def window(self, a: datetime, b: datetime) -> list[float]:
        i, j = bisect_right(self.t, a), bisect_right(self.t, b)
        return self.v[i:j]

    def interpolate(self, t: datetime) -> float | None:
        if not self.t:
            return None
        i = bisect_right(self.t, t)
        if i == 0:
            return self.v[0]
        if i >= len(self.t):
            return self.v[-1]
        t0, t1, v0, v1 = self.t[i - 1], self.t[i], self.v[i - 1], self.v[i]
        span = (t1 - t0).total_seconds()
        return v0 if span <= 0 else v0 + (v1 - v0) * (t - t0).total_seconds() / span


def thermal_days(temps: Series, a: datetime, b: datetime, q10: float, default: float | None) -> float:
    """Thermische Zeit zwischen a und b in Tagen (Temperatur stückweise konstant)."""
    if b <= a:
        return 0.0
    edges = [a] + [t for t in temps.t if a < t < b] + [b]
    total = 0.0
    for t0, t1 in zip(edges, edges[1:]):
        temp = temps.at(t0) if temps else default
        total += thermal_factor(temp if temp is not None else default, q10) * (t1 - t0).total_seconds() / 86400.0
    return total


@dataclass(frozen=True)
class DecayFit:
    k: float  # je thermischem Tag
    rel_err: float
    n: int


def fit_decay(points: list[tuple[float, float, float]], tau_now: float | None = None) -> DecayFit | None:
    """ln S = a − k·τ, gewichtet mit (S/σ)² und dem Alter der Punkte.

    points: (τ in thermischen Tagen, S, σ). Mit tau_now zählen jüngere Punkte mehr
    (Halbwertszeit FIT_HALF_LIFE), ältere als FIT_HORIZON fallen weg.
    """
    pts = []
    for tau, s, sig in points:
        if s <= 1.0:
            continue
        w = (s / max(sig, 0.1)) ** 2
        if tau_now is not None:
            age = tau_now - tau
            if age > FIT_HORIZON:
                continue
            w *= 0.5 ** (max(0.0, age) / FIT_HALF_LIFE)
        pts.append((tau, math.log(s), w))
    if len(pts) < 3:
        return None
    taus = [p[0] for p in pts]
    if max(taus) - min(taus) < 0.25:
        return None
    sw = sum(p[2] for p in pts)
    mx = sum(p[2] * p[0] for p in pts) / sw
    my = sum(p[2] * p[1] for p in pts) / sw
    sxx = sum(p[2] * (p[0] - mx) ** 2 for p in pts)
    sxy = sum(p[2] * (p[0] - mx) * (p[1] - my) for p in pts)
    if sxx <= 0:
        return None
    slope = sxy / sxx
    k = -slope
    if k <= 0.005:
        return None
    resid = sum(p[2] * (p[1] - (my + slope * (p[0] - mx))) ** 2 for p in pts)
    dof = max(1, len(pts) - 2)
    se = math.sqrt(resid / dof / sxx) if sxx > 0 else k
    rel = min(0.6, max(0.05, se / k))
    return DecayFit(k=k, rel_err=rel, n=len(pts))


def time_to_sugar(
    now: datetime, s_now: float, s_target: float, k: float, settings: Settings, temp_now: float | None
) -> datetime | None:
    """Zeitpunkt, an dem S den Zielwert erreicht (Temperaturplan berücksichtigt)."""
    if s_target >= s_now:
        return now
    if k <= 0:
        return None
    need = math.log(s_now / max(s_target, 0.05)) / k  # thermische Tage
    step = timedelta(minutes=30)
    step_days = step.total_seconds() / 86400.0
    t, tau = now, 0.0
    while t - now <= MAX_FORECAST:
        s = s_now * math.exp(-k * tau)
        temp = settings.planned_temp(s, temp_now)
        dtau = thermal_factor(temp, settings.q10) * step_days
        if tau + dtau >= need:
            return t + step * ((need - tau) / dtau)
        tau += dtau
        t += step
    return None


def project(
    now: datetime,
    s_now: float,
    k: float,
    settings: Settings,
    temp_now: float | None,
    until: datetime,
    step: timedelta = timedelta(hours=1),
) -> list[tuple[datetime, float]]:
    """Zuckerverlauf ab jetzt bis `until`, gerechnet wie time_to_sugar (Temperaturplan inklusive)."""
    out = [(now, s_now)]
    step_days = step.total_seconds() / 86400.0
    t, s = now, s_now
    while t < until:
        temp = settings.planned_temp(s, temp_now)
        s *= math.exp(-k * thermal_factor(temp, settings.q10) * step_days)
        t += step
        out.append((t, s))
    return out


def remove_steps(
    points: list[tuple[datetime, float]], max_kg_per_min: float, noise_kg: float
) -> tuple[list[tuple[datetime, float]], int]:
    """Sprünge (Probe, Abstich, Anlehnen) aus einer Gewichtsreihe herausrechnen.

    Ändert sich das Gewicht zwischen zwei Werten schneller, als eine Gärung es kann, zählt die
    Änderung nicht als Gärung. Rückgabe: bereinigte Reihe und Zahl der Sprünge.
    """
    out: list[tuple[datetime, float]] = []
    shift, steps = 0.0, 0
    prev: tuple[datetime, float] | None = None
    for t, v in sorted(points, key=lambda p: p[0]):
        if prev is not None:
            minutes = (t - prev[0]).total_seconds() / 60.0
            if abs(v - prev[1]) > 3.0 * max_kg_per_min * minutes + 5.0 * noise_kg:
                shift -= v - prev[1]
                steps += 1
        out.append((t, v + shift))
        prev = (t, v)
    return out, steps


def observed_rate(points: list[tuple[datetime, float, float]], t_end: datetime, hours: float = 24.0) -> float | None:
    """Zuckerabbau (g/L pro Tag) über `hours` bis t_end, aus Medianen um Anfang und Ende."""
    span = timedelta(hours=hours)
    edge = timedelta(hours=6)
    end_vals = [s for t, s, _ in points if t_end - edge <= t <= t_end]
    start_vals = [s for t, s, _ in points if t_end - span - edge <= t <= t_end - span]
    if not end_vals or not start_vals:
        return None
    return (median(start_vals) - median(end_vals)) / (hours / 24.0)


def relative_rate(
    points: list[tuple[datetime, float, float]], t_end: datetime, temps: Series, q10: float, hours: float = 24.0
) -> float | None:
    """Abbau relativ zum vorhandenen Zucker und temperaturbereinigt (je thermischem Tag).

    Bei einer gesunden Gärung bleibt dieser Wert in der späten Phase ungefähr gleich; bei einer
    stockenden bricht er ein.
    """
    rate = observed_rate(points, t_end, hours)
    if rate is None:
        return None
    vals = [s for t, s, _ in points if t_end - timedelta(hours=hours) <= t <= t_end]
    mean_s = sum(vals) / len(vals) if vals else 0.0
    if mean_s <= 0.5:
        return None
    temp = temps.at(t_end - timedelta(hours=hours / 2)) if temps else None
    return rate / mean_s / thermal_factor(temp, q10)


def _weight_points(
    est: "Estimate",
    settings: Settings,
    start: datetime,
    anc: list[Anchor],
    temp_s: Series,
    weight: list[tuple[datetime, float]],
    now: datetime,
) -> tuple[list[tuple[datetime, float, float]], tuple[datetime, float, float] | None]:
    """Zucker aus dem Gewicht, stündlich, und der Jetzt-Wert mit seiner vollen Unsicherheit.

    S(t) = S_Anker − k · (w_Anker − w(t)) − (CO2 gelöst(t) − CO2 gelöst(Anker)) / 0,47
    k = 1000 / (0,47 · Volumen) g/L je kg, oder über alle Anker im Verlauf geeicht.

    Die Punkte tragen nur ihr zufälliges Rauschen; Eichung und Volumen verschieben alle Punkte
    gemeinsam und gehören deshalb nicht in die Kurvenanpassung, nur in den Jetzt-Wert.
    """
    weight = sorted((p for p in weight if p[0] <= now), key=lambda p: p[0])
    if len(weight) < 2:
        return [], None
    ref = abs(median(v for _, v in weight)) or 1.0
    noise = WEIGHT_NOISE * ref
    volume = settings.volume_l
    max_rate = PEAK_SUGAR_RATE * YIELD_CO2_SUGAR * (volume or 1000.0) / 1000.0 / 1440.0  # kg/min
    cleaned, est.weight_steps = remove_steps(weight, max_rate, noise)
    if est.weight_steps:
        est.notes.append(f"Waage: {est.weight_steps} Sprung/Sprünge herausgerechnet (Probe, Abstich?)")
    wser = Series(cleaned)
    w_start = wser.v[0] if wser.t[0] - start <= timedelta(hours=12) else None

    def dissolved(t: datetime, is_start: bool = False) -> float:
        """Gelöstes CO2 in g/L: frischer Most 0, sonst gesättigt, sobald Gas entweicht."""
        if is_start:
            return 0.0
        if w_start is not None and w_start - wser.interpolate(t) <= 10 * noise:
            return 0.0  # noch kein Gewichtsverlust: das CO2 löst sich noch
        temp = temp_s.at(t) if temp_s else None
        return henry(temp if temp is not None else T_REF)

    within = [a for a in anc if wser.t[0] - timedelta(hours=12) <= a.t <= wser.t[-1]]
    if not within:
        return [], None
    k = 1000.0 / (YIELD_CO2_SUGAR * volume) if volume else None
    rel = WEIGHT_REL_SIGMA_THEO
    base = within[-1]
    w_base = wser.interpolate(base.t)
    d_base = dissolved(base.t, base.kind == "start")
    # Eichen: Ausgleichsgerade durch alle Anker im Verlauf, bezogen auf den jüngsten
    pairs = []
    for a in within[:-1]:
        dw = wser.interpolate(a.t) - w_base
        ds = (a.sugar - base.sugar) - (d_base - dissolved(a.t, a.kind == "start")) / YIELD_CO2_SUGAR
        if dw > 10 * noise and ds > 0:
            pairs.append((ds, dw, a.sigma**2 + base.sigma**2))
    if pairs and max(p[0] for p in pairs) >= 2.0:
        k_cal = sum(ds * dw / var for ds, dw, var in pairs) / sum(dw * dw / var for _, dw, var in pairs)
        if k is None or 0.25 * k <= k_cal <= 4.0 * k:
            if k is not None and k_cal > 2.2 * k:
                est.notes.append("Waage zeigt etwa ein Drittel: mit Testgewicht in der Deckelmitte eichen")
            k, rel = k_cal, WEIGHT_REL_SIGMA_CAL
            est.weight_calibrated = True
        else:
            est.notes.append("Waage passt nicht zu den Messungen: Eichung prüfen")
    if k is None:
        return [], None
    est.weight_g_l_per_kg = k
    sig_point = WEIGHT_DISSOLVED_SIGMA + k * noise
    out: list[tuple[datetime, float, float]] = []
    hour = timedelta(hours=1)
    t0 = wser.t[0]
    while t0 <= wser.t[-1]:
        vals = wser.window(t0 - timedelta(seconds=1), t0 + hour)
        if vals:
            tm = t0 + hour / 2
            s = base.sugar - k * (w_base - median(vals)) - (dissolved(tm) - d_base) / YIELD_CO2_SUGAR
            out.append((tm, max(0.0, s), sig_point))
        t0 += hour
    if not out:
        return [], None
    t_last, s_last, _ = out[-1]
    days = abs((t_last - base.t).total_seconds()) / 86400.0
    sig_now = base.sigma + rel * abs(s_last - base.sugar) + sig_point + k * WEIGHT_DRIFT_PER_DAY * ref * days
    return out, (t_last, s_last, sig_now)


@dataclass
class Estimate:
    now: datetime
    sugar: float | None = None
    sigma: float | None = None
    abv: float | None = None
    abv_end: float | None = None  # Alkohol in der Flasche nach vollständiger Vergärung
    abv_end_sigma: float | None = None
    abv_label: float | None = None
    abv_label_ok: bool = False
    abv_pairs: int = 0
    rate_g_l_day: float | None = None
    target_sugar: float | None = None
    best: datetime | None = None
    start: datetime | None = None
    end: datetime | None = None
    past: bool = False
    dub_hours: float | None = None
    display_state: str = "none"  # none | ok | soon | now | late
    status: str = "waiting"  # waiting | fermenting | approaching | window | past | dry | stuck
    p_now_10: float | None = None
    p_now_20: float | None = None
    p_target_10: float | None = None
    p_target_20: float | None = None
    p_worst_20: float | None = None
    limit_ok: bool = True
    category: str | None = None
    planned_temp: float | None = None
    measurement_recommended: bool = False
    spindle_offset: float | None = None
    bubble_g_l_per_bubble: float | None = None
    weight_g_l_per_kg: float | None = None
    weight_calibrated: bool = False
    weight_steps: int = 0
    fit_k: float | None = None
    fit_rel: float | None = None
    notes: list[str] = field(default_factory=list)
    series: list[tuple[datetime, float, float]] = field(default_factory=list)  # (t, S, σ) fürs Diagramm
    forecast: list[tuple[datetime, float, float, float]] = field(default_factory=list)  # (t, S, oben, unten)


def _set_bottle_abv(est: Estimate, bottle: BottleAbv) -> None:
    est.abv_end, est.abv_end_sigma = bottle.value, bottle.sigma
    est.abv_label, est.abv_label_ok, est.abv_pairs = bottle.label, bottle.label_ok, bottle.pairs


def estimate(
    model: WineModel,
    settings: Settings,
    start: datetime,
    now: datetime,
    anchors: list[Anchor] | None = None,
    gravity: list[tuple[datetime, float]] | None = None,
    bubbles: list[tuple[datetime, float]] | None = None,
    temps: list[tuple[datetime, float]] | None = None,
    weight: list[tuple[datetime, float]] | None = None,
) -> Estimate:
    est = Estimate(now=now)
    temp_s = Series(temps)
    temp_now = temp_s.latest()[1] if temp_s else None
    grav = Series(gravity)
    bub = Series(bubbles)

    # Ziel, Zieldruck und Flaschengrenze hängen nicht vom Jetzt-Wert ab
    target = settings.target_sugar()
    est.target_sugar = target
    if settings.mode == "petnat":
        b, mal = BOTTLES[settings.bottle], settings.malic()
        est.p_target_10 = bottle_pressure(target, 10, b, FILL_MID, mal)
        est.p_target_20 = bottle_pressure(target, 20, b, FILL_MID, mal)
        est.p_worst_20 = bottle_pressure(target, 20, b, FILL_WORST, mal)
        est.limit_ok = est.p_worst_20 <= b.limit_bar
        est.category = eu_category(settings.target_bar_20c)

    # Alkohol in der Flasche: braucht nur Most, Endzucker und Messpaare, steht also ab dem Start
    abv_pairs = [a.pair for a in anchors or [] if a.pair is not None and a.t <= now]
    abv_tol = ABV_TOLERANCE_SPARKLING if settings.mode == "petnat" and est.category != "still" else ABV_TOLERANCE_STILL
    _set_bottle_abv(est, bottle_abv(model, settings.dry_sugar_g_l, abv_pairs, abv_tol))

    anc = sorted([Anchor(start, model.s0, SIGMA["start"], "start")] + list(anchors or []), key=lambda a: a.t)
    anc = [a for a in anc if a.t <= now]
    last = anc[-1]

    def tau(t: datetime) -> float:
        return thermal_days(temp_s, start, t, settings.q10, temp_now)

    points: list[tuple[datetime, float, float]] = [(a.t, a.sugar, a.sigma) for a in anc]

    # --- Spindel: Versatz am jüngsten Anker mit Spindelwerten in der Nähe ---------------------
    offset, offset_t = None, None
    for a in reversed(anc):
        near = grav.window(a.t - timedelta(hours=3), a.t + timedelta(hours=3))
        if near:
            offset, offset_t = median(near) - model.density(a.sugar), a.t
            break
    est.spindle_offset = offset
    grav_points: list[tuple[datetime, float, float]] = []
    if grav:
        hour = timedelta(hours=1)
        t0 = grav.t[0]
        while t0 <= min(grav.t[-1], now):
            vals = grav.window(t0 - timedelta(seconds=1), t0 + hour)
            if vals:
                sg = median(vals) - (offset or 0.0)
                s = model.sugar_from_density(sg)
                if offset is None:
                    sig = SPINDLE_SIGMA_UNCALIBRATED
                else:
                    sig = SPINDLE_SIGMA + SPINDLE_DRIFT_PER_DAY * abs((t0 - offset_t).total_seconds()) / 86400
                grav_points.append((t0 + hour / 2, s, sig))
            t0 += hour
    points += grav_points

    # --- Blasen: Eichung zwischen den letzten beiden Ankern ------------------------------------
    bub_points: list[tuple[datetime, float, float]] = []
    if bub and len(anc) >= 2:
        a1, a2 = anc[-2], anc[-1]
        n1, n2 = bub.interpolate(a1.t), bub.interpolate(a2.t)
        if n1 is not None and n2 is not None and n2 - n1 >= 100 and a1.sugar - a2.sugar >= 1.0:
            k_b = (a1.sugar - a2.sugar) / (n2 - n1)
            est.bubble_g_l_per_bubble = k_b
            for t_b, n in zip(bub.t, bub.v):
                if a2.t < t_b <= now:
                    ds = k_b * (n - n2)
                    bub_points.append((t_b, a2.sugar - ds, a2.sigma + BUBBLE_REL_SIGMA * abs(ds)))
    points += bub_points[:: max(1, len(bub_points) // 200)]

    # --- Waage: Gewichtsverlust ist entwichenes CO2 --------------------------------------------
    w_points, w_now = _weight_points(est, settings, start, anc, temp_s, weight or [], now)
    points += w_points

    # --- Prognosemodell -------------------------------------------------------------------------
    tau_now = tau(now)
    decline = [(tau(t), s, sig) for t, s, sig in points if s <= DECLINE_FRACTION * model.s0]
    fit = fit_decay(decline, tau_now)
    if fit is None and len(decline) >= 2:
        recent = sorted(decline)[-12:]
        (ta, sa, _), (tb, sb, _) = recent[0], recent[-1]
        if tb - ta >= 0.25 and sa > sb > 0:
            k = (sa - sb) / (tb - ta) / max(sb, 1.0)
            fit = DecayFit(k=k, rel_err=0.5, n=len(recent))
            est.notes.append("Prognose aus dem linearen Trend, noch keine Kurvenanpassung")
    est.fit_k = fit.k if fit else None
    est.fit_rel = fit.rel_err if fit else None

    # --- Jetzt-Wert -------------------------------------------------------------------------------
    cands: list[tuple[float, float]] = []
    for src in (grav_points, bub_points):
        if src and now - src[-1][0] <= FRESH:
            cands.append((src[-1][1], src[-1][2]))
    if w_now is not None and now - w_now[0] <= FRESH:
        cands.append((w_now[1], w_now[2]))
    if fit is not None and last.sugar <= DECLINE_FRACTION * model.s0:
        # Fortschreiben nur von einem Anker aus der späten Phase: dort gilt das Zerfallsmodell
        dt = tau_now - tau(last.t)
        s_proj = last.sugar * math.exp(-fit.k * dt)
        cands.append((s_proj, last.sigma + abs(last.sugar - s_proj) * fit.rel_err))
    elif now - last.t <= FRESH:
        cands.append((last.sugar, last.sigma))
    if not cands:
        est.status = "waiting"
        est.notes.append("Noch keine aktuellen Werte")
        return est
    wsum = sum(1 / sig**2 for _, sig in cands)
    s_now = max(0.0, sum(s / sig**2 for s, sig in cands) / wsum)
    sigma = 1 / math.sqrt(wsum)
    est.sugar, est.sigma = s_now, sigma
    est.abv = model.abv(s_now)
    if s_now < settings.dry_sugar_g_l:  # trockener als angenommen: dann endet die Gärung hier
        _set_bottle_abv(est, bottle_abv(model, s_now, abv_pairs, abv_tol))
    est.series = sorted(points + [(now, s_now, sigma)], key=lambda p: p[0])
    est.planned_temp = settings.planned_temp(s_now, temp_now)

    # --- Fenster, Anzeige ----------------------------------------------------------------------
    if fit is not None:
        est.rate_g_l_day = fit.k * s_now * thermal_factor(temp_now, settings.q10)
        delta = max(1.0, math.sqrt(sigma**2 + 0.5**2))
        est.best = time_to_sugar(now, s_now, target, fit.k, settings, temp_now)
        est.start = time_to_sugar(now, s_now, target + delta, fit.k * (1 + fit.rel_err), settings, temp_now)
        est.end = time_to_sugar(now, s_now, max(0.3, target - delta), fit.k * (1 - fit.rel_err), settings, temp_now)
        est.past = s_now < target - delta
        # Kurve fürs Diagramm: Mitte, oben langsam (k·(1−rel)) + σ, unten schnell (k·(1+rel)) − σ
        ends = [t for t in (est.best, est.end) if t is not None]
        until = min(max(ends, default=now + timedelta(days=3)) + FORECAST_TAIL, now + FORECAST_MAX)
        mid = project(now, s_now, fit.k, settings, temp_now, until)
        slow = project(now, s_now, fit.k * (1 - fit.rel_err), settings, temp_now, until)
        fast = project(now, s_now, fit.k * (1 + fit.rel_err), settings, temp_now, until)
        est.forecast = [
            (t, s, s_hi + sigma, max(0.0, s_lo - sigma))
            for (t, s), (_, s_hi), (_, s_lo) in zip(mid, slow, fast)
        ]
    if est.best is not None:
        est.dub_hours = max(0.0, (est.best - now).total_seconds() / 3600.0)
    still = settings.mode == "still"
    if est.past and not still:
        est.display_state = "late"
    elif (est.start is not None and est.start <= now) or (still and s_now <= target + 0.5):
        est.display_state = "now"
    elif est.best is not None:
        est.display_state = "ok" if est.best - now > SOON else "soon"

    # --- Druck --------------------------------------------------------------------------------
    if settings.mode == "petnat":
        b, mal = BOTTLES[settings.bottle], settings.malic()
        est.p_now_10 = bottle_pressure(s_now, 10, b, FILL_MID, mal)
        est.p_now_20 = bottle_pressure(s_now, 20, b, FILL_MID, mal)

    # --- Status -------------------------------------------------------------------------------
    if still and s_now <= settings.dry_sugar_g_l + 0.5:
        est.status = "dry"
        if now - last.t > timedelta(hours=24):
            est.notes.append("Trocken laut Schätzung; mit einer Messung bestätigen")
    elif est.display_state == "late":
        est.status = "past"
    elif est.display_state == "now":
        est.status = "window"
    elif est.display_state == "soon":
        est.status = "approaching"
    else:
        est.status = "fermenting"

    # Stockt: Abbau bricht gegenüber den Vortagen ein oder fehlt seit 48 h, ohne dass es kühler wurde
    if est.status in ("fermenting", "approaching") and target + 2 < s_now < 0.8 * model.s0:
        obs = relative_rate(points, now, temp_s, settings.q10)
        prev = [
            r
            for r in (relative_rate(points, now - timedelta(hours=h), temp_s, settings.q10) for h in (24, 48, 72))
            if r is not None
        ]
        flat48 = observed_rate(points, now, hours=48)
        t_then = temp_s.at(now - timedelta(hours=48)) if temp_s else None
        cooled = t_then is not None and temp_now is not None and t_then - temp_now >= 3.0
        collapsed = obs is not None and bool(prev) and max(prev) >= 0.1 and obs <= 0.2 * max(prev)
        stalled = flat48 is not None and flat48 < 0.5
        if not cooled and (collapsed or stalled):
            est.status = "stuck"
            est.display_state = "none"
            est.notes.append("Zucker fällt kaum, ohne dass es kühler wurde")

    if est.best is not None and est.best - now <= timedelta(hours=48):
        if sigma > 1.5 or now - last.t > timedelta(hours=24):
            est.measurement_recommended = True
    if est.status == "stuck":
        est.measurement_recommended = True
    return est
