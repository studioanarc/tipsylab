"""Konstanten der TIPSYLAB-Integration."""

from __future__ import annotations

DOMAIN = "tipsylab"
VERSION = "0.1.0"

# Konfiguration eines Ansatzes (entry.data)
CONF_NAME = "name"
CONF_MODE = "mode"  # petnat | still | charmat
CONF_START = "start"
CONF_BRIX0 = "brix0"
CONF_SG0 = "sg0"
CONF_VOLUME = "volume_l"
CONF_BUBBLE_DEVICE = "bubble_device"  # z. B. tipsy-a1b2c3 (Geräte-ID des AtomS3)
CONF_GRAVITY_ENTITY = "gravity_entity"
CONF_GRAVITY_UNIT = "gravity_unit"  # sg | oe | plato
CONF_TEMP_ENTITY = "temperature_entity"
CONF_PRESSURE_ENTITY = "pressure_entity"  # Charmat: Tankdruck
CONF_CO2_TARGET_ENTITY = "co2_target_entity"  # Charmat: number-Entität des ESPHome-Reglers
CONF_HEATER_HOST = "heater_host"  # Shelly mit thermostat.js
CONF_WEIGHT_ENTITY = "weight_entity"  # Waage (kg oder g), z. B. Gärbox mit HX711 oder Waagebox
CONF_BOTTLE_PRESSURE_ENTITY = "bottle_pressure_entity"  # Messflasche: Druck (Flaschenbox)
CONF_BOTTLE_TEMP_ENTITY = "bottle_temperature_entity"  # Messflasche: Temperatur

# Quellen eines Ansatzes: lassen sich über "Neu konfigurieren" ändern
SOURCE_KEYS = (
    "bubble_device",
    "gravity_entity",
    "gravity_unit",
    "temperature_entity",
    "weight_entity",
    "heater_host",
    "pressure_entity",
    "co2_target_entity",
    "bottle_pressure_entity",
    "bottle_temperature_entity",
)

# Einstellungen (entry.options)
OPT_TARGET_BAR = "target_bar_20c"
OPT_BOTTLE = "bottle"  # 330 | 750
OPT_MALO = "malo_in_bottle"
OPT_MALIC = "malic_g_l"
OPT_Q10 = "q10"
OPT_DRY_SUGAR = "dry_sugar_g_l"
OPT_TEMP_START = "temp_start"
OPT_TEMP_LATE = "temp_late"
OPT_TEMP_SWITCH_SUGAR = "temp_switch_sugar"
OPT_FILLING_LOSS = "filling_loss"
OPT_PRV_BAR = "prv_bar"

MODES = ["petnat", "still", "charmat"]
BOTTLES = ["750", "330"]
GRAVITY_UNITS = ["sg", "oe", "plato"]

DEFAULT_OPTIONS = {
    OPT_TARGET_BAR: 2.5,
    OPT_BOTTLE: "750",
    OPT_MALO: False,
    OPT_MALIC: 0.0,
    OPT_Q10: 2.2,
    OPT_DRY_SUGAR: 2.0,
    OPT_FILLING_LOSS: 0.08,
}

MEASUREMENT_KINDS = ["brix", "density", "brix_density", "sugar", "malic", "ph", "bottle_pressure"]
DENSITY_UNITS = ["sg", "oe", "baume", "gcm3"]
EVENT_KINDS = ["racking", "volume", "cooling", "heating", "bottled", "closed", "note"]

STATUS_OPTIONS = ["waiting", "fermenting", "approaching", "window", "past", "dry", "stuck", "bottled", "charmat"]

SERVICE_ADD_MEASUREMENT = "add_measurement"
SERVICE_ADD_EVENT = "add_event"
SERVICE_UPDATE_SETTINGS = "update_settings"
SERVICE_REMOVE_ENTRY = "remove_entry"

ATTR_ENTRY_ID = "config_entry_id"

DISPLAY_TOPIC = "tipsy/{device}/display"
BUBBLE_TOPIC = "sensors/bubble/{device}"
HEATER_KVS_KEY = "tipsylab_soll"

STORAGE_VERSION = 1
READING_INTERVAL_S = 300  # Sensorwerte werden auf 5 min verdichtet
READING_RETENTION_DAYS = 90
FORECAST_SNAPSHOT_MINUTES = 60  # Prognose-Stände für die Nachkalkulation, höchstens stündlich
FORECAST_SNAPSHOT_MAX = 24 * 45

PANEL_URL = "tipsylab"
STATIC_URL = "/tipsylab_static"
