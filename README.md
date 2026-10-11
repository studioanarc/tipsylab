# TIPSYLAB

Gärüberwachung für Tipsy Wines: wann ein Pet Nat in die Flasche muss, wann ein Naturwein durch
ist und welcher Druck im Charmat-Tank gehalten werden soll. Alles läuft in Home Assistant; am
Gärröhrchen zählt ein M5 AtomS3 die Blasen und zeigt, wie lange es noch dauert.

Hintergrund, Physik und Entscheidungen: [docs/PLAN-Abfuellzeitpunkt.md](docs/PLAN-Abfuellzeitpunkt.md).
Gestaltung: [docs/ui-entwurf/](docs/ui-entwurf/) (Schriften und Farben wie tipsy.pt, keine runden Ecken).

## Was es kann

- **Pet Nat:** Restzucker aus Refraktometer, Dichte oder Labor, laufend fortgeschrieben mit
  Spindel, Blasenzähler und Temperatur. Prognose in thermischer Zeit, so dass Kühlen und
  Temperaturplan das Fenster verschieben. Ergebnis: Abfüllfenster mit Unsicherheit, Zeit bis zum
  Abfüllen (DUB), Druck beim Öffnen bei 10 und 20 °C, Prüfung der Flaschengrenze im ungünstigen
  Fall (330 ml 4,5 bar, 750 ml 6 bar), Malo in der Flasche als Option.
- **Naturwein:** Zeit bis trocken, Warnung bei stockender Gärung.
- **Charmat:** Tank-Sollwert aus dem Flaschenziel und der Tanktemperatur. Die Regelung läuft
  lokal auf dem Gerät am Tank und regelt ohne WLAN weiter.
- **Temperaturplan:** Heizmanschetten über Shelly, Solltemperatur aus dem Plan des Ansatzes.
- **Kellerluft:** CO₂ mit Alarm aufs Handy.

## Aufbau

```
 Gärröhrchen                    Home Assistant                         Handy, Tablet
 AtomS3, Firmware 2.1  ──MQTT──  Integration tipsylab  ──WebSocket──   Panel TIPSYLAB
  Blasen, Temperatur      ◄──     ├ Messungen, Ansätze, Prognose         Heute · Messung · Ziel · Tank
  zeigt BPM · DUB · °     DUB     ├ Spindel (vorhandene Entität)
                                  ├ Shelly: Solltemperatur ──────────►   Heizmanschette (Skript regelt)
                                  └ ESPHome: CO₂-Ziel ───────────────►   Charmat-Tank (regelt selbst)
```

| Ordner | Inhalt |
|---|---|
| `custom_components/tipsylab/` | Home-Assistant-Integration mit Panel (`frontend/`) |
| `custom_components/tipsylab/core/` | Physik, Weinmodell, Gärschätzung, Blasenzählung, Charmat; ohne Home Assistant testbar |
| `firmware/` | AtomS3-Blasenzähler, Firmware 2.1 (PlatformIO), eigenes [README](firmware/README.md) |
| `esphome/` | Charmat-Tank (`tipsy-tank.yaml`) und Kellerluft (`tipsy-kellerluft.yaml`) |
| `shelly/` | Heizregler-Skript für Shelly 1PM Gen3/Gen4 mit Plus Add-on |
| `blueprints/automation/tipsylab/` | Benachrichtigungen: Abfüllfenster und Alarme |
| `tools/` | Druckmodell, Simulator, Font-Generator fürs AtomS3 |
| `tests/` | Physik, Gärschätzung gegen den Simulator, Integration in Home Assistant, Panel-Physik |
| `assets/` | Tipsy-Logo fürs AtomS3 (128 × 128) |

## Einrichten

### Integration und Panel

1. HACS → Benutzerdefinierte Repositories → `https://github.com/studioanarc/tipsylab`, Typ
   Integration → TIPSYLAB installieren. Ohne HACS: `custom_components/tipsylab` in den Ordner
   `custom_components` der Home-Assistant-Konfiguration kopieren.
2. Home Assistant neu starten (ab 2025.8, getestet mit 2026.2).
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → **TIPSYLAB**. Jeder Ansatz ist ein
   eigener Eintrag: Name, Betriebsart, Start-Brix oder Startdichte, Volumen, dann die Quellen
   (Blasenzähler-ID, Spindel, Temperatur, Shelly, beim Charmat Tankdruck und CO₂-Ziel des Reglers)
   und das Ziel.
4. In der Seitenleiste erscheint **TIPSYLAB**. Messungen trägst du dort ein; dieselben Services
   (`tipsylab.add_measurement`, `add_event`, `update_settings`) gibt es für Automationen.

