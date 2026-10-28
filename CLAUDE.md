# TIPSYLAB

Gärüberwachung für Tipsy Wines (Ovar, Portugal; ab dem nächsten Jahr Produktion in Frankreich).
Nur Pet Nat, Naturwein und Charmat, kein Bier. Der ausführliche Plan mit Physik, Recherche und
allen Entscheidungen: `docs/PLAN-Abfuellzeitpunkt.md`. Bei Fachfragen dort zuerst nachsehen.

## Zusammenarbeit

- Deutsch, den Nutzer duzen. Oberflächen gibt es auf Deutsch, Französisch und Englisch; Deutsch
  ist die Quelle. Neue Texte immer in allen drei Sprachen: im Panel als `L(Deutsch, Englisch,
  Französisch)`, in der Integration über `tools/make_translations.py`, Handlungen für
  Benachrichtigungen in `texts.py`, in Blueprints über die Eingabe „Sprache“. Der Kern liefert
  Codes statt Sätzen. Französisch duzt wie das Deutsche.
- Gestaltung wie tipsy.pt und der Entwurf in `docs/ui-entwurf/`: Rubik Mono One für die eine
  Antwort, Fraunces für Text, JetBrains Mono für Daten; Papier-Rosé `#f9e3e7`, Ultramarin
  `#2b2c78`, Koralle nur für Warnungen. **Keine runden Ecken**, nirgends.
- Doku auf Englisch (`README.md`, `boxen/README.md`, `boxen/gaerbox/README.md`,
  `website/datawein/README.md`), denn das Repo ist für Mitmachende gedacht. Der Plan in `docs/`
  bleibt Deutsch. Box-Namen (Gärbox, Waagebox …) und ESPHome-Entitäten bleiben deutsch.
- Minimal und intuitiv: lieber eine Zahl weniger als eine Erklärung mehr.

## Wo was liegt

Zwei Teile: die **Integration** rechnet (Sensorfusion, Prognose, Panel), die **Boxen** messen und
regeln vor Ort. Übersicht der Boxen: `boxen/README.md`.

- `custom_components/tipsylab/core/`: Physik, Weinmodell, Gärschätzung (Anker, Spindel, Blasen,
  Waage), Alkohol fürs Etikett, Messflasche nach dem Abfüllen, Hauswerte, Blasenzählung, Charmat.
  Ohne Home Assistant, direkt testbar. Hier wird gerechnet.
- `custom_components/tipsylab/`: Integration (Coordinator, Config Flow mit „Neu konfigurieren“,
  Sensoren, Services, WebSocket `tipsylab/batches` und `tipsylab/preview`).
- `custom_components/tipsylab/frontend/`: Panel als Web Component ohne Build-Schritt.
- `boxen/gaerbox/`: Gärbox-Firmware (PlatformIO): Blasen, Temperatur, optional HX711-Waage.
- `boxen/esphome/`: Tankbox, Waagebox, Flaschenbox, Kellerluftbox, `pakete/waage.yaml` für
  bestehende ESP32.
- `boxen/heizbox/`: Shelly-Skript. `blueprints/`: Benachrichtigungen und DataWein-Feed.
- `website/datawein/`: Empfänger `feed.php` und `tipsylab.js` für die DataWein-Seite; was öffentlich
  wird, bestimmt `core/feed.py` (nur gerundete Zahlen, keine Geräte-IDs oder Adressen).
- `tools/`: `druckmodell.py` (Tabellen im Plan), `simulator.py` (Ansätze mit bekannter Wahrheit,
  auch Waage und Proben), `make_translations.py`, `make_atom_font.py`, `panel-vorschau/`.

## Regeln, die nicht verhandelbar sind

- **Sicherheit (Plan 3.8):** Druck immer für vollständige Vergärung rechnen; Flaschengrenzen
  330 ml 4,5 bar, 750 ml 6 bar im ungünstigen Fall prüfen; Charmat-Sollwert mindestens 0,3 bar
  unter dem mechanischen Sicherheitsventil, Magnetventil stromlos zu, bei Sensorfehler zu;
  Heizung aus über 26 °C oder ohne Fühler, Rückfall-Timer im Shelly-Skript. Gelernte Hauswerte
  dürfen den ungünstigen Fall nie milder machen (`fill_conditions` in `core/bottling.py`); gelernt
  wird nur aus plausiblen Messflaschen. Nichts davon aufweichen, auch nicht „vorübergehend“.
- **Charmat beim Abkühlen:** Der Sollwert sinkt im ESPHome-Regler absichtlich verzögert
  (Nachführzeit). CO₂ löst sich erst über Stunden; ohne Verzögerung würde das Ventil CO₂ ablassen,
  das im Wein bleiben soll.
- **Physik doppelt:** `core/physics.py` und `frontend/physics.js` müssen gleich rechnen, ebenso
  `fill_conditions` (`core/bottling.py`) und `fills` (`physics.js`). Immer beide ändern;
  `tests/frontend/test_physics_js.py` prüft das. Die Tabellen im Plan kommen aus
  `tools/druckmodell.py` und müssen zu `core/physics.py` passen (`tests/core/test_physics.py`).
- **Geheimnisse:** `boxen/gaerbox/secrets.ini` (echte WLAN-, MQTT- und OTA-Passwörter),
  `boxen/esphome/secrets.yaml` und `boxen/gaerbox/backup/` (Abbild der alten Firmware, darin
  Passwörter) nie committen (stehen in `.gitignore`). Zugangsdaten nie ausgeben.

## Arbeiten

```bash
uv sync && uv run pytest                   # Tests (Home Assistant 2026.2)
cd boxen/gaerbox && pio run               # Firmware bauen; FW_VERSION und Changelog mitziehen
esphome config boxen/esphome/tankbox.yaml  # braucht boxen/esphome/secrets.yaml
```

- `boxen/gaerbox/include/tipsy_fonts.h` wird von `tools/make_atom_font.py` erzeugt,
  `strings.json` und `translations/` von `tools/make_translations.py`: nie von Hand ändern.
- Neue Quellen im Schätzer immer erst im Simulator abbilden und dort testen (bekannte Wahrheit).
- Panel ansehen ohne Home Assistant: Anleitung oben in `tools/panel-vorschau/index.html`
  (echte Daten aus der Integration, Screenshots mit Chrome headless).
- Commits auf Deutsch im Stil `Bereich: was sich ändert`, etwa `Kern: …`, `Panel: …`,
  `Firmware: …`, `Docs: …`.
