"""Die Panel-Physik (frontend/physics.js) muss mit core/physics.py übereinstimmen."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from core.bottling import fill_conditions
from core.fermentation import thermal_factor
from core.physics import (
    BOTTLES,
    FILL_MID,
    FILL_MILD,
    FILL_WORST,
    bottle_pressure,
    charmat_co2_target,
    charmat_setpoint,
    dissolved_co2,
    eu_category,
    henry,
    malo_sugar_offset,
    sugar_for_pressure,
)

PHYSICS_JS = Path(__file__).parents[2] / "custom_components" / "tipsylab" / "frontend" / "physics.js"
FILLS = {"mid": FILL_MID, "worst": FILL_WORST, "mild": FILL_MILD}

SCRIPT = """
import * as P from "./physics.mjs";
const out = {henry: [], pressure: [], sugar: [], malo: [], cat: [], charmat: [], dissolved: [], thermal: [], fills: []};
for (const t of [0, 10, 12, 20, 25, 30]) out.henry.push(P.henry(t));
for (const b of ["330", "750"]) for (const f of ["mid", "worst", "mild"]) for (const s of [0, 4, 6.5, 12, 24])
  for (const t of [10, 20]) for (const mal of [0, 2]) out.pressure.push(P.bottlePressure(s, t, P.BOTTLES[b], P.FILL[f], mal));
for (const b of ["330", "750"]) for (const p of [1.5, 2.5, 3.5, 4.5]) for (const mal of [0, 1.5])
  out.sugar.push(P.sugarForPressure(p, 20, P.BOTTLES[b], P.FILL.mid, mal));
for (const m of [0, 1, 2.5]) out.malo.push(P.maloSugarOffset(m));
for (const p of [0.5, 1, 2.5, 2.7, 3, 3.4, 3.5, 5]) out.cat.push(P.euCategory(p));
for (const p of [2, 2.5, 4]) for (const t of [8, 12, 18]) out.charmat.push(P.charmatSetpoint(P.charmatCo2Target(p, 0.08), t));
for (const p of [0, 1.8, 4]) for (const t of [8, 15]) out.dissolved.push(P.dissolvedCo2(p, t));
for (const t of [null, 10, 15, 20]) out.thermal.push(P.thermalFactor(t, 2.2));
for (const sat of [0.5, 0.8, 1.1]) for (const f of ["mid", "worst", "mild"])
  out.fills.push(P.bottlePressure(6.5, 20, P.BOTTLES["750"], P.fills(sat, 14)[f], 0));
console.log(JSON.stringify(out));
"""


def python_values() -> dict:
    out: dict = {k: [] for k in ("henry", "pressure", "sugar", "malo", "cat", "charmat", "dissolved", "thermal", "fills")}
    out["henry"] = [henry(t) for t in (0, 10, 12, 20, 25, 30)]
    for b in ("330", "750"):
        for f in ("mid", "worst", "mild"):
            for s in (0, 4, 6.5, 12, 24):
                for t in (10, 20):
                    for mal in (0, 2):
                        out["pressure"].append(bottle_pressure(s, t, BOTTLES[b], FILLS[f], mal))
    for b in ("330", "750"):
        for p in (1.5, 2.5, 3.5, 4.5):
            for mal in (0, 1.5):
                out["sugar"].append(sugar_for_pressure(p, 20, BOTTLES[b], FILL_MID, mal))
    out["malo"] = [malo_sugar_offset(m) for m in (0, 1, 2.5)]
    out["cat"] = [eu_category(p) for p in (0.5, 1, 2.5, 2.7, 3, 3.4, 3.5, 5)]
    out["charmat"] = [charmat_setpoint(charmat_co2_target(p, 0.08), t) for p in (2, 2.5, 4) for t in (8, 12, 18)]
    out["dissolved"] = [dissolved_co2(p, t) for p in (0, 1.8, 4) for t in (8, 15)]
    out["thermal"] = [thermal_factor(t, 2.2) for t in (None, 10, 15, 20)]
    for sat in (0.5, 0.8, 1.1):
        for fill in fill_conditions(sat, 14.0):
            out["fills"].append(bottle_pressure(6.5, 20, BOTTLES["750"], fill, 0))
    return out


@pytest.mark.skipif(shutil.which("node") is None, reason="node nicht installiert")
def test_panel_physics_matches_python(tmp_path):
    shutil.copy(PHYSICS_JS, tmp_path / "physics.mjs")
    (tmp_path / "check.mjs").write_text(SCRIPT)
    res = subprocess.run(["node", "check.mjs"], cwd=tmp_path, capture_output=True, text=True, timeout=60, check=True)
    js = json.loads(res.stdout)
    py = python_values()
    assert js["cat"] == py["cat"]
    for key in ("henry", "pressure", "sugar", "malo", "charmat", "dissolved", "thermal"):
        assert len(js[key]) == len(py[key]), key
        for a, b in zip(js[key], py[key]):
            assert a == pytest.approx(b, rel=1e-9, abs=1e-9), key
