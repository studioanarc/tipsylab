# TIPSYLAB · Plan: Abfüllzeitpunkt für Pet Nat, Druckregelung für Charmat

Stand 11.10.2026, fünfte Fassung: Home Assistant als Plattform (3.2), Anzeige am AtomS3 mit DUB-Farben (3.12), Malo als Option, Waage für Ballons und Malo-Überwachung (3.11), Temperaturplan mit Heizmanschetten (3.4), Unsicherheiten der Modelle (2.9), Hardware-Übersicht (3.13), dazu der Abgleich mit Winegrid wineplus (2.8). Grundlage: die vier Versionen in `TipsyLab OLD VERSIONS/`, das GitHub-Repo `studioanarc/tipsyhomelab`, tipsy.pt (lokal: `website-project/`), deine Tech Sheets und eine Internet-Recherche (Quellen am Ende).

Dieser Ordner (`Tipsy/tipsylab/`) ist als künftiges Projekt-Repo gedacht:
- `docs/PLAN-Abfuellzeitpunkt.md`: dieser Plan
- `docs/ui-entwurf/tipsylab-abfuellfenster.html`: UI-Entwurf, auch online (privat, Beispieldaten, funktionierende Regler): https://claude.ai/artifact/DfirSE32FmDQZJyc5CVBwk
- `tools/druckmodell.py`: rechnet alle Drucktabellen in diesem Plan nach (`python3 tools/druckmodell.py`)
- `assets/logo-atoms3-128.png`: Logo fürs Display des AtomS3 (128 × 128, ohne Kreis), zum Hochladen über die Einstellungen der Firmware; `assets/logo-atoms3.svg` ist die Vorlage dazu

**Stand der Umsetzung (11.10.2026):** Phase 1 ist programmiert (Integration mit Panel, Prognose Stufe 1, Druckmodell, Blueprints), dazu die Software aus Phase 2 und Phase 4 Stufe B: die Boxen in `boxen/` (Gärbox-Firmware 2.2 mit optionaler Waage, ESPHome für Tank, Waage und Kellerluft, das Shelly-Skript der Heizbox). Überblick und Einrichten: `README.md` und `boxen/README.md`. Abweichungen vom Plan:
- Charmat: Beim Abkühlen folgt der Sollwert verzögert (Nachführzeit, Standard 6 h). CO₂ löst sich erst über Stunden; ohne Verzögerung würde das Ventil ablassen, was im Wein bleiben soll. Das CO₂-Ziel geht als ESPHome-Zahl über die native API statt per MQTT.
- Heizung: Das Shelly-Skript schaltet jedes Mal mit Rückfall-Timer ein; bleibt das Skript stehen, ist die Heizung nach zwei Minuten aus.
- Firmware: Legacy-Topics sind nur bei neuen Geräten aus; ein aktualisiertes Gerät behält seine Einstellung.
- Waage (11.10.): eine Wägezelle unter einem von drei Tankbeinen reicht, weil drei Beine die Last eindeutig verteilen; geeicht wird mit einem Testgewicht in der Deckelmitte oder über die Messungen. Gelöstes CO₂ und Proben rechnet die Integration heraus.
- Alkohol (12.10.): Die App zeigt den Alkohol in der fertigen Flasche mit Unsicherheit und Etikettwert; Messpaare aus Refraktometer und Dichte eichen ihn (Abschnitt 2.10).
- Laborwert (13.10.): Die Messart „Labor“ nimmt neben dem Restzucker den Alkohol derselben Probe an; er macht den Alkohol fürs Etikett genau (Abschnitt 2.10).
- Phase 5 (13.10.): „Abgefüllt“ hält den Restzucker fest (die Schätzung bleibt auf dem Stand beim Abfüllen), schaltet die Heizung aus (Sollwert 0, das Shelly-Skript sieht keinen gültigen Wert) und schickt dem Display „keine Prognose“. Die Messflasche wird über die CO₂-Bilanz auf 20 °C umgerechnet und mit dem Druck bei vollständiger Vergärung verglichen; Alarm mit Handlung ab 0,5 bar darüber („auf 0–2 °C kühlen“) und ab 80 % der Flaschengrenze („sofort kühlen, Schutzbrille“). Die Flaschenbox (ESPHome) liefert Druck und Temperatur automatisch. „Ansatz abschließen“ legt ihn ins Archiv mit Nachkalkulation (Prognose-Stände stündlich gespeichert, verglichen 48, 24 und 12 h vor dem Durchgang). Hauswerte: nur, was sich beobachten lässt, also die Sättigung beim Abfüllen aus durchgegorenen Messflaschen (gelernt nur zwischen 0,4 und 1,4; eine steckengebliebene Flaschengärung darf den nächsten Ansatz nicht mit mehr Zucker abfüllen lassen) und Zucker je % vol aus Laborwerten. Sie werden aus dem Archiv neu gerechnet; der ungünstige Fall bleibt mindestens bei Sättigung 1,0 und 0,2 über dem gelernten Wert. Q10, CO₂-Ausbeute und Kopfraum lassen sich ohne zusätzliche Messungen nicht getrennt lernen; Startwerte für Spindel-Versatz und Blasen je Gerät noch nicht.
- Phase 3 (13.10.): Statt eines Kalman- oder Partikelfilters eine Monte-Carlo-Prognose auf der Stufe-1-Schätzung (`core/forecast.py`). Gestreut werden Restzucker jetzt, Gärrate (±25 %), ihre Drift (die Hefe darf gegen Ende schneller oder müder werden, k = k₀·e^{βτ}, β ±0,1 je thermischem Tag), Q10 (±0,3) und Kellertemperatur (±0,5 °C); der Zeitpunkt jedes Zugs wird analytisch über den Temperaturplan gerechnet. Fenster = P10–P90, beste Zeit = P50. Geeicht im Simulator über zufällige Ansätze (Kinetik, müde Hefe, Q10, Kühlplan, Spindel-Versatz): Das Fenster enthält den Durchgang 48, 24 und 12 h vorher in 89, 90 und 85 % der Fälle (Kriterium ≥ 80 %, `tests/core/test_forecast.py`). Gelernt beim Eichen: Die Anpassung meldet ihre Unsicherheit zu klein (die Restfehler hängen zusammen), und der gemittelte Restzucker ist unsicherer, als sein σ sagt, weil Spindel und Fortschreibung am selben Anker hängen (σ × 1,3). Messempfehlung als erwarteter Gewinn: eine Refraktometer-Messung jetzt, wenn sie das Fenster um mindestens 4 h und ein Viertel enger macht („von ±14 h auf ±9 h“). Dazu die Chance, beim Abfüllen jetzt über dem Ziel oder im ungünstigen Fall über der Flaschengrenze zu landen. Gesättigte Blasenzähler: über so eine Strecke wird nicht geeicht, danach zählen Blasen erst nach der nächsten Messung wieder. Was-wäre-wenn für die Temperatur gibt es seit Phase 1 im Panel, Löslichkeit und Kopfraum rechnet das Druck- und Gewichtsmodell.
- DataWein-Feed (13.10.): wie in 3.2 beschrieben. Je Ansatz die Option „Auf der Website zeigen“; der Dienst `tipsylab.website_feed` liefert nur gerundete öffentliche Zahlen (`core/feed.py`), der Blueprint schickt sie alle 15 min per `rest_command` mit Schlüssel an `website/datawein/feed.php`, das nur bekannte Felder in plausiblen Grenzen speichert. `tipsylab.js` liest `feed.json` und läuft ohne Feed als gekennzeichnete Demo weiter; die sechste Anzeige zeigt „Bottling in“ statt Kopfraum-CO₂, das wir nicht messen. `feed.php` ist mangels PHP nur gelesen, nicht ausgeführt.
- Noch offen: die Extras aus Phase 6 (Kühlung, Kolorimeter, Füllstand) und Startwerte für Spindel-Versatz und Blasen je Gerät aus dem Archiv.

**Rahmenbedingungen (von dir):**
- Nur Pet Nat und Naturwein, kein Bier. Charmat als Option.
- Kronkorken halten bei 330 ml locker 4,5 bar, bei 750 ml 6–7 bar. Lagerung bei 30 °C ist damit kein Problem. Relevant ist der **Druck beim Öffnen zwischen 10 und höchstens 20 °C**.
- Es gibt keine belastbaren historischen Messwerte. Pro Jahr entstehen mehrere Ansätze, und jeder liefert eigene Werte.
- Oberfläche minimal, Schriften wie tipsy.pt, **keine abgerundeten Ecken**.

Inhalt
0. Kurzfassung
1. Bestandsaufnahme
2. Recherche: was es gibt, was man daraus lernt, was die Physik sagt
3. Zielbild
4. Wiederverwendung im Detail
5. Umsetzung in Phasen
6. Offene Fragen an dich
7. Quellen

---

## 0 Kurzfassung

**Was gebaut wird.** Eine kleine App („TIPSYLAB“) mit drei Betriebsarten, die du beim Anlegen eines Ansatzes wählst:

- **Pet Nat:** Sie sammelt Blasenzähler, Spindel und deine Refraktometer-Messungen, schätzt Restzucker und Alkohol und rechnet das Abfüllfenster für einen **Druck beim Öffnen** aus, nicht für einen Zuckerwert. Die Antwort lautet etwa: „Abfüllen So 18.10., ≈ 12 Uhr“, mit Fenster und Unsicherheit.
- **Charmat:** Sie rechnet aus deinem Flaschenziel und der Tanktemperatur den Sollwert für den Tankdruck. Ein Magnetventil am Tank hält ihn, oder die App sagt dir, worauf du ein Spundventil einstellst.
- **Naturwein (still):** Sie beantwortet, wann die Gärung trocken ist und ob sie stockt.

Die App läuft als Integration in Home Assistant, wo deine Daten ohnehin zusammenlaufen. Sie liest die vorhandenen Sensoren, legt ihre Ergebnisse als Entitäten an und bringt ein eigenes Panel im tipsy.pt-Look mit. Auf dem Handy öffnet es die Home-Assistant-App, und Push-Nachrichten kommen auch von dort (Abschnitt 3.2).

**Was wiederverwendet wird.** Die Firmware 2.0.7 (`TIPSYlab incl Webportal`) bleibt die Basis und braucht nur kleine Erweiterungen. Aus `tipsyhomelab` bleiben die Pet-Nat-Logik (Anker-Kalibrierung, Alarme mit Hysterese, MQTT-Zählerlogik, HA-Discovery) und die Tests. Die ML-Schicht fällt weg: Ihre Modelle sind untrainierte Platzhalter (`pretrained/metadata.json`: `"trained": false`), und für die Genauigkeitsangaben im README (±3–6 h) gibt es keine Daten. Schriften, Farben und Logo kommen 1:1 von tipsy.pt.

**Drei Befunde bestimmen das Design:**

1. **Das Add-on rechnet den Druck zu niedrig.** Es nimmt 4,1 g/L Zucker pro bar „bei 20 °C“ an. Diese Faustregel gilt aber bei etwa 12 °C; bei 20 °C reichen rund 3 g/L pro bar. Dazu kommt das CO₂, das beim Abfüllen schon im gärenden Wein gelöst ist. Für 10 g/L Restzucker zeigt das Add-on 2,5 bar. Physikalisch sind es beim Öffnen bei 20 °C je nach Abfüllbedingungen 2,9–4,3 bar, bei 10 °C 1,8–2,9 bar. Das passt zu zu wilden Flaschen und kommt zuerst (Abschnitt 2.3).
2. **Der Blasenzähler misst Geschwindigkeit, nicht Zucker.** Er braucht Anker in Form echter Messungen, und er muss Temperaturwechsel verstehen. Kühlt man von 15 auf 10 °C, wie es bei Pet Nat üblich ist, löst der Wein so viel CO₂ zurück, wie die späte Gärung in rund 9 Stunden produziert. So lange zeigen die Blasen fast Stillstand, obwohl die Hefe weiterarbeitet (Abschnitt 2.4).
3. **Spindel und Refraktometer zusammen** liefern Zucker *und* Alkohol, auch ohne genauen Startwert, weil Alkohol die Dichte senkt und die Lichtbrechung erhöht. Das ist der stärkste Anker, den du ohne Labor hast (Abschnitt 2.5).

**Ohne Altdaten** wird mit einem Simulator und mit dem ersten echten Ansatz im Schattenbetrieb geprüft. Der Gärverlauf wird für jeden Ansatz neu angepasst. Über die Jahre gelernt werden nur Haus- und Gerätewerte, etwa das gelöste CO₂ beim Abfüllen oder die Kalibrierung der Spindel (Abschnitt 3.4 und 5).

**Zusätzlich messen** lohnt vor allem vier Dinge: CO₂ in der Kellerluft (Sicherheit), die Temperatur im Wein statt im Raum, das Gewicht der Ballons und vor dem Abfüllen die Äpfelsäure. Ob die App die Malo mitrechnet, ist eine Option pro Ansatz. Das Volumen ist ein Eingabefeld (Abschnitt 3.11).

Deine Tech Sheets zeigen, warum das zählt: DATA 2024 (330 ml) trägt den Hinweis „open very slowly outdoors“, DATA 2025 (750 ml) „pop gently, expect a small sigh“. Diese Streuung soll das Werkzeug beseitigen.

---

## 1 Bestandsaufnahme

### 1.1 Was wo liegt

| Ort | Inhalt | Stand | Urteil |
|---|---|---|---|
| `Tipsy/tipsylab/` (neu) | dieser Plan, UI-Entwurf, Druckmodell | 11.10.2026 | Keimzelle des neuen Projekts |
| GitHub `studioanarc/tipsyhomelab` | HA-Add-on „Wine Fermentation Monitor“ | Branch `claude/monitor-wine-production-…`, Commit 882e8df | Öffentlich gibt es kein Repo „tipsylab“ (ein privates konnte ich ohne Login nicht prüfen). Gemeint ist vermutlich dieses. |
| `TipsyLab OLD VERSIONS/tipsyhomelab` | lokale Kopie, **zwei Commits weiter** als GitHub: Pet-Nat-Restzucker-Schätzer (Add-on 1.1.0) und Installierbarkeit | 20.09.2026, nicht gepusht | teilweise wiederverwenden |
| `TipsyLab OLD VERSIONS/Tipsy` | erste AtomS3-Firmware, ~130 Zeilen, fester Gyro-Schwellwert | 04/2025 | Archiv |
| `TipsyLab OLD VERSIONS/TIPSY CLAUDE` | Firmware mit Display, blockierend | 04/2025 | Archiv. **Enthält WLAN- und MQTT-Passwort im Klartext.** Nie hochladen. |
| `TipsyLab OLD VERSIONS/TIPSYlab incl Webportal` | Firmware **2.0.7**: Impulsdetektor, Autokalibrierung, OTA, HA-Discovery, Web-UI auf dem Gerät | 20.09.2026, eigenes Git ohne Remote | Basis, behalten |
| `Website/TIPSYLAB — DataWein · live fermentation feed` | Demo-Seite „Fermentation, read live“ mit im Browser simuliertem Feed | 07/2026 | später mit echten Daten speisen |
| `website-project/` | tipsy.pt: Fonts, Farben, Logo (live identisch, geprüft) | 07/2026 | Quelle für die UI |

