"""Anzeige am AtomS3: DUB im Format „3d 12h“ und der Farbzustand (siehe docs/PLAN 3.12)."""

from __future__ import annotations

from typing import Any

from .fermentation import Estimate


def format_dub(hours: float | None) -> str:
    """Stunden bis zum Abfüllen als „3d 12h“; ohne Prognose „--“."""
    if hours is None:
        return "--"
    total = max(0, round(hours))
    return f"{total // 24}d {total % 24}h"


def display_payload(est: Estimate, mode: str) -> dict[str, Any]:
    """Nachricht für tipsy/<id>/display. Die Firmware formatiert und färbt selbst.

    state: ok (grün, > 3 Tage) | soon (gelb) | now (Koralle, Fenster offen)
           | late (Koralle blinkend, Fenster vorbei) | none (keine Prognose)
    """
    return {
        "dub_h": None if est.dub_hours is None else round(est.dub_hours, 1),
        "state": est.display_state,
        "mode": mode,
        "status": est.status,
        "measure": est.measurement_recommended,
    }
