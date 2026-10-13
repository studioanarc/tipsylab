"""Die Integration im echten Home Assistant: Einrichten, Messen, Rechnen, Panel-Daten."""

from datetime import timedelta
from itertools import pairwise
import json
from unittest.mock import ANY

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

DOMAIN = "tipsylab"


def _entity(hass: HomeAssistant, entry: MockConfigEntry, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry.entry_id}_{key}")
    assert entity_id, key
    return entity_id


async def test_config_flow_creates_petnat_batch(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "DATA Rosé 2026", "mode": "petnat", "brix0": 20.5, "volume_l": 750}
    )
    assert result["step_id"] == "sources"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"gravity_unit": "sg"})
    assert result["step_id"] == "target"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"target_bar_20c": 2.5, "bottle": "750", "malo_in_bottle": True, "malic_g_l": 1.5, "q10": 2.2},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "DATA Rosé 2026"
    assert result["data"]["brix0"] == 20.5
    assert result["options"]["malo_in_bottle"] is True
    await hass.async_block_till_done()


async def test_config_flow_needs_must_value(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Ohne Most", "mode": "petnat", "volume_l": 50}
    )
    assert result["errors"] == {"base": "must_required"}


async def test_measurements_drive_estimate(hass: HomeAssistant, petnat_entry: MockConfigEntry) -> None:
    hass.states.async_set("sensor.spindel_gravity", "1.0040")
    hass.states.async_set("sensor.wein_temperatur", "14.0")
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    await hass.async_block_till_done()

    sugar_id = _entity(hass, petnat_entry, "sensor", "restzucker")
    status_id = _entity(hass, petnat_entry, "sensor", "status")
    assert hass.states.get(status_id) is not None

    now = dt_util.utcnow()
    model = petnat_entry.runtime_data.model()
    r30, r20, r14 = (round(model.refractometer_reading(s), 2) for s in (30, 20, 14))
    for days, brix in ((3, r30), (1, r20)):
        await hass.services.async_call(
            DOMAIN,
            "add_measurement",
            {"config_entry_id": petnat_entry.entry_id, "kind": "brix", "value": brix, "time": now - timedelta(days=days)},
            blocking=True,
        )
    await hass.services.async_call(
        DOMAIN,
        "add_measurement",
        {"config_entry_id": petnat_entry.entry_id, "kind": "brix", "value": r14},
        blocking=True,
    )
    await hass.async_block_till_done()
    expected = model.sugar_from_refractometer(r14)
    sugar = float(hass.states.get(sugar_id).state)
    assert sugar == pytest.approx(expected, abs=3.0)
    assert hass.states.get(_entity(hass, petnat_entry, "sensor", "zielzucker")).state == "6.53"
    assert float(hass.states.get(_entity(hass, petnat_entry, "sensor", "druck_jetzt_20")).state) > 2.5
    assert hass.states.get(_entity(hass, petnat_entry, "sensor", "dub")).state not in ("unknown", "unavailable")
    assert hass.states.get(_entity(hass, petnat_entry, "binary_sensor", "flaschengrenze")).state == "off"


async def test_gravity_changes_are_recorded(hass: HomeAssistant, petnat_entry: MockConfigEntry) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    hass.states.async_set("sensor.spindel_gravity", "1.0120")
    hass.states.async_set("sensor.wein_temperatur", "15.5")
    await hass.async_block_till_done()
    readings = petnat_entry.runtime_data.store_data["readings"]
    assert readings["gravity"][-1][1] == pytest.approx(1.012)
    assert readings["temps"][-1][1] == pytest.approx(15.5)


async def test_settings_service_and_malo(hass: HomeAssistant, petnat_entry: MockConfigEntry) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        "update_settings",
        {"config_entry_id": petnat_entry.entry_id, "malo_in_bottle": True, "malic_g_l": 2.0, "volume_l": 700},
        blocking=True,
    )
    coord = petnat_entry.runtime_data
    assert coord.settings().malo_in_bottle is True
    assert coord.settings().malic_g_l == 2.0
    assert coord.volume_l == 700
    target = float(hass.states.get(_entity(hass, petnat_entry, "sensor", "zielzucker")).state)
    assert target == pytest.approx(6.53 - 1.40, abs=0.05)


