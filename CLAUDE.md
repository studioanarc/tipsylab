# TIPSYLAB

Gärüberwachung für Tipsy Wines (Ovar, Portugal; ab dem nächsten Jahr Produktion in Frankreich).
Nur Pet Nat, Naturwein und Charmat, kein Bier. Der ausführliche Plan mit Physik, Recherche und
allen Entscheidungen: `docs/PLAN-Abfuellzeitpunkt.md`. Bei Fachfragen dort zuerst nachsehen.

## Zusammenarbeit

- Deutsch, den Nutzer duzen. Oberflächen sind deutsch.
- Gestaltung wie tipsy.pt und der Entwurf in `docs/ui-entwurf/`: Rubik Mono One für die eine
  Antwort, Fraunces für Text, JetBrains Mono für Daten; Papier-Rosé `#f9e3e7`, Ultramarin
  `#2b2c78`, Koralle nur für Warnungen. **Keine runden Ecken**, nirgends.
- Minimal und intuitiv: lieber eine Zahl weniger als eine Erklärung mehr.

## Wo was liegt

- `custom_components/tipsylab/core/`: Physik, Weinmodell, Gärschätzung, Blasen, Charmat. Ohne
  Home Assistant, direkt testbar. Hier wird gerechnet; alles andere ruft das nur auf.
- `custom_components/tipsylab/`: Integration (Coordinator, Config Flow, Sensoren, Services,
  WebSocket `tipsylab/batches` und `tipsylab/preview`).
- `custom_components/tipsylab/frontend/`: Panel als Web Component ohne Build-Schritt.
- `firmware/`: AtomS3-Blasenzähler (PlatformIO), eigenes README mit Changelog.
- `esphome/`, `shelly/`, `blueprints/`: Geräte und Benachrichtigungen.
- `tools/`: `druckmodell.py` (Tabellen im Plan), `simulator.py` (Ansätze mit bekannter Wahrheit),
  `make_atom_font.py`, `panel-vorschau/`.

## Regeln, die nicht verhandelbar sind

- **Sicherheit (Plan 3.8):** Druck immer für vollständige Vergärung rechnen; Flaschengrenzen
  330 ml 4,5 bar, 750 ml 6 bar im ungünstigen Fall prüfen; Charmat-Sollwert mindestens 0,3 bar
  unter dem mechanischen Sicherheitsventil, Magnetventil stromlos zu, bei Sensorfehler zu;
  Heizung aus über 26 °C oder ohne Fühler, Rückfall-Timer im Shelly-Skript. Nichts davon
  aufweichen, auch nicht „vorübergehend“.
- **Charmat beim Abkühlen:** Der Sollwert sinkt im ESPHome-Regler absichtlich verzögert
  (Nachführzeit). CO₂ löst sich erst über Stunden; ohne Verzögerung würde das Ventil CO₂ ablassen,
  das im Wein bleiben soll.
- **Physik doppelt:** `core/physics.py` und `frontend/physics.js` müssen gleich rechnen. Immer beide
  ändern; `tests/frontend/test_physics_js.py` prüft das. Die Tabellen im Plan kommen aus
  `tools/druckmodell.py` und müssen zu `core/physics.py` passen (`tests/core/test_physics.py`).
- **Geheimnisse:** `firmware/secrets.ini`, `esphome/secrets.yaml` und `firmware/backup/` nie
  committen (stehen in `.gitignore`). Aus `../TipsyLab OLD VERSIONS/TIPSY CLAUDE/` nie etwas
  übernehmen oder hochladen: Dort stehen WLAN- und MQTT-Passwort im Klartext. Zugangsdaten nie
  ausgeben.

## Arbeiten

```bash
uv sync && uv run pytest                   # Tests (Home Assistant 2026.2)
cd firmware && pio run                     # Firmware bauen; FW_VERSION und Changelog mitziehen
esphome config esphome/tipsy-tank.yaml     # braucht esphome/secrets.yaml
```

- `firmware/include/tipsy_fonts.h` wird von `tools/make_atom_font.py` erzeugt, nicht von Hand ändern.
- Übersetzungen (`strings.json`, `translations/`) gemeinsam ändern, Deutsch und Englisch.
- Panel ansehen ohne Home Assistant: Anleitung oben in `tools/panel-vorschau/index.html`
  (echte Daten aus der Integration, Screenshots mit Chrome headless).
- Commits auf Deutsch im Stil `Bereich: was sich ändert`, etwa `Kern: …`, `Panel: …`,
  `Firmware: …`, `Docs: …`.
