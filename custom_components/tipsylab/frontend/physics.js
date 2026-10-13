// CO2-Physik fürs Panel: Spiegel von core/physics.py, damit Regler ohne Server-Rundreise rechnen.
// tests/frontend/test_physics_js.py vergleicht beide; Änderungen immer in beiden Dateien.

export const R = 8.314;
export const P_ATM = 1.013;
export const K298 = 1.21;
export const DH_DISS = 24800;
export const YIELD_CO2_SUGAR = 0.47;
export const YIELD_CO2_MALIC = 0.328;
export const T_REF = 15;

export const henry = (tC, k298 = K298) => k298 * Math.exp((DH_DISS / R) * (1 / (tC + 273.15) - 1 / 298.15));

export const BOTTLES = {
  330: { wine: 0.318, head: 0.012, limit: 4.5 },
  750: { wine: 0.73, head: 0.02, limit: 6.0 },
};

// Sättigung beim Abfüllen, Luftanteil im Kopfraum, Weintemperatur beim Abfüllen
export const FILL = {
  mid: { sat: 0.8, air: 0.4, tFill: 12 },
  worst: { sat: 1.0, air: 0.79, tFill: 12 },
  mild: { sat: 0.6, air: 0.0, tFill: 12 },
};

// Wie fill_conditions in core/bottling.py: mittel, ungünstig, mild für eine gelernte Sättigung.
// Der ungünstige Fall wird nie milder als FILL.worst und liegt immer mindestens 0,2 darüber.
export const WORST_SATURATION_MARGIN = 0.2;
export function fills(sat = FILL.mid.sat, tFill = FILL.mid.tFill) {
  return {
    mid: { ...FILL.mid, sat, tFill },
    worst: { ...FILL.worst, sat: Math.max(FILL.worst.sat, sat + WORST_SATURATION_MARGIN), tFill },
    mild: { ...FILL.mild, sat: Math.max(0, Math.min(FILL.mild.sat, sat - WORST_SATURATION_MARGIN)), tFill },
  };
}

export function bottlePressure(sugar, tC, bottle = BOTTLES[750], fill = FILL.mid, malic = 0) {
  const c0 = fill.sat * henry(fill.tFill);
  const m = bottle.wine * (c0 + YIELD_CO2_SUGAR * Math.max(0, sugar) + YIELD_CO2_MALIC * Math.max(0, malic));
  const tK = tC + 273.15;
  const pCo2 = (m * R * tK) / (4.4e3 * bottle.head + henry(tC) * R * tK * bottle.wine);
  const pAir = (fill.air * P_ATM * tK) / (fill.tFill + 273.15);
  return pCo2 + pAir - P_ATM;
}

export function sugarForPressure(target, tC = 20, bottle = BOTTLES[750], fill = FILL.mid, malic = 0) {
  let lo = 0;
  let hi = 120;
  if (bottlePressure(lo, tC, bottle, fill, malic) >= target) return 0;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (bottlePressure(mid, tC, bottle, fill, malic) > target) hi = mid;
    else lo = mid;
  }
  return (lo + hi) / 2;
}

export const maloSugarOffset = (malic) => (YIELD_CO2_MALIC * Math.max(0, malic)) / YIELD_CO2_SUGAR;

export function euCategory(p20) {
  if (p20 < 1.0) return "still";
  if (p20 <= 2.5) return "semi_sparkling";
  if (p20 < 3.0) return "gap";
  if (p20 < 3.5) return "sparkling";
  return "quality_sparkling";
}

export const charmatCo2Target = (target20, loss = 0.08) => (henry(20) * (target20 + P_ATM)) / (1 - loss);
export const charmatSetpoint = (co2, tankC) => co2 / henry(tankC) - P_ATM;
export const dissolvedCo2 = (pGauge, tC) => henry(tC) * Math.max(0, pGauge + P_ATM);
export const thermalFactor = (tC, q10) => (tC == null ? 1 : q10 ** ((tC - T_REF) / 10));