async def test_websocket_batches(hass: HomeAssistant, petnat_entry: MockConfigEntry, hass_ws_client) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    await hass.services.async_call(
        DOMAIN, "add_measurement", {"config_entry_id": petnat_entry.entry_id, "kind": "brix", "value": 9.0},
        blocking=True,
    )
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "tipsylab/batches"})
    msg = await client.receive_json()
    assert msg["success"]
    batch = msg["result"]["batches"][0]
    assert batch["name"] == "Test"
    assert batch["settings"]["target_bar_20c"] == 2.5
    assert batch["estimate"]["target_sugar"] == pytest.approx(6.53, abs=0.01)
    assert batch["measurements"][-1]["value"] == 9.0


async def test_unknown_batch_is_rejected(hass: HomeAssistant, petnat_entry: MockConfigEntry) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    with pytest.raises(Exception, match="TIPSYLAB"):
        await hass.services.async_call(
            DOMAIN, "add_measurement", {"config_entry_id": "gibtsnicht", "kind": "brix", "value": 9.0}, blocking=True
        )


async def test_bubbles_via_mqtt_and_display(hass: HomeAssistant, mqtt_mock_entry, tmp_path) -> None:
    (tmp_path / "configuration.yaml").write_text("")  # das Test-Plugin bringt keine mit
    hass.config.config_dir = str(tmp_path)
    mqtt_mock = await mqtt_mock_entry()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ballon",
        data={"name": "Ballon", "mode": "petnat", "brix0": 20.0, "volume_l": 50,
              "start": (dt_util.utcnow() - timedelta(days=2)).isoformat(), "bubble_device": "tipsy-abc123"},
        options={"target_bar_20c": 2.5, "bottle": "750", "q10": 2.2, "dry_sugar_g_l": 2.0, "filling_loss": 0.08},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    for seq, (n, total) in enumerate(((12, 12), (15, 27), (9, 36)), start=1):
        async_fire_mqtt_message(
            hass, "sensors/bubble/tipsy-abc123",
            json.dumps({"bubbles": n, "total": total, "boot_id": "b1", "seq": seq, "temperature": 16.2}),
        )
    await hass.async_block_till_done()
    coord = entry.runtime_data
    assert coord.store_data["readings"]["bubbles"][-1][1] == 36
    assert coord.store_data["readings"]["temps"][-1][1] == pytest.approx(16.2)
    await coord.async_refresh()
    mqtt_mock.async_publish.assert_any_call("tipsy/tipsy-abc123/display", ANY, 0, True)


