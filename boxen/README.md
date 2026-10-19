# Die Boxen

Die Boxen messen und regeln vor Ort. Gerechnet wird in Home Assistant: Die TIPSYLAB-Integration
führt alle Quellen eines Ansatzes zusammen (Messungen, Spindel, Blasen, Gewicht, Temperatur),
schätzt daraus den Restzucker mit seiner Unsicherheit und sagt das Abfüllfenster voraus. Diese
Sensorfusion steckt also nicht in einer Box, sondern in der Integration
([`custom_components/tipsylab`](../custom_components/tipsylab)).

Jede Box arbeitet auch ohne WLAN weiter: Die Gärbox zählt, die Tankbox hält den Druck, die
Heizbox regelt auf den letzten Sollwert.

## Übersicht

| Box | Wofür | Misst / schaltet | Software | Datei |
|---|---|---|---|---|
| [Gärbox](#gärbox) | jedes Gefäß mit Gärröhrchen | Blasen, Weintemperatur, optional Gewicht; zeigt BPM · DUB · ° | eigene Firmware (C++, PlatformIO) | [`gaerbox/`](gaerbox) |
| [Waagebox](#waagebox) | Gewicht, wenn keine Gärbox am Gefäß hängt | Gewicht | ESPHome | [`esphome/waagebox.yaml`](esphome/waagebox.yaml) |
| [Waage-Paket](#waage-paket) | Waage an einem ESP32, der schon ESPHome hat | Gewicht | ESPHome-Paket | [`esphome/pakete/waage.yaml`](esphome/pakete/waage.yaml) |
| [Tankbox](#tankbox) | Charmat-Drucktank | Tankdruck, Weintemperatur; schaltet das Ablassventil | ESPHome | [`esphome/tankbox.yaml`](esphome/tankbox.yaml) |
| [Flaschenbox](#flaschenbox) | die Messflasche nach dem Abfüllen | Druck und Temperatur der Flasche | ESPHome | [`esphome/flaschenbox.yaml`](esphome/flaschenbox.yaml) |
| [Kellerluftbox](#kellerluftbox) | ein Raum | CO₂ in der Kellerluft, Temperatur, Feuchte, Luftdruck | ESPHome | [`esphome/kellerluftbox.yaml`](esphome/kellerluftbox.yaml) |
| [Heizbox](#heizbox) | eine Heizmanschette | Weintemperatur; schaltet die Heizung | Shelly-Skript | [`heizbox/thermostat.js`](heizbox/thermostat.js) |

Nicht von uns, aber unterstützt: jede Spindel, die einen Dichte-Sensor in Home Assistant liefert
(z. B. iSpindel über das Nautilis iRelay). Sie wird im Ansatz als „Spindel“ eingetragen.

## Welche Boxen für welchen Ansatz

| Ansatz | nötig | sinnvoll |
|---|---|---|
| Pet Nat oder Naturwein im **Ballon** | Gärbox | Waage unter dem Ballon (an der Gärbox); Spindel |
| Pet Nat oder Naturwein im **Edelstahltank** mit Gärröhrchen | Gärbox | eine Wägezelle unter einem Bein (an der Gärbox oder als Waagebox); Heizbox, wenn der Tank eine Heizmanschette hat; Spindel |
| **Pet Nat in der Flasche** | – | Flaschenbox an einer Messflasche (sonst Aphrometer und von Hand eintragen) |
| **Charmat** im Drucktank | Tankbox | Heizbox |
| der **Keller** | – | Kellerluftbox, eine pro Raum |

Gewicht, Blasen und Spindel ersetzen einander nicht, sie ergänzen sich: Die Integration gewichtet
jede Quelle nach ihrer Unsicherheit. Am wichtigsten bleiben deine Messungen mit Refraktometer oder
Dichtemeter; an ihnen eicht die Integration alle anderen Quellen.

---

## Gärbox

**Zweck:** sitzt am Gärröhrchen jedes Gefäßes. Zählt die Blasen, misst die Temperatur im Wein und
zeigt auf dem Display die Blasen pro Minute (BPM), die Zeit bis zum Abfüllen (DUB) und die
Temperatur. Mit Wägezelle wiegt sie das Gefäß mit.

**Hardware**
- M5Stack AtomS3R (Nachfolger der AtomS3, die bei M5Stack ausläuft; eine vorhandene AtomS3 geht
  auch, die AtomS3 Lite nicht: ihr fehlen Display und Bewegungssensor)
- DS18B20 wasserdicht, in einer Tauchhülse im Wein; 4,7 kΩ zwischen Daten und 3,3 V
- optional: HX711-Board und Wägezelle: unter dem Ballon eine Single-Point-Zelle unter einer
  Platte; unter dem Tank eine Druck-Wägezelle oder ein Wägemodul für etwa 500 kg unter **einem**
  Bein, die beiden anderen Beine auf harten Unterlagen gleicher Höhe (Stahl oder POM, kein Holz,
  kein Gummi)
- USB-C-Netzteil

**Anschluss:** DS18B20 an G2 (Grove); HX711 DT an G5, SCK an G6, VCC an 3V3.

**Software:** eigene Firmware, [`gaerbox/`](gaerbox), bauen und flashen mit PlatformIO. Dort steht
auch, wie man die Waage eicht und welches MQTT-Format die Box spricht.

**Einrichten:** Firmware flashen, WLAN und MQTT im Einrichtungsportal der Box eintragen, unter
Einstellungen das Logo `assets/logo-atoms3-128.png` hochladen. Mit Waage: einmal eichen (Tara,
Testgewicht auflegen – beim Tank mittig auf den Deckel –, eichen).

**In Home Assistant:** Im Ansatz die Geräte-ID der Box (steht auf dem Display, z. B. `tipsy-a1b2c3`)
als „Blasenzähler“ eintragen. Temperatur und Gewicht kommen dann automatisch mit; ein eigener
Eintrag ist nur nötig, wenn sie von einem anderen Sensor kommen sollen.

## Waagebox

**Zweck:** wiegt ein Gefäß, das keine Gärbox hat, oder wenn das Kabel vom Tankbein hinauf zum
Gärröhrchen stört. Für die Gärung gilt dasselbe wie bei der Gärbox: Gewichtsverlust ist
entwichenes CO₂.

**Hardware:** M5Stack AtomS3R (oder AtomS3), HX711-Board, Wägezelle wie bei der Gärbox, USB-C-Netzteil.

**Anschluss:** HX711 DT an G5, SCK an G6, VCC an 3V3. Optional ein DS18B20 an G2 an der Wägezelle,
um Temperaturdrift zu sehen (in der YAML auskommentiert).

**Software:** ESPHome, [`esphome/waagebox.yaml`](esphome/waagebox.yaml); die eigentliche Waage steckt
im [Waage-Paket](#waage-paket).

**Einrichten:** siehe [ESPHome-Boxen einrichten](#esphome-boxen-einrichten). Eichen in Home
Assistant mit den Knöpfen „Waage Tara“, „Waage eichen“ und „Waage Inhalt setzen“.

**In Home Assistant:** den Sensor „Gewicht“ im Ansatz als „Waage“ eintragen.

## Waage-Paket

**Zweck:** dieselbe Waage für einen ESP32, der schon mit ESPHome läuft, etwa die Kellerluftbox
oder ein eigenes Gerät. In dessen YAML einfügen (Pins anpassen):

```yaml
packages:
  waage: !include
    file: pakete/waage.yaml
    vars:
      dout_pin: GPIO5
      sck_pin: GPIO6
```

Das Paket bringt den Sensor „Gewicht“, die Eich-Knöpfe und das Testgewicht mit.

## Tankbox

**Zweck:** hält einen Charmat-Drucktank auf dem Druck, der in der Flasche beim Öffnen bei 20 °C
den Zieldruck ergibt. Home Assistant schickt nur das CO₂-Ziel; den Sollwert für die aktuelle
Tanktemperatur rechnet die Box selbst und regelt ohne WLAN weiter. Beim Abkühlen folgt der
Sollwert langsam nach, damit kein CO₂ abgelassen wird, das sich gerade im Wein löst.

**Hardware**
- M5Stack AtomS3R (oder AtomS3), ADS1115-Modul (auf 3,3 V)
- der vorhandene Drucktransmitter, 0,5–4,5 V, über einen Spannungsteiler 10 kΩ/20 kΩ an A0
- DS18B20 in einer Tauchhülse im Wein
- Magnetventil 12 V, **stromlos geschlossen** und **direktgesteuert**, Edelstahl, kleine Düse;
  Logik-MOSFET mit Freilaufdiode; 12-V-Netzteil
- ein **mechanisches Sicherheitsventil** unter der Zulassung des Tanks: Pflicht, die Regelung
  ersetzt es nie

**Anschluss:** ADS1115 an Grove (G2 SDA, G1 SCL); DS18B20 an G6; MOSFET-Gate über 220 Ω an G5.
Sensor und Ventil sitzen oben im Gasraum, nie im Wein.

**Software:** ESPHome, [`esphome/tankbox.yaml`](esphome/tankbox.yaml).

**In Home Assistant:** Charmat-Ansatz anlegen; „Tankdruck“ und „Weintemperatur“ der Box als
Quellen, die Zahl „CO₂-Ziel“ als Regler eintragen, das Sicherheitsventil im Ziel angeben.

## Flaschenbox

**Zweck:** misst den Druck in einer Messflasche, solange der Pet Nat in der Flasche gärt: ein
eigenes e-aphrom. Die Integration rechnet den Druck auf 20 °C um, vergleicht ihn mit dem Druck bei
vollständiger Vergärung und meldet, wenn er höher steigt („auf 0–2 °C kühlen“). Ist die Flasche
durchgegoren, eicht sie beim Abschließen des Ansatzes das Druckmodell für die nächsten Ansätze.

**Hardware**
- M5Stack AtomS3R (oder AtomS3), ADS1115-Modul (auf 3,3 V)
- Drucktransmitter 0–10 bar, 0,5–4,5 V, Edelstahl, G1/4, über einen Spannungsteiler 10 kΩ/20 kΩ an A0
- Kronkorken-Adapter mit Durchführung (wie bei Aphrometern) für denselben Kronkorken wie die anderen
  Flaschen
- DS18B20 außen an der Flasche, mit Wärmeleitpaste

**Anschluss:** wie die Tankbox ohne Ventil: ADS1115 an Grove (G2 SDA, G1 SCL), DS18B20 an G6.

**Sicherheit:** Transmitter, Adapter und Kronkorken müssen den Grenzdruck der Flasche aushalten
(750 ml: 6 bar, 330 ml: 4,5 bar). Den Adapter nur mit Schutzbrille aufsetzen und abnehmen.

**Software:** ESPHome, [`esphome/flaschenbox.yaml`](esphome/flaschenbox.yaml).

**In Home Assistant:** im Pet-Nat-Ansatz unter „Neu konfigurieren“ die Sensoren „Flaschendruck“
und „Flaschentemperatur“ als „Messflasche: Druck“ und „Messflasche: Temperatur“ eintragen. Ohne
Flaschenbox geht es auch: das Aphrometer ablesen und unter „Messung → Flaschendruck“ eintragen.

## Kellerluftbox

**Zweck:** misst CO₂ in der Kellerluft. Gär-CO₂ ist schwerer als Luft und sammelt sich am Boden;
ab 5.000 ppm (Arbeitsplatzgrenzwert) gibt es Alarm. Dazu Temperatur, Feuchte und Luftdruck.
Tief montieren, etwa 30 cm über dem Boden. Nebenbei ist sie Bluetooth-Proxy: Sie empfängt
Spindeln mit Bluetooth (RAPT Pill, Tilt) im Keller und reicht sie an Home Assistant weiter.

**Hardware:** M5Stack AtomS3 Lite (die Box braucht kein Display; AtomS3R oder AtomS3 gehen auch),
Grove-Hub, Sensirion SCD41 (CO₂), M5 ENV IV (SHT40 und BMP280).

**Anschluss:** alles über Grove (I²C, G2 SDA, G1 SCL).

**Software:** ESPHome, [`esphome/kellerluftbox.yaml`](esphome/kellerluftbox.yaml).

**In Home Assistant:** die Sensoren „CO₂ lüften“ und „CO₂ Alarm“ in den Blueprint „Alarm aufs
Handy“ eintragen. Alle paar Monate an der frischen Luft „CO₂ an Frischluft kalibrieren“ drücken.
Eine RAPT Pill (in der RAPT-App auf Bluetooth gestellt) taucht danach unter „Entdeckt“ auf
(Integration „RAPT Bluetooth“); ihre Dichte dann im Ansatz als Spindel eintragen, Einheit SG.
Den Proxy nicht in die Tankbox setzen: Die regelt das Ventil und soll nichts anderes tun.

## Heizbox

**Zweck:** regelt eine Heizmanschette auf die Solltemperatur aus dem Temperaturplan des Ansatzes.
Geregelt wird auf dem Shelly; fällt Home Assistant aus, gilt der letzte Sollwert. Über 26 °C oder
ohne Fühler ist die Heizung aus; bleibt das Skript stehen, schaltet sie nach zwei Minuten ab.

**Hardware:** Shelly 1PM Gen3 oder Gen4, Shelly Plus Add-on, DS18B20 in einer Tauchhülse im Wein.
Die Heizmanschette hängt an 230 V: **Anschluss durch eine Elektrofachkraft.**

**Software:** Shelly-Skript, [`heizbox/thermostat.js`](heizbox/thermostat.js).

**Einrichten:** in der Shelly-Weboberfläche den Fühler unter Add-on als Temperatur 100 anlegen,
unter Scripts das Skript einfügen, „Run on startup“ einschalten, starten. Den Passwortschutz des
Shelly ausgeschaltet lassen: Die Integration schreibt den Sollwert ohne Anmeldung.

**In Home Assistant:** die IP-Adresse des Shelly im Ansatz als „Heizung“ eintragen.

---

## ESPHome-Boxen einrichten

Alle ESPHome-Boxen teilen sich eine `secrets.yaml` im Ordner [`esphome/`](esphome):

```bash
cd boxen/esphome
cp secrets.yaml.example secrets.yaml     # WLAN, Einrichtungs-Passwort, API-Schlüssel eintragen
esphome run tankbox.yaml                 # erstes Mal per USB, danach über WLAN
```

Im ESPHome-Dashboard von Home Assistant: die YAML-Datei und den Ordner `pakete/` in den
ESPHome-Ordner kopieren und dort die vorhandene `secrets.yaml` um `ap_password` und
`api_encryption_key` ergänzen.

**Welches Board:** Tank-, Waage- und Flaschenbox holen Display, Licht und Pins aus einem
Board-Paket, oben in der YAML unter `packages: board:`.

| Gerät | Paket |
|---|---|
| AtomS3R ab Mai 2026, Display ST7735 (Standard) | `pakete/board-atoms3r.yaml` |
| frühe AtomS3R, Display GC9107 | `pakete/board-atoms3r-gc9107.yaml` |
| AtomS3 (Vorgänger) | `pakete/board-atoms3.yaml` |

Welches Display eine AtomS3R hat, steht im Startlog der Gärbox-Firmware; sonst probieren: Bleibt
das Bild schwarz oder verrauscht, das andere Paket nehmen. Die Kellerluftbox braucht kein Paket.

Die Displays sind am Gerät noch nicht geprüft. Ist das Bild verschoben oder gedreht, im
Board-Paket Versatz und Drehung anpassen; sind die Farben vertauscht, `invert_colors` umschalten
(bei der ST7735 vertauschte Rot/Blau: `use_bgr: true`).

## Im Keller: Feuchte, Spritzwasser, Gehäuse

- **Boxen am Tank und in Bodennähe** (Tank-, Waage-, Flaschenbox): in eine IP65-Abzweigdose aus
  Polycarbonat mit durchsichtigem Deckel, Kabel durch Kabelverschraubungen, dazu ein
  Druckausgleichselement (Membran). Ohne den Ausgleich pumpt jeder Temperaturwechsel feuchte Luft
  hinein, die drinnen kondensiert.
- **Gärbox:** leicht lassen. Sie zählt die Blasen über ihren Bewegungssensor; ein schweres oder
  steifes Gehäuse dämpft genau dieses Signal. Kein Metall: Es schirmt das WLAN ab. Gegen Spritzer
  reicht eine dünne Hülle.
- **Kellerluftbox:** Die Sensoren brauchen Luft, also nicht dicht einbauen; tief, aber außerhalb
  des Spritzbereichs der Bodenreinigung montieren.
- **Edelstahl gehört an den Wein, nicht um die Elektronik:** Fühler in Edelstahl-Tauchhülsen.
- **Netzteile** außerhalb des Nassbereichs, Steckdosen hinter einem FI-Schutzschalter.
