"""Archiv und Hauswerte im Home-Assistant-Speicher (.storage/tipsylab.house).

Abgeschlossene Ansätze landen im Archiv, auch wenn ihr Eintrag später gelöscht wird. Die
Hauswerte werden aus dem Archiv gerechnet (core/house.py).
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .core.house import DEVICE_PRIORS, HouseValue, device_values, house_values

HOUSE_STORAGE_VERSION = 1


class House:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, HOUSE_STORAGE_VERSION, f"{DOMAIN}.house")
        self.archive: list[dict[str, Any]] = []
        self.values: dict[str, HouseValue] = house_values({})
        self.devices: dict[str, dict[str, HouseValue]] = {kind: {} for kind in DEVICE_PRIORS}

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.archive = list(stored.get("archive", []))
        self._update()

    def _update(self) -> None:
        obs: dict[str, list[tuple[float, float]]] = {}
        for record in self.archive:
            for name, pair in (record.get("observed") or {}).items():
                if pair:
                    obs.setdefault(name, []).append((float(pair[0]), float(pair[1])))
        self.values = house_values(obs)
        dev: dict[str, dict[str, list[tuple[float, float]]]] = {kind: {} for kind in DEVICE_PRIORS}
        for record in self.archive:
            for kind, per_device in (record.get("observed_devices") or {}).items():
                if kind not in dev:
                    continue
                for device, pair in per_device.items():
                    if pair:
                        dev[kind].setdefault(device, []).append((float(pair[0]), float(pair[1])))
        self.devices = {kind: device_values(kind, obs_k) for kind, obs_k in dev.items()}

    def device(self, kind: str, device: str | None) -> HouseValue | None:
        """Gelernter Wert eines Geräts; None, solange kein Ansatz beigetragen hat."""
        return self.devices.get(kind, {}).get(device) if device else None

    async def async_put(self, record: dict[str, Any]) -> None:
        """Archiv-Eintrag eines Ansatzes speichern; ein älterer Eintrag desselben Ansatzes wird ersetzt."""
        self.archive = [r for r in self.archive if r.get("entry_id") != record["entry_id"]] + [record]
        self._update()
        await self._store.async_save({"archive": self.archive})

    async def async_drop(self, entry_id: str) -> None:
        self.archive = [r for r in self.archive if r.get("entry_id") != entry_id]
        self._update()
        await self._store.async_save({"archive": self.archive})

    def as_dict(self) -> dict[str, Any]:
        return {
            "values": {k: {"mean": v.mean, "sigma": v.sigma, "n": v.n} for k, v in self.values.items()},
            "devices": {
                kind: {d: {"mean": v.mean, "sigma": v.sigma, "n": v.n} for d, v in per.items()}
                for kind, per in self.devices.items()
            },
            "archive": sorted(self.archive, key=lambda r: r.get("closed") or "", reverse=True),
        }


def get_house(hass: HomeAssistant) -> House | None:
    return hass.data.get(DOMAIN, {}).get("house")