### 1.2 Firmware 2.0.7 (M5 AtomS3, ESP32-S3, MPU6886)

**Stark.** Den schwierigsten Teil des Blasenzählens hast du gelöst und dokumentiert. Die Baseline wird nur aus Ruhefenstern gelernt. Ein Rauschboden und ein Vibrationsboden (gegen Kompressor-Brummen) schützen vor Fehlzählungen, eine Handling-Sperre greift, wenn das Gerät bewegt wird. Gezählt wird ein Blop nur als steiler Impuls über dem Trigger, mit Mindestabstand. Dazu kommen Autokalibrierung, OTA (espota und HTTP-Push), Konfiguration im NVS, eine Geräte-ID aus der MAC, HA-Discovery mit Slidern und Buttons sowie `/api/trace` für Rohsignale. Das MQTT-Payload `sensors/bubble/<id>` geht alle 60 s raus und enthält `bubbles` (Intervall), `total` (seit Boot), `rate_60s`, `temperature`, `noise`, `peak`, `trigger` und einen ISO-Zeitstempel.

**Lücken, die für die Prognose zählen:**

- `total` beginnt nach jedem Neustart bei null. Fällt MQTT aus und das Gerät startet neu, fehlen Blasen. Es braucht eine `boot_id`, eine laufende Nummer `seq` und einen im NVS gesicherten Zähler.
- Die Luftfeuchtigkeit fehlt (1.x hatte einen DHT22; 2.x schickt im Legacy-Topic `humidity: 0`), ebenso der Luftdruck. Beides ist für die Kopfraum-Korrektur nützlich (2.4).
- Die Zählgrenze liegt bei etwa 6 Blops/s (Mindestabstand 100–150 ms). Bei starkem Gasfluss „streamt“ das Gärröhrchen, dann zählt der Detektor zu wenig. Das Payload sagt nicht, wann das passiert. Es braucht ein Flag `saturated`, ebenso `handling`, das bisher nur in `/api/status` steht.
- Die Legacy-Topics sind standardmäßig an. Bei mehreren Geräten mischen sie die Daten.

### 1.3 tipsyhomelab (HA-Add-on 1.1.0)

Rund 42.000 Zeilen inklusive etwa 15 Doku-Dateien, davon viel generiertes Gerüst (`COMPLETION_REPORT.md`, `BUILD_SUMMARY.md`, `IMPLEMENTATION_SUMMARY.md`, `TEST_RESULTS.md` …).

**Brauchbar:**

- `ml_engine/residual_sugar.py`: Restzucker = S₀ − k·N(t), wobei k aus einer Hydrometer-Messung („Anker“) kalibriert wird, dazu Alarme mit Hysterese. Reines Python, testbar, gut kommentiert. Das ist dieselbe Idee wie bei iBlopper (2.1).
- `petnat_service.py`: robuste Verarbeitung der Blasenzähler-Nachrichten (kumulierte Summe pro Ansatz, Reset-Erkennung, Lücken aus `total` füllen, persistenter Zustand), Ratenhistorie, Discovery-Bausteine (Sensoren, Binary Sensor, Number, Button), Benachrichtigungen über die Supervisor-API.
- `tests/test_residual_sugar.py` und `tests/test_petnat_service.py`. Ich habe sie nicht ausgeführt, pytest ist auf diesem Rechner nicht installiert.
- Add-on-Packaging (`config.yaml`, `Dockerfile`, `run.sh`, `repository.json`) und CI-Workflows als Vorlage.

**Problematisch:**

- **Druckmodell:** 0,5 bar pro g/L CO₂ „bei 20 °C“ und ein linearer Temperaturkoeffizient von 0,9 %/K. Richtig wären bei 20 °C etwa 0,7 bar pro g/L und rund 3 % pro Kelvin. Das bei der Abfüllung schon gelöste CO₂ fehlt ganz. Folge: Der Druck wird um 1–2 bar unterschätzt (Tabelle in 2.3). Dieselben Konstanten stehen in `docs/THEORY.md` („Bottle at 1.004 SG for 3.5 bar“).
- **Ein globales k aus einem Anker mitten in der Gärung:** Streamt das Röhrchen im Gärmaximum, sind dort zu wenige Blasen gezählt, und k fällt zu groß aus. Danach wird jede korrekt gezählte Blase übergewichtet. Der geschätzte Restzucker sinkt schneller als der echte, man füllt zu früh ab und bekommt zu viel Druck. Das verstärkt den Fehler oben.
- **ML-Stufen** (`petnat_predictor.py`, `models.py`, `feature_engineering.py`, `anomaly_detector.py`, `training_pipeline.py`, `pretrained/`): Platzhalter ohne Trainingsdaten. Ihr Ziel „1–2 Blasen/min, ~1.002 SG“ hängt vom Gefäß, vom Röhrchen und vom Alkohol ab und taugt nicht als Abfüllkriterium.
- `sensors/ispindel_sensor.py` rechnet Alkohol mit fester Startdichte 1.090 und einem erfundenen Standardpolynom.
- `custom_components/wine_monitor` kann nicht laden: `__init__.py` enthält nur einen Docstring, `sensor.py` importiert eine nicht vorhandene `WineMonitorDataUpdateCoordinator`. Außerdem fragt die Komponente `/api/status`, `/api/sensors` usw. auf Port 5000 ab, während das Add-on nur `/health`, `/metrics` und `/ready` auf 8099 anbietet.
- `www/wine-monitor-card` (845 Zeilen Lovelace-Karte) ist überflüssig, sobald es eine eigene Oberfläche gibt.
- Schwere Abhängigkeiten (numpy, pandas, scikit-learn, Flask). Das Dockerfile installiert Rust und Cargo, was den Build auf einem Raspberry Pi lang macht.

### 1.4 Design (tipsy.pt)

`website-project/css/style.css`, live identisch geprüft:

- Farben: Papier `#f9e3e7` (lab rosé), Tinte `#2b2c78` (Ultramarin), Rot `#d24e35` (Koralle).
- Schriften, selbst gehostet: **Rubik Mono One** (Display), **Fraunces** mit „wonky“-Achsen (Fließtext), **JetBrains Mono** (Daten), Teko nur für CARMA.
- Prinzip aus dem README: „One ground, one ink, one red. Mono speaks, serif tells.“ Punktierte Führungslinien wie auf den Hangtags, ★ als Trenner.
- Logo: `img/logo.svg`, ein einzelner Pfad mit `currentColor`, also beliebig einfärbbar. Für Hintergründe gibt es `logo-badge-blue.svg`.
- Für die App gilt zusätzlich: keine abgerundeten Ecken.

---

## 2 Recherche

### 2.1 Vergleichbare Projekte

Du hast gebeten, auch im Brau-Bereich zu suchen. Deshalb stehen hier Bier-Werkzeuge; übernommen werden nur Ideen, keine Bier-Begriffe.

| Projekt | Herkunft | Messprinzip | Was man lernt |
|---|---|---|---|
| **iBlopper** (kbaggen, Hackster) | DIY | ESP8266 außen am Gärröhrchen spürt die kleine Bewegung beim Blop; loggt Blasen/min, „Sum blops/L“, Temperatur; Dichteschätzung per Polynom | Dein Vorbild. Auch dort ist die Dichte nur „indikativ“ und braucht **eine zusätzliche Hydrometer-Messung nach dem Gärmaximum**, um das Polynom neu zu rechnen. |
| **Brew Bubbles** (lbussy) | DIY, US | Gabellichtschranke im S-Röhrchen, ESP8266, Anbindung an Fermentrack/BrewPi | Optisches Zählen funktioniert. Das Projekt ist archiviert (Firmware 2.2.3 final). |
| **Plaato Airlock** | kommerziell, Norwegen | Infrarot im Röhrchen; schätzt Dichte und Alkohol aus Blasen, nachdem man Volumen und Startdichte eingibt | Herstellerangabe ±1,5 °Oe. Laut Hersteller verfälschen Undichtigkeiten die Werte; Nutzer berichten gemischt, besser nach mehreren Chargen im Lernmodus. |
| **Speidel GÄRSPUNDmobil** | kommerziell, Deutschland | zählt Blops im Speidel-Zylinderröhrchen, Temperaturfühler, WLAN zum myspeidel-Portal | Händler werben damit, Dichte und Abfüllzeit abzuschätzen. Ein Modell ist nicht veröffentlicht. |
| **iSpindel** + **GravityMon** (mp-se) | Open Hardware | Neigungswinkel eines Schwimmkörpers → Dichte per Polynom | Siehe 2.7. Die Kalibrierung in Zuckerwasser überträgt sich nicht immer sauber auf gärende Flüssigkeit; Nutzer berichten von zu niedrigen Werten gegen Ende (anekdotisch). |
| **Nautilis** iSpindel „Pill“ / iRelay / iTAP | kommerziell, Kroatien | iSpindel-Hydrometer; Relais mit Display leitet an MQTT/Home Assistant, Brewfather u. a. weiter; **iTAP misst Druck und Temperatur** (HA mindestens alle 10 s) | Vermutlich deine „Nautilus Spindel“. Der Weg nach MQTT/HA existiert schon; der iTAP ist ein fertiger Sensor für den Charmat-Tank. |
| **Fermentrack**, **Brewblox** | Open Source, self-hosted (Docker; Brewblox mit MQTT) | sammeln Tilt-, iSpindel- und Plaato-Daten, zeichnen Kurven | Gute Logger, keine Abfüllprognose. |
| **Brewfather**, **BierBot Bricks** | Cloud (BierBot: Deutschland) | Logging von iSpindel/Tilt | BierBots Anleitung zur Gärende-Prognose extrapoliert ein Polynom in Excel; ihr eigenes Beispiel landet im Jahr 2091. |
| **iSpindle Plotter** (MIT-Lizenz) | Open Source, Android | modifizierter Gompertz-Fit (Levenberg-Marquardt, Zwietering 1990), Attenuations-Prior für frühe Phasen, Endvergärungsgrad mit Unsicherheitsband | Das beste offene Beispiel für eine ehrliche Prognose mit Band. Eine Zeitprognose („wann“) macht es nicht. |
| **Spundomat** (InnuendoPi) | DIY, Deutschland | ESP8266, Drucksensor, zwei Magnetventile; spundet auf einen Sollwert aus CO₂-Ziel und Temperatur | Die Regel-Logik für deinen Charmat-Modus (2.6). |
| **Winegrid** (Watgrid, Partner u. a. Sogrape) | kommerziell, **Portugal** | Faseroptik im Tank (Dichte, Temperatur, Farbe, Trübung, Füllstand); **e-aphrom** misst den Flaschendruck während der Zweitgärung, **e-charmat** den Tankdruck, jeweils mit Alarmen | Profistandard: Dichte im Tank, Druck in Flasche oder Drucktank. |
| **INRAE** (Sablayrolles u. a.) | Forschung, Frankreich | CO₂-Freisetzung online als Gärgeschwindigkeit | Die CO₂-Rate ist in der Önologie *die* Messgröße für den Gärverlauf; die Modelle skalieren vom Labor zum Tank. Dein Blasenzähler ist ein günstiger CO₂-Flussmesser. |
| **UC Davis** (Boulton, Nelson, Coleman) | Forschung, USA | modellbasierte Online-Prognose aus Brix-Reihen; Parameterschätzung aus Dichte-Zeitreihen (Coleman 2024) | Prognose = Modell + laufende Parameterschätzung. |
| **Sipos 2020** | Forschung | Kalman-Filter und erweiterter Kalman-Filter zur indirekten Überwachung der alkoholischen Gärung im Weinbau | Zustandsschätzung aus indirekten Messungen funktioniert für Wein. |
| **Heriot-Watt 2021** | Forschung, UK | vierparametrige Logistik (ASBC Yeast-14) mit Vorhersagebändern | Einfaches, gut belegtes Kurvenmodell für Phase 1. |
| **Cojocaru & Antoce 2012** | Forschung, **Rumänien** | Refraktometer-Korrektur für Alkohol in gärendem Most, aus Brechungsindex-Tabellen | Grundlage für die Refraktometer-Auswertung. |

**Was daraus folgt:**

1. Niemand bekommt zuverlässigen Zucker nur aus Blasen. Wer es versucht, braucht mindestens eine echte Messung (iBlopper, Plaato-Lernmodus).
2. Gute Prognosen sind Modell-Fits mit Unsicherheit (Gompertz, Logistik, Kalman). Polynom-Extrapolation ist es nicht.
3. Profis messen den Druck in der Flasche oder im Tank (e-aphrom, e-charmat). Für dich ist eine einzelne Messflasche pro Ansatz der billigste Weg, das Modell auf deine Weine zu eichen.
4. Für Pet Nat rechnet keines der Werkzeuge einen Abfüllzeitpunkt aus einem Zieldruck. Genau diese Lücke soll TIPSYLAB füllen.

### 2.2 Pet Nat in Zahlen

- **Hanna Instruments** (technischer Blog zur Pet-Nat-Herstellung): Grundwein ≤ 12 % vol, pH < 3,5. Erstgärung bei 14–16 °C. In der Nähe des Ziels auf 8 °C kühlen. Abfüllen mit **8–15 g/L Restzucker → bis 3–4 bar**. Flaschengärung bei 13–15 °C, Stopp durch 0–2 °C, Verschluss Kronkorken. Hanna impft dabei frische Hefe nach; das ist nicht deine Arbeitsweise, die Zahlen gelten trotzdem als Orientierung.
- **EU-Kategorien** (VO 1308/2013, Anhang VII Teil II; Überdruck bei 20 °C): Perlwein, *vinho frisante*, 1–2,5 bar. Schaumwein, *vinho espumante*, ab 3 bar; Qualitätsschaumwein ab 3,5 bar. Zwischen 2,5 und 3 bar gibt es keine Kategorie. Der Druck bei 20 °C ist also zugleich die obere Grenze deines Öffnungsbereichs und die Etikettenfrage. Den konsolidierten Text auf EUR-Lex vor dem Etikettieren prüfen.
- **Faustregel:** 4 g/L Zucker ≈ 1 bar; Champagner mit 24 g/L Tirage landet bei etwa 6 bar, gemessen bei Kellertemperatur (siehe 2.3).
- **Torulaspora delbrueckii** (laut deinen Tech Sheets deine Gärhefe): verträgt je nach Stamm etwa 7–9 % vol, wird unter Ethanolstress langsam oder bleibt stecken, und überlebt in der Flasche keine ~3,5 atm CO₂. In Studien haben eingeschleppte Saccharomyces die Flaschengärung zu Ende geführt. Ob der Restzucker in deiner Flasche ganz vergärt, ist also offen. Die App rechnet mit vollständiger Vergärung; bleibt Zucker übrig, wird die Flasche leiser als berechnet.

