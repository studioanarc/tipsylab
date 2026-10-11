from datetime import datetime

import pytest

from core.bubbles import BubbleAccumulator
from core.charmat import charmat_status, sugar_consumed
from core.display import display_payload, format_dub
from core.fermentation import Estimate
from core.physics import YIELD_CO2_SUGAR, co2_in_tank


def test_counts_intervals_and_fills_gaps():
    acc = BubbleAccumulator()
    assert acc.add({"bubbles": 10, "total": 10, "boot_id": "a", "seq": 1}) == 10
    assert acc.add({"bubbles": 5, "total": 15, "boot_id": "a", "seq": 2}) == 5
    # zwei Nachrichten verpasst: total springt um 30, Intervall meldet nur 8
    assert acc.add({"bubbles": 8, "total": 45, "boot_id": "a", "seq": 5}) == 30
    assert acc.total == 45


def test_reboot_and_duplicates():
    acc = BubbleAccumulator()
    acc.add({"bubbles": 10, "total": 100, "boot_id": "a", "seq": 7})
    assert acc.add({"bubbles": 10, "total": 100, "boot_id": "a", "seq": 7}) == 0  # doppelt
    assert acc.add({"bubbles": 4, "total": 4, "boot_id": "b", "seq": 1}) == 4  # Neustart
    assert acc.total == 14


def test_old_firmware_without_boot_id():
    acc = BubbleAccumulator()
    acc.add({"bubbles": 6, "total": 50})
    assert acc.add({"bubbles": 6, "total": 56}) == 6
    assert acc.add({"bubbles": 3, "total": 3}) == 3  # Summe fällt: Neustart
    assert acc.add({"bubbles": "x"}) == 0
    assert acc.add({"bubbles": 10**7, "total": 10**7}) == 0  # kaputtes Paket


def test_long_outage_within_one_boot_is_counted():
    acc = BubbleAccumulator()
    acc.add({"bubbles": 200, "total": 1_000, "boot_id": "a", "seq": 1})
    # zehn Stunden ohne MQTT bei 250 Blasen pro Minute: mehr als ein einzelnes Intervall je haben kann
    assert acc.add({"bubbles": 250, "total": 151_000, "boot_id": "a", "seq": 601}) == 150_000


def test_reboot_recovers_saved_counts():
    acc = BubbleAccumulator()
    acc.add({"bubbles": 10, "total": 10, "total_all": 5_010, "boot_id": "a", "seq": 1})
    # WLAN weg, das Gerät zählt weiter und sichert bis 7.800, dann Stromausfall und Neustart
    assert acc.add({"bubbles": 12, "total": 12, "total_all": 7_812, "boot_id": "b", "seq": 1}) == 12 + 2_790
    assert acc.add({"bubbles": 8, "total": 20, "total_all": 7_820, "boot_id": "b", "seq": 2}) == 8


def test_normal_reboot_does_not_double_count():
    acc = BubbleAccumulator()
    acc.add({"bubbles": 10, "total": 500, "total_all": 5_010, "boot_id": "a", "seq": 50})
    # zuletzt vor 6 min gesichert (4.900): die Summe liegt nach dem Neustart erst unter dem letzten Wert
    assert acc.add({"bubbles": 12, "total": 12, "total_all": 4_912, "boot_id": "b", "seq": 1}) == 12
    assert acc.add({"bubbles": 8, "total": 20, "total_all": 4_920, "boot_id": "b", "seq": 2}) == 8
    # Werksreset: gesicherte Summe von vorn
    assert acc.add({"bubbles": 5, "total": 5, "total_all": 5, "boot_id": "c", "seq": 1}) == 5


def test_accumulator_roundtrip():
    acc = BubbleAccumulator()
    acc.add({"bubbles": 3, "total": 3, "boot_id": "z", "seq": 1, "suppressed": 2})
    again = BubbleAccumulator.from_dict(acc.to_dict())
    assert again == acc
    assert again.suppressed == 2


@pytest.mark.parametrize(("hours", "text"), [(None, "--"), (0, "0d 0h"), (18.4, "0d 18h"), (84, "3d 12h"), (43.6, "1d 20h")])
def test_format_dub(hours, text):
    assert format_dub(hours) == text


def test_display_payload():
    est = Estimate(now=datetime(2026, 10, 16, 18), dub_hours=43.6, display_state="soon", status="approaching")
    assert display_payload(est, "petnat") == {
        "dub_h": 43.6,
        "state": "soon",
        "mode": "petnat",
        "status": "approaching",
        "measure": False,
    }


def test_charmat_status():
    st = charmat_status(2.5, 12, p_tank=1.82, prv_bar=5.5)
    assert st.setpoint == pytest.approx(1.86, abs=0.01)
    assert st.margin_ok
    assert st.table[18] == pytest.approx(2.55, abs=0.01)
    assert st.dissolved == pytest.approx(5.41, abs=0.05)
    assert not charmat_status(5.0, 18, prv_bar=5.0).margin_ok


def test_sugar_consumed_from_pressure_balance():
    wine, head = 300.0, 30.0
    # 2 g/L Zucker vergoren -> so viel CO2 bleibt bei geschlossenem Ventil im Tank
    target_co2 = co2_in_tank(0.5, 12, wine, head) + 2.0 * YIELD_CO2_SUGAR * wine
    lo, hi = 0.5, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if co2_in_tank(mid, 12, wine, head) > target_co2:
            hi = mid
        else:
            lo = mid
    assert sugar_consumed(0.5, 12, lo, 12, 0.0, wine, head) == pytest.approx(2.0, abs=0.01)
