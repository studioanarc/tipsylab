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

from dataclasses import dataclass

from .units import brix_from_solids, brix_to_sg, sg_to_brix, solids_from_brix

G_SUGAR_PER_ABV = 16.83  # g/L Zucker je % vol (Literatur 16–18, pro Haus eichbar)
K_ETHANOL_BRIX = 0.37  # Refraktometer-Anzeige in °Bx je % vol Alkohol
DSG_ETHANOL = -0.00134  # Änderung der relativen Dichte je % vol Alkohol
BYPRODUCT_FRACTION = 0.04  # g Extrakt (Glycerin u. a.) je g vergorenem Zucker
FERMENTABLE_FRACTION = 0.92  # Anteil vergärbarer Zucker an den gelösten Stoffen im Most (Säuren, Mineralstoffe, Phenole ~8 %)


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
    ) -> "WineModel":
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