### 2.3 Physik: Druck in der Flasche

Nach Liger-Belair et al. (2013), die Henry-Konstante für Champagner aus Daten von Agabaliantz (1963):

```
kH(T) = 1,21 g/(L·bar) · exp[ ΔH/R · (1/T − 1/298 K) ],   ΔH ≈ 24,8 kJ/mol

P_CO2 = m · R · T / (4,4·10³ · v + kH(T) · R · T · V)          [bar]
m     = V · (C₀ + 0,47 · S)                                     [g CO₂ in der Flasche]

V  = Weinvolumen (L), v = Kopfraum (L), S = Restzucker beim Abfüllen (g/L),
C₀ = beim Abfüllen schon gelöstes CO₂ (g/L), 0,47 g CO₂ je g Zucker (theoretisch 0,49)
Überdruck ≈ P_CO2 + Restluft im Kopfraum − 1,013 bar
```

kH bei 8 °C: 2,22 · 10 °C: 2,06 · 12 °C: 1,91 · 15 °C: 1,71 · 18 °C: 1,54 · 20 °C: 1,44 g/(L·bar). Die Faustregel „4 g/L pro bar“ entspricht kH ≈ 1,9, also etwa 12 °C.

Druck beim Öffnen nach vollständiger Vergärung, 750 ml, 20 ml Kopfraum, abgefüllt bei 12 °C. Erster Wert: ungünstiger Fall (Wein CO₂-gesättigt, Luft im Kopfraum); in Klammern der mittlere Fall:

| Restzucker beim Abfüllen | Öffnen bei 10 °C | Öffnen bei 20 °C | Add-on 1.1, „20 °C“ |
|---|---|---|---|
| 4 g/L | 1,6 (1,0) bar | 2,4 (1,7) bar | 1,0 bar |
| 6 g/L | 2,0 (1,5) | 3,0 (2,3) | 1,5 |
| 8 g/L | 2,5 (1,9) | 3,6 (3,0) | 2,0 |
| 10 g/L | 2,9 (2,3) | 4,3 (3,6) | 2,5 |
| 12 g/L | 3,4 (2,8) | 4,9 (4,2) | 2,9 |
| 15 g/L | 4,0 (3,5) | 5,8 (5,2) | 3,7 |

Benötigter Restzucker für einen Zieldruck beim Öffnen bei 20 °C (750 ml). Die Spanne reicht vom ungünstigen bis zum günstigen Fall (60 % gesättigt, CO₂ im Kopfraum):

| Ziel bei 20 °C | Restzucker, mittlerer Fall | Spanne | dazu Öffnen bei 10 °C | Faustregel 4 g/L/bar |
|---|---|---|---|---|
| 1,5 bar | 3,4 g/L | 1,3–5,5 g/L | 0,9 bar | 6 g/L |
| 2,0 bar | 5,0 g/L | 2,9–7,1 g/L | 1,2 bar | 8 g/L |
| 2,5 bar (frisante max.) | 6,5 g/L | 4,4–8,7 g/L | 1,6 bar | 10 g/L |
| 3,0 bar (espumante min.) | 8,1 g/L | 6,0–10,2 g/L | 1,9 bar | 12 g/L |
| 3,5 bar | 9,7 g/L | 7,6–11,8 g/L | 2,3 bar | 14 g/L |
| 4,0 bar | 11,3 g/L | 9,2–13,4 g/L | 2,6 bar | 16 g/L |

**Prüfung gegen deine Kronkorken-Werte**, ungünstiger Fall beim Öffnen bei 20 °C, abgefüllt beim mittleren Zielzucker: Bei 330 ml (Grenze 4,5 bar) passen Ziele bis 3,5 bar (bis 4,2 bar im ungünstigen Fall); ein Ziel von 4,0 bar ergibt bis 4,7 bar und ist zu hoch. Bei 750 ml (Grenze 6 bar) passen alle Ziele bis 4,0 bar.

**Folgerungen:**

- Die größte Unbekannte ist, wie viel CO₂ beim Abfüllen schon im Wein steckt. Das macht ±0,5–1 bar aus. Eine Messflasche mit Manometer pro Ansatz eicht das; nach zwei, drei Ansätzen ist es dein Hauswert, und die Spanne in der Tabelle schrumpft.
- Zwischen 10 und 20 °C ändert sich der Öffnungsdruck bei gleicher Flasche um rund 50 %. Die App zeigt deshalb immer beide Werte.
- **Malo in der Flasche:** Wird Äpfelsäure erst nach dem Abfüllen abgebaut, entsteht zusätzlich CO₂ (0,33 g je g Äpfelsäure). 2 g/L ergeben rund +0,3 bar bei 10 °C und +0,4 bar bei 20 °C. Ausgleich: pro 1 g/L ausstehender Äpfelsäure 0,7 g/L weniger Restzucker abfüllen. Die App fragt deshalb vor dem Abfüllen nach dem Malo-Status (3.11).
- Höhere Lagertemperaturen zeigt die App nicht an. Eine Prüfung dafür ist im Code vorgesehen, aber standardmäßig aus.
- Diese Zahlen sind ein Modell auf Basis veröffentlichter Konstanten für Champagner (12,5 % vol). Sie sind ein Startwert, den eigene Messungen korrigieren, keine Wahrheit. `tools/druckmodell.py` rechnet sie nach; in Phase 1 wird die Tabelle zum Test.

### 2.4 Physik: Was der Blasenzähler sieht

Blasen sind CO₂, das das Gefäß verlässt:

```
Blasenfluss = produziertes CO₂ (≈ 0,47 × Zuckerabbau)
            − CO₂, das sich gerade im Wein löst (Temperatur!)
            ± Ausdehnung/Schrumpfung des Kopfraums (Temperatur, Luftdruck)
            − Lecks
```

Größenordnungen für 50 L, Wein gesättigt (für 300 L gelten dieselben Stundenwerte):

- Späte Phase, 2 g/L Zuckerabbau pro Tag: rund 47 g CO₂ am Tag, also etwa 25 L Gas am Tag oder 1 L pro Stunde.
- **Kühlen von 15 auf 10 °C:** Der Wein löst 0,34 g/L zurück, also 17 g ≈ 9 L Gas. Das sind rund 9 Stunden späte Gärung ohne sichtbare Blasen. Von 16 auf 8 °C sind es etwa 15 L ≈ 14 Stunden.
- Aufwärmen wirkt umgekehrt: Die Blasen zeigen mehr als die Gärung produziert.
- Gärbeginn: Die ersten 1,5–2 g/L CO₂ lösen sich, ohne eine Blase zu machen. Das entspricht 3–4 g/L Zucker.
- Gärmaximum: In großen Gefäßen streamt das Röhrchen, der Zähler läuft in die Sättigung (~6 Blops/s).

Der Blasenzähler ist also ein guter **relativer Ratensensor in der späten Phase**, genau der Phase, in der abgefüllt wird. Als absoluter Zuckermesser taugt er nicht. Das Modell braucht deshalb einen Löslichkeitsterm (Temperatur vom DS18B20) und einen Kopfraumterm (Luftdruck von einem neuen Barometer).

### 2.5 Spindel plus Refraktometer: Zucker und Alkohol

Zucker erhöht Dichte und Lichtbrechung. Alkohol senkt die Dichte, erhöht aber die Lichtbrechung. Zwei Messungen an derselben Probe ergeben also zwei Gleichungen für zwei Unbekannte. Das Prinzip steckt hinter der Bonham-Methode und hinter den Weinrefraktometern von Bellingham + Stanley (≈ 0,5 % vol Genauigkeit); Cojocaru & Antoce (2012) korrigieren Refraktometerwerte in gärendem Most mit dem Start-Brix.

Meine grobe Fehlerrechnung: Mit einem guten Hydrometer (±0,5 °Oe) und einem Refraktometer (±0,1 °Bx) kommt man auf etwa ±1 g/L Restzucker. Mit der Spindel (±2 °Oe) eher auf ±3 g/L. Deshalb zeigt die Spindel den Trend, die Anker kommen vom Refraktometer, am besten zusammen mit einem Hydrometer, mindestens aber zusammen mit dem Start-Brix. Die Spindel kann in gärender Flüssigkeit driften (CO₂-Bläschen, Hefe am Körper), gerade gegen Ende, wenn Pet Nat abgefüllt wird. Ihr Versatz ist im Modell deshalb eine unbekannte Größe, die bei jedem Anker neu geschätzt wird.

Pro Ansatz einmal kalibrieren: den Most vor der Gärung mit beiden Geräten messen. Noch ist kein Alkohol drin, also lässt sich der Beitrag der Nicht-Zucker-Extrakte direkt bestimmen.

Einheiten in der App: Dichte (g/cm³), °Oechsle, °Brix und °Baumé, frei wählbar. Kein Plato.

### 2.6 Charmat und Druckregelung

- **Verfahren:** Beim Charmat (Martinotti, Tankgärverfahren) läuft die zweite Gärung im Drucktank. Quellen nennen 10–12 °C für die beste CO₂-Aufnahme, in der Praxis oft 14–18 °C. Für Spumante liegen die Ziele um 4,5–6 bar; Prosecco DOC verlangt mindestens 30 Tage. Gestoppt wird durch Kühlen (ein Patent nennt etwa −1 °C), danach wird geklärt und isobar abgefüllt.
- **Für dich heißt das:** Für einen frisante mit 2,5 bar beim Öffnen braucht der Tank je nach Temperatur nur 1,5–2,6 bar (Tabelle in 3.9). Ein Tank für wenige bar reicht also, kein Autoklav für 6 bar.
- **Spundomat** (InnuendoPi, DIY): Wemos D1 mini (ESP8266), Drucksensor 0–5 bar am Analogeingang, DS18B20, zwei 12-V-Magnetventile (Ablassen und CO₂ zuführen). Er rechnet den Solldruck aus einem CO₂-Ziel in g/L und der gemessenen Temperatur. Die Ventile pulsen (Standard 200 ms auf, 10 s zu; am Ziel 10 ms auf). Die Doku warnt, dass Öffnungen über 500 ms schäumen lassen, und empfiehlt vor jedem Einsatz einen Dichtheitstest. Geschrieben ist er fürs Bier, die Physik ist dieselbe. Code übernehmen lohnt nicht (ESP8266, LCD, Drehgeber), die Logik schon.
- **Winegrid e-charmat:** Druck- und Temperaturüberwachung im Tank mit Grenzwert-Alarmen, das Profi-Gegenstück.
- **Nautilis iTAP:** fertiger Druck- und Temperatursensor mit HA-Anbindung. Reicht für die beratende Stufe (3.9).

### 2.7 Eigene Firmware für die iSpindel?

**Geht das?** Ja. Die iSpindel ist Open Hardware: ein Wemos D1 mini (ESP8266) oder ein pin-kompatibles ESP32-Mini-Board, ein MPU-6050-Gyro und ein DS18B20. Geflasht wird per USB, am einfachsten mit Brewflasher. Die fertige Alternative zur Original-Firmware ist **GravityMon** (mp-se, v2.6, nach eigener Angabe an über 40 Gärungen getestet). Sie läuft ohne Hardware-Änderung und sendet an mehrere Ziele gleichzeitig (HTTP, MQTT, Home Assistant, InfluxDB, Brewfather …). Kalibriert wird im Web-UI. Auf ESP32-Boards glättet sie die Werte (gleitender Mittelwert) und schickt eine Gärgeschwindigkeit mit. Was in der Nautilis „Pill“ steckt, konnte ich nicht klären, die Shopseite war für mich gesperrt. Aufschrauben und nachsehen: D1 mini oder ESP32-C3? Ist der USB-Anschluss erreichbar?

**Lohnt es sich?** Eine eigene Firmware von Grund auf: nein. Die Grenze setzt die Physik des Schwimmkörpers (Neigung, CO₂-Bläschen, Hefebelag, Temperatur), nicht der Code. Was die Genauigkeit wirklich verbessert, macht die Integration mit dem Rohwinkel: Kalibrierung gegen deine Refraktometer- und Dichtemessungen, Versatz pro Ansatz, Glättung. Von der Firmware brauchst du nur, dass sie Winkel und Temperatur zuverlässig an Home Assistant schickt. Das kann die Original-iSpindel-Firmware schon (MQTT, mit `angle`), und das iRelay leitet es weiter.

GravityMon lohnt sich in drei Fällen: Die Nautilis-Firmware kann nicht direkt an Home Assistant senden; du willst auf einem ESP32 schon im Gerät glätten; du brauchst mehrere Ziele gleichzeitig.

Für Wein wichtiger als die Firmware:
- Kalibrierpunkte in Zuckerlösung von etwa 0,990 bis 1,110 g/cm³, also von trockenem Wein bis Most.
- Vor jedem Ansatz den Nullpunkt in Wasser prüfen.
- Die Spindel zwischen den Ansätzen gründlich reinigen.
- In den letzten Tagen vor dem Abfüllen alle 15 min senden. Das geht per Konfiguration.
- In einem geschlossenen Edelstahl-Drucktank kommt das WLAN schlecht heraus. Dort ist der Druck der bessere Gärsensor (3.9).

### 2.8 Winegrid wineplus im Abgleich

Wineplus (Winegrid, Portugal) ist das professionelle Gegenstück zum Pet-Nat-Teil. Eine lebensmittelechte Edelstahlsonde im Tank (IP65) misst Dichte, Temperatur und Füllstand bzw. Volumen. Aus der Dichte der letzten 24 h berechnet das System die Gärkinetik. Das Dashboard prognostiziert das Gärende bei der aktuellen Temperatur und vergleicht Gärungen bei verschiedenen Temperaturen. Dazu kommen Alarme, Aufgabenlisten und Rückverfolgbarkeit. Die Premium-Sonde zeigt den Gärstatus mit einer RGB-LED direkt am Tank; übertragen wird per LoRa über eine „Smartbox“.

Zur Familie gehören außerdem:
- **e-bung** (Fass): Abstand zur Flüssigkeit ±2 mm, Temperatur, Bewegung; WLAN oder LoRa.
- **smartcellar** (Kellerumgebung): Ein Händler nennt CO₂-Überwachung gegen Vergiftung.
- **e-aphrom und e-charmat**: Druck in Flasche und Tank.

Einen Abfüllzeitpunkt für einen Zieldruck rechnet wineplus nicht. Das bleibt TIPSYLABs eigener Teil.

