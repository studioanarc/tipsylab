"""Quellen überwachen: „Quelle stumm“ und „Akku schwach“, Handlungen in der Sprache des Servers."""

from datetime import timedelta

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tipsylab.texts import lang_of, say
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

DOMAIN = "tipsylab"


def _entity(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id, key
    return entity_id


def _entry(**data) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        data={
            "name": "Test",
            "mode": "petnat",
            "brix0": 20.5,
            "volume_l": 750,
            "start": (dt_util.utcnow() - timedelta(days=5)).isoformat(),
            **data,
        },
        options={"target_bar_20c": 2.5, "bottle": "750"},
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data


async def _refresh(hass: HomeAssistant, coord) -> None:
    await coord.async_refresh()
    await hass.async_block_till_done()


def test_server_language():
    assert lang_of("de") == "de"
    assert lang_of("fr-CA") == "fr"
    assert lang_of("pt") == "en"  # alles andere: Englisch
    assert lang_of(None) == "en"
    assert "Spindel" in say("silent", "de", hours=3, sources=say("source_gravity", "de"))
    assert "densimètre" in say("silent", "fr", hours=3, sources=say("source_gravity", "fr"))


async def test_silent_source_after_three_hours(hass: HomeAssistant, freezer) -> None:
    hass.states.async_set("sensor.pill_gravity", "1.010")
    entry = _entry(gravity_entity="sensor.pill_gravity")
    coord = await _setup(hass, entry)
    silent = _entity(hass, entry, "binary_sensor", "quelle_stumm")
    assert hass.states.get(silent).state == "off"

    freezer.tick(timedelta(hours=2))
    hass.states.async_set("sensor.pill_gravity", "1.010")  # gleicher Wert: trotzdem ein Lebenszeichen
    freezer.tick(timedelta(hours=2, minutes=30))
    await _refresh(hass, coord)
    assert hass.states.get(silent).state == "off"

    freezer.tick(timedelta(hours=1))
    await _refresh(hass, coord)
    state = hass.states.get(silent)
    assert state.state == "on"
    assert state.attributes["quellen"] == ["gravity"]
    assert state.attributes["handlung"] == say("silent", "en", hours=3, sources="hydrometer")

    hass.states.async_set("sensor.pill_gravity", "1.009")  # meldet sich wieder
    await _refresh(hass, coord)
    assert hass.states.get(silent).state == "off"


async def test_missing_source_counts_from_the_start_and_speaks_german(hass: HomeAssistant, freezer) -> None:
    """Eine Quelle, die nie etwas geschickt hat, gilt erst 3 h nach dem Laden als stumm (kein Fehlalarm beim Neustart)."""
    hass.config.language = "de"
    entry = _entry(gravity_entity="sensor.gibts_nicht", temperature_entity="sensor.wein_temperatur")
    hass.states.async_set("sensor.wein_temperatur", "14.0")
    coord = await _setup(hass, entry)
    silent = _entity(hass, entry, "binary_sensor", "quelle_stumm")
    freezer.tick(timedelta(hours=2, minutes=50))
    hass.states.async_set("sensor.wein_temperatur", "14.1")
    await _refresh(hass, coord)
    assert hass.states.get(silent).state == "off"
    freezer.tick(timedelta(minutes=20))
    await _refresh(hass, coord)
    state = hass.states.get(silent)
    assert state.state == "on"
    assert state.attributes["quellen"] == ["gravity"]
    assert "Spindel" in state.attributes["handlung"]


async def test_after_bottling_only_the_bottle_counts(hass: HomeAssistant, freezer) -> None:
    entry = _entry(gravity_entity="sensor.pill_gravity", bottle_pressure_entity="sensor.flasche_druck")
    hass.states.async_set("sensor.pill_gravity", "1.004")
    coord = await _setup(hass, entry)
    model = coord.model()
    await hass.services.async_call(
        DOMAIN, "add_measurement",
        {"config_entry_id": entry.entry_id, "kind": "brix", "value": round(model.refractometer_reading(7.0), 2)},
        blocking=True,
    )
    await hass.services.async_call(DOMAIN, "add_event", {"config_entry_id": entry.entry_id, "kind": "bottled"}, blocking=True)
    hass.states.async_set("sensor.flasche_druck", "1.2")
    freezer.tick(timedelta(hours=4))
    hass.states.async_set("sensor.flasche_druck", "1.3")
    await _refresh(hass, coord)
    # die Spindel ist nach dem Abfüllen raus; die Flaschenbox meldet sich
    assert hass.states.get(_entity(hass, entry, "binary_sensor", "quelle_stumm")).state == "off"


async def test_low_battery_of_the_hydrometer(hass: HomeAssistant) -> None:
    pill_entry = MockConfigEntry(domain="rapt_ble")
    pill_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=pill_entry.entry_id, identifiers={("rapt_ble", "pill")}, name="RAPT Pill"
    )
    entities = er.async_get(hass)
    gravity = entities.async_get_or_create(
        "sensor", "rapt_ble", "pill_sg", device_id=device.id, suggested_object_id="pill_gravity"
    )
    battery = entities.async_get_or_create(
        "sensor", "rapt_ble", "pill_battery", device_id=device.id,
        original_device_class=SensorDeviceClass.BATTERY, suggested_object_id="pill_battery",
    )
    hass.states.async_set(gravity.entity_id, "1.010")
    hass.states.async_set(battery.entity_id, "15")
    entry = _entry(gravity_entity=gravity.entity_id)
    coord = await _setup(hass, entry)

    low = _entity(hass, entry, "binary_sensor", "akku_schwach")
    state = hass.states.get(low)
    assert state.state == "on"
    assert state.attributes["geraet"] == "RAPT Pill"
    assert state.attributes["akku"] == 15
    assert state.attributes["handlung"] == say("battery", "en", device="RAPT Pill", pct=15)
    assert coord.panel_data()["battery"] == ["RAPT Pill", 15.0]

    hass.states.async_set(battery.entity_id, "80")
    await _refresh(hass, coord)
    assert hass.states.get(low).state == "off"
    assert hass.states.get(low).attributes["akku"] == 80
