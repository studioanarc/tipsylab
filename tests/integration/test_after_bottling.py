"""Nach dem Abfüllen: eingefrorene Schätzung, Messflasche, Alarm, Heizung aus, Archiv und Hauswerte."""

from datetime import timedelta

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tipsylab.core.bottling import ACTION_DANGER, ACTION_HIGH
from custom_components.tipsylab.house import get_house
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

DOMAIN = "tipsylab"


def _entity(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id, key
    return entity_id


def _entry(title: str = "Test", **data) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={
            "name": title,
            "mode": "petnat",
            "brix0": 20.5,
            "volume_l": 750,
            "start": (dt_util.utcnow() - timedelta(days=9)).isoformat(),
            **data,
        },
        options={"target_bar_20c": 2.5, "bottle": "750", "malo_in_bottle": False, "malic_g_l": 0.0,
                 "q10": 2.2, "dry_sugar_g_l": 2.0, "filling_loss": 0.08},
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data


async def _call(hass: HomeAssistant, entry: MockConfigEntry, service: str, **data) -> None:
    await hass.services.async_call(DOMAIN, service, {"config_entry_id": entry.entry_id, **data}, blocking=True)
    await hass.async_block_till_done()


async def _bottle_at(hass: HomeAssistant, entry: MockConfigEntry, sugar: float) -> None:
    """Refraktometer kurz vor dem Abfüllen, dann „Abgefüllt“."""
    reading = round(entry.runtime_data.model().refractometer_reading(sugar), 2)
    await _call(hass, entry, "add_measurement", kind="brix", value=reading)
    await _call(hass, entry, "add_event", kind="bottled")


async def test_bottling_needs_a_current_sugar(hass: HomeAssistant) -> None:
    entry = _entry()
    await _setup(hass, entry)
    with pytest.raises(HomeAssistantError, match="Restzucker"):
        await _call(hass, entry, "add_event", kind="bottled")
    assert entry.runtime_data.bottling is None


async def test_bottling_freezes_the_estimate(hass: HomeAssistant) -> None:
    entry = _entry()
    coord = await _setup(hass, entry)
    await _bottle_at(hass, entry, 7.0)
    snap = coord.store_data["bottling"]
    assert snap["sugar"] == pytest.approx(7.0, abs=0.5)
    assert hass.states.get(_entity(hass, entry, "sensor", "status")).state == "bottled"
    sugar_id = _entity(hass, entry, "sensor", "restzucker")
    before = float(hass.states.get(sugar_id).state)
    # Eine spätere Messung (etwa aus einer Flasche) ändert die Schätzung beim Abfüllen nicht mehr
    await _call(hass, entry, "add_measurement", kind="brix", value=round(coord.model().refractometer_reading(1.0), 2))
    assert float(hass.states.get(sugar_id).state) == pytest.approx(before, abs=0.01)
    assert hass.states.get(_entity(hass, entry, "binary_sensor", "im_fenster")).state == "off"


async def test_heater_is_switched_off_after_bottling(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post("http://192.0.2.10/rpc", json={"id": 1, "result": {}})
    entry = _entry(heater_host="192.0.2.10")
    await _setup(hass, entry)
    await _bottle_at(hass, entry, 7.0)
    sent = [call[2]["params"]["value"] for call in aioclient_mock.mock_calls if call[2]]
    assert sent, "kein Sollwert an den Shelly"
    assert sent[-1] == 0.0  # unter 5 °C: Das Skript schaltet die Heizung aus


async def test_measurement_bottle_raises_and_clears_the_alarm(hass: HomeAssistant) -> None:
    entry = _entry()
    coord = await _setup(hass, entry)
    await _bottle_at(hass, entry, 7.0)
    expected = coord.data.bottle.expected_20
    alarm_id = _entity(hass, entry, "binary_sensor", "flaschendruck_alarm")
    pressure_id = _entity(hass, entry, "sensor", "flaschendruck")
    assert hass.states.get(alarm_id).state == "off"

    await _call(hass, entry, "add_measurement", kind="bottle_pressure", value=round(expected + 1.0, 2), temperature=20.0)
    state = hass.states.get(alarm_id)
    assert state.state == "on"
    assert state.attributes["handlung"] == ACTION_HIGH
    assert float(hass.states.get(pressure_id).state) == pytest.approx(expected + 1.0, abs=0.02)

    await _call(hass, entry, "add_measurement", kind="bottle_pressure", value=5.2, temperature=20.0)
    assert hass.states.get(alarm_id).attributes["handlung"] == ACTION_DANGER

    await _call(hass, entry, "add_measurement", kind="bottle_pressure", value=round(expected - 0.5, 2), temperature=20.0)
    assert hass.states.get(alarm_id).state == "off"


async def test_bottle_box_feeds_the_measurement_bottle(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.flasche_druck", "1.0")
    hass.states.async_set("sensor.flasche_temperatur", "10.0")
    entry = _entry(bottle_pressure_entity="sensor.flasche_druck", bottle_temperature_entity="sensor.flasche_temperatur")
    coord = await _setup(hass, entry)
    await _bottle_at(hass, entry, 7.0)
    hass.states.async_set("sensor.flasche_druck", "2.0")
    await hass.async_block_till_done()
    await coord.async_refresh()
    await hass.async_block_till_done()
    latest = coord.data.bottle.latest
    assert latest.p == pytest.approx(2.0)
    assert latest.temp_c == pytest.approx(10.0)
    assert latest.p20 > 2.0  # bei 20 °C höher als bei 10 °C


async def test_bottling_can_be_undone(hass: HomeAssistant) -> None:
    entry = _entry()
    coord = await _setup(hass, entry)
    await _bottle_at(hass, entry, 7.0)
    event = next(e for e in coord.store_data["events"] if e["kind"] == "bottled")
    await _call(hass, entry, "remove_entry", kind="bottled", time=event["time"])
    assert coord.bottling is None
    assert hass.states.get(_entity(hass, entry, "sensor", "status")).state != "bottled"
    with pytest.raises(HomeAssistantError):
        await _call(hass, entry, "remove_entry", kind="bottled", time=event["time"])


async def test_closing_archives_and_teaches_the_house(hass: HomeAssistant, hass_ws_client) -> None:
    entry = _entry("DATA 2025", start=(dt_util.utcnow() - timedelta(days=50)).isoformat())
    other = _entry("DATA 2026")
    coord = await _setup(hass, entry)
    await _setup(hass, other)
    await _bottle_at(hass, entry, 7.0)
    model = coord.model()
    await _call(hass, entry, "add_measurement", kind="sugar", value=7.0, value2=round(model.abv(7.0) + 0.3, 2))
    # Abfüllen liegt fünf Wochen zurück; die Messflasche ist durchgegoren und steht höher als erwartet
    now = dt_util.utcnow()
    coord.store_data["bottling"]["time"] = (now - timedelta(days=35)).isoformat()
    for days, p in ((14, 3.0), (7, 3.1), (1, 3.1)):
        await _call(hass, entry, "add_measurement", kind="bottle_pressure", value=p, temperature=20.0,
                    time=now - timedelta(days=days))
    assert coord.data.bottle.done

    house = get_house(hass)
    before = house.values["saturation"].mean
    await _call(hass, entry, "add_event", kind="closed")
    assert len(house.archive) == 1
    record = house.archive[0]
    assert record["name"] == "DATA 2025"
    assert record["observed"]["saturation"][0] > before  # mehr Druck als erwartet: mehr CO2 beim Abfüllen
    assert record["observed"]["g_sugar_per_abv"] is not None
    assert house.values["saturation"].mean > before
    assert house.values["saturation"].n == 1
    await hass.async_block_till_done()
    assert other.runtime_data.settings().saturation == pytest.approx(house.values["saturation"].mean)

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "tipsylab/batches"})
    result = (await client.receive_json())["result"]
    assert result["house"]["archive"][0]["name"] == "DATA 2025"
    assert result["house"]["values"]["saturation"]["n"] == 1

    closed = next(e for e in coord.store_data["events"] if e["kind"] == "closed")
    await _call(hass, entry, "remove_entry", kind="closed", time=closed["time"])
    assert house.archive == []
    assert house.values["saturation"].n == 0