async def test_charmat_setpoint(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.tank_druck", "1.82")
    hass.states.async_set("sensor.tank_temperatur", "12.0")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Tank 03",
        data={"name": "Tank 03", "mode": "charmat", "volume_l": 300,
              "start": dt_util.utcnow().isoformat(),
              "pressure_entity": "sensor.tank_druck", "temperature_entity": "sensor.tank_temperatur"},
        options={"target_bar_20c": 2.5, "filling_loss": 0.08, "prv_bar": 5.5},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    setpoint = float(hass.states.get(_entity(hass, entry, "sensor", "tank_sollwert")).state)
    assert setpoint == pytest.approx(1.86, abs=0.01)
    assert hass.states.get(_entity(hass, entry, "binary_sensor", "sicherheitsabstand")).state == "off"
    assert hass.states.get(_entity(hass, entry, "sensor", "status")).state == "charmat"


async def test_options_flow_updates_target(hass: HomeAssistant, petnat_entry: MockConfigEntry) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    result = await hass.config_entries.options.async_init(petnat_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"target_bar_20c": 3.0, "bottle": "330", "malo_in_bottle": False, "malic_g_l": 0.0, "q10": 2.0,
         "temp_start": 20.0, "temp_switch_sugar": 25.0, "temp_late": 14.0},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert petnat_entry.options["target_bar_20c"] == 3.0
    assert petnat_entry.options["temp_late"] == 14.0
    settings = petnat_entry.runtime_data.settings()
    assert settings.temp_plan == ((None, 20.0), (25.0, 14.0))
    assert settings.bottle == "330"


async def test_preview_does_not_store(hass: HomeAssistant, petnat_entry: MockConfigEntry, hass_ws_client) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    coord = petnat_entry.runtime_data
    model = coord.model()
    reading = model.refractometer_reading(15.0)
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "tipsylab/preview", "entry_id": petnat_entry.entry_id, "kind": "brix", "value": reading}
    )
    msg = await client.receive_json()
    assert msg["success"], msg
    result = msg["result"]
    assert result["sugar"] == pytest.approx(15.0, abs=0.05)
    assert result["plausible"] is True
    assert result["abv"] > 9
    assert coord.store_data["measurements"] == []

    await client.send_json(
        {"id": 2, "type": "tipsylab/preview", "entry_id": petnat_entry.entry_id, "kind": "malic", "value": 2.0}
    )
    msg = await client.receive_json()
    assert msg["result"]["target_sugar"] == pytest.approx(6.53, abs=0.05)  # Malo nicht mitgerechnet

    await client.send_json(
        {"id": 3, "type": "tipsylab/preview", "entry_id": "gibtsnicht", "kind": "brix", "value": 8.0}
    )
    msg = await client.receive_json()
    assert not msg["success"]


async def test_bottle_alcohol_from_a_pair(hass: HomeAssistant, petnat_entry: MockConfigEntry, hass_ws_client) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    await hass.async_block_till_done()
    model = petnat_entry.runtime_data.model()
    bottle_id = _entity(hass, petnat_entry, "sensor", "alkohol_flasche")
    before = hass.states.get(bottle_id)
    assert float(before.state) == pytest.approx(model.abv(2.0), abs=0.05)
    assert before.attributes["messpaare"] == 0

    pair = {"kind": "brix_density", "value": model.refractometer_reading(15.0), "value2": model.density(15.0), "unit": "sg"}
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "tipsylab/preview", "entry_id": petnat_entry.entry_id, **pair})
    msg = await client.receive_json()
    assert msg["success"], msg
    result = msg["result"]
    assert result["abv_pair"] == pytest.approx(model.abv(15.0), abs=0.05)
    assert result["abv_pairs"] == 1
    assert result["abv_end_sigma"] < result["prev_abv_end_sigma"]

    await hass.services.async_call(
        DOMAIN, "add_measurement", {"config_entry_id": petnat_entry.entry_id, **pair}, blocking=True
    )
    await hass.async_block_till_done()
    after = hass.states.get(bottle_id)
    assert after.attributes["messpaare"] == 1
    assert after.attributes["unsicherheit"] < before.attributes["unsicherheit"]
    assert after.attributes["etikett"] == 12.0
    assert after.attributes["etikett_sicher"] is True
    await client.send_json({"id": 2, "type": "tipsylab/batches"})
    batch = (await client.receive_json())["result"]["batches"][0]
    assert batch["estimate"]["abv_pairs"] == 1
    assert batch["estimate"]["abv_label"] == 12.0


async def test_readings_keep_latest_time(hass: HomeAssistant, petnat_entry: MockConfigEntry) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    coord = petnat_entry.runtime_data
    t0 = dt_util.utcnow() - timedelta(hours=2)
    for minute in range(31):  # jede Minute ein Wert
        coord._record("bubbles", t0 + timedelta(minutes=minute), 10.0 * minute)
    series = coord.store_data["readings"]["bubbles"]
    times = [dt_util.parse_datetime(t) for t, _ in series]
    assert series[-1][1] == 300.0
    assert times[-1] == t0 + timedelta(minutes=30)
    assert all((b - a) >= timedelta(minutes=4) for a, b in pairwise(times[:-1]))
    assert len(series) <= 9


