"""Blasenzählung: laufende Summe pro Ansatz aus den Intervall-Nachrichten des TIPSYlab.

Jede Nachricht enthält die Blasen des letzten Intervalls (`bubbles`), die Summe seit dem
Start des Geräts (`total`) und ab Firmware 2.1 eine Boot-Kennung (`boot_id`), eine laufende
Nummer (`seq`) und die im NVS gesicherte Summe über alle Neustarts (`total_all`, alle 10 min
gesichert). Fehlende Nachrichten innerhalb desselben Boots werden aus `total` ergänzt. Nach einem
Neustart holt `total_all` nach, was vor dem Neustart gezählt, aber nie gesendet wurde (WLAN weg,
dann Stromausfall); ohne `total_all` zählt nur das neue Intervall. Doppelte Nachrichten werden
verworfen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MAX_PER_MESSAGE = 100_000  # Blasen in einem Intervall; mehr ist ein kaputtes Paket, keine Gärung
MAX_GAP = 2_000_000  # nachgezählte Lücke; eine Woche bei 200 Blasen pro Minute


@dataclass
class BubbleAccumulator:
    total: float = 0.0
    boot_id: str | None = None
    last_device_total: int | None = None
    last_seq: int | None = None
    last_total_all: int | None = None
    suppressed: int = 0  # Impulse, die der Mindestabstand verschluckt hat (Sättigung)

    def add(self, msg: dict[str, Any]) -> float:
        """Nachricht verarbeiten und die neu gezählten Blasen zurückgeben."""
        try:
            bubbles = int(msg.get("bubbles") or 0)
        except (TypeError, ValueError):
            return 0.0
        if bubbles < 0 or bubbles > MAX_PER_MESSAGE:
            return 0.0  # kaputtes Paket: verwerfen, Zustand nicht ändern
        total = msg.get("total")
        total = int(total) if isinstance(total, (int, float)) else None
        total_all = msg.get("total_all")
        total_all = int(total_all) if isinstance(total_all, (int, float)) else None
        boot = msg.get("boot_id")
        seq = msg.get("seq")
        seq = int(seq) if isinstance(seq, (int, float)) else None

        if boot is not None and boot == self.boot_id and seq is not None and self.last_seq is not None:
            if seq <= self.last_seq:
                return 0.0  # doppelt oder veraltet

        if boot is not None:
            same_boot = boot == self.boot_id
        else:  # alte Firmware ohne boot_id: Neustart an fallender Summe erkennen
            same_boot = total is not None and self.last_device_total is not None and total >= self.last_device_total

        new = bubbles
        if same_boot and total is not None and self.last_device_total is not None:
            gap = total - self.last_device_total
            if bubbles < gap <= MAX_GAP:
                new = gap  # verpasste Nachrichten nachzählen
        elif not same_boot and total_all is not None and self.last_total_all is not None:
            # Neustart: gezählt, gesichert, aber nie gesendet
            lost = total_all - bubbles - self.last_total_all
            if 0 < lost <= MAX_GAP:
                new = bubbles + lost

        self.total += new
        self.boot_id = boot if boot is not None else self.boot_id
        self.last_device_total = total
        if total_all is not None:
            self.last_total_all = total_all
        if seq is not None:
            self.last_seq = seq
        sup = msg.get("suppressed")
        if isinstance(sup, (int, float)):
            self.suppressed += int(sup)
        return float(new)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BubbleAccumulator":
        if not data:
            return cls()
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)
