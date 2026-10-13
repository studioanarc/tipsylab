# TIPSYLAB

Gärüberwachung für Tipsy Wines: wann ein Pet Nat in die Flasche muss, wann ein Naturwein durch
ist und welcher Druck im Charmat-Tank gehalten werden soll.

TIPSYLAB besteht aus zwei Teilen:

- **Die Home-Assistant-Integration** ([`custom_components/tipsylab`](custom_components/tipsylab))
  ist das Gehirn. Sie sammelt für jeden Ansatz alle Quellen ein (deine Messungen, Spindel,
  Blasen, Gewicht, Temperatur), führt sie zu einem Restzucker mit Unsicherheit zusammen, sagt das
  Abfüllfenster voraus und rechnet den Druck in der Flasche. Dazu gehört das Panel „TIPSYLAB“
  in der Seitenleiste, am Handy, Tablet oder PC.
- **Die Boxen** ([`boxen/`](boxen)) sitzen an Gefäßen, Tanks und im Keller. Sie messen, zeigen
  das Nötigste an und regeln vor Ort, auch ohne WLAN.

```
 BOXEN (vor Ort)                     HOME ASSISTANT                         ANZEIGE
 Gärbox    Blasen · ° · Gewicht ─┐
           zeigt BPM · DUB · ° ◄─┤   TIPSYLAB-Integration                   Panel TIPSYLAB
 Waagebox  Gewicht ──────────────┤    Sensorfusion: Restzucker ± σ  ───►    Heute · Messung
 Spindel   Dichte ───────────────┤    Prognose: Abfüllfenster, DUB          Ziel · Tank
 Tankbox   Druck · ° ────────────┤    Druck beim Öffnen, Flaschengrenze
           regelt das Ventil ◄───┤    Temperaturplan, CO₂-Ziel              Handy: Blueprints
 Heizbox   ° · regelt Heizung ◄──┤                                          für Fenster und Alarme
 Kellerluftbox  CO₂ · Klima ─────┘
```

## Die Teile

| Teil | Was es ist | Software | Ordner |
|---|---|---|---|
| **Integration** | rechnet und speichert; Panel | Python, Home-Assistant-Integration | [`custom_components/tipsylab`](custom_components/tipsylab) |
| **Gärbox** | AtomS3 am Gärröhrchen: Blasen, Weintemperatur, optional Gewicht | eigene Firmware (PlatformIO) | [`boxen/gaerbox`](boxen/gaerbox) |
| **Waagebox** | AtomS3 mit Wägezelle, für Gefäße ohne Gärbox; auch als Paket für jeden ESPHome-ESP32 | ESPHome | [`boxen/esphome`](boxen/esphome) |
| **Tankbox** | Charmat: Druck halten, Ventil regeln | ESPHome | [`boxen/esphome`](boxen/esphome) |
| **Kellerluftbox** | CO₂ und Klima im Keller | ESPHome | [`boxen/esphome`](boxen/esphome) |
| **Heizbox** | Shelly an der Heizmanschette | Shelly-Skript | [`boxen/heizbox`](boxen/heizbox) |
| **Benachrichtigungen** | Abfüllfenster und Alarme aufs Handy | Blueprints | [`blueprints/automation/tipsylab`](blueprints/automation/tipsylab) |

Welche Box wofür, Einkaufslisten, Anschlüsse und Einrichtung: **[boxen/README.md](boxen/README.md)**.
Hintergrund, Physik und Entscheidungen: [docs/PLAN-Abfuellzeitpunkt.md](docs/PLAN-Abfuellzeitpunkt.md).

## Was die Integration rechnet

- **Pet Nat:** Restzucker aus Refraktometer, Dichte oder Labor, fortgeschrieben mit Spindel,
  Blasen und Gewicht. Die Prognose rechnet in thermischer Zeit, so dass Kühlen und
  Temperaturplan das Fenster verschieben. Ergebnis: Abfüllfenster mit Unsicherheit, DUB, Druck
  beim Öffnen bei 10 und 20 °C, Prüfung der Flaschengrenze im ungünstigen Fall (330 ml 4,5 bar,
  750 ml 6 bar), Malo in der Flasche als Option, Alkohol in der Flasche mit Unsicherheit und
  Etikettwert.
- **Naturwein:** Zeit bis trocken, Warnung bei stockender Gärung, Alkohol fürs Etikett.
- **Charmat:** CO₂-Ziel und Tank-Sollwert aus dem Flaschenziel; die Tankbox regelt danach.
- **Gewicht:** Gewichtsverlust ist entwichenes CO₂. Mit dem Volumen ergibt das den vergorenen
  Zucker direkt; liegen Messungen im Verlauf, wird an ihnen geeicht. Gelöstes CO₂ und Proben
  rechnet die Integration heraus. Unter einem Tank mit drei Beinen reicht eine Wägezelle.

## Einrichten

Das Repo ist privat. HACS und der Blueprint-Import per Link brauchen ein öffentliches Repo; solange
es privat bleibt, die Ordner von Hand kopieren: `custom_components/tipsylab` nach
`/config/custom_components/` und `blueprints/automation/tipsylab` nach `/config/blueprints/automation/`.