async def test_panel_history_bubble_rates(hass: HomeAssistant, petnat_entry: MockConfigEntry) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    coord = petnat_entry.runtime_data
    now = dt_util.utcnow()
    t0 = now - timedelta(hours=3)
    for minute in range(0, 181, 1):  # 12 Blasen pro Minute
        coord._record("bubbles", t0 + timedelta(minutes=minute), 12.0 * minute)
    history = coord.panel_data()["history"]
    assert history["bubbles_bpm"]
    for _, bpm in history["bubbles_bpm"]:
        assert bpm == pytest.approx(12.0, abs=0.01)
    assert history["bpm_now"] == pytest.approx(12.0, abs=0.1)


async def test_charmat_without_must_accepts_brix(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Tank 04",
        data={"name": "Tank 04", "mode": "charmat", "volume_l": 300, "start": dt_util.utcnow().isoformat()},
        options={"target_bar_20c": 2.5, "filling_loss": 0.08},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.services.async_call(
        DOMAIN, "add_measurement", {"config_entry_id": entry.entry_id, "kind": "brix", "value": 9.0}, blocking=True
    )
    data = entry.runtime_data.panel_data()
    assert data["measurements"][-1]["value"] == 9.0
    assert data["s0"] is None
    assert data["anchors"] == []


async def test_weight_in_grams_is_recorded_as_kg(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.waage", "64250", {"unit_of_measurement": "g"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ballon 2",
        data={"name": "Ballon 2", "mode": "petnat", "brix0": 20.5, "volume_l": 50,
              "start": (dt_util.utcnow() - timedelta(days=3)).isoformat(), "weight_entity": "sensor.waage"},
        options={"target_bar_20c": 2.5, "bottle": "750", "q10": 2.2, "dry_sugar_g_l": 2.0, "filling_loss": 0.08},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coord = entry.runtime_data
    assert coord.store_data["readings"]["weight"][-1][1] == pytest.approx(64.25)
    assert coord.settings().volume_l == 50
    assert coord.panel_data()["has_weight"] is True


async def test_weight_from_gaerbox_payload(hass: HomeAssistant, mqtt_mock_entry, tmp_path) -> None:
    (tmp_path / "configuration.yaml").write_text("")
    hass.config.config_dir = str(tmp_path)
    await mqtt_mock_entry()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ballon 3",
        data={"name": "Ballon 3", "mode": "petnat", "brix0": 20.0, "volume_l": 50,
              "start": (dt_util.utcnow() - timedelta(days=2)).isoformat(), "bubble_device": "tipsy-def456"},
        options={"target_bar_20c": 2.5, "bottle": "750", "q10": 2.2, "dry_sugar_g_l": 2.0, "filling_loss": 0.08},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    async_fire_mqtt_message(
        hass, "sensors/bubble/tipsy-def456",
        json.dumps({"bubbles": 20, "total": 20, "boot_id": "b1", "seq": 1, "weight_kg": 69.125}),
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.store_data["readings"]["weight"][-1][1] == pytest.approx(69.125)


async def test_reconfigure_adds_a_scale_and_keeps_data(hass: HomeAssistant, petnat_entry: MockConfigEntry) -> None:
    petnat_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(petnat_entry.entry_id)
    await hass.services.async_call(
        DOMAIN, "add_measurement", {"config_entry_id": petnat_entry.entry_id, "kind": "brix", "value": 9.0},
        blocking=True,
    )
    result = await petnat_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"gravity_entity": "sensor.spindel_gravity", "gravity_unit": "sg",
         "temperature_entity": "sensor.wein_temperatur", "weight_entity": "sensor.waage"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert petnat_entry.data["weight_entity"] == "sensor.waage"
    assert petnat_entry.data["brix0"] == 20.5
    assert petnat_entry.runtime_data.store_data["measurements"][-1]["value"] == 9.0