Was wir übernehmen:
- **Gärgeschwindigkeit als eigene Größe** (g/L Zucker pro Tag, über 24 h geglättet). Sie zeigt eine stockende Gärung am frühesten und kommt in die Statuszeile von „Heute“.
- **Volumen:** Es macht aus Blasen „Blasen pro Liter“ wie bei iBlopper und liefert im Charmat-Tank den Kopfraum für die Druckbilanz (3.9). Den Füllstand automatisch zu messen ist teuer; deshalb ist das Volumen ein Eingabefeld. Steht ein Ballon auf einer Waage, rechnet die App es aus dem Gewicht.
- **Status direkt am Gerät:** Das Display des AtomS3 zeigt BPM, DUB (Tage bis zum Abfüllen) und die Temperatur, bei jedem Blop kurz das Logo (3.12).
- **Funk im Keller:** Reicht das WLAN nicht bis an die Gefäße, funken die ESP32-Geräte per ESP-NOW an einen AtomS3 nahe dem Router, ohne Zusatzhardware. LoRa wie bei Winegrid wäre die Profi-Variante.

### 2.9 Wie sicher sind die Zahlen?

**Die Physik ist gut belegt.** Henry-Gesetz, Gasgesetz und Gärungs-Stöchiometrie sind Lehrbuch. Die Henry-Konstante aus Liger-Belair et al. trifft eine unabhängige Angabe: 8,4 g/L CO₂ entsprechen laut Literatur 5,9 bar bei 20 °C, das Modell ergibt 5,85 bar.

**Unsicher ist, was beim Abfüllen in der Flasche steckt.** Die Empfindlichkeitsrechnung (`tools/druckmodell.py`, Teil 5) zeigt, welche Annahme den Öffnungsdruck wie stark verschiebt. Basis ist ein Ziel von 2,5 bar bei 20 °C; bei 10 °C wirkt alles etwa zu 70 %:

| Einfluss | Spanne | Wirkung bei 20 °C |
|---|---|---|
| Restzucker falsch gemessen | ±1 / ±2 / ±3 g/L | ±0,3 / ±0,6 / ±0,95 bar |
| Kopfraum: Luft oder CO₂ | | ±0,4 bar |
| gelöstes CO₂ beim Abfüllen | 60–120 % der Sättigung | −0,26 bis +0,51 bar |
| unvergärbarer Zucker (Pentosen, 1,5 g/L) mitgezählt | | −0,47 bar |
| Malo in der Flasche (2 g/L Äpfelsäure) | | +0,44 bar |
| Henry-Konstante | ±7 % | ±0,15 bar |
| Abfülltemperatur 15 statt 12 °C | | −0,11 bar |
| CO₂-Ausbeute | 0,45–0,49 g/g | ±0,09 bar |
| Kopfraum 10 oder 30 statt 20 ml | | ±0,05 bar |

Zusammen sind das nach meiner Schätzung vor jeder Eichung etwa ±0,8 bar bei 20 °C. Drei Maßnahmen bringen es auf etwa ±0,3 bar: Restzucker kurz vor dem Abfüllen direkt messen (auf ±0,5 g/L), zwei, drei Messflaschen pro Ansatz (sie eichen gelöstes CO₂ und Kopfraum in einem Schritt) und die Äpfelsäure messen. Den unvergärbaren Rest lernt die App aus dem trockenen Endwert jedes Weins.

**Weniger sicher als das Druckmodell:**
- **Zeitprognose:** Logistische Kurve und Q10 sind allgemeine Annahmen. Gerade das Ende der Gärung, wo Pet Nat abgefüllt wird, verläuft bei Torulaspora und Spontangärung oft unregelmäßig. Wie genau die Prognose wird, zeigt erst der erste echte Ansatz. Deshalb zeigt die App ein Fenster statt eines Zeitpunkts und verlangt in den letzten Tagen Messungen.
- **Blasen → CO₂:** Die Richtung aller Effekte ist sicher, die Größen sind Schätzungen. Frisch gärender Wein ist oft übersättigt; dann löst er beim Kühlen weniger CO₂ zurück als berechnet.
- **Refraktometer plus Dichte:** Die ±1 g/L sind meine Abschätzung aus den Empfindlichkeiten der Geräte, nicht gemessen. Gegen zwei, drei Laborwerte prüfen.
- **Charmat:** Im ruhenden Tank stellt sich das Gleichgewicht zwischen Gas und Wein langsam ein, und die 8 % Abfüllverlust sind ein Startwert. Die ersten Flaschen eichen beides.

### 2.10 Alkohol fürs Etikett

Fürs Etikett zählt der Alkohol in der fertigen Flasche. Beim Pet Nat vergärt der Restzucker nach dem Abfüllen noch, das ist gut 1 % vol mehr als beim Abfüllen. Die App rechnet deshalb den Endwert nach vollständiger Vergärung bis zum Endzucker (Standard 2 g/L, wie beim Druck). Ist der Wein schon trockener, endet die Rechnung dort.

Zwei Wege führen zur selben Zahl:
- **Aus dem Most:** vergärbarer Zucker geteilt durch 16,83 g/L je % vol. Das ist der Umrechnungswert des EU-Weinrechts für den potenziellen Alkohol; in der Literatur liegt er bei 16–18, bei Torulaspora und Spontangärung eher höher. Unsicher sind der Faktor (±0,5 g/L), der vergärbare Anteil am Brix (92 ± 2 %) und der Start-Brix (±0,2 °Bx). Zusammen sind das etwa ±0,46 % vol (1σ).
- **Aus einem Messpaar** (Refraktometer und Dichte an derselben, entgasten Probe, Abschnitt 2.5): Es misst den Alkohol direkt, ohne Umrechnungsfaktor. Der Rest bis trocken kommt im Verhältnis dazu, in dem bisher Zucker zu Alkohol wurde. Unsicher sind die Koeffizienten des Alkohols in Brechung und Dichte (je ±3 %; damit trifft ein Paar allein etwa ±0,5 % vol, wie es Bellingham + Stanley für Weinrefraktometer angibt) und die Geräte. Paare zählen erst, wenn höchstens die Hälfte des Zuckers übrig ist; vorher sagen sie wenig über den Endwert.

Beide Wege teilen sich den vergärbaren Anteil: Wie viel vom Restzucker noch vergärt, lässt sich ohne Labor nicht messen. Die App gewichtet deshalb mit der vollen Kovarianz (verallgemeinerte kleinste Quadrate) und nicht wie unabhängige Messungen; sonst wäre das ± zu klein. Bei 200 simulierten Weinen, deren Wahrheit so streut wie angenommen, liegt sie in 96–97 % der Fälle innerhalb 2σ (`tests/core/test_alcohol.py`).

| Grundlage | ± (1σ) |
|---|---|
| nur der Most | 0,46 % vol |
| ein Messpaar kurz vor dem Abfüllen | 0,37 % vol |
| mehrere Messpaare | 0,34–0,36 % vol |
| ein Messpaar am trockenen Wein | 0,31 % vol |
| ein Laborbefund (Alkohol und Restzucker derselben Probe) | 0,1 % vol |

**Etikett (VO (EU) 2019/33, Art. 44):** Angegeben wird in ganzen oder halben % vol. Die Analyse darf höchstens ±0,5 % vol abweichen, bei Schaum- und Perlwein ±0,8 % vol; ein Pet Nat unter 1 bar ist Stillwein. Die App rundet auf halbe % vol und nennt den Etikettwert sicher, wenn der wahre Wert mit 95 % Wahrscheinlichkeit in der Toleranz liegt. Beim Pet Nat reicht dafür meist ein Messpaar kurz vor dem Abfüllen. Beim Stillwein reicht es ohne Labor nicht.

**Laborbefund:** Bei der Messart „Labor“ lässt sich neben dem Restzucker der Alkohol derselben Probe eintragen. Er zählt als dritter Weg mit ±0,1 % vol (Laboranalyse) und ±0,5 g/L Zucker; der Rest bis trocken kommt wie beim Messpaar im bisherigen Verhältnis dazu. Damit ist der Etikettwert auch beim Stillwein sicher.

---

## 3 Zielbild

### 3.1 Drei Betriebsarten, je eine Hauptfrage

| Betriebsart | Hauptfrage | Nebenfragen |
|---|---|---|
| **Pet Nat** | Wann abfüllen? (Datum, Uhrzeit, Fenster mit Unsicherheit) | Was passiert beim Öffnen bei 10 und 20 °C, wenn ich jetzt abfülle? Was bewirkt Kühlen? Wann bringt eine Messung am meisten? |
| **Charmat** | Welcher Tankdruck jetzt? (Sollwert, hält das Ventil ihn?) | Wie weit ist die Gärung? Wann kühlen, wenn Restsüße bleiben soll? |
| **Naturwein (still)** | Wann ist die Gärung trocken? | Stockt sie? Stimmt die Temperatur? |

### 3.2 Architektur: Home Assistant als Plattform

Deine Daten laufen schon in Home Assistant zusammen, also wird TIPSYLAB dort eine **eigene Integration** (`custom_components/tipsylab`). Sie läuft in jeder Installationsart (HA OS, Container, Core) und braucht weder einen eigenen Dienst noch eine eigene Datenbank.

```
 AtomS3 (Blasen) ─────┐
 AtomS3 (Tank) ───────┤
 iSpindel ─▶ iRelay ──┼── MQTT ──▶ Mosquitto ──▶ Home Assistant
 SCD41 · ENV · Waage ─┘                                │
                                                       ├─ Integration „tipsylab“: Modell, Prognose, Alarme
                                                       ├─ Entitäten: Restzucker, DUB, Fenster … → Verlauf, Automationen
                                                       ├─ Panel „TIPSYLAB“ im tipsy.pt-Design → Browser, HA-App
                                                       ├─ Benachrichtigungen über die HA-App
                                                       └─ MQTT zurück: DUB fürs Display, CO₂-Ziel für den Tank
```

- **Eingang:** Die Integration liest vorhandene Entitäten (Spindel, Temperaturen, Druck, Gewicht). Die Blasen holt sie zusätzlich direkt vom MQTT-Topic, damit Neustarts des Zählers sauber erkannt werden.
- **Rechnen:** bei jeder Änderung, höchstens alle paar Minuten, und nach jeder Messung. Längere Rechnungen (Monte Carlo in Phase 3) laufen in einem Hintergrund-Thread, damit Home Assistant nicht hängt. numpy wird als Abhängigkeit im Manifest angegeben (Home Assistant nutzt es selbst, etwa für die Trend-Integration); scipy braucht es nicht.
- **Speichern:** Ansätze, Messungen, Ereignisse und Hauswerte im HA-Speicher (`.storage/tipsylab`); die Sensorverläufe im Recorder wie bisher.
- **Oberfläche:** ein eigenes Panel in der Seitenleiste, gebaut aus dem UI-Entwurf: dieselben Screens, dieselben Schriften, eckig. Es spricht über die Home-Assistant-Verbindung mit der Integration; Messungen gehen als Service-Aufruf (`tipsylab.add_measurement`). Auf dem Handy öffnet es die HA-App, unterwegs über deinen bestehenden Fernzugang.
- **Benachrichtigungen:** über die HA-App, als Blueprint mitgeliefert („Fenster öffnet in 12 h“, „Messung empfohlen“, „CO₂ im Keller“).
- **Installation:** über HACS aus dem GitHub-Repo, Updates per Klick; alternativ von Hand nach `/config/custom_components`.
- **Website (optional):** Die Seite „TIPSYLAB · DataWein, Fermentation read live“ liegt bisher nur als Entwurf mit simulierten Zahlen in deinem Ordner `Website/`; auf tipsy.pt ist sie nicht online. Soll sie einmal echte Zahlen zeigen, schickt Home Assistant alle 15 min eine kleine Datei mit den aktuellen Werten an deinen Webserver (etwa per `rest_command` an ein kleines PHP-Skript mit Schlüssel), und die Seite liest diese Datei. Home Assistant bleibt dabei vom Internet aus unerreichbar, und veröffentlicht wird nur, was in der Datei steht.

**Nachteile:** Der Code hängt an der API von Home Assistant; nach großen HA-Updates muss man ihn gelegentlich anpassen. Und die Oberfläche lebt im HA-Rahmen; als ganzflächiges Panel stört das kaum.

**Alternative auf deinem Server:** derselbe Code als eigenständiger Dienst in Docker neben Mosquitto, der seine Ergebnisse per MQTT Discovery an Home Assistant meldet. Das lohnt sich nur, wenn die App einmal ohne Home Assistant laufen soll.

**Vercel** ist vom Tisch: Du hast einen eigenen Server, die Daten liegen schon in Home Assistant, und für einen Betrieb wäre dort ohnehin der bezahlte Plan nötig.

### 3.3 Datenquellen und Schnittstellen

Alles läuft über Home Assistant. Die Geräte melden sich per MQTT Discovery an; die Integration liest ihre Entitäten und für die Blasenzählung zusätzlich das rohe MQTT-Topic (wegen der Reset-Erkennung). Messungen kommen über das Panel als Service-Aufruf.

| Quelle | Weg | Inhalt |
|---|---|---|
| TIPSYlab (Blasen) | MQTT `sensors/bubble/<id>` (besteht) | wie heute, neu in 2.1: `boot_id`, `seq`, gesicherter Gesamtzähler, `saturated`, `handling`, `pressure_hpa`, `humidity`, `ambient_temp` |
| Spindel | über das Nautilis iRelay per MQTT nach Home Assistant, oder direkt per MQTT `ispindel/<name>/<feld>` (Felder `angle, temperature, battery, gravity, interval, RSSI`) | **Winkel immer mitspeichern**, dann lässt sich später neu kalibrieren, ohne Daten zu verlieren |
| Tank (Charmat) | MQTT `sensors/tank/<id>`: Druck, Temperatur, Ventilpulse (Zeit, Dauer, Druck davor und danach), Status; oder Nautilis iTAP über MQTT/HA | Ist-Druck, Sollwert-Bestätigung, Alarme |
| Messungen | Panel (Service `tipsylab.add_measurement`) | Refraktometer (°Bx), Dichte (°Oe, g/cm³, °Baumé, bei 20 °C), Labor (g/L Zucker, % vol), **Äpfelsäure** (g/L), pH, **Flaschendruck** (bar + Temperatur); jede mit einstellbarer Standardunsicherheit |
| Ansatz | Panel bzw. Konfigurationsdialog der Integration | Betriebsart, Name, Rebsorte, Gefäß (**Volumen als Eingabe**, Kopfraum, Röhrchentyp oder Tank-Zulassung), Quellsensoren, Start-Brix und Startdichte (am Most gemessen), Hefe (Saccharomyces / Torulaspora / spontan), **Ziel: Druck beim Öffnen bei 20 °C**, Flasche (Volumen, Kopfraum, Grenze), **Malo mitrechnen** (an/aus, Äpfelsäure), Abfülltemperatur |