1. **Integration:** HACS → Benutzerdefinierte Repositories → `https://github.com/studioanarc/tipsylab`,
   Typ Integration → TIPSYLAB installieren (ohne HACS: `custom_components/tipsylab` in den
   gleichnamigen Ordner der Home-Assistant-Konfiguration kopieren). Home Assistant ab 2025.8
   neu starten (getestet mit 2026.2). Für Gärbox und Display braucht es die MQTT-Integration.
2. **Boxen** aufbauen und einrichten: [boxen/README.md](boxen/README.md).
3. **Ansatz anlegen:** Einstellungen → Geräte & Dienste → Integration hinzufügen → TIPSYLAB. Jeder
   Ansatz ist ein Eintrag: Name, Betriebsart, Start-Brix oder Startdichte, Volumen, dann die
   Quellen (Gärbox-ID, Spindel, Temperatur, Waage, Shelly, beim Charmat Tankdruck und CO₂-Ziel),
   dann das Ziel. Quellen lassen sich später über „Neu konfigurieren“ ändern, etwa um eine Waage
   nachzurüsten; Messungen bleiben dabei erhalten.
4. **Panel** „TIPSYLAB“ in der Seitenleiste: Messungen eintragen, Ziel einstellen. Dieselben Services
   (`tipsylab.add_measurement`, `add_event`, `update_settings`) gibt es für Automationen.
5. **Benachrichtigungen:** Einstellungen → Automationen → Blueprints → Blueprint importieren:
   - `https://github.com/studioanarc/tipsylab/blob/main/blueprints/automation/tipsylab/abfuellfenster.yaml`
   - `https://github.com/studioanarc/tipsylab/blob/main/blueprints/automation/tipsylab/alarm.yaml`

## Sicherheit

- **Charmat:** Ein mechanisches Sicherheitsventil unter der Zulassung des Tanks ist Pflicht; die
  Regelung ersetzt es nie. Der Sollwert bleibt mindestens 0,3 bar darunter. Das Magnetventil ist
  stromlos geschlossen und direktgesteuert; bei einem Sensorfehler bleibt es zu.
- **Heizung:** aus über 26 °C und ohne Fühlerwert, auch ohne Home Assistant; bleibt das Skript
  stehen, schaltet der Shelly nach zwei Minuten ab. 230 V nur durch eine Elektrofachkraft.
- **Druck in der Flasche:** gerechnet für die vollständige Vergärung des Restzuckers. Ohne eigene
  Messflaschen liegt das Modell bis etwa ±0,8 bar daneben, geeicht etwa ±0,3 bar (Plan 2.9).
  Jede Abfüllung mit einer Messflasche und einem Aphrometer prüfen.
- **Waage unter dem Tank:** Wägezelle mit Sicherung gegen Verrutschen; da steht fast eine Tonne drauf.

## Entwickeln

```
custom_components/tipsylab/   Integration; core/ rechnet ohne Home Assistant, frontend/ ist das Panel
boxen/                        Software der Boxen (gaerbox/, esphome/, heizbox/) und ihre Doku
blueprints/                   Benachrichtigungen
docs/                         Plan und UI-Entwurf
tools/                        Druckmodell, Simulator, Generatoren für Übersetzungen und Display-Schrift, Panel-Vorschau
tests/                        Kern gegen den Simulator, Integration in Home Assistant, Panel-Physik
assets/                       Logo für das Display der Gärbox
```

```bash
uv sync && uv run pytest                   # alle Tests (Home Assistant 2026.2)
python3 tools/druckmodell.py               # Drucktabellen aus dem Plan
python3 tools/simulator.py                 # simulierter Ansatz mit Prognose
python3 tools/make_translations.py         # strings.json und translations/ aus einer Quelle
cd boxen/gaerbox && pio run                # Gärbox-Firmware bauen
esphome config boxen/esphome/tankbox.yaml  # braucht boxen/esphome/secrets.yaml
```

Die Physik steht zweimal: `core/physics.py` für die Integration und `frontend/physics.js` für die
Regler im Panel; ein Test vergleicht beide. Das Panel lässt sich ohne Home Assistant ansehen:
Anleitung in [`tools/panel-vorschau/index.html`](tools/panel-vorschau/index.html).

## Stand

Umgesetzt: Integration mit Panel, Prognose Stufe 1, Druckmodell, Gewicht als Quelle, Alkohol fürs
Etikett; Gärbox-Firmware 2.2 mit Display und optionaler Waage; ESPHome für Tank-, Waage- und
Kellerluftbox; Heizbox-Skript; Blueprints.

Noch offen: das probabilistische Modell (Phase 3 im Plan; in der Simulation kommt die Prognose der
Stufe 1 einige Stunden zu spät), die Nachkalkulation mit Messflaschen (Phase 5) und der öffentliche
Feed für die DataWein-Seite.

Geprüft ist, was ohne Hardware geht: Tests gegen einen Simulator mit bekannter Wahrheit, Builds,
Konfigurationsprüfung, das Panel im Browser mit echten Daten der Integration, das Shelly-Skript in
einer Simulation. Am Gerät noch nicht gelaufen sind die Gärbox-Firmware 2.1/2.2, die ESPHome-Boxen
(bei den Displays können Versatz und Farben abweichen) und das Shelly-Skript.
