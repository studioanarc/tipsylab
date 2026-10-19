"""Erzeugt strings.json und translations/{de,en,fr}.json der Integration aus einer Quelle.

Aufruf: python3 tools/make_translations.py
Texte hier ändern, nie in den erzeugten JSON-Dateien. Reihenfolge: L(Deutsch, Englisch, Französisch).
"""

import json
import pathlib
import sys

LANGS = ("de", "en", "fr")


def tr(lang: str) -> dict:
    def L(d: str, e: str, f: str) -> str:
        return {"de": d, "en": e, "fr": f}[lang]

    target_data = {
        "target_bar_20c": L("Druck beim Öffnen bei 20 °C", "Opening pressure at 20 °C", "Pression à l'ouverture à 20 °C"),
        "bottle": L("Flasche", "Bottle", "Bouteille"),
        "malo_in_bottle": L(
            "Malo in der Flasche mitrechnen", "Count malolactic in the bottle", "Compter la malolactique en bouteille"
        ),
        "malic_g_l": L("Äpfelsäure beim Abfüllen", "Malic acid at bottling", "Acide malique à la mise en bouteille"),
        "dry_sugar_g_l": L("Trocken unter", "Dry below", "Sec en dessous de"),
        "prv_bar": L("Sicherheitsventil öffnet bei", "Safety valve opens at", "La soupape de sécurité s'ouvre à"),
        "filling_loss": L(
            "CO₂-Verlust beim isobaren Abfüllen (Anteil)",
            "CO₂ loss in isobaric filling (fraction)",
            "Perte de CO₂ au tirage isobarique (fraction)",
        ),
        "temp_start": L("Temperatur zu Beginn", "Temperature at start", "Température au début"),
        "temp_switch_sugar": L("Umschalten ab Restzucker", "Switch at residual sugar", "Changer à partir du sucre résiduel"),
        "temp_late": L("Temperatur danach", "Temperature afterwards", "Température ensuite"),
        "q10": L("Q10 (Temperaturfaktor je 10 °C)", "Q10 (rate factor per 10 °C)", "Q10 (facteur par 10 °C)"),
        "public": L(
            "Auf der Website zeigen (DataWein-Feed)",
            "Show on the website (DataWein feed)",
            "Afficher sur le site (flux DataWein)",
        ),
    }
    target_desc = {
        "target_bar_20c": L(
            "EU: frisante/pétillant bis 2,5 bar, espumante/mousseux ab 3 bar (bei 20 °C).",
            "EU: semi-sparkling up to 2.5 bar, sparkling from 3 bar (at 20 °C).",
            "UE : pétillant jusqu'à 2,5 bar, mousseux à partir de 3 bar (à 20 °C).",
        ),
        "malo_in_bottle": L(
            "An, wenn beim Abfüllen noch Äpfelsäure da ist: Pro g/L wird 0,7 g/L weniger Restzucker abgefüllt.",
            "On if malic acid remains at bottling: 0.7 g/L less sugar per g/L malic acid.",
            "Activer s'il reste de l'acide malique à la mise en bouteille : 0,7 g/L de sucre en moins par g/L.",
        ),
        "temp_switch_sugar": L(
            "Zum Beispiel 20 °C für die Malo, ab 25 g/L 14 °C. Leer lassen für keinen Plan.",
            "E.g. 20 °C for malolactic, 14 °C from 25 g/L. Leave empty for no plan.",
            "Par exemple 20 °C pour la malo, 14 °C à partir de 25 g/L. Laisser vide pour aucun plan.",
        ),
    }
    source_data = {
        "bubble_device": L(
            "Blasenzähler: Geräte-ID der Gärbox, z. B. tipsy-a1b2c3",
            "Bubble counter: Gärbox device id, e.g. tipsy-a1b2c3",
            "Compteur de bulles : identifiant de la Gärbox, p. ex. tipsy-a1b2c3",
        ),
        "gravity_entity": L("Spindel: Dichte-Sensor", "Hydrometer: gravity sensor", "Densimètre : capteur de densité"),
        "gravity_unit": L("Einheit der Spindel", "Hydrometer unit", "Unité du densimètre"),
        "temperature_entity": L("Temperatur im Wein", "Wine temperature", "Température du vin"),
        "weight_entity": L("Waage (Gewicht des Gefäßes)", "Scale (vessel weight)", "Balance (poids de la cuve)"),
        "heater_host": L("Heizung: Shelly-Adresse (IP)", "Heater: Shelly address (IP)", "Chauffage : adresse du Shelly (IP)"),
        "pressure_entity": L("Tankdruck", "Tank pressure", "Pression de la cuve"),
        "co2_target_entity": L(
            "CO₂-Ziel am Regler (ESPHome-Zahl der Tankbox)",
            "CO₂ target on the controller (Tankbox ESPHome number)",
            "Objectif CO₂ du régulateur (nombre ESPHome de la Tankbox)",
        ),
        "bottle_pressure_entity": L(
            "Messflasche: Druck (Flaschenbox)",
            "Measurement bottle: pressure (bottle box)",
            "Bouteille témoin : pression (Flaschenbox)",
        ),
        "bottle_temperature_entity": L(
            "Messflasche: Temperatur", "Measurement bottle: temperature", "Bouteille témoin : température"
        ),
    }
    return {
        "config": {
            "step": {
                "user": {
                    "title": L("Neuer Ansatz", "New batch", "Nouvelle cuvée"),
                    "description": L(
                        "Start-Brix oder Startdichte des Mosts angeben (bei Charmat nicht nötig).",
                        "Give the starting Brix or density of the must (not needed for Charmat).",
                        "Indiquer le Brix ou la densité de départ du moût (inutile pour le Charmat).",
                    ),
                    "data": {
                        "name": L("Name", "Name", "Nom"),
                        "mode": L("Betriebsart", "Mode", "Mode"),
                        "brix0": L("Start-Brix (Refraktometer)", "Starting Brix (refractometer)", "Brix de départ (réfractomètre)"),
                        "sg0": L("Startdichte (SG)", "Starting gravity (SG)", "Densité de départ (SG)"),
                        "volume_l": L("Volumen", "Volume", "Volume"),
                        "start": L(
                            "Gärbeginn (leer = jetzt)",
                            "Start of fermentation (empty = now)",
                            "Début de fermentation (vide = maintenant)",
                        ),
                    },
                },
                "sources": {
                    "title": L("Quellen", "Sources", "Sources"),
                    "description": L(
                        "Alles optional; Messungen trägst du später im Panel ein.",
                        "All optional; you enter measurements later in the panel.",
                        "Tout est facultatif ; les mesures se saisissent ensuite dans le panneau.",
                    ),
                    "data": source_data,
                },
                "reconfigure": {
                    "title": L("Quellen ändern", "Change sources", "Modifier les sources"),
                    "description": L(
                        "Zum Beispiel eine Waage nachrüsten. Messungen und Verlauf bleiben erhalten.",
                        "For example add a scale. Measurements and history are kept.",
                        "Par exemple ajouter une balance. Les mesures et l'historique sont conservés.",
                    ),
                    "data": source_data,
                },
                "target": {
                    "title": L("Ziel", "Target", "Objectif"),
                    "data": target_data,
                    "data_description": target_desc,
                },
            },
            "error": {
                "must_required": L(
                    "Start-Brix oder Startdichte fehlt.",
                    "Starting Brix or gravity is missing.",
                    "Il manque le Brix ou la densité de départ.",
                )
            },
            "abort": {
                "reconfigure_successful": L("Quellen gespeichert.", "Sources saved.", "Sources enregistrées."),
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": L("Ziel und Temperaturplan", "Target and temperature plan", "Objectif et plan de température"),
                    "data": target_data,
                    "data_description": target_desc,
                }
            }
        },
        "selector": {
            "mode": {
                "options": {
                    "petnat": "Pet Nat",
                    "still": L("Naturwein (still)", "Natural wine (still)", "Vin nature (tranquille)"),
                    "charmat": "Charmat",
                }
            },
            "bottle": {
                "options": {
                    "750": L("750 ml · Kronkorken bis 6 bar", "750 ml · crown cap up to 6 bar", "750 ml · capsule jusqu'à 6 bar"),
                    "330": L(
                        "330 ml · Kronkorken bis 4,5 bar", "330 ml · crown cap up to 4.5 bar", "330 ml · capsule jusqu'à 4,5 bar"
                    ),
                }
            },
            "gravity_unit": {
                "options": {
                    "sg": "SG",
                    "oe": "°Oechsle",
                    "plato": L(
                        "°Plato (falls die Spindel so sendet)",
                        "°Plato (if the hydrometer sends it)",
                        "°Plato (si le densimètre l'envoie ainsi)",
                    ),
                }
            },
            "measurement_kind": {
                "options": {
                    "brix": L("Refraktometer (°Bx)", "Refractometer (°Bx)", "Réfractomètre (°Bx)"),
                    "density": L("Dichte", "Density", "Densité"),
                    "brix_density": L("Refraktometer + Dichte", "Refractometer + density", "Réfractomètre + densité"),
                    "sugar": L("Restzucker (Labor, g/L)", "Residual sugar (lab, g/L)", "Sucre résiduel (labo, g/L)"),
                    "malic": L("Äpfelsäure (g/L)", "Malic acid (g/L)", "Acide malique (g/L)"),
                    "ph": "pH",
                    "bottle_pressure": L("Flaschendruck (bar)", "Bottle pressure (bar)", "Pression en bouteille (bar)"),
                }
            },
            "density_unit": {"options": {"sg": "SG", "oe": "°Oechsle", "baume": "°Baumé", "gcm3": "g/cm³"}},
            "event_kind": {
                "options": {
                    "racking": L("Abstich", "Racking", "Soutirage"),
                    "volume": L("Volumen geändert", "Volume changed", "Volume modifié"),
                    "cooling": L("Kühlen", "Cooling", "Refroidissement"),
                    "heating": L("Heizen", "Heating", "Chauffage"),
                    "bottled": L("Abgefüllt", "Bottled", "Mis en bouteille"),
                    "closed": L("Abgeschlossen (ins Archiv)", "Closed (to the archive)", "Clôturé (aux archives)"),
                    "note": L("Notiz", "Note", "Note"),
                }
            },
        },
        "entity": {
            "sensor": {
                "restzucker": {"name": L("Restzucker", "Residual sugar", "Sucre résiduel")},
                "alkohol": {"name": L("Alkohol", "Alcohol", "Alcool")},
                "alkohol_flasche": {"name": L("Alkohol in der Flasche", "Alcohol in the bottle", "Alcool en bouteille")},
                "flaschendruck": {
                    "name": L("Messflasche bei 20 °C", "Measurement bottle at 20 °C", "Bouteille témoin à 20 °C")
                },
                "gaergeschwindigkeit": {"name": L("Gärgeschwindigkeit", "Fermentation rate", "Vitesse de fermentation")},
                "zielzucker": {"name": L("Zielzucker", "Target sugar", "Sucre visé")},
                "dub": {"name": L("Zeit bis zum Abfüllen", "Time until bottling", "Temps avant la mise en bouteille")},
                "abfuellen": {"name": L("Abfüllen", "Bottling", "Mise en bouteille")},
                "fenster_beginn": {"name": L("Fenster Beginn", "Window start", "Début de la fenêtre")},
                "fenster_ende": {"name": L("Fenster Ende", "Window end", "Fin de la fenêtre")},
                "druck_jetzt_10": {
                    "name": L("Druck wenn jetzt (10 °C)", "Pressure if now (10 °C)", "Pression si maintenant (10 °C)")
                },
                "druck_jetzt_20": {
                    "name": L("Druck wenn jetzt (20 °C)", "Pressure if now (20 °C)", "Pression si maintenant (20 °C)")
                },
                "solltemperatur": {"name": L("Solltemperatur", "Target temperature", "Température de consigne")},
                "tank_sollwert": {"name": L("Tank-Sollwert", "Tank set point", "Consigne de la cuve")},
                "co2_ziel": {"name": L("CO₂-Ziel", "CO₂ target", "Objectif CO₂")},
                "co2_geloest": {"name": L("CO₂ gelöst", "Dissolved CO₂", "CO₂ dissous")},
                "status": {
                    "name": L("Status", "Status", "État"),
                    "state": {
                        "waiting": L("wartet auf Daten", "waiting for data", "attend des données"),
                        "fermenting": L("gärt", "fermenting", "fermente"),
                        "approaching": L("nähert sich", "approaching", "approche"),
                        "window": L("im Fenster", "in window", "dans la fenêtre"),
                        "past": L("Fenster vorbei", "window passed", "fenêtre passée"),
                        "dry": L("trocken", "dry", "sec"),
                        "stuck": L("stockt?", "stuck?", "bloquée ?"),
                        "bottled": L("abgefüllt", "bottled", "mis en bouteille"),
                        "charmat": L("Charmat-Regelung", "Charmat control", "Régulation Charmat"),
                    },
                },
            },
            "binary_sensor": {
                "im_fenster": {"name": L("Im Abfüllfenster", "In bottling window", "Dans la fenêtre de mise en bouteille")},
                "messung_empfohlen": {"name": L("Messung empfohlen", "Measurement recommended", "Mesure recommandée")},
                "flaschengrenze": {
                    "name": L("Flaschengrenze überschritten", "Bottle limit exceeded", "Limite de la bouteille dépassée")
                },
                "sicherheitsabstand": {
                    "name": L(
                        "Sollwert zu nah am Sicherheitsventil",
                        "Set point too close to safety valve",
                        "Consigne trop proche de la soupape de sécurité",
                    )
                },
                "flaschendruck_alarm": {
                    "name": L(
                        "Messflasche über dem erwarteten Druck",
                        "Measurement bottle above expected pressure",
                        "Bouteille témoin au-dessus de la pression attendue",
                    )
                },
                "quelle_stumm": {"name": L("Quelle stumm", "Source silent", "Source muette")},
                "akku_schwach": {"name": L("Akku schwach", "Battery low", "Batterie faible")},
            },
        },
        "exceptions": {
            "unknown_batch": {
                "message": L(
                    "Kein TIPSYLAB-Ansatz mit der ID {entry_id}.",
                    "No TIPSYLAB batch with the id {entry_id}.",
                    "Aucune cuvée TIPSYLAB avec l'identifiant {entry_id}.",
                )
            },
            "no_entry": {
                "message": L(
                    "Kein Eintrag {kind} um {time}.", "No {kind} entry at {time}.", "Aucune entrée {kind} à {time}."
                )
            },
            "bottling_needs_sugar": {
                "message": L(
                    "Zum Abfüllen braucht es einen aktuellen Restzucker: erst messen, dann abfüllen.",
                    "Bottling needs a current residual sugar: measure first, then bottle.",
                    "La mise en bouteille demande un sucre résiduel actuel : mesurer d'abord, puis mettre en bouteille.",
                )
            },
            "pair_needs_both": {
                "message": L(
                    "Für Refraktometer + Dichte braucht es beide Werte.",
                    "Refractometer + density needs both values.",
                    "Réfractomètre + densité demande les deux valeurs.",
                )
            },
        },
        "services": {
            "add_measurement": {
                "name": L("Messung eintragen", "Add measurement", "Ajouter une mesure"),
                "description": L(
                    "Refraktometer, Dichte, Labor, Äpfelsäure, pH oder Flaschendruck.",
                    "Refractometer, density, lab, malic acid, pH or bottle pressure.",
                    "Réfractomètre, densité, labo, acide malique, pH ou pression en bouteille.",
                ),
                "fields": {
                    "config_entry_id": {"name": L("Ansatz", "Batch", "Cuvée"), "description": ""},
                    "kind": {"name": L("Art", "Kind", "Type"), "description": ""},
                    "value": {
                        "name": L("Wert", "Value", "Valeur"),
                        "description": L(
                            "Bei Refraktometer + Dichte: der Brix-Wert.",
                            "For refractometer + density: the Brix value.",
                            "Pour réfractomètre + densité : la valeur Brix.",
                        ),
                    },
                    "value2": {
                        "name": L("Zweiter Wert", "Second value", "Deuxième valeur"),
                        "description": L(
                            "Bei Refraktometer + Dichte: die Dichte. Beim Labor: der Alkohol derselben Probe in % vol.",
                            "For refractometer + density: the density. For a lab result: the alcohol of the same sample in % vol.",
                            "Pour réfractomètre + densité : la densité. Pour un résultat de labo : l'alcool du même échantillon en % vol.",
                        ),
                    },
                    "unit": {"name": L("Dichte-Einheit", "Density unit", "Unité de densité"), "description": ""},
                    "temperature": {
                        "name": L("Temperatur", "Temperature", "Température"),
                        "description": L(
                            "Bei Flaschendruck: Temperatur der Flasche.",
                            "For bottle pressure: bottle temperature.",
                            "Pour la pression en bouteille : température de la bouteille.",
                        ),
                    },
                    "time": {
                        "name": L("Zeitpunkt", "Time", "Moment"),
                        "description": L("Leer = jetzt.", "Empty = now.", "Vide = maintenant."),
                    },
                    "note": {"name": L("Notiz", "Note", "Note"), "description": ""},
                },
            },
            "add_event": {
                "name": L("Ereignis eintragen", "Add event", "Ajouter un événement"),
                "description": L(
                    "Abstich, Volumen, Kühlen, Heizen, Abgefüllt, Abgeschlossen oder Notiz.",
                    "Racking, volume, cooling, heating, bottled, closed or note.",
                    "Soutirage, volume, refroidissement, chauffage, mis en bouteille, clôturé ou note.",
                ),
                "fields": {
                    "config_entry_id": {"name": L("Ansatz", "Batch", "Cuvée"), "description": ""},
                    "kind": {"name": L("Art", "Kind", "Type"), "description": ""},
                    "value": {
                        "name": L("Wert", "Value", "Valeur"),
                        "description": L(
                            "Bei Volumen: neues Volumen in Litern.",
                            "For volume: new volume in litres.",
                            "Pour le volume : nouveau volume en litres.",
                        ),
                    },
                    "note": {"name": L("Notiz", "Note", "Note"), "description": ""},
                },
            },
            "remove_entry": {
                "name": L("Eintrag löschen", "Remove entry", "Supprimer une entrée"),
                "description": L(
                    "Löscht eine Messung oder ein Ereignis, etwa ein versehentliches „Abgefüllt“.",
                    'Removes a measurement or an event, for example an accidental "bottled".',
                    "Supprime une mesure ou un événement, par exemple un « mis en bouteille » saisi par erreur.",
                ),
                "fields": {
                    "config_entry_id": {"name": L("Ansatz", "Batch", "Cuvée"), "description": ""},
                    "kind": {"name": L("Art", "Kind", "Type"), "description": ""},
                    "time": {
                        "name": L("Zeitpunkt", "Time", "Moment"),
                        "description": L("Wie gespeichert (ISO).", "As stored (ISO).", "Tel qu'enregistré (ISO)."),
                    },
                },
            },
            "website_feed": {
                "name": L("Feed für die Website", "Website feed", "Flux pour le site"),
                "description": L(
                    "Öffentliche Zahlen aller Ansätze mit „Auf der Website zeigen“, für den Blueprint DataWein-Feed.",
                    'Public numbers of all batches with "show on the website", for the DataWein feed blueprint.',
                    "Chiffres publics de toutes les cuvées avec « afficher sur le site », pour le blueprint du flux DataWein.",
                ),
                "fields": {},
            },
            "update_settings": {
                "name": L("Einstellungen ändern", "Update settings", "Modifier les réglages"),
                "description": L(
                    "Ziel, Flasche, Malo, Volumen und Temperaturplan eines Ansatzes.",
                    "Target, bottle, malolactic, volume and temperature plan of a batch.",
                    "Objectif, bouteille, malo, volume et plan de température d'une cuvée.",
                ),
                "fields": {
                    "config_entry_id": {"name": L("Ansatz", "Batch", "Cuvée"), "description": ""},
                    **{k: {"name": v, "description": ""} for k, v in target_data.items()},
                    "volume_l": {"name": L("Volumen", "Volume", "Volume"), "description": ""},
                },
            },
        },
    }


if __name__ == "__main__":
    base = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tipsylab"
    (base / "translations").mkdir(exist_ok=True)
    for lang in LANGS:
        (base / "translations" / f"{lang}.json").write_text(json.dumps(tr(lang), ensure_ascii=False, indent=2) + "\n")
    (base / "strings.json").write_text(json.dumps(tr("en"), ensure_ascii=False, indent=2) + "\n")
    print("ok")