**Datenmodell:** Die Integration speichert Ansätze, Messungen, Ereignisse und Hauswerte im Home-Assistant-Speicher (`.storage/tipsylab`). Die Sensorverläufe liegen ohnehin im Recorder; für die Rechnung hält die Integration zusätzlich einen kompakten eigenen Puffer, damit sie nicht von den Recorder-Einstellungen abhängt. Logisch sind es: `batch`, `device`, `assignment` (welches Gerät wann an welchem Ansatz), `reading` (Rohzeitreihe: Zeit, Gerät, Art, Wert, Original-JSON), `measurement` (deine Anker), `estimate` (Modell-Schnappschüsse mit Modellversion), `event` (Kühlen, Abstich, Abfüllen, Ventilpuls, Notizen), `outcome` (gemessener Druck nach dem Abfüllen, Gushing, Verkostung), `house_value` (Haus- und Gerätewerte mit Unsicherheit und Herkunft). Rohdaten werden nie verändert; Schätzungen lassen sich mit einer neuen Modellversion neu berechnen.

### 3.4 Das Gärmodell

**Stufe 1 (Phase 1, deterministisch):**

- Die jüngste Messung setzt Restzucker S und Unsicherheit σ: Refraktometer mit Start-Brix-Korrektur oder das Paar Refraktometer + Dichte.
- Zwischen zwei Messungen laufen zwei Schätzungen parallel:
  - Spindel: S = S_Anker + (SG − SG_Anker)/(dSG/dS). Der Spindel-Versatz wird am Anker festgelegt.
  - Blasen: S = S_Anker − k_lokal · (N − N_Anker), mit k_lokal aus den letzten beiden Ankern. Gesättigte Intervalle bleiben außen vor, der Löslichkeitsterm wird abgezogen.
  - Beide werden nach ihrer Unsicherheit gewichtet; σ wächst mit dem Abstand zur letzten Messung.
- Prognose: eine vierparametrige Logistik wird an S(t) nach dem Gärmaximum angepasst. Die Zeitachse wird mit der Temperatur skaliert (Startwert Q10 ≈ 2, pro Ansatz nachgeschätzt). Gesucht ist der Zeitpunkt, an dem S den Zielzucker S* erreicht (aus dem Öffnungsdruck, 2.3), mit Band.
- Was-wäre-wenn und **Temperaturplan:** Ein geplanter Temperaturverlauf („ab jetzt 10 °C“) erzeugt eine neue Prognose. Pro Ansatz lässt sich daraus ein Plan festlegen, etwa 20 °C für die Malo und ab 25 g/L 14 °C. Home Assistant setzt ihn über die Heizmanschetten (Relais, z. B. Shelly) und die Wärmepumpe um, und die Prognose rechnet mit dem Plan.

**Stufe 2 (Phase 3, probabilistisch):**

- Zustandsraummodell mit Unscented-Kalman-Filter oder Partikelfilter. Zustand: Restzucker S, ln(Gärrate), ln(Blasen je g CO₂), Spindel-Versatz, gelöstes CO₂.
- Prozess: dS/dt = −r·f(T); die Rate fällt in der späten Phase ab. Das gelöste CO₂ läuft gegen kH(T) · p.
- Messungen: Spindel (σ 1–2 °Oe), Blasenzählung (Poisson mit Skalenfaktor; gesättigte Intervalle als zensierte Werte), Refraktometer (σ 0,1–0,2 °Bx über ein Brechungsmodell), Dichtemessung (σ 0,5 °Oe), Temperatur, Luftdruck; im Charmat-Modus der Tankdruck (3.9).
- Prognose per Monte Carlo: P10, P50 und P90 des Abfüllzeitpunkts und die Wahrscheinlichkeit, dass der Öffnungsdruck bei 20 °C über dem Ziel oder über der Flaschengrenze liegt.
- **Messempfehlung:** „Eine Refraktometer-Messung jetzt würde das Fenster von ±14 h auf ±5 h verkleinern.“ Berechnet als erwarteter Informationsgewinn.

**Was über Ansätze hinweg gelernt wird (statt ML):**

Jeder Ansatz bringt seine eigene Kinetik mit: Traube, Hefe, Temperatur, Nährstoffe. Der Gärverlauf wird deshalb für jeden Ansatz neu angepasst; frühere Ansätze liefern höchstens weite Startwerte. Über die Ansätze gelernt werden nur **Haus- und Gerätewerte**:

- Blasen je g CO₂ pro Gefäß und Röhrchen
- Kalibrierung und typischer Versatz der Spindel
- gelöstes CO₂ beim Abfüllen, aus den Messflaschen
- CO₂-Ausbeute je g Zucker
- Kopfraum deiner Flaschen
- Q10 als Startwert

Jeder neue Ansatz aktualisiert diese Werte nach seiner Unsicherheit (Bayes-Mittel). ML fällt weg: Bei mehreren Ansätzen pro Jahr kämen in Jahren nicht genug Daten zusammen, und die Ansätze unterscheiden sich zu stark.

### 3.5 Messprotokoll

1. **Vor der Gärung (Pflicht):** Start-Brix (Refraktometer) und Dichte des Mosts bei 20 °C, dazu Äpfelsäure und pH. Die Spindel in genau diesem Most einsetzen und den Nullpunkt prüfen.
2. **Nach dem Gärmaximum** (Blasen fallen deutlich): eine Refraktometer-Messung, Probe entgast.
3. **Ab etwa 25 g/L** sagt die App „jetzt täglich messen“: täglich Refraktometer, wenn möglich mit Dichte. In den letzten ein, zwei Tagen zusätzlich den Restzucker direkt messen (Labor oder Fotometer für reduzierende Zucker, z. B. Hanna HI83746, 0–50 g/L), denn 2 g/L Fehler bedeuten 0,6 bar.
4. **Vor dem Kühlen und etwa 12 h danach** je eine Messung. Das eicht die Temperaturabhängigkeit.
5. **Beim Abfüllen:** Schlussmessung, Äpfelsäure (für die Malo-Option), Temperatur, Füllhöhe. Die App rechnet den erwarteten Öffnungsdruck aus und speichert das Ereignis „abgefüllt“. Immer gleich abfüllen: gleiche Temperatur, gleiche Füllhöhe, gleich lange bis zum Kronkorken. Gleichmäßigkeit ist wichtiger als der genaue Wert, weil die App die Hauswerte daraus lernt.
6. **Messflasche:** eine Flasche mit Druckmessung (Aphrometer mit Nadel durch den Kronkorken oder Kronkorken-Manometer). Ablesen nach 3, 7 und 14 Tagen, und am Ende einmal bei 10 °C und einmal bei 20 °C. Das Ergebnis eicht das Modell.

Probe entgasen: zwischen zwei Gläsern umgießen oder in einem geschlossenen Gefäß schütteln und öffnen, dann zwei Tropfen aufs Refraktometer (mit Temperaturausgleich) und zweimal ablesen. Im Charmat-Tank über das Probenventil; die Probe schäumt stark und braucht länger.

### 3.6 Oberfläche

Siehe den UI-Entwurf (Link oben). Regeln:

- Eine Frage und eine Antwort pro Screen. Rubik Mono One nur für die eine Antwort, JetBrains Mono für alle Daten, Fraunces für die Sätze, die etwas erklären.
- **Keine abgerundeten Ecken**: Rahmen, Knöpfe, Eingabefelder, Regler und Markierungen sind eckig.
- Rot nur für Warnungen. Punktierte Führungslinien wie auf den Hangtags.
- Keine Navigationsleiste. Gebaut fürs Handy im Keller: große Tastflächen, Zifferntastatur, einhändig bedienbar.
- Texte in einer Tabelle, damit Deutsch, Englisch (wie tipsy.pt), Portugiesisch und Französisch möglich sind. Die EU-Kategorien heißen je Land anders: frisante/espumante (PT), pétillant/mousseux (FR), Perlwein/Schaumwein (DE).

| Screen | Inhalt |
|---|---|
| **Heute** (Pet Nat, Naturwein) | Antwort (Datum, Uhrzeit, Fenster), Regler für die Kellertemperatur als Was-wäre-wenn mit Hinweis auf das CO₂-Rücklösen, vier Zeilen (Restzucker ± σ, Alkohol, Druck wenn jetzt, Ziel beim Öffnen 10–20 °C), ein Diagramm (Restzucker mit Prognosekegel und Zielband, Blasen blass darunter), ein Knopf „+ Messung“, eine Statuszeile |
| **Messung** | drei Arten (Refraktometer, Dichte, Labor), ein großes Zahlenfeld, sofortige Wirkung: neuer Restzucker, Alkohol, Spindel-Korrektur, neues Fenster |
| **Ziel** (beim Anlegen) | Druck beim Öffnen: Regler für 20 °C, dazu der Wert bei 10 °C, EU-Kategorie, Flasche (330 ml bis 4,5 bar, 750 ml bis 6 bar), Malo mitrechnen (an/aus, Äpfelsäure in g/L), Volumen als Eingabe, Restzucker zum Abfüllen, ungünstiger Fall gegen die Flaschengrenze |
| **Tank** (Charmat) | Sollwert jetzt, Ist-Druck, Ventilstatus, Regler für Flaschenziel und Tanktemperatur, Sollwert-Tabelle, gelöstes CO₂, Restzucker aus der Druckbilanz, Sicherheitsventil, Wahl „Durchgären“ oder „Restsüße halten“, Druckverlauf mit Ventilpulsen |
| **Archiv** | frühere Ansätze: Kurve, Abfüllpunkt, gemessener Druck, Nachkalkulation, „was wir gelernt haben“ |
| Einstellungen (versteckt) | Geräte, MQTT, Home Assistant, Benachrichtigungen, Haus- und Gerätewerte |

Die Web-UI auf dem AtomS3 bleibt technisch (Einrichtung, Kalibrierung) und bekommt nur Schriften, Farben und eckige Formen.

### 3.7 Home Assistant

Die Integration legt pro Ansatz ein Gerät „TIPSYLAB ‹Ansatz›“ mit diesen Entitäten an:

- Pet Nat und Naturwein: `restzucker` (g/L), `alkohol` (% vol), `gaergeschwindigkeit` (g/L pro Tag), `dub` (Tage bis zum Abfüllen), `druck_wenn_jetzt_10c` und `_20c` (bar), `fenster_beginn` und `fenster_ende` (Zeitstempel), `status` (gärt / nähert sich / im Fenster / vorbei / trocken / stockt? / Malo?), `messung_empfohlen`, Binary Sensor `im_fenster`.
- Charmat: `tank_soll` und `tank_ist` (bar), `co2_geloest` (g/L), `ventil_letzter_puls` (Zeitstempel), Binary Sensor `tank_alarm`.
- Eingaben laufen über das Panel und den Service `tipsylab.add_measurement`; Ziel, Flasche und die Malo-Option sind Einstellungen des Ansatzes.
- Ans Display des AtomS3 schickt die Integration DUB und Status per MQTT (`tipsy/<id>/display`), an den Charmat-Tank das CO₂-Ziel.
- Beispiel-Automationen: „Fenster öffnet in 12 h“ aufs Handy; Kühlung per Smart Plug schalten, wenn die Gärung zu schnell fürs Fenster ist. Damit wird eure Website-Aussage „we steer with the timing and the environment“ wörtlich. Beide kommen als Blueprint mit.
- Aus `petnat_service.py` übernommen: die robuste Zählung der Blasennachrichten (Reset-Erkennung, Lücken füllen). Den Discovery-Baukasten und die Supervisor-Benachrichtigungen braucht es nicht mehr: Die Integration legt Entitäten direkt an und benachrichtigt über die HA-App.

### 3.8 Sicherheitsregeln (fest eingebaut)

**Pet Nat und Naturwein:**
- Der Druck wird immer für die **vollständige Vergärung** des Restzuckers gerechnet. Angezeigt wird der Öffnungsdruck bei 10 und bei 20 °C.
- Ist die Option „Malo mitrechnen“ an, zählt die angegebene Äpfelsäure als vollständig abgebaut. Fehlt ein Wert vom Abfüllen, nimmt die App den vom Most; das ist der sichere Fall.
- Die Grenzprüfung nimmt den ungünstigen Fall bei 20 °C und vergleicht ihn mit deinen Werten: 330 ml 4,5 bar, 750 ml 6 bar (Standard am unteren Ende deiner 6–7 bar). Beide Werte sind pro Flaschentyp einstellbar.
- Heizen: Jede Heizmanschette schaltet lokal ab, wenn der Wein über eine Höchsttemperatur steigt (Standard 26 °C) oder der Fühler fehlt, auch wenn Home Assistant nicht läuft.
- Kein Fenster ohne Unsicherheit. Ist σ zu groß (keine Messung in den letzten 24 h vor dem Fenster), zeigt die App „Messung nötig“ statt eines Datums.
- Stockende Gärung erkennen: Die Rate fällt, ohne dass die Temperatur sich geändert hat oder CO₂-Rücklösung zu erwarten ist → „Gärung stockt?“.
- Blasendaten gelten als ungültig während des Handlings, nach Temperatursprüngen (bis die Löslichkeit sich eingependelt hat) und in gesättigten Intervallen.
- Plausibilität: Weicht eine Messung um mehr als 3 σ vom Modell ab, fragt die App nach („Probe entgast? Einheit?“).

**Charmat:**
- Ein **mechanisches Sicherheitsventil** unter der Zulassung des Tanks ist Pflicht. Die Regelung ersetzt es nie.
- Der Sollwert liegt immer mindestens 0,3 bar unter dem Sicherheitsventil; sonst meldet die App „Ziel zu hoch für diesen Tank“.
- Der Regelkreis läuft auf dem Gerät am Tank und funktioniert ohne WLAN und ohne Home Assistant. Die Integration schickt nur das CO₂-Ziel per MQTT; die Temperaturkorrektur rechnet das Gerät selbst.
- Das Magnetventil ist stromlos geschlossen und direktgesteuert: Bei Stromausfall bleibt das CO₂ im Tank, und das Sicherheitsventil übernimmt. Gepulst wird kurz (≤ 200–500 ms), damit kein Schaum ins Ventil steigt.
- Alarme: Ist-Druck mehr als 0,3 bar über dem Sollwert, Sensorfehler, Ventil öffnet ohne Wirkung, Druck fällt ohne Ventilpuls (Leck).

### 3.9 Charmat-Druckregelung

**Sollwert.** Der Wein soll nach dem isobaren Abfüllen beim Öffnen bei 20 °C den Zieldruck haben. Daraus folgt der CO₂-Gehalt, und daraus der Gleichgewichtsdruck bei der aktuellen Tanktemperatur:

```
C_ziel   = kH(20 °C) · (P_Öffnen,20 + 1,013) / (1 − Verlust)     [g/L CO₂ im Wein]
P_soll   = C_ziel / kH(T_Tank) − 1,013                            [bar Überdruck im Tank]
```

Annahmen: Kopfraum des Tanks mit Gär-CO₂ gespült (Ventil am Anfang offen lassen), Gleichgewicht zwischen Gas und Wein, 8 % CO₂-Verlust beim isobaren Abfüllen (Startwert, wird an deinen Messflaschen geeicht).

