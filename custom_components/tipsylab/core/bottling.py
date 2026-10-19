"""Nach dem Abfüllen: Messflasche gegen den erwarteten Druck (docs/PLAN, Phase 5).

Gerechnet wird mit demselben Modell wie vor dem Abfüllen (core/physics): Das CO2 in der Flasche
ist gelöst (Henry) oder im Kopfraum (Gasgesetz), dazu kommt die Luft, die beim Verschließen im
Kopfraum war. Eine Messung bei beliebiger Temperatur ergibt so die CO2-Menge in der Flasche und
daraus den Druck bei 20 °C. Verglichen wird mit dem Druck bei vollständiger Vergärung des
Restzuckers beim Abfüllen.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from .physics import (
    BOTTLES,
    FILL_MID,
    FILL_MILD,
    FILL_WORST,
    P_ATM,
    YIELD_CO2_MALIC,
    YIELD_CO2_SUGAR,
    Bottle,
    FillConditions,
    R,
    bottle_pressure,
    henry,
)

WORST_SATURATION_MARGIN = 0.2  # so weit liegt der ungünstige Fall mindestens über der gelernten Sättigung
HIGH_MARGIN_BAR = 0.5  # so weit darf die Messflasche (bei 20 °C) über dem erwarteten Enddruck liegen
DANGER_FRACTION = 0.8  # Anteil der Flaschengrenze, ab dem es gefährlich wird
DEFAULT_TEMP_C = 10.0  # Temperatur der Messflasche, wenn keine angegeben ist: rechnet vorsichtig hoch
DONE_AFTER = timedelta(days=21)  # frühestens dann gilt die Flaschengärung als durch
DONE_STABLE_BAR = 0.15  # zwei Messungen mit mindestens drei Tagen Abstand, die so nah beieinander liegen
READING_SIGMA_BAR = 0.1  # Ablesefehler eines Aphrometers
# Gelernt wird nur aus plausibler Sättigung. Weit daneben liegt eher der Restzucker oder die
# Flaschengärung steckt; das darf den Hauswert nicht verschieben (sonst würde etwa eine stockende
# Flaschengärung den nächsten Ansatz mit mehr Zucker abfüllen lassen).
PLAUSIBLE_SATURATION = (0.4, 1.4)

def fill_conditions(
    saturation: float = FILL_MID.saturation, t_bottling_c: float = FILL_MID.t_bottling_c
) -> tuple[FillConditions, FillConditions, FillConditions]:
    """Mittlerer, ungünstiger und milder Fall für eine (gelernte) Sättigung beim Abfüllen.

    Der ungünstige Fall wird nie milder als FILL_WORST und liegt immer mindestens
    WORST_SATURATION_MARGIN über dem mittleren.
    """
    mid = replace(FILL_MID, saturation=saturation, t_bottling_c=t_bottling_c)
    worst = replace(
        FILL_WORST,
        saturation=max(FILL_WORST.saturation, saturation + WORST_SATURATION_MARGIN),
        t_bottling_c=t_bottling_c,
    )
    mild = replace(
        FILL_MILD,
        saturation=max(0.0, min(FILL_MILD.saturation, saturation - WORST_SATURATION_MARGIN)),
        t_bottling_c=t_bottling_c,
    )
    return mid, worst, mild


def _air(fill: FillConditions, t_c: float) -> float:
    """Teildruck der eingeschlossenen Luft (bar absolut) bei t_c."""
    return fill.air_fraction * P_ATM * (t_c + 273.15) / (fill.t_bottling_c + 273.15)


def co2_in_bottle(p_gauge: float, t_c: float, bottle: Bottle, fill: FillConditions) -> float:
    """CO2 in g je Liter Wein (gelöst und im Kopfraum) aus Überdruck und Temperatur."""
    t_k = t_c + 273.15
    p_co2 = max(0.0, p_gauge + P_ATM - _air(fill, t_c))
    grams = p_co2 * (4.4e3 * bottle.headspace_l + henry(t_c) * R * t_k * bottle.wine_l) / (R * t_k)
    return grams / bottle.wine_l


def pressure_from_co2(co2_g_l: float, t_c: float, bottle: Bottle, fill: FillConditions) -> float:
    """Überdruck (bar) bei t_c für eine CO2-Menge je Liter Wein; Umkehrung von co2_in_bottle."""
    t_k = t_c + 273.15
    grams = co2_g_l * bottle.wine_l
    p_co2 = grams * R * t_k / (4.4e3 * bottle.headspace_l + henry(t_c) * R * t_k * bottle.wine_l)
    return p_co2 + _air(fill, t_c) - P_ATM


def pressure_at_20(p_gauge: float, t_c: float, bottle: Bottle, fill: FillConditions) -> float:
    """Gemessenen Überdruck auf 20 °C umrechnen (gleiche CO2-Menge in der Flasche)."""
    return pressure_from_co2(co2_in_bottle(p_gauge, t_c, bottle, fill), 20.0, bottle, fill)


@dataclass(frozen=True)
class Bottling:
    """Stand beim Abfüllen: Grundlage für alles, was danach in der Flasche passiert."""

    time: datetime
    sugar: float  # vergärbarer Restzucker (g/L), Schätzung beim Abfüllen
    sigma: float
    bottle: str = "750"
    malic: float = 0.0  # Äpfelsäure, die in der Flasche abgebaut wird (0 ohne Malo-Option)
    temp_c: float = FILL_MID.t_bottling_c  # Weintemperatur beim Abfüllen
    saturation: float = FILL_MID.saturation  # gelöstes CO2 relativ zur Sättigung (Hauswert)

    @property
    def flask(self) -> Bottle:
        return BOTTLES[self.bottle]

    @property
    def fill(self) -> FillConditions:
        return fill_conditions(self.saturation, self.temp_c)[0]

    @property
    def fill_worst(self) -> FillConditions:
        return fill_conditions(self.saturation, self.temp_c)[1]

    @property
    def co2_start(self) -> float:
        """Gelöstes CO2 beim Abfüllen (g/L)."""
        return self.fill.saturation * henry(self.temp_c)

    @property
    def co2_to_come(self) -> float:
        """CO2 (g/L), das die vollständige Flaschengärung (und Malo) noch bildet."""
        return YIELD_CO2_SUGAR * max(0.0, self.sugar) + YIELD_CO2_MALIC * max(0.0, self.malic)

    def expected(self, t_c: float, sugar: float | None = None) -> float:
        """Überdruck bei t_c nach vollständiger Vergärung (mittlerer Fall)."""
        s = self.sugar if sugar is None else sugar
        return bottle_pressure(s, t_c, self.flask, self.fill, self.malic)

    def worst(self, t_c: float = 20.0) -> float:
        """Ungünstiger Fall: 2σ mehr Zucker und ungünstige Abfüllbedingungen."""
        return bottle_pressure(self.sugar + 2 * self.sigma, t_c, self.flask, self.fill_worst, self.malic)

    def to_dict(self) -> dict:
        return {
            "time": self.time.isoformat(),
            "sugar": self.sugar,
            "sigma": self.sigma,
            "bottle": self.bottle,
            "malic": self.malic,
            "temp_c": self.temp_c,
            "saturation": self.saturation,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Bottling:
        return cls(
            time=datetime.fromisoformat(data["time"]),
            sugar=float(data["sugar"]),
            sigma=float(data["sigma"]),
            bottle=str(data.get("bottle", "750")),
            malic=float(data.get("malic", 0.0)),
            temp_c=float(data.get("temp_c", FILL_MID.t_bottling_c)),
            saturation=float(data.get("saturation", FILL_MID.saturation)),
        )


@dataclass(frozen=True)
class BottleReading:
    t: datetime
    p: float  # gemessener Überdruck (bar)
    temp_c: float
    p20: float  # dieselbe Flasche bei 20 °C


@dataclass
class BottleStatus:
    bottling: Bottling
    days: float
    expected_10: float
    expected_20: float
    expected_sigma_20: float
    worst_20: float
    limit: float
    readings: list[BottleReading] = field(default_factory=list)
    progress: float | None = None  # Anteil der erwarteten Flaschengärung laut jüngster Messung
    done: bool = False  # Flaschengärung durch: Druck seit Tagen gleich
    state: str = "wait"  # wait | ok | high | danger; die Handlung dazu steht in texts.py der Integration
    alarm: bool = False

    @property
    def latest(self) -> BottleReading | None:
        return self.readings[-1] if self.readings else None


def bottle_status(
    bottling: Bottling, readings: list[tuple[datetime, float, float | None]], now: datetime
) -> BottleStatus:
    """Messflasche auswerten: umrechnen, Fortschritt, Alarm mit Stufe (high: kühlen, danger: sofort kühlen)."""
    b = bottling
    sig = (b.expected(20.0, b.sugar + b.sigma) - b.expected(20.0, max(0.0, b.sugar - b.sigma))) / 2
    status = BottleStatus(
        bottling=b,
        days=max(0.0, (now - b.time).total_seconds() / 86400.0),
        expected_10=b.expected(10.0),
        expected_20=b.expected(20.0),
        expected_sigma_20=sig,
        worst_20=b.worst(20.0),
        limit=b.flask.limit_bar,
    )
    for t, p, temp in sorted(readings, key=lambda r: r[0]):
        if t < b.time:
            continue
        t_c = DEFAULT_TEMP_C if temp is None else temp
        status.readings.append(BottleReading(t, p, t_c, pressure_at_20(p, t_c, b.flask, b.fill)))
    last = status.latest
    if last is None:
        return status
    co2 = co2_in_bottle(last.p, last.temp_c, b.flask, b.fill)
    if b.co2_to_come > 0.5:
        status.progress = (co2 - b.co2_start) / b.co2_to_come
    earlier = [r for r in status.readings if last.t - r.t >= timedelta(days=3)]
    status.done = (
        last.t - b.time >= DONE_AFTER and bool(earlier) and abs(last.p20 - earlier[-1].p20) <= DONE_STABLE_BAR
    )
    if last.p20 >= DANGER_FRACTION * status.limit:
        status.state, status.alarm = "danger", True
    elif last.p20 > status.expected_20 + HIGH_MARGIN_BAR:
        status.state, status.alarm = "high", True
    else:
        status.state = "ok"
    return status


def observed_saturation(status: BottleStatus) -> tuple[float, float] | None:
    """Sättigung beim Abfüllen, die zum gemessenen Enddruck passt, mit Unsicherheit.

    Nur wenn die Flaschengärung durch ist: Dann steckt im Druck das CO2 vom Abfüllen plus das
    aus dem ganzen Restzucker. Die Messflasche eicht so gelöstes CO2 und Kopfraum in einem Schritt.
    """
    last = status.latest
    if last is None or not status.done:
        return None
    b = status.bottling
    k = henry(b.temp_c)

    def sat(p: float, sugar: float) -> float:
        co2 = co2_in_bottle(p, last.temp_c, b.flask, b.fill)
        return (co2 - YIELD_CO2_SUGAR * max(0.0, sugar) - YIELD_CO2_MALIC * max(0.0, b.malic)) / k

    value = sat(last.p, b.sugar)
    if not PLAUSIBLE_SATURATION[0] <= value <= PLAUSIBLE_SATURATION[1]:
        return None
    from_sugar = abs(sat(last.p, b.sugar + b.sigma) - sat(last.p, b.sugar - b.sigma)) / 2
    from_reading = abs(sat(last.p + READING_SIGMA_BAR, b.sugar) - sat(last.p - READING_SIGMA_BAR, b.sugar)) / 2
    return value, (from_sugar**2 + from_reading**2) ** 0.5
