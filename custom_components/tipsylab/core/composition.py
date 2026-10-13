"""Weinmodell: Zucker und Alkohol aus Refraktometer- und Dichtewerten.

Das Modell trennt die gelösten Stoffe in vergärbaren Zucker S, unvergärbaren Extrakt und
Gärungsnebenprodukte (vor allem Glycerin). Alkohol entsteht aus dem vergorenen Zucker.

    Brix der Lösung      B(S)  aus den gelösten Stoffen (Saccharose-Näherung)
    Refraktometer zeigt  B(S) + k_e · A          (Alkohol erhöht die Lichtbrechung)
    Dichte               SG(B(S)) + d_e · A      (Alkohol senkt die Dichte)

Zwei Messungen an derselben Probe ergeben zwei Gleichungen für S und A; mit dem Start-Brix
genügt eine. Die Koeffizienten sind Startwerte aus Brechungs- und Dichtetabellen und lassen
sich pro Haus an Laborwerten eichen (siehe docs/PLAN, Abschnitte 2.5 und 2.9).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from .units import brix_from_solids, brix_to_sg, sg_to_brix, solids_from_brix

G_SUGAR_PER_ABV = 16.83  # g/L Zucker je % vol (Literatur 16–18, pro Haus eichbar)
K_ETHANOL_BRIX = 0.37  # Refraktometer-Anzeige in °Bx je % vol Alkohol
DSG_ETHANOL = -0.00134  # Änderung der relativen Dichte je % vol Alkohol
BYPRODUCT_FRACTION = 0.04  # g Extrakt (Glycerin u. a.) je g vergorenem Zucker
FERMENTABLE_FRACTION = 0.92  # Anteil vergärbarer Zucker an den gelösten Stoffen im Most (Säuren, Mineralstoffe, Phenole ~8 %)

# Alkohol in der Flasche (docs/PLAN, Abschnitt 2.10). Unsicherheiten als 1σ; Startwerte.
ABV_PARAM_SIGMA = {
    "g_sugar_per_abv": 0.5,  # Spanne 16–18 als ±2σ; Torulaspora und Spontangärung eher oben
    "fermentable_fraction": 0.02,
    "brix0": 0.2,  # Messung des Mosts
    # Koeffizienten je ±3 %: damit trifft ein Messpaar allein etwa ±0,5 % vol (2σ), wie es
    # Bellingham + Stanley für Weinrefraktometer angibt
    "k_ethanol_brix": 0.03 * K_ETHANOL_BRIX,
    "dsg_ethanol": 0.03 * -DSG_ETHANOL,
}
PAIR_SIGMA_BRIX = 0.1  # Refraktometer, °Bx
PAIR_SIGMA_SG = 0.0005  # Hydrometer oder Dichtemeter, entgaste Probe bei 20 °C
PAIR_MAX_FRACTION = 0.5  # Messpaare zählen erst, wenn höchstens die Hälfte des Zuckers übrig ist
# VO (EU) 2019/33, Art. 44: Angabe in ganzen oder halben % vol; Abweichung zur Analyse höchstens
# ±0,5 % vol, bei Schaum- und Perlwein ±0,8 % vol.
ABV_TOLERANCE_STILL = 0.5
ABV_TOLERANCE_SPARKLING = 0.8
ABV_LABEL_CONFIDENCE = 0.95  # so sicher soll der Etikettwert in der Toleranz liegen


@dataclass(frozen=True)
class WineModel:
    """Most-Kalibrierung und Koeffizienten eines Ansatzes."""

    brix0: float
    sg0: float | None = None
    fermentable_fraction: float = FERMENTABLE_FRACTION
    g_sugar_per_abv: float = G_SUGAR_PER_ABV
    k_ethanol_brix: float = K_ETHANOL_BRIX
    dsg_ethanol: float = DSG_ETHANOL
    byproduct_fraction: float = BYPRODUCT_FRACTION

    @classmethod
    def from_must(
        cls, brix0: float | None = None, sg0: float | None = None, **kwargs: float
    ) -> WineModel:
        """Aus Start-Brix und/oder Startdichte des Mosts."""
        if brix0 is None and sg0 is None:
            raise ValueError("Start-Brix oder Startdichte nötig")
        if brix0 is None:
            brix0 = sg_to_brix(sg0)  # type: ignore[arg-type]
        return cls(brix0=brix0, sg0=sg0, **kwargs)

    # --- Most ------------------------------------------------------------------------------
    @property
    def solids0(self) -> float:
        return solids_from_brix(self.brix0)

    @property
    def s0(self) -> float:
        """Vergärbarer Zucker im Most (g/L)."""
        return self.solids0 * self.fermentable_fraction

    @property
    def nonfermentable(self) -> float:
        """Unvergärbarer Extrakt im Most (g/L)."""
        return self.solids0 - self.s0

    @property
    def sg_offset(self) -> float:
        """Abweichung der gemessenen Mostdichte vom Modell (Gerät, Zusammensetzung)."""
        if self.sg0 is None:
            return 0.0
        return self.sg0 - brix_to_sg(self.brix0)

    @property
    def potential_abv(self) -> float:
        return self.s0 / self.g_sugar_per_abv

    # --- Vorwärtsmodell ---------------------------------------------------------------------
    def abv(self, sugar: float) -> float:
        return max(0.0, self.s0 - sugar) / self.g_sugar_per_abv

    def _solution_brix(self, sugar: float, abv: float) -> float:
        consumed = abv * self.g_sugar_per_abv
        solids = max(0.0, sugar) + self.nonfermentable + self.byproduct_fraction * consumed
        return brix_from_solids(solids)

    def refractometer_reading(self, sugar: float, abv: float | None = None) -> float:
        a = self.abv(sugar) if abv is None else abv
        return self._solution_brix(sugar, a) + self.k_ethanol_brix * a

    def density(self, sugar: float, abv: float | None = None) -> float:
        a = self.abv(sugar) if abv is None else abv
        return brix_to_sg(self._solution_brix(sugar, a)) + self.dsg_ethanol * a + self.sg_offset

    # --- Umkehrungen ------------------------------------------------------------------------
    def _bisect_sugar(self, f, target: float) -> float:
        """Zucker S in [0, s0] mit f(S) = target; f steigt monoton mit S."""
        lo, hi = 0.0, self.s0
        if f(lo) >= target:
            return 0.0
        if f(hi) <= target:
            return self.s0
        for _ in range(60):
            mid = (lo + hi) / 2
            if f(mid) > target:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    def sugar_from_refractometer(self, reading_brix: float) -> float:
        """Zucker aus einer Refraktometer-Messung, Alkohol aus dem Start-Brix gerechnet."""
        return self._bisect_sugar(self.refractometer_reading, reading_brix)

    def sugar_from_density(self, sg: float) -> float:
        """Zucker aus einer Dichtemessung (Hydrometer, Spindel), Alkohol aus dem Start-Brix."""
        return self._bisect_sugar(self.density, sg)

    def sugar_and_abv_from_pair(self, reading_brix: float, sg: float) -> tuple[float, float]:
        """Zucker und Alkohol aus Refraktometer und Dichte an derselben Probe.

        Braucht den Start-Brix nur für den unvergärbaren Extrakt, nicht für den Alkohol.
        """

        def split(abv: float) -> tuple[float, float]:
            brix_sol = reading_brix - self.k_ethanol_brix * abv
            solids = solids_from_brix(max(0.0, brix_sol))
            sugar = solids - self.nonfermentable - self.byproduct_fraction * abv * self.g_sugar_per_abv
            sg_model = brix_to_sg(max(0.0, brix_sol)) + self.dsg_ethanol * abv + self.sg_offset
            return sugar, sg_model

        lo, hi = 0.0, 20.0
        for _ in range(60):  # sg_model fällt monoton mit dem Alkohol
            mid = (lo + hi) / 2
            if split(mid)[1] > sg:
                lo = mid
            else:
                hi = mid
        abv = (lo + hi) / 2
        sugar, _ = split(abv)
        return max(0.0, sugar), abv


# --- Alkohol in der Flasche -------------------------------------------------------------------
@dataclass(frozen=True)
class BottleAbv:
    """Alkohol nach vollständiger Vergärung, mit Unsicherheit und Etikettwert."""

    value: float
    sigma: float
    label: float
    label_ok: bool
    pairs: int


def abv_label(value: float) -> float:
    """Etikettwert: auf halbe % vol gerundet."""
    return math.floor(value * 2 + 0.5) / 2


def _final_abvs(model: WineModel, dry_sugar: float, pairs: list[tuple[float, float]]) -> list[float]:
    """Endalkohol auf zwei Wegen: aus dem Most und aus jedem Messpaar.

    Das Messpaar misst den Alkohol direkt; der Rest bis trocken kommt im selben Verhältnis dazu,
    in dem bisher Zucker zu Alkohol wurde. So hängt es nicht vom Umrechnungsfaktor ab.
    """
    out = [max(0.0, model.s0 - dry_sugar) / model.g_sugar_per_abv]
    for reading, sg in pairs:
        sugar, abv = model.sugar_and_abv_from_pair(reading, sg)
        out.append(abv + max(0.0, sugar - dry_sugar) * abv / max(model.s0 - sugar, 1.0))
    return out


def _usable_pair(model: WineModel, pair: tuple[float, float]) -> bool:
    sugar, abv = model.sugar_and_abv_from_pair(*pair)
    return sugar <= PAIR_MAX_FRACTION * model.s0 and 0.5 < abv < 19.5


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Lineares Gleichungssystem (Gauß mit Pivotsuche); klein, ohne numpy."""
    n = len(b)
    m = [[*row, b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def bottle_abv(
    model: WineModel,
    dry_sugar: float,
    pairs: list[tuple[float, float]] | tuple[tuple[float, float], ...] = (),
    tolerance: float = ABV_TOLERANCE_SPARKLING,
) -> BottleAbv:
    """Alkohol in der Flasche nach vollständiger Vergärung bis dry_sugar.

    Most und Messpaare (Refraktometer °Bx, relative Dichte an derselben Probe) liefern je einen
    Schätzwert. Sie teilen sich Fehlerquellen (vergärbarer Anteil, Koeffizienten), deshalb werden
    sie mit ihrer vollen Kovarianz gewichtet (verallgemeinerte kleinste Quadrate), nicht wie
    unabhängige Messungen.
    """
    used = [p for p in pairs if _usable_pair(model, p)]
    base = _final_abvs(model, dry_sugar, used)
    n = len(base)
    cov = [[0.0] * n for _ in range(n)]

    def add(d: list[float]) -> None:
        for i in range(n):
            for j in range(n):
                cov[i][j] += d[i] * d[j]

    for name, sig in ABV_PARAM_SIGMA.items():
        v = getattr(model, name)
        hi = _final_abvs(replace(model, **{name: v + sig}), dry_sugar, used)
        lo = _final_abvs(replace(model, **{name: v - sig}), dry_sugar, used)
        add([(up - down) / 2 for up, down in zip(hi, lo)])
    for i, (reading, sg) in enumerate(used, start=1):
        for pair_hi, pair_lo in (
            ((reading + PAIR_SIGMA_BRIX, sg), (reading - PAIR_SIGMA_BRIX, sg)),
            ((reading, sg + PAIR_SIGMA_SG), (reading, sg - PAIR_SIGMA_SG)),
        ):
            d = (_final_abvs(model, dry_sugar, [pair_hi])[1] - _final_abvs(model, dry_sugar, [pair_lo])[1]) / 2
            cov[i][i] += d * d
    w = _solve(cov, [1.0] * n)
    total = sum(w)
    value = sum(wi * f for wi, f in zip(w, base)) / total
    sigma = math.sqrt(1.0 / total)
    label = abv_label(value)
    return BottleAbv(value, sigma, label, label_within(label, value, sigma, tolerance), len(used))


def label_within(label: float, value: float, sigma: float, tolerance: float) -> bool:
    """Liegt der wahre Alkohol mit ABV_LABEL_CONFIDENCE höchstens tolerance vom Etikett entfernt?"""

    def phi(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    d = value - label
    return phi((tolerance - d) / sigma) - phi((-tolerance - d) / sigma) >= ABV_LABEL_CONFIDENCE
