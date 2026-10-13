"""Öffentlicher Nur-Lese-Feed für die DataWein-Seite (docs/PLAN, Phase 6).

Home Assistant schickt die Datei an den Webserver; vom Internet aus bleibt es unerreichbar.
Veröffentlicht wird nur, was hier steht: gerundete Zahlen eines Ansatzes, keine Geräte-IDs,
Adressen oder Entitäten.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .composition import WineModel
from .fermentation import Estimate

FEED_VERSION = 1
HISTORY_POINTS = 44  # so viele Werte zeigt das Diagramm der Seite
MAX_NAME = 60


def _r(value: float | None, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def feed_entry(
    name: str,
    mode: str,
    start: datetime,
    now: datetime,
    est: Estimate | None,
    model: WineModel | None,
    bpm: float | None,
    temp: float | None,
) -> dict[str, Any]:
    """Ein Ansatz für die Website. Dichte und Verlauf rechnet das Weinmodell aus dem Restzucker."""
    out: dict[str, Any] = {
        "name": name[:MAX_NAME],
        "mode": mode,
        "day": max(0, (now - start).days),
        "status": est.status if est else "waiting",
        "bpm": _r(bpm, 0),
        "temp": _r(temp, 1),
    }
    if est is None or est.sugar is None:
        return out
    out.update(
        {
            "sugar": _r(est.sugar, 1),
            "abv": _r(est.abv, 1),
            "abv_end": _r(est.abv_end, 1),
            "dub_h": _r(est.dub_hours, 0),
            "window": [est.start.isoformat(), est.end.isoformat()] if est.start and est.end else None,
        }
    )
    if model is not None:
        out["sg"] = _r(model.density(est.sugar), 4)
        series = [p for p in est.series if p[0] <= now]
        step = max(1, len(series) // HISTORY_POINTS)
        out["history"] = [[t.isoformat(), _r(model.density(s), 4)] for t, s, _ in series[::step]][-HISTORY_POINTS:]
    return out


def feed(entries: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    return {"version": FEED_VERSION, "updated": now.isoformat(), "batches": entries}
