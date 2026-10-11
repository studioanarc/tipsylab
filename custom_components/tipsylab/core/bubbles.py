"""Blasenzählung: laufende Summe pro Ansatz aus den Intervall-Nachrichten des TIPSYlab.

Jede Nachricht enthält die Blasen des letzten Intervalls (`bubbles`), die Summe seit dem
Start des Geräts (`total`) und ab Firmware 2.1 eine Boot-Kennung (`boot_id`) und eine laufende
Nummer (`seq`). Fehlende Nachrichten innerhalb desselben Boots werden aus `total` ergänzt;
nach einem Neustart zählt nur das neue Intervall, doppelte Nachrichten werden verworfen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MAX_PER_MESSAGE = 100_000  # mehr ist ein kaputtes Paket, keine Gärung


@dataclass
class BubbleAccumulator:
    total: float = 0.0
    boot_id: str | None = None
    last_device_total: int | None = None
    last_seq: int | None = None
    suppressed: int = 0  # Impulse, die der Mindestabstand verschluckt hat (Sättigung)

    def add(self, msg: dict[str, Any]) -> float:
        """Nachricht verarbeiten und die neu gezählten Blasen zurückgeben."""
        try:
            bubbles = int(msg.get("bubbles") or 0)
        except (TypeError, ValueError):
            return 0.0
        total = msg.get("total")
        total = int(total) if isinstance(total, (int, float)) else None
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
            if gap > bubbles:
                new = gap  # verpasste Nachrichten nachzählen

        if new < 0 or new > MAX_PER_MESSAGE:
            new = 0

        self.total += new
        self.boot_id = boot if boot is not None else self.boot_id
        self.last_device_total = total
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