Sollwerte aus `tools/druckmodell.py` (bar Überdruck im Tank):

| Ziel beim Öffnen, 20 °C | Tank 8 °C | 10 °C | 12 °C | 15 °C | 18 °C |
|---|---|---|---|---|---|
| 2,0 bar | 1,11 | 1,27 | 1,45 | 1,73 | 2,04 |
| 2,5 bar | 1,46 | 1,65 | 1,86 | 2,19 | 2,55 |
| 3,0 bar | 1,81 | 2,03 | 2,27 | 2,64 | 3,05 |
| 4,0 bar | 2,52 | 2,79 | 3,08 | 3,55 | 4,07 |
| 5,0 bar | 3,22 | 3,55 | 3,90 | 4,47 | 5,08 |

Wird der Tank wärmer, steigt der Sollwert mit. Wird er kälter, fällt der Druck von selbst, weil sich CO₂ löst. Das Ventil öffnet nur, wenn der Ist-Druck über dem Sollwert plus einer kleinen Hysterese liegt. CO₂ zuführen ist nicht vorgesehen (Naturwein); der Spundomat kann es, falls du es je willst.

**Zwei Ausbaustufen:**
- **A · beraten:** ein Drucksensor (Nautilis iTAP oder ein Transmitter am AtomS3) plus Temperatur. Du stellst ein mechanisches Spundventil auf den Sollwert der App ein. Die App meldet sich, wenn sich der Sollwert durch Temperaturänderung um mehr als 0,1 bar verschiebt.
- **B · regeln:** ein AtomS3 mit **ESPHome**, dein vorhandener Drucksensor über einen ADS1115 am I²C, ein **stromlos geschlossenes, direktgesteuertes** Magnetventil (12 V, Edelstahl, kleine Düse) über einen Logik-MOSFET mit Freilaufdiode, dazu der DS18B20 in einer Tauchhülse. Direktgesteuert ist wichtig: Vorgesteuerte Ventile brauchen einen Mindest-Differenzdruck und schalten bei den niedrigen Drücken eines frisante-Tanks nicht sicher. Sensor und Ventil sitzen oben im Gasraum, nie im Wein. Der Regelkreis läuft lokal (3.8), in ESPHome etwa so:

```yaml
script:
  - id: puls                      # Ventil 200 ms öffnen, ohne die Schleife zu blockieren
    mode: single
    then:
      - switch.turn_on: ventil
      - delay: 200ms
      - switch.turn_off: ventil

interval:
  - interval: 2s
    then:
      - lambda: |-
          // Sollwert aus CO2-Ziel (Zahl aus Home Assistant) und Weintemperatur, Henry nach Liger-Belair
          float T = id(t_wein).state + 273.15f;
          float kH = 1.21f * expf(24800.0f / 8.314f * (1.0f / T - 1.0f / 298.15f));
          float soll = id(co2_ziel).state / kH - 1.013f;
          if (isnan(id(p_tank).state) || isnan(T)) { id(ventil).turn_off(); return; }   // Sensorfehler: zu lassen
          if (id(p_tank).state > soll + 0.05f && millis() - id(letzter_puls) > 10000) {
            id(puls).execute();
            id(letzter_puls) = millis();
          }
```

**Gärfortschritt aus der Druckbilanz.** Im geschlossenen Tank ist der Druck der bessere Gärsensor: keine Sättigung, und die Löslichkeit wird explizit gerechnet.

```
CO₂ im Tank   = P_CO₂ · (kH(T) · V_Wein + 44 · V_Kopfraum / (0,08314 · T))
produziert    = Δ(CO₂ im Tank) + Σ abgelassen (aus dem Druckabfall je Ventilpuls)
Zucker vergoren = produziert / 0,47
```

Beispiel: 300 L Wein, 30 L Kopfraum, 12 °C ergibt rund 630 g CO₂ pro bar. 2 g/L Zuckerabbau am Tag lassen den Druck bei geschlossenem Ventil um etwa 0,45 bar am Tag steigen; das löst ein 0–10-bar-Sensor problemlos auf. Refraktometer-Anker kommen über das Probenventil (3.5).

**Ende der Gärung:**
- **Durchgären:** Die Hefe arbeitet bis trocken, das Ventil hält den CO₂-Gehalt. Danach kühlen, klären und isobar abfüllen. Das Ergebnis ist ein trockener Wein mit genau dem CO₂-Ziel.
- **Restsüße halten:** Die App prognostiziert, wann der Ziel-Restzucker erreicht ist, und erinnert ans Kühlen auf etwa −1 bis −2 °C. Das stoppt die Hefe, und der Sollwert folgt der Temperatur nach unten, ohne dass CO₂ verloren geht.

### 3.10 Naturwein (still)

- Gleiche Sensoren, gleiches Modell; das Ziel ist S* ≤ 2 g/L.
- Die Antwort auf „Heute“ lautet „Trocken in ≈ 3 Tagen“ oder „Gärung stockt seit 18 h bei 9 g/L“.
- „Trocken“ gilt erst nach zwei Messungen im Abstand von mindestens 24 h mit gleichem Wert. In der Endphase zeigen die Blasen vor allem ausgasendes CO₂.
- Das Refraktometer zeigt bei trockenem Wein wegen Alkohol und Extrakt noch etwa 5–7 °Bx. Die App rechnet das heraus und erklärt es beim ersten Mal.

### 3.11 Was man zusätzlich messen sollte

Sortiert nach Nutzen für Pet Nat und Naturwein ohne SO₂ und nach Aufwand. A = jetzt einplanen, B = lohnt sich, C = später oder nie.

| Messgröße | Wozu | Wie, Kosten | Prio |
|---|---|---|---|
| **CO₂ in der Kellerluft** | Sicherheit: Gär-CO₂ sammelt sich am Boden; der Arbeitsplatzgrenzwert liegt bei 5.000 ppm (0,5 %). Alarm aufs Handy, Lüfter per Home Assistant | NDIR-Sensor SCD41 am AtomS3 (Ausgabe bis 40.000 ppm, genau spezifiziert bis 5.000 ppm), tief montiert; rund 30–50 € | A |
| **Temperatur im Wein** | Das Modell braucht die Temperatur des Weins, nicht die des Raums. Mit Gärwärme liegen beide mehrere Grad auseinander | DS18B20 in einer Edelstahl-Tauchhülse durch Spund oder Deckel; der zweite Fühler misst den Raum | A |
| **Gewicht** (Ballons bis ~60 L) | Gewichtsverlust = entwichenes CO₂, auch durch Lecks; kein Röhrchenfaktor, keine Sättigung. Bei 50 L entspricht 1 g/L Zucker etwa 24 g | eine Single-Point-Wägezelle (z. B. Bosche H40A, 100–150 kg) unter einer Platte, HX711 am AtomS3 des Ballons, Temperaturkorrektur über den Raumfühler | A für Ballons |
| **Gewicht** (750-L-Inox-Tanks, drei Füße) | wie bei Ballons, dazu das Volumen automatisch. Bei 750 L entspricht 1 g/L Zuckerabbau etwa 350 g, die ganze Gärung rund 70 kg | je Fuß eine Edelstahl-Biegestab-Wägezelle 500 kg (C3) mit Montageteilen, ein Anschlusskasten, ein Wandler (HX711 oder NAU7802) am AtomS3. Markenzellen kosten 130–210 € pro Stück, der Anschlusskasten ab etwa 110 €; grob 600–1.000 € pro Tank | C, vorerst nicht |
| **Druck in der Messflasche** | eicht das Druckmodell, vor allem das gelöste CO₂ beim Abfüllen | Aphrometer oder Kronkorken-Manometer, später ein Transmitter (Phase 5) | A |
| **Äpfelsäure, Malo-Status** (von Hand) | Läuft die Malo erst in der Flasche, entsteht zusätzlich CO₂: 2 g/L Äpfelsäure ergeben rund +0,3 bar bei 10 °C und +0,4 bar bei 20 °C. Ausgleich: 0,7 g/L weniger Restzucker je g/L Äpfelsäure | enzymatischer Test oder Messgerät; Papierchromatografie als Ja/Nein-Test. Eintrag am Most und vor dem Abfüllen (siehe „Malo überwachen“) | A |
| **pH** (von Hand) | mikrobielle Stabilität ohne SO₂; Hanna nennt für Pet-Nat-Grundwein pH < 3,5 | Handmessgerät, Eintrag in der App. Keine Dauersonde: sie driftet und braucht Pflege | B |
| **Hefeverwertbarer Stickstoff** (von Hand, am Most) | Er bestimmt die Gärgeschwindigkeit am stärksten (Malherbe, Coleman). Wenig Stickstoff ergibt einen frühen Hinweis „könnte stocken“ und bessere Startwerte für die Prognose | Labor oder Schnelltest | B |
| **Farbe** (Dark Rosé) | Zeitpunkt zum Abpressen nach Farbtiefe; Bräunung (Absorption bei 420 nm) bei Wein ohne SO₂ verfolgen | kleines Kolorimeter: Spektralsensor AS7341, weiße LED und Küvette am AtomS3, Probe von Hand; rund 25 € | B |
| **Volumen** | „Blasen pro Liter“, Kopfraum für die Charmat-Bilanz | Eingabefeld beim Ansatz, nach jedem Abstich anpassen; bei Ballons auf der Waage automatisch. Ein Füllstandssensor lohnt sich nicht | A (Eingabe) |
| **Trübung** | Absetzen der Hefe vor dem Abfüllen, Klären im Charmat-Tank | Infrarot-Durchlicht an einer Küvette; bei Rot und Rosé ungenau | C |
| **Gelöster Sauerstoff, H₂S** | Oxidation bzw. Böckser früh erkennen | Optische Sauerstoffsonden kosten vierstellig; billige H₂S-Sensoren sind unzuverlässig. Hier ist die Nase besser | C |

Die A-Gruppe kostet ohne die Tankwaagen zusammen unter 150 € und landet in Phase 2.

**Waage für Ballons, nicht für Tanks.** Bei Ballons ist die Waage billig und einfach: eine Single-Point-Wägezelle (z. B. Bosche H40A, 100–150 kg) unter einer Platte und ein HX711 am AtomS3 des Ballons. Die Zelle braucht eine eigene lineare Temperaturkorrektur; die Bastler von Bienenstockwaagen im Hiveeyes-Projekt kommen damit auf Schwankungen von 5–25 g, also gut 1 g/L Zucker bei 50 L. Bei den 750-L-Tanks lohnt sie sich vorerst nicht: Sie kostet rund 600–1.000 € pro Tank, und im langsamen Endspurt (rund 0,7 kg Gewichtsverlust am Tag) stören Temperaturgang und Kriechen der Zellen. Dort reichen Blasen, Spindel und Messungen.

**Piezo-Elemente** taugen nicht als Waage: Sie messen nur Kraftänderungen, und bei ruhender Last fließt ihre Ladung ab. Statisch messen geht nur mit aufwendigen Ladungsverstärkern und Kompensation. Ihr Einsatz wäre die Blop-Erkennung, und die macht der Gyro schon.

**Malo überwachen.** Ob und wann die Malo läuft, hängt vor allem an Temperatur und pH. Unter etwa 15 °C ist sie deutlich langsamer als ab 20 °C, das Optimum liegt ohne SO₂ um 20–25 °C, und unter pH 3,2 wird es für die Bakterien schwer. Manche Stämme schaffen sie aber auch bei pH 3,0 und unter 17 °C; sicher ausschließen lässt sie sich also nicht. In Portugal (über 20 °C vor dem Abfüllen) läuft sie deshalb meist schon während der Gärung, in Frankreich (etwa 15 °C) eher in der Flasche.

Empfehlung in drei Stufen:
1. **Äpfelsäure messen**, am Most und kurz vor dem Abfüllen. Mengen liefert ein enzymatischer Test mit Fotometer oder ein Gerät wie der Vinmetrica SC-55 (laut Hersteller auf 0,1 g/L genau). Teststreifen (0–500 mg/L) und Papierchromatografie sind billiger, zeigen aber nur grob bzw. nur, ob noch Äpfelsäure da ist. Eine Laboranalyse pro Ansatz eicht das Ganze. Als abgeschlossen gilt die Malo unter 30 mg/L.
2. **Mitlesen, was die Sensoren ohnehin sehen:** Gibt der Wein weiter CO₂ ab (Blasen oder Gewicht), obwohl der Zucker laut Messung nicht mehr fällt und die Temperatur gleich bleibt, läuft wahrscheinlich die Malo. Die App meldet das als „CO₂ ohne Zuckerabbau, Malo?“. Der pH steigt dabei meist um 0,1–0,3.
3. **In der Flasche:** Die Messflasche zeigt es am deutlichsten. Steigt ihr Druck über den Wert, den der Restzucker allein erklärt, rechnet die App den Überschuss in abgebaute Äpfelsäure um (bei 20 °C etwa 0,2 bar je g/L) und meldet ihn.

In der App heißt das: Option „Malo mitrechnen“ an, sobald beim Abfüllen messbar Äpfelsäure da ist (in Frankreich also meist), mit dem gemessenen Wert. Ohne Messung vom Abfüllen nimmt die App den Wert vom Most.

**Malo fördern, damit sie vor dem Abfüllen durch ist.** Das ist der beste Fall: Die Malo-Unsicherheit fällt aus der Druckrechnung, und die Option bleibt aus.
- **Wärme ist der wichtigste Hebel.** Den Wein auf 18–22 °C halten, nicht über etwa 25 °C. Bei einem 750-L-Tank braucht das Anheben um 5 °C rund 4 kWh Wärme plus Verluste. Deine Tanks haben teils Heizmanschetten, die übrigen lassen sich nachrüsten; Home Assistant schaltet sie über ein Relais nach dem Fühler im Wein. Die Wärmepumpe vor Ort kann den Raum temperieren. Wann es wie warm sein soll, legt der Temperaturplan des Ansatzes fest (3.4).
- **Hefe und Zeit:** auf der Hefe lassen und ein- bis zweimal pro Woche aufrühren, damit die Bakterien nicht unter dem Trub liegen. Ohne SO₂ (wie bei dir) und bei pH über 3,2 läuft sie leichter an.
- **Der Haken bei Pet Nat:** Wärme beschleunigt auch die alkoholische Gärung, das Abfüllfenster rückt also nach vorn. Die Malo muss deshalb früh beginnen, das heißt: warm von Anfang an. Kühlen, um das Fenster hinauszuzögern, bremst die Malo stärker als die Hefe.
- **Risiko:** Milchsäurebakterien plus viel Restzucker können Essigsäure bilden (Milchsäurestich, *piqûre lactique*), vor allem wenn die Hefe stockt. Bei Torulaspora ist das ein echtes Thema. Die App warnt deshalb früh bei fallender Gärgeschwindigkeit; flüchtige Säure solltest du kosten oder messen lassen.
- **Optional, falls spontan zu unsicher:** Malo-Bakterien früh zusetzen (Ko-Inokulation). In Studien verkürzt das die Gesamtzeit um bis zu zwei Wochen und hält die flüchtige Säure niedrig. Für Naturwein ist das ein Eingriff; die Entscheidung liegt bei dir.
- **Wenn es zeitlich nicht passt (Frankreich, kühler Keller):** den Wein ganz durchgären und die Malo abschließen lassen und dann mit eingefrorenem Most derselben Lese abfüllen. Die Zweitgärung kommt aus dem eigenen Most, und der Druck lässt sich aus der zugegebenen Zuckermenge genau rechnen. Ob das unter deiner Bezeichnung als Pet Nat bzw. méthode ancestrale durchgeht, vorher prüfen.