Für Blasenzähler und Display braucht Home Assistant die MQTT-Integration.

### Blasenzähler (AtomS3)

Firmware bauen und flashen wie in [firmware/README.md](firmware/README.md). Danach in der
Weboberfläche des Geräts unter Einstellungen → Display-Logo `assets/logo-atoms3-128.png`
hochladen. Die Geräte-ID (`tipsy-a1b2c3`) steht auf dem Display; sie gehört ins Feld
„Blasenzähler“ des Ansatzes. Das Display zeigt dann BPM, DUB und die Temperatur.

### Charmat-Tank und Kellerluft (ESPHome)

```bash
cd esphome
cp secrets.yaml.example secrets.yaml   # ausfüllen; secrets.yaml bleibt lokal
esphome run tipsy-tank.yaml
esphome run tipsy-kellerluft.yaml
```

Verdrahtung und Annahmen stehen oben in den YAML-Dateien. Im Charmat-Ansatz die Zahl
**CO₂-Ziel** des Tanks als Regler eintragen, dazu Tankdruck und Weintemperatur als Quellen.

### Heizung (Shelly)

Auf dem Shelly unter Scripts den Inhalt von `shelly/thermostat.js` anlegen, „Run on startup“
einschalten, den Fühler am Add-on als Temperatur 100 einrichten. Im Ansatz die IP des Shelly
eintragen; Home Assistant schreibt die Solltemperatur in den KVS-Eintrag `tipsylab_soll`. Die
Integration schreibt ohne Anmeldung, der Shelly darf deshalb keinen Passwortschutz haben.

### Benachrichtigungen

Einstellungen → Automationen → Blueprints → Blueprint importieren:

- `https://github.com/studioanarc/tipsylab/blob/main/blueprints/automation/tipsylab/abfuellfenster.yaml`
- `https://github.com/studioanarc/tipsylab/blob/main/blueprints/automation/tipsylab/alarm.yaml`

## Sicherheit

- **Charmat:** Ein mechanisches Sicherheitsventil unter der Zulassung des Tanks ist Pflicht; die
  Regelung ersetzt es nie. Der Sollwert bleibt mindestens 0,3 bar unter dem Sicherheitsventil.
  Das Magnetventil ist stromlos geschlossen und direktgesteuert; bei einem Sensorfehler bleibt es zu.
- **Heizung:** aus über 26 °C und ohne Fühlerwert, auch ohne Home Assistant. Bleibt das Skript
  stehen, schaltet der Shelly die Heizung nach zwei Minuten von selbst ab.
- **Druck in der Flasche:** gerechnet für die vollständige Vergärung des Restzuckers. Ohne eigene
  Messflaschen liegt das Modell bis etwa ±0,8 bar daneben, geeicht etwa ±0,3 bar (Plan 2.9).
  Jede Abfüllung mit einer Messflasche und einem Aphrometer prüfen.

## Entwickeln

```bash
uv sync                                    # Python 3.13, Home Assistant 2026.2, pytest-Plugin
uv run pytest                              # alle Tests
python3 tools/druckmodell.py               # Drucktabellen aus dem Plan
python3 tools/simulator.py                 # simulierter Ansatz mit Prognose
cd firmware && pio run                     # Firmware bauen
uv run --no-project --with fonttools --with brotli --with pillow python tools/make_atom_font.py
esphome config esphome/tipsy-tank.yaml     # braucht esphome/secrets.yaml
```

Die Physik steht zweimal: `core/physics.py` für die Integration und `frontend/physics.js` für
die Regler im Panel. `tests/frontend/test_physics_js.py` vergleicht beide mit Node.

## Stand

Umgesetzt: die Integration mit Panel, Prognose Stufe 1 und Druckmodell (Phase 1 im Plan),
Firmware 2.1 mit neuem Display und erweiterter MQTT-Nachricht, ESPHome für Tank und Kellerluft,
das Shelly-Skript und die Blueprints.

Noch offen: das probabilistische Modell (Phase 3), die Waage für Ballons, die Nachkalkulation
und Hauswerte aus Messflaschen (Phase 5), der öffentliche Feed für die DataWein-Seite.

Geprüft ist alles, was ohne Hardware geht: Tests, Builds und Konfigurationsprüfung, das Panel
im Browser mit echten Daten der Integration, das Shelly-Skript in einer Simulation. Am Gerät
noch nicht gelaufen sind die Firmware 2.1, die ESPHome-Konfigurationen (beim Tank-Display können
Versatz und Farbinvertierung abweichen) und das Shelly-Skript.
