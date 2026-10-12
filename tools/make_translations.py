"""Erzeugt strings.json und translations/{de,en}.json der Integration aus einer Quelle.

Aufruf: python3 tools/make_translations.py
Texte hier ändern, nie in den erzeugten JSON-Dateien.
"""

import json
import pathlib
import sys


def tr(lang: str) -> dict:
    de = lang == "de"

    def L(d: str, e: str) -> str:
        return d if de else e

    target_data = {
        "target_bar_20c": L("Druck beim Öffnen bei 20 °C", "Opening pressure at 20 °C"),
        "bottle": L("Flasche", "Bottle"),
        "malo_in_bottle": L("Malo in der Flasche mitrechnen", "Count malolactic in the bottle"),
        "malic_g_l": L("Äpfelsäure beim Abfüllen", "Malic acid at bottling"),
        "dry_sugar_g_l": L("Trocken unter", "Dry below"),
        "prv_bar": L("Sicherheitsventil öffnet bei", "Safety valve opens at"),
        "filling_loss": L("CO₂-Verlust beim isobaren Abfüllen (Anteil)", "CO₂ loss in isobaric filling (fraction)"),
        "temp_start": L("Temperatur zu Beginn", "Temperature at start"),
        "temp_switch_sugar": L("Umschalten ab Restzucker", "Switch at residual sugar"),
        "temp_late": L("Temperatur danach", "Temperature afterwards"),
        "q10": L("Q10 (Temperaturfaktor je 10 °C)", "Q10 (rate factor per 10 °C)"),
    }
    target_desc = {
        "target_bar_20c": L(
            "EU: frisante/pétillant bis 2,5 bar, espumante/mousseux ab 3 bar (bei 20 °C).",
            "EU: semi-sparkling up to 2.5 bar, sparkling from 3 bar (at 20 °C).",
        ),
        "malo_in_bottle": L(
            "An, wenn beim Abfüllen noch Äpfelsäure da ist: Pro g/L wird 0,7 g/L weniger Restzucker abgefüllt.",
            "On if malic acid remains at bottling: 0.7 g/L less sugar per g/L malic acid.",
        ),
        "temp_switch_sugar": L(
            "Zum Beispiel 20 °C für die Malo, ab 25 g/L 14 °C. Leer lassen für keinen Plan.",
            "E.g. 20 °C for malolactic, 14 °C from 25 g/L. Leave empty for no plan.",
        ),
    }
    source_data = {
        "bubble_device": L(
            "Blasenzähler: Geräte-ID der Gärbox, z. B. tipsy-a1b2c3", "Bubble counter: Gärbox device id, e.g. tipsy-a1b2c3"
        ),
        "gravity_entity": L("Spindel: Dichte-Sensor", "Hydrometer: gravity sensor"),
        "gravity_unit": L("Einheit der Spindel", "Hydrometer unit"),
        "temperature_entity": L("Temperatur im Wein", "Wine temperature"),
        "weight_entity": L("Waage (Gewicht des Gefäßes)", "Scale (vessel weight)"),
        "heater_host": L("Heizung: Shelly-Adresse (IP)", "Heater: Shelly address (IP)"),
        "pressure_entity": L("Tankdruck", "Tank pressure"),
        "co2_target_entity": L(
            "CO₂-Ziel am Regler (ESPHome-Zahl der Tankbox)", "CO₂ target on the controller (Tankbox ESPHome number)"
        ),
    }
    return {
        "config": {
            "step": {
                "user": {
                    "title": L("Neuer Ansatz", "New batch"),
                    "description": L(
                        "Start-Brix oder Startdichte des Mosts angeben (bei Charmat nicht nötig).",
                        "Give the starting Brix or density of the must (not needed for Charmat).",
                    ),
                    "data": {
                        "name": L("Name", "Name"),
                        "mode": L("Betriebsart", "Mode"),
                        "brix0": L("Start-Brix (Refraktometer)", "Starting Brix (refractometer)"),
                        "sg0": L("Startdichte (SG)", "Starting gravity (SG)"),
                        "volume_l": L("Volumen", "Volume"),
                        "start": L("Gärbeginn (leer = jetzt)", "Start of fermentation (empty = now)"),
                    },
                },
                "sources": {
                    "title": L("Quellen", "Sources"),
                    "description": L(
                        "Alles optional; Messungen trägst du später im Panel ein.",
                        "All optional; you enter measurements later in the panel.",
                    ),
                    "data": source_data,
                },
                "reconfigure": {
                    "title": L("Quellen ändern", "Change sources"),
                    "description": L(
                        "Zum Beispiel eine Waage nachrüsten. Messungen und Verlauf bleiben erhalten.",
                        "For example add a scale. Measurements and history are kept.",
                    ),
                    "data": source_data,
                },
                "target": {"title": L("Ziel", "Target"), "data": target_data, "data_description": target_desc},
            },
            "error": {"must_required": L("Start-Brix oder Startdichte fehlt.", "Starting Brix or gravity is missing.")},
            "abort": {
                "reconfigure_successful": L("Quellen gespeichert.", "Sources saved."),
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": L("Ziel und Temperaturplan", "Target and temperature plan"),
                    "data": target_data,
                    "data_description": target_desc,
                }
            }
        },
        "selector": {
            "mode": {
                "options": {
                    "petnat": "Pet Nat",
                    "still": L("Naturwein (still)", "Natural wine (still)"),
                    "charmat": "Charmat",
                }
            },
            "bottle": {
                "options": {
                    "750": L("750 ml · Kronkorken bis 6 bar", "750 ml · crown cap up to 6 bar"),
                    "330": L("330 ml · Kronkorken bis 4,5 bar", "330 ml · crown cap up to 4.5 bar"),
                }
            },
            "gravity_unit": {
                "options": {
                    "sg": "SG",
                    "oe": "°Oechsle",
                    "plato": L("°Plato (falls die Spindel so sendet)", "°Plato (if the hydrometer sends it)"),
                }
            },
            "measurement_kind": {
                "options": {
                    "brix": L("Refraktometer (°Bx)", "Refractometer (°Bx)"),
                    "density": L("Dichte", "Density"),
                    "brix_density": L("Refraktometer + Dichte", "Refractometer + density"),
                    "sugar": L("Restzucker (Labor, g/L)", "Residual sugar (lab, g/L)"),
                    "malic": L("Äpfelsäure (g/L)", "Malic acid (g/L)"),
                    "ph": "pH",
                    "bottle_pressure": L("Flaschendruck (bar)", "Bottle pressure (bar)"),
                }
            },
            "density_unit": {"options": {"sg": "SG", "oe": "°Oechsle", "baume": "°Baumé", "gcm3": "g/cm³"}},
            "event_kind": {
                "options": {
                    "racking": L("Abstich", "Racking"),
                    "volume": L("Volumen geändert", "Volume changed"),
                    "cooling": L("Kühlen", "Cooling"),
                    "heating": L("Heizen", "Heating"),
                    "bottled": L("Abgefüllt", "Bottled"),
                    "note": L("Notiz", "Note"),
                }
            },
        },
        "entity": {
            "sensor": {
                "restzucker": {"name": L("Restzucker", "Residual sugar")},
                "alkohol": {"name": L("Alkohol", "Alcohol")},
                "gaergeschwindigkeit": {"name": L("Gärgeschwindigkeit", "Fermentation rate")},
                "zielzucker": {"name": L("Zielzucker", "Target sugar")},
                "dub": {"name": L("Zeit bis zum Abfüllen", "Time until bottling")},
                "abfuellen": {"name": L("Abfüllen", "Bottling")},
                "fenster_beginn": {"name": L("Fenster Beginn", "Window start")},
                "fenster_ende": {"name": L("Fenster Ende", "Window end")},
                "druck_jetzt_10": {"name": L("Druck wenn jetzt (10 °C)", "Pressure if now (10 °C)")},
                "druck_jetzt_20": {"name": L("Druck wenn jetzt (20 °C)", "Pressure if now (20 °C)")},
                "solltemperatur": {"name": L("Solltemperatur", "Target temperature")},
                "tank_sollwert": {"name": L("Tank-Sollwert", "Tank set point")},
                "co2_ziel": {"name": L("CO₂-Ziel", "CO₂ target")},
                "co2_geloest": {"name": L("CO₂ gelöst", "Dissolved CO₂")},
                "status": {
                    "name": "Status",
                    "state": {
                        "waiting": L("wartet auf Daten", "waiting for data"),
                        "fermenting": L("gärt", "fermenting"),
                        "approaching": L("nähert sich", "approaching"),
                        "window": L("im Fenster", "in window"),
                        "past": L("Fenster vorbei", "window passed"),
                        "dry": L("trocken", "dry"),
                        "stuck": L("stockt?", "stuck?"),
                        "charmat": L("Charmat-Regelung", "Charmat control"),
                    },
                },
            },
            "binary_sensor": {
                "im_fenster": {"name": L("Im Abfüllfenster", "In bottling window")},
                "messung_empfohlen": {"name": L("Messung empfohlen", "Measurement recommended")},
                "flaschengrenze": {"name": L("Flaschengrenze überschritten", "Bottle limit exceeded")},
                "sicherheitsabstand": {
                    "name": L("Sollwert zu nah am Sicherheitsventil", "Set point too close to safety valve")
                },
            },
        },
        "services": {
            "add_measurement": {
                "name": L("Messung eintragen", "Add measurement"),
                "description": L(
                    "Refraktometer, Dichte, Labor, Äpfelsäure, pH oder Flaschendruck.",
                    "Refractometer, density, lab, malic acid, pH or bottle pressure.",
                ),
                "fields": {
                    "config_entry_id": {"name": L("Ansatz", "Batch"), "description": ""},
                    "kind": {"name": L("Art", "Kind"), "description": ""},
                    "value": {
                        "name": L("Wert", "Value"),
                        "description": L("Bei Refraktometer + Dichte: der Brix-Wert.", "For refractometer + density: the Brix value."),
                    },
                    "value2": {
                        "name": L("Zweiter Wert", "Second value"),
                        "description": L("Bei Refraktometer + Dichte: die Dichte.", "For refractometer + density: the density."),
                    },
                    "unit": {"name": L("Dichte-Einheit", "Density unit"), "description": ""},
                    "temperature": {
                        "name": L("Temperatur", "Temperature"),
                        "description": L("Bei Flaschendruck: Temperatur der Flasche.", "For bottle pressure: bottle temperature."),
                    },
                    "time": {"name": L("Zeitpunkt", "Time"), "description": L("Leer = jetzt.", "Empty = now.")},
                    "note": {"name": L("Notiz", "Note"), "description": ""},
                },
            },
            "add_event": {
                "name": L("Ereignis eintragen", "Add event"),
                "description": L(
                    "Abstich, Volumen, Kühlen, Heizen, Abgefüllt oder Notiz.",
                    "Racking, volume, cooling, heating, bottled or note.",
                ),
                "fields": {
                    "config_entry_id": {"name": L("Ansatz", "Batch"), "description": ""},
                    "kind": {"name": L("Art", "Kind"), "description": ""},
                    "value": {
                        "name": L("Wert", "Value"),
                        "description": L("Bei Volumen: neues Volumen in Litern.", "For volume: new volume in litres."),
                    },
                    "note": {"name": L("Notiz", "Note"), "description": ""},
                },
            },
            "update_settings": {
                "name": L("Einstellungen ändern", "Update settings"),
                "description": L(
                    "Ziel, Flasche, Malo, Volumen und Temperaturplan eines Ansatzes.",
                    "Target, bottle, malolactic, volume and temperature plan of a batch.",
                ),
                "fields": {
                    "config_entry_id": {"name": L("Ansatz", "Batch"), "description": ""},
                    **{k: {"name": v, "description": ""} for k, v in target_data.items()},
                    "volume_l": {"name": L("Volumen", "Volume"), "description": ""},
                },
            },
        },
    }


if __name__ == "__main__":
    base = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tipsylab"
    (base / "translations").mkdir(exist_ok=True)
    for lang in ("en", "de"):
        (base / "translations" / f"{lang}.json").write_text(json.dumps(tr(lang), ensure_ascii=False, indent=2) + "\n")
    (base / "strings.json").write_text(json.dumps(tr("en"), ensure_ascii=False, indent=2) + "\n")
    print("ok")