### 3.12 Anzeige am AtomS3

Das Display hat 128 × 128 Pixel. Es zeigt deshalb nur drei Zahlen (Entwurf im UI-Artifact, Abschnitt 5):

```
 12     BPM
 2,1    DUB
 13,1°
```

- **BPM:** Blops der letzten 60 Sekunden; das misst das Gerät selbst (heute schon als „bubbles/min“).
- **DUB:** Zeit bis zum wahrscheinlichsten Abfüllzeitpunkt im Format „3d 12h“, Ziffern groß, d und h klein. Der Wert kommt per MQTT von der Integration (`tipsy/<id>/display`); ohne Prognose steht „--“. Die Farbe sagt, was zu tun ist:
  - **grün**, mehr als 3 Tage: nichts zu tun.
  - **gelb**, 3 Tage oder weniger, bis das Fenster öffnet: täglich messen, Flaschen und Kronkorken bereitlegen.
  - **Koralle**, Fenster offen: abfüllen.
  - **Koralle blinkend**, Fenster vorbei: Der Druck wird niedriger als geplant.

  Rot wird es, wenn das Fenster öffnet, nicht zu einer festen Zeit wie 3 h vor dem Termin. Das Fenster enthält die Unsicherheit schon, und ein fester Abstand vor einem unsicheren Zeitpunkt täuscht eine Genauigkeit vor, die es nicht gibt.
- **Temperatur:** nur Zahl und Gradzeichen, aus dem Fühler im Wein; fehlt der, aus dem Raumfühler.
- **Bei jedem Blop** erscheint für etwa 0,3 s das Tipsy-Logo. Die Firmware 2.0.7 lässt an dieser Stelle einen bunten Kreis aufblitzen und zeigt das Logo als Dauerbild; beides wird getauscht. Das Logo kommt aus dem vorhandenen Upload (Einstellungen → Display-Logo, PNG oder JPEG bis 120 KB, gespeichert als `/logo.png`); für den Blitz wird es auf volle 128 × 128 Pixel gesetzt statt wie bisher 128 × 116 mit Statusleiste. Es kommt ohne Kreis außen herum: Smiley in Papier-Rosé auf Ultramarin, fertig zum Hochladen als `assets/logo-atoms3-128.png`. Kommen die Blops schneller als alle 1,2 s, wird nicht jeder als Logo gezeigt, sonst wären die Zahlen im Gärmaximum kaum lesbar. Dauer und Abstand sind einstellbar.
- **Farben und Schrift:** Ultramarin als Grund, Papier-Rosé für BPM und Temperatur; Grün, Gelb und Koralle nur für DUB. Das sind die drei Lampenfarben aus deinem DataWein-Entwurf. Die Ziffern in JetBrains Mono Bold als kleiner Bitmap-Font (nur Ziffern, Komma, Grad und die Buchstaben der Kürzel; wenige KB). Das Dezimalzeichen folgt der Einstellung der App.
- **Störungen:** Fehlt WLAN oder MQTT, erscheint ein kleines Quadrat in einer Ecke, sonst nichts. Hostname, IP und Diagnose bleiben auf dem Knopf (kurz drücken, wie heute).
- **Andere Betriebsarten:** Beim Naturwein steht statt DUB die Zeit bis trocken (DRY). Das Gerät am Charmat-Tank zeigt BAR (Ist-Druck) statt BPM.

### 3.13 Hardware: was wofür

Grundsatz: **Geregelt wird am Gerät, Home Assistant plant, speichert und benachrichtigt, Handy oder Tablet zeigen an.** Fällt Home Assistant oder das WLAN aus, halten die Geräte ihren letzten Sollwert und ihre Sicherheitsgrenzen.

| Aufgabe | Hardware | Firmware | Warum |
|---|---|---|---|
| Blasen zählen, je Gefäß | AtomS3 am Gärröhrchen, DS18B20 im Wein | TIPSYlab 2.x | Der Impulsdetektor existiert nur dort und bleibt. |
| Waage, je Ballon | Single-Point-Zelle unter einer Platte, HX711 am AtomS3 des Ballons | TIPSYlab 2.x, erweitert | ein Gerät pro Ballon |
| Charmat: Druck messen, Ventil steuern | AtomS3 (Display für BAR/Soll), ADS1115, Logik-MOSFET mit Freilaufdiode, Magnetventil NC direktgesteuert 12 V, 12-V-Netzteil, DS18B20 in Tauchhülse, mechanisches Sicherheitsventil | ESPHome | Regelkreis in wenigen Zeilen (3.9), native HA-Anbindung, OTA, kein eigener C++-Code |
| Heizmanschetten (230 V) | Shelly 1PM Gen3/Gen4 mit Shelly Plus Add-on und DS18B20 im Wein | Shelly-Firmware plus kleines Skript | zertifiziert für Netzspannung, lokal regelbar, misst den Verbrauch, direkt in Home Assistant |
| Wärmepumpe | je nach Modell über Modbus oder einen Schalteingang (z. B. SG-Ready, dann per Shelly) | – | nur, wenn sie sich ansprechen lässt |
| Kellerluft | ein AtomS3 mit SCD41 (CO₂) und ENV IV (Temperatur, Feuchte, Luftdruck), tief montiert | ESPHome oder TIPSYlab | ein Gerät pro Raum |
| Anzeige im Keller (optional) | einfaches Android-Tablet an der Wand | HA-App oder Fully Kiosk Browser | zeigt das Panel; Eingabe der Messungen mit großen Feldern |

**Drucksensor anschließen**, je nach Ausgang deines vorhandenen Sensors:
- **0,5–4,5 V (ratiometrisch, 5 V Versorgung):** über einen Spannungsteiler an den ADS1115, damit höchstens 3,3 V ankommen. Kalibrieren bei 0 bar und bei einem bekannten Druck (Manometer daneben).
- **4–20 mA (Industrie, 12–24 V):** über einen 150-Ω-Messwiderstand, das ergibt 0,6–3,0 V am ADS1115.
- **I²C digital:** direkt an den Grove-Port.

Messbereich 0–6 oder 0–10 bar, Edelstahl, Einbau oben im Gasraum. Ein Gerät mit eigenem ADC (ADS1115) misst deutlich ruhiger als der eingebaute ADC des ESP32.

**Tablet:** Als Anzeige im Keller ja, als Server nein. Android beendet Hintergrunddienste, Home Assistant läuft dort nicht offiziell, und ein Akku, der dauernd lädt, bläht sich auf (Laden per Steckdosen-Automation zwischen etwa 20 und 80 % hilft). Die Regelkreise hängen ohnehin an den Geräten. Home Assistant bleibt also das Gehirn auf deinem Server: MQTT, Verlauf, Automationen, Benachrichtigungen, Fernzugriff und Backups. Das Tablet ist nur ein weiteres Fenster darauf.

**Elektrik im Keller:** Netzspannung nur über zertifizierte Geräte (Shelly), Fehlerstromschutzschalter, Gehäuse gegen Feuchte; feste Installationen macht ein Elektriker.

---

## 4 Wiederverwendung im Detail

| Teil | Entscheidung | Was genau | Aufwand |
|---|---|---|---|
| **Firmware 2.0.7:** Detektor, Autokalibrierung, `/api/trace` | übernehmen, unverändert | das Herzstück; mit Rohsignalen getestet | – |
| Firmware: Netzwerk, OTA, NVS, HA-Discovery, Geräte-ID | übernehmen; die Tank-Steuerung läuft dagegen mit ESPHome (3.13) | | – |
| Firmware: MQTT-Payload | erweitern | `boot_id`, `seq`, gesicherter Zähler, `saturated`, `handling`, Umgebungswerte | klein |
| Firmware: Legacy-Topics | standardmäßig aus, später entfernen | | klein |
| Firmware: Web-UI am Gerät | optional neu einkleiden | Fonts, Farben, eckig | klein |
| `Tipsy`, `TIPSY CLAUDE` | Archiv | Klartext-Passwörter in `TIPSY CLAUDE` | – |
| `residual_sugar.py` | umbauen | behalten: Datenklassen, Anker-Logik, Alarme mit Hysterese, Zustandsspeicherung, Brix/SG-Umrechnung. Ersetzen: Druckmodell (durch `tools/druckmodell.py`); globales k durch lokales k plus Spindel-Fusion | mittel |
| `petnat_service.py` | Teile übernehmen | Verarbeitung der Blasennachrichten (Summe, Reset-Erkennung, Lücken). Weg: Discovery-Baukasten, Supervisor-Benachrichtigungen und Add-on-Optionen; die Integration legt Entitäten nativ an | mittel |
| `tests/test_residual_sugar.py`, `tests/test_petnat_service.py` | übernehmen, an die neue Physik anpassen | | klein |
| `data_manager.py` | nur Ideen (SQLite, WAL, Aufbewahrung) | neues Schema (3.3) | klein |
| `main.py`, `mqtt_handler.py`, `config.py` | ersetzen | durch die neue Integration | – |
| `ml_engine/*` außer `residual_sugar.py` | verwerfen | Platzhalter | – |
| `sensors/*` | verwerfen | | – |
| `custom_components/wine_monitor` | verwerfen | lädt nicht (1.3); die neue Integration `tipsylab` ersetzt sie | – |
| `www/wine-monitor-card` | verwerfen | | – |
| `addon/`-Packaging | verwerfen | eine Integration braucht kein Add-on; Installation über HACS | – |
| `.github/workflows` | als Vorlage | Tests und HACS-Prüfung | klein |
| `docs/THEORY.md`, `docs/PETNAT_GUIDE.md` | neu schreiben | falsche Konstanten | klein |
| `*_SUMMARY.md`, `COMPLETION_REPORT.md`, `TEST_RESULTS.md` u. ä. | löschen | | – |
| `tools/druckmodell.py` (neu) | wird Kern des Physik-Moduls im Server | Flaschendruck, Charmat-Sollwert | – |
| Spundomat (fremd) | Logik als Vorlage, kein Code | Puls-Regelung, Dichtheitstest | – |
| tipsy.pt: Fonts, CSS-Tokens, `logo.svg` | 1:1 übernehmen | | – |
| DataWein-Seite (`tipsylab.js`) | anbinden (Phase 6) | die Datei sagt selbst: `tick()` durch einen Fetch auf die Sensor-API ersetzen | klein |

**Wo entwickeln:** in diesem Ordner `Tipsy/tipsylab/` als Monorepo mit `firmware/` (aus `TIPSYlab incl Webportal`, Historie per `git subtree` mitnehmen), `custom_components/tipsylab/` (die Home-Assistant-Integration mit Panel), `docs/` und `tools/`; auf GitHub als `studioanarc/tipsylab`. `tipsyhomelab` danach archivieren. Vor jedem Push prüfen, dass weder `secrets.ini` noch der Code aus `TIPSY CLAUDE` mitkommt.

---

## 5 Umsetzung in Phasen

### Validierung ohne Altdaten

- **Simulator** (Teil von Phase 1): synthetische Ansätze mit bekannter Wahrheit. Er bildet Gärkurven mit Kühlphasen nach, CO₂-Rücklösung, Lecks, ein streamendes Röhrchen, Rauschen und Drift der Spindel und einen Charmat-Tank mit Ventilpulsen. Daran werden Schätzer und Prognose getestet, bevor ein echter Ansatz davon abhängt.
- **Kalibrier-Gärung im Winter:** ein Ballon (20–50 L) mit Most oder Traubensaft, mit Blasenzähler, Waage und Spindel. Abgefüllt wird in drei, vier Stufen (etwa bei 4, 7 und 10 g/L Restzucker), je zwei Messflaschen. Nach der Flaschengärung bei 10 und 20 °C messen. Das ergibt deine eigene Kurve Restzucker → Druck, unabhängig von meinem Modell, und testet nebenbei Sensoren, Display und Prognose vor der nächsten Lese.
- **Schattenbetrieb beim ersten echten Ansatz:** Du entscheidest wie bisher, die App prognostiziert parallel. Ab etwa 25 g/L misst du täglich, damit es eine Wahrheit zum Vergleichen gibt.
- **Nachkalkulation nach jedem Ansatz** (im Archiv): Wie gut lag die Prognose 48, 24 und 12 h vor dem tatsächlichen Durchgang? Wie gut lag der vorhergesagte Öffnungsdruck gegen die Messflasche bei 10 und 20 °C? Danach werden die Hauswerte aktualisiert.

### Phase 0 · Sofort (ein Abend)

- Den Druckwerten des Add-ons beim nächsten Abfüllen nicht trauen. Stattdessen die Tabellen in 2.3 oder den Ziel-Screen im Entwurf nutzen und eine Messflasche mit Manometer füllen.
- Falls der Code aus `TIPSY CLAUDE` je geteilt wurde: WLAN- und MQTT-Passwort ändern.
- Die zwei lokalen `tipsyhomelab`-Commits pushen oder bewusst liegen lassen (sie gehen sonst irgendwann verloren).
- Nachsehen, was in der Nautilis-Spindel steckt (2.7).
- Ein Kronkorken-Manometer (Aphrometer) besorgen und ein paar übrige Flaschen DATA 2024 und 2025 bei 10 und 20 °C messen, dazu Restzucker und Äpfelsäure im Labor. Das sind die ersten echten Datenpunkte für das Druckmodell.

### Phase 1 · Integration-MVP: Pet Nat und Naturwein (etwa 2–3 Wochenenden)

Lieferumfang:
- Home-Assistant-Integration `tipsylab`, installierbar über HACS: Konfigurationsdialog für Ansätze (Betriebsart, Quellsensoren, Volumen, Ziel, Flasche, Malo-Option), Services für Messungen und Ereignisse.
- Gärmodell Stufe 1 und Druckmodell (aus `tools/druckmodell.py`, inklusive Malo).
- Die Entitäten aus 3.7, darunter DUB fürs Display.
- Panel mit den Screens Heute, Messung und Ziel aus dem UI-Entwurf, Gärgeschwindigkeit in der Statuszeile.
- Blueprint für Benachrichtigungen über die Home-Assistant-App.
- Simulator und Tests (mit `pytest-homeassistant-custom-component`).

