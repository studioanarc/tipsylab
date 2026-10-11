"""Erzeugt echte Panel-Daten aus Simulator und Integration für tools/panel-vorschau/.

Nur auf Wunsch:  PANEL_DUMP=tools/panel-vorschau uv run pytest tests/integration/test_panel_dump.py
"""

from datetime import timedelta
import json
import math
import os
from pathlib import Path
import random
import sys

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
from simulator import SimConfig, simulate  # noqa: E402

OUT = os.environ.get("PANEL_DUMP")
pytestmark = pytest.mark.skipif(not OUT, reason="nur für die Panel-Vorschau (PANEL_DUMP=<Ordner>)")


async def _batch(hass, now, day, title, mode="petnat", cfg=None, every=None):
    start = now - timedelta(days=day)
    sim = simulate(cfg or SimConfig(), start=start)
    entry = MockConfigEntry(
        domain="tipsylab",
        title=title,
        data={"name": title, "mode": mode, "brix0": 20.5, "volume_l": 750, "start": start.isoformat(),
              "gravity_entity": "sensor.spindel", "gravity_unit": "sg", "temperature_entity": "sensor.temp"},
        options={"target_bar_20c": 2.5, "bottle": "750", "malo_in_bottle": False, "malic_g_l": 0.0, "q10": 2.2,
                 "dry_sugar_g_l": 2.0, "filling_loss": 0.08, "temp_start": 17.0, "temp_switch_sugar": 30.0,
                 "temp_late": 12.0},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coord = entry.runtime_data
    for name, series in (("gravity", sim.gravity), ("temps", sim.temps), ("bubbles", sim.bubbles)):
        for t, v in series:
            if t <= now:
                coord._record(name, t, v)
    rng = random.Random(3)
    for d in every or (2, 4, 6, 8, day - 0.3):
        t = start + timedelta(days=d)
        coord.store_data["measurements"].append(
            {"kind": "brix", "value": round(sim.refractometer(t, rng, 0.1), 1), "time": t.isoformat()})
    coord.store_data["measurements"].append({"kind": "malic", "value": 2.1, "time": (start + timedelta(days=5)).isoformat()})
    coord.store_data["events"].append(
        {"kind": "racking", "time": (start + timedelta(days=3, hours=4)).isoformat(), "note": "grobe Hefe ab"})
    coord.store_data["measurements"].sort(key=lambda m: m["time"])
    await coord.async_refresh()
    return coord


async def test_dump_panel_data(hass: HomeAssistant) -> None:
    now = dt_util.utcnow()
    petnat = await _batch(hass, now, 9.4, "DATA Rosé 2026")
    still = await _batch(hass, now, 15.5, "Branco Ovar", mode="still",
                         cfg=SimConfig(days=16, cool_at_sugar=None), every=(2, 5, 8, 11, 14))

    entry = MockConfigEntry(
        domain="tipsylab",
        title="Tank 03",
        data={"name": "Tank 03", "mode": "charmat", "volume_l": 300, "start": (now - timedelta(days=6)).isoformat()},
        options={"target_bar_20c": 2.5, "filling_loss": 0.08, "prv_bar": 5.5},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    tank = entry.runtime_data
    for i in range(72 * 12):  # Druck baut sich auf, danach Sägezahn mit Ventilpulsen
        t, h = now - timedelta(hours=72) + timedelta(minutes=5 * i), i / 12
        if h < 6:
            p = 0.02
        elif h < 26:
            p = 1.86 * (1 - (1 - (h - 6) / 20) ** 1.6)
        else:
            p = 1.80 + 0.06 * ((h - 26) % 1.6) / 1.6
        tank._record("pressure", t, round(p, 3))
        tank._record("temps", t, round(12.0 + 0.3 * math.sin(h / 4), 2))
    await tank.async_refresh()

    reading = round(petnat.model().refractometer_reading(13.0), 1)
    out = Path(OUT)
    out.mkdir(parents=True, exist_ok=True)
    batches = [petnat.panel_data(), still.panel_data(), tank.panel_data()]
    (out / "batches.json").write_text(json.dumps({"batches": batches}, ensure_ascii=False))
    previews = {petnat.config_entry.entry_id: {"reading": reading, "result": await petnat.async_preview("brix", reading)}}
    (out / "previews.json").write_text(json.dumps(previews, ensure_ascii=False))
    assert batches[0]["estimate"]["forecast"]