Fertig, wenn: die Tabellen aus 2.3 als Test grün sind; der Simulator für typische Ansätze das richtige Fenster trifft; das Panel in der HA-App am Handy einhändig bedienbar ist.

### Phase 2 · Firmware 2.1 und Sensoren der A-Gruppe (1–2 Wochenenden)

- Neues Dauerbild nach 3.12: BPM, DUB und Temperatur, bei jedem Blop kurz das Logo. DUB kommt per MQTT von der Integration.
- I²C-Sensoren am Grove-Port über einen Grove-Hub: ENV IV (SHT40 + BMP280) für Raumklima und Luftdruck, SCD41 für CO₂ in der Kellerluft. Den DS18B20 dafür auf einen freien Pin der Stiftleiste legen (Pinout prüfen); ein zweiter Fühler steckt in einer Tauchhülse im Wein.
- Waage für Ballons: Single-Point-Wägezelle unter einer Platte, HX711 am AtomS3 des Ballons, Temperaturkorrektur.
- Je Heizmanschette ein Shelly 1PM (Gen3 oder Gen4) mit Shelly Plus Add-on und DS18B20 im Wein; ein kleines Skript auf dem Shelly regelt mit dem Sollwert aus Home Assistant und schaltet bei Übertemperatur oder fehlendem Fühler ab (3.13).
- Payload-Erweiterungen aus 3.3, Gesamtzähler im NVS (alle 10 min sichern, das schont den Flash), Flag `saturated`, Legacy-Topics standardmäßig aus.

### Phase 3 · Probabilistisches Modell (2–3 Wochenenden)

Kalman- oder Partikelfilter, Monte-Carlo-Prognose, Messempfehlung, Temperatur-Szenarien, Löslichkeits- und Kopfraumkorrektur, Behandlung der Sättigung.

Fertig, wenn: im Simulator das P10–P90-Fenster aus Prognosen, die 48 h vorher gemacht wurden, den tatsächlichen Durchgang in mindestens 80 % der Fälle enthält. Das ist ein Kalibrierungstest, kein Genauigkeitsversprechen; die echte Bewährung kommt mit der Nachkalkulation der ersten Ansätze.

### Phase 4 · Charmat-Druckregelung (2 Wochenenden plus Hardware)

- Stufe A (beraten): Tank-Screen, Sollwert aus Ziel und Temperatur, Druckbilanz, Alarme. Sensor: Nautilis iTAP oder Transmitter am AtomS3.
- Stufe B (regeln): Tank-Steuerung mit ESPHome auf einem AtomS3 (3.9, 3.13): Drucksensor über ADS1115, direktgesteuertes Magnetventil, lokaler Regelkreis mit kurzen Pulsen, Dichtheitstest, Alarme. Das CO₂-Ziel kommt als Zahl aus Home Assistant; fehlt die Verbindung, hält das Gerät den letzten Wert.
- Fertig, wenn: der Regelkreis im Simulator und an einem Wassertank mit Druckluft den Sollwert hält; bei getrenntem WLAN weiterregelt; jeder Alarm aus 3.8 auslöst.

### Phase 5 · Nach dem Abfüllen und Hauswerte (1–2 Wochenenden plus Hardware)

- Messflasche: Druckmessung von Hand eintragen, oder einen Drucktransmitter über einen Kronkorken-Adapter an einen zweiten AtomS3 hängen. Das ist dein eigenes e-aphrom.
- Nachkalkulation und Hauswerte (3.4) im Archiv.
- Alarm, wenn eine Messflasche über den erwarteten Öffnungsdruck steigt, mit konkreter Handlung („auf 0–2 °C kühlen“).

### Phase 6 · Extras

- Öffentlicher Nur-Lese-Feed für die DataWein-Seite auf tipsy.pt („Fermentation, read live“ mit echten Zahlen).
- Kühlung per Home Assistant steuern.
- Kolorimeter für die Farbe, Füllstandssensoren in Tanks (3.11).
- Mehrere Tanks gleichzeitig.

---

## 6 Offene Fragen an dich

1. **Gefäße und Mengen** für Pet Nat und Naturwein: Glasballons (20–60 L), IBC oder Edelstahltank? Welche Gärröhrchen? Das bestimmt, wann der Zähler sättigt und wie viele Blasen auf ein Gramm CO₂ kommen.
2. **Charmat:** Welcher Tank (Volumen, zugelassener Druck laut Typenschild)? Gibt es schon ein Spundventil, ein Sicherheitsventil und eine Möglichkeit, isobar abzufüllen?
3. **Refraktometer und Dichte:** Welches Refraktometer (Modell, Temperaturausgleich, Bluetooth oder USB)? Hast du ein Hydrometer oder Dichtemeter?
4. **Spindel:** Was steckt in der Nautilis „Pill“ (D1 mini oder ESP32-C3), und wohin sendet sie heute (MQTT nach HA, Brewfather …)?
5. **Home Assistant:** Auf welchem Server, und welche Installationsart (HA OS, Container oder Core)? Die Integration läuft in allen; Add-ons gäbe es nur mit HA OS.
6. **Ziel pro Wein:** frisante (bis 2,5 bar bei 20 °C) oder espumante (ab 3 bar)? Das legt das Ziel und das Etikett fest.
7. **Degorgierst du?** Dann zählt auch die Phase in der Flasche, und die Messflasche sagt, wann.
8. **Sprache der App:** Deutsch, Englisch wie tipsy.pt, Portugiesisch?
9. **WLAN im Keller:** Reicht es bis an die Gefäße, oder braucht es ein Gateway per ESP-NOW? Gilt das auch für den Keller in Frankreich?
10. **Wärmepumpe:** Kann sie auch kühlen (Raum oder Wasser), und hat sie eine Schnittstelle zu Home Assistant (z. B. Modbus)? Dann setzt Home Assistant den Temperaturplan mit Heizen und Kühlen um.
11. **Drucksensor:** Welches Modell hast du (Ausgang 0,5–4,5 V, 4–20 mA oder I²C; Messbereich; Material; Gewinde)?
12. **Heizmanschetten:** Welche Leistung, und wie sind sie angeschlossen (Schuko-Stecker oder fest)?

---

## 7 Quellen

Projekte und Geräte
- iBlopper: https://hackster.io/kbaggen/iblopper-a-fermentation-logger-for-homebrewing-9abd56
- Brew Bubbles: https://brew-bubbles.readthedocs.io/
- Plaato (Spezifikation, Undichtigkeiten): https://help.brouwland.com/hc/en-gb/articles/360020629478 · https://help.brouwland.com/hc/en-gb/articles/360020627298
- Speidel GÄRSPUNDmobil: https://www.vigoltd.com/Catalogue/test-equipment/gaerspundmobil-fermentation-monitor
- Nautilis iRelay / iSpindel / iTAP: https://www.tindie.com/products/nautilis/nautilis-ispindel-irelay-nxt/
- iSpindel: https://hackaday.io/project/20421-ispindel
- GravityMon: https://github.com/mp-se/gravitymon · Doku-Quellen (Funktionen): https://github.com/mp-se/gravitymon/blob/master/src_docs/source/functionality.rst · Releases: https://github.com/mp-se/gravitymon/releases
- iSpindle Plotter: https://f-droid.org/de/packages/com.ispindle.plotter/ · https://github.com/GlassOnTin/iSpindlePlotter
- Spundomat: https://github.com/InnuendoPi/Spundomat · Doku: https://innuendopi.github.io/Spundomat/
- Fermentrack: https://fermentrack.readthedocs.io/ · Brewblox Tilt: https://pypi.org/project/brewblox-tilt/2.0.0/
- BierBot, Gärende-Prognose: https://bierbot.com/?p=1124
- Winegrid: https://sogrape.com/project/winegrid · e-aphrom: https://www.watgrid.com/?p=7623 · e-aphrom und e-charmat: https://vinitech-sifel.com/en/offering/4b0e5e98-9b8f-ef11-8473-6045bda07ccf/e-aphrom-e-charmat-second-fermentation-monitoring-system-for-bottles-and-tanks

Forschung und Physik
- Liger-Belair et al. (2013), J. Food Eng. 116, 78–85, Henry-Konstante, Flaschendruck: https://www.sfb1064.med.uni-muenchen.de/holiday-calendar/december_13/liger_belair-et-al-2013.pdf
- Liger-Belair & Cordier, kH ≈ 1,5 g/L/bar bei 20 °C: https://www.refletsdelaphysique.fr/articles/refdp/pdf/2019/01/refdp201961p32.pdf
- Sektdruck ≈ 5,9 bar ≈ 8,4 g/L CO₂ bei 20 °C: https://winegrowers.info/wine-making/winemaking/making-quality-sparkling-wine.htm
- Online-CO₂-Messung in der Weingärung (Übersicht): https://www.mdpi.com/2311-5637/7/3/155 · Patent EP0469998B1: https://patents.google.com/patent/EP0469998B1/en
- INRAE, Gärmodell auf Basis der Hefephysiologie (AJEV 2005): https://hal.inrae.fr/hal-02681151v1
- UC Davis, Seeded-Search-Schätzer: https://asev.org/abstract/seeded-search-estimation-algorithm-line-prediction-wine-fermentation
- Coleman et al. (2024), Parameter aus Dichte-Zeitreihen: https://mdpi-res.com/d_attachment/fermentation/fermentation-10-00386/article_deploy/fermentation-10-00386.pdf
- Sipos (2020), Kalman-Filter in der Weingärung: https://ideas.repec.org/a/gam/jsusta/v12y2020i17p7105-d406615.html
- Heriot-Watt (2021), Logistik-Modelle: https://researchportal.hw.ac.uk/en/publications/predicting-fermentation-rates-in-ale-lager-and-whisky/
- Cojocaru & Antoce (2012), Refraktometrie in der Gärung: https://www.horticulturejournal.usamv.ro/pdf/vol12issue4/Art78.pdf
- Bonham-Methode (Refraktometer + Hydrometer): https://byo.com/?p=8754 · Brewfather Refraktometer: https://docs.brewfather.app/tools/refractometer

Pet Nat, Charmat, Recht, Hefe
- Hanna Instruments, Pet-Nat-Technologie: https://blog.hannaservice.eu/technology-of-petillant-naturels-pet-nats-production/
- Charmat-Verfahren (Temperaturen, Drücke): https://www.winewithseth.com/winewiki/charmat-tank-method-metodo-martinotti/ · https://wiki.ubc.ca/Course:FNH200/Projects/2022/Wine_-_Prosecco
- Stopp durch Kühlen (Patent US 11618869): https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11618869
- EU-Kategorien: https://www.legislation.gov.uk/eur/2013/1308/annex/VII/part/II/division/5 · https://www.vinarskecentrum.cz/en/o-vine/klasifikace-sumiva-a-perliva-vina
- Torulaspora delbrueckii (Ethanol- und Drucktoleranz): https://pmc.ncbi.nlm.nih.gov/articles/PMC7564342 · https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2020.595023/pdf

Winegrid, Sensoren, Wägezellen, Malo, Home Assistant
- Winegrid wineplus (deutsch): https://marketing.winegrid.com/wineplus-de
- Winegrid e-bung, Datenblatt: https://www.enartis.com/wp-content/uploads/2024/03/WINEGRID-datasheet-e-bung_EN.pdf · smartcellar: https://vinitech-sifel.com/en/offering/aa6ba2cc-c98f-ef11-8473-6045bda07ccf/smartcellar-environment-monitoring-system-for-cellars
- Wägezellen 500 kg, Edelstahl-Biegestab (Preise): https://www.bosche.eu/p/biegestab-waegezelle-b10n/100-300-10-69 · https://omega-waagen.de/waagen-komponenten/waegezellen/biegestab-waegezellen/biegestab-waegezelle-b10s/b10n · https://www.pce-instruments.com/deutsch/waegetechnik/waagen-im-online-vertrieb/waegezelle-cas-deutschland-ag-waegezelle-hbs-l-500-mit-eichzulassung-det_415416.htm · https://hanse-waagen.de/SHBxR-Edelstahl-Biegestab-Waegezelle-HWO10058.8
- Wandler für Wägezellen (Alternativen zum HX711): https://e2e.ti.com/support/data-converters-group/data-converters/f/data-converters-forum/1514864/ads1231-hx711-replacement · Hiveeyes, Bienenstockwaagen: https://community.hiveeyes.org/t/adc-choice-for-load-cell/4543/2
- Single-Point-Zelle H40A und Temperaturkorrektur (Hiveeyes): https://community.hiveeyes.org/t/bosche-h40a-or-h30a/5581 · https://community.hiveeyes.org/t/more-on-load-cell-temperature-compensation/4391/22
- Piezo und ruhende Lasten: https://www.machinedesign.com/automation-iiot/sensors/article/21833476/sensor-sense-piezoelectric-force-sensors · https://www.imeko.info/publications/tc3-2005/IMEKO-TC3-2005-028u.pdf
- Malo testen (Chromatografie, Streifen, Grenze 30 mg/L): https://winemakermag.com/technique/testing-for-malolactic-dont-be-in-doubt · Testkits und Geräte: https://morewinemaking.com/category/malolactic-fermentation-testing.html
- Malo fördern: Wärme, wenig SO₂, pH, Risiken der Spontan-Malo: https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/5607854 · Hefe aufrühren: https://morewine.com/blogs/articles/5-steps-to-a-succesful-malolactic-fermentation-mlf · Ko-Inokulation (kürzere Gärzeit, flüchtige Säure): https://rodin.uca.es/handle/10498/22791 · Protokoll: https://www.enartis.com/wp-content/uploads/2020/09/Coinoculation-protocol.pdf · Risiko flüchtige Säure bei viel Zucker (Review 2025): https://eprints.ugd.edu.mk/36642/1/2025-Ailer%20et%20al%20_Inter%20J%20Food%20Sci%20Tech.pdf
- Malo, Temperatur und pH: https://extension.psu.edu/understanding-difficult-malolactic-fermentations-a-review · https://catalogs.gusmerenterprises.com/view/525133696/15/ · https://www.journals.ac.za/sajev/article/view/1433/638
- Home Assistant, eigene Panels: https://www.home-assistant.io/integrations/panel_custom/ · HACS: https://hacs.xyz/
- Shelly Plus Add-on mit DS18B20 (Plus, Gen3, Gen4): https://www.shelly.com/products/shelly-temp-sensor-ds18b20 · https://taphome.com/en/compatibility/shelly-sensor-add-on/ · Skript-Beispiel auf dem 1PM Gen3: https://shelly.guide/en/scripting/ntc-sensor-control/
- ESPHome mit ADS1115 und Drucksensor, Hinweis zu induktiven Lasten: https://github.com/raberrio/gaggia_coffee_controller/blob/main/README.md
- Sensirion SCD41: https://sensirion.com/products/catalog/SCD41
