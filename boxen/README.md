# The boxes

The boxes measure and regulate on site. The calculating happens in Home Assistant: the TIPSYLAB
integration brings all sources of a batch together (measurements, hydrometer, bubbles, weight,
temperature), estimates the residual sugar with its uncertainty and forecasts the bottling
window. So this sensor fusion does not live in a box but in the integration
([`custom_components/tipsylab`](../custom_components/tipsylab)).

Every box keeps working without WiFi: the Gärbox keeps counting, the Tankbox holds the pressure,
the Heizbox regulates to the last set point.

## Overview

| Box | For | Measures / switches | Software | File |
|---|---|---|---|---|
| [Gärbox](#gärbox) | every vessel with an airlock | bubbles, wine temperature, optional weight; shows BPM · DUB · ° | own firmware (C++, PlatformIO) | [`gaerbox/`](gaerbox) |
| [Waagebox](#waagebox) | weight, when no Gärbox sits on the vessel | weight | ESPHome | [`esphome/waagebox.yaml`](esphome/waagebox.yaml) |
| [Scale package](#scale-package) | a scale on an ESP32 that already runs ESPHome | weight | ESPHome package | [`esphome/pakete/waage.yaml`](esphome/pakete/waage.yaml) |
| [Tankbox](#tankbox) | Charmat pressure tank | tank pressure, wine temperature; switches the release valve | ESPHome | [`esphome/tankbox.yaml`](esphome/tankbox.yaml) |
| [Flaschenbox](#flaschenbox) | the measurement bottle after bottling | pressure and temperature of the bottle | ESPHome | [`esphome/flaschenbox.yaml`](esphome/flaschenbox.yaml) |
| [Kellerluftbox](#kellerluftbox) | one room | CO₂ in the cellar air, temperature, humidity, air pressure | ESPHome | [`esphome/kellerluftbox.yaml`](esphome/kellerluftbox.yaml) |
| [Heizbox](#heizbox) | one heating jacket | wine temperature; switches the heater | Shelly script | [`heizbox/thermostat.js`](heizbox/thermostat.js) |

Not ours, but supported: any hydrometer that provides a gravity sensor in Home Assistant (e.g. an
iSpindel via the Nautilis iRelay). It is entered in the batch as the "hydrometer".

## Which boxes for which batch

| Batch | needed | useful |
|---|---|---|
| Pét-Nat or natural wine in a **demijohn** | Gärbox | scale under the demijohn (on the Gärbox); hydrometer |
| Pét-Nat or natural wine in a **stainless steel tank** with an airlock | Gärbox | one load cell under one leg (on the Gärbox or as a Waagebox); Heizbox if the tank has a heating jacket; hydrometer |
| **Pét-Nat in the bottle** | – | Flaschenbox on a measurement bottle (otherwise an aphrometer, entered by hand) |
| **Charmat** in a pressure tank | Tankbox | Heizbox |
| the **cellar** | – | Kellerluftbox, one per room |

Weight, bubbles and hydrometer do not replace each other, they complement each other: the
integration weights every source by its uncertainty. Your measurements with a refractometer or
density meter remain the most important; the integration calibrates all other sources against
them.

---

## Gärbox

**Purpose:** sits on the airlock of every vessel. Counts the bubbles, measures the temperature in
the wine and shows bubbles per minute (BPM), the time until bottling (DUB) and the temperature on
its display. With a load cell it also weighs the vessel.

**Hardware**
- M5Stack AtomS3R (successor of the AtomS3, which M5Stack is phasing out; an existing AtomS3 works
  too, the AtomS3 Lite does not: it lacks the display and the motion sensor)
- DS18B20, waterproof, in a thermowell in the wine; 4.7 kΩ between data and 3.3 V
- optional: HX711 board and load cell: under a demijohn a single-point cell under a plate; under a
  tank a compression load cell or a weigh module for about 500 kg under **one** leg, the other two
  legs on rigid spacers of the same height (steel or POM, no wood, no rubber)
- USB-C power supply

**Wiring:** DS18B20 on G2 (Grove); HX711 DT on G5, SCK on G6, VCC on 3V3.

**Software:** own firmware, [`gaerbox/`](gaerbox), built and flashed with PlatformIO. That folder
also explains how to calibrate the scale and which MQTT format the box speaks.

**Setup:** flash the firmware, enter WiFi and MQTT in the box's setup portal, upload the logo
`assets/logo-atoms3-128.png` under Settings. With a scale: calibrate once (tare, put on a test
weight – on a tank in the middle of the lid –, calibrate).

**In Home Assistant:** enter the box's device ID (shown on the display, e.g. `tipsy-a1b2c3`) in
the batch as the "bubble counter". Temperature and weight then come along automatically; a
separate entry is only needed if they should come from another sensor.

## Waagebox

**Purpose:** weighs a vessel that has no Gärbox, or when the cable from the tank leg up to the
airlock is in the way. For the fermentation the same applies as with the Gärbox: weight loss is
escaped CO₂.

**Hardware:** M5Stack AtomS3R (or AtomS3), HX711 board, load cell as for the Gärbox, USB-C power
supply.

**Wiring:** HX711 DT on G5, SCK on G6, VCC on 3V3. Optionally a DS18B20 on G2 at the load cell, to
see temperature drift (commented out in the YAML).

**Software:** ESPHome, [`esphome/waagebox.yaml`](esphome/waagebox.yaml); the scale itself lives
in the [scale package](#scale-package).

**Setup:** see [Setting up the ESPHome boxes](#setting-up-the-esphome-boxes). Calibrate in Home
Assistant with the buttons "Waage Tara" (tare), "Waage eichen" (calibrate) and "Waage Inhalt
setzen" (set content).

**In Home Assistant:** enter the sensor "Gewicht" (weight) in the batch as the "scale".

## Scale package

**Purpose:** the same scale for an ESP32 that already runs ESPHome, such as the Kellerluftbox or a
device of your own. Add this to its YAML (adjust the pins):

```yaml
packages:
  waage: !include
    file: pakete/waage.yaml
    vars:
      dout_pin: GPIO5
      sck_pin: GPIO6
```

The package brings the sensor "Gewicht" (weight), the calibration buttons and the test weight.

## Tankbox

**Purpose:** holds a Charmat pressure tank at the pressure that gives the target pressure in the
bottle when it is opened at 20 °C. Home Assistant only sends the CO₂ target; the box calculates
the set point for the current tank temperature itself and keeps regulating without WiFi. When the
tank cools down, the set point follows slowly, so that no CO₂ is released that is just dissolving
in the wine.

**Hardware**
- M5Stack AtomS3R (or AtomS3), ADS1115 module (at 3.3 V)
- the existing pressure transmitter, 0.5–4.5 V, via a 10 kΩ/20 kΩ voltage divider to A0
- DS18B20 in a thermowell in the wine
- 12 V solenoid valve, **normally closed** and **direct-acting**, stainless steel, small orifice;
  logic-level MOSFET with flyback diode; 12 V power supply
- a **mechanical safety valve** within the rating of the tank: mandatory, the control never
  replaces it

**Wiring:** ADS1115 on Grove (G2 SDA, G1 SCL); DS18B20 on G6; MOSFET gate via 220 Ω on G5. Sensor
and valve sit at the top in the headspace, never in the wine.

**Software:** ESPHome, [`esphome/tankbox.yaml`](esphome/tankbox.yaml).

**In Home Assistant:** create a Charmat batch; enter the box's "Tankdruck" (tank pressure) and
"Weintemperatur" (wine temperature) as sources and its number "CO₂-Ziel" (CO₂ target) as the
controller, and give the safety valve in the target.

## Flaschenbox

**Purpose:** measures the pressure in a measurement bottle while the Pét-Nat ferments in the
bottle: your own e-aphrometer. The integration converts the pressure to 20 °C, compares it with
the pressure at complete fermentation and warns when it rises higher ("chill to 0–2 °C"). Once the
bottle has fermented to dryness, closing the batch uses it to calibrate the pressure model for the
next batches.

**Hardware**
- M5Stack AtomS3R (or AtomS3), ADS1115 module (at 3.3 V)
- pressure transmitter 0–10 bar, 0.5–4.5 V, stainless steel, G1/4, via a 10 kΩ/20 kΩ voltage
  divider to A0
- crown-cap adapter with a feed-through (as on aphrometers) for the same crown cap as the other
  bottles
- DS18B20 on the outside of the bottle, with thermal paste

**Wiring:** like the Tankbox without the valve: ADS1115 on Grove (G2 SDA, G1 SCL), DS18B20 on G6.

**Safety:** transmitter, adapter and crown cap must withstand the limit pressure of the bottle
(750 ml: 6 bar, 330 ml: 4.5 bar). Only put the adapter on and take it off with safety glasses.

**Software:** ESPHome, [`esphome/flaschenbox.yaml`](esphome/flaschenbox.yaml).

**In Home Assistant:** in the Pét-Nat batch, under "Reconfigure", enter the sensors
"Flaschendruck" (bottle pressure) and "Flaschentemperatur" (bottle temperature) as "Measurement
bottle: pressure" and "Measurement bottle: temperature". It also works without a Flaschenbox: read
the aphrometer and enter the value under "Measure → Bottle pressure".

## Kellerluftbox

**Purpose:** measures CO₂ in the cellar air. Fermentation CO₂ is heavier than air and collects at
the floor; from 5,000 ppm (the occupational exposure limit) there is an alarm. Plus temperature,
humidity and air pressure. Mount it low, about 30 cm above the floor. On the side it is a
Bluetooth proxy: it receives Bluetooth hydrometers (RAPT Pill, Tilt) in the cellar and passes them
on to Home Assistant.

**Hardware:** M5Stack AtomS3 Lite (the box needs no display; an AtomS3R or AtomS3 works too), Grove
hub, Sensirion SCD41 (CO₂), M5 ENV IV (SHT40 and BMP280).

**Wiring:** everything via Grove (I²C, G2 SDA, G1 SCL).

**Software:** ESPHome, [`esphome/kellerluftbox.yaml`](esphome/kellerluftbox.yaml).

**In Home Assistant:** enter the sensors "CO₂ lüften" (ventilate) and "CO₂ Alarm" in the blueprint
"TIPSYLAB · Alarm aufs Handy". Every few months, press "CO₂ an Frischluft kalibrieren" (calibrate
in fresh air) out in the open. A RAPT Pill (set to Bluetooth in the RAPT app) then shows up under
"Discovered" (integration "RAPT Bluetooth"); enter its gravity in the batch as the hydrometer,
unit SG. Do not put the proxy into the Tankbox: it drives the valve and should do nothing else.

## Heizbox

**Purpose:** regulates a heating jacket to the set temperature from the batch's temperature plan.
The regulation runs on the Shelly; if Home Assistant fails, the last set point applies. Above
26 °C or without a probe the heater is off; if the script stops, it switches off after two
minutes.

**Hardware:** Shelly 1PM Gen3 or Gen4, Shelly Plus Add-on, DS18B20 in a thermowell in the wine.
The heating jacket runs on 230 V: **wiring by a qualified electrician.**

**Software:** Shelly script, [`heizbox/thermostat.js`](heizbox/thermostat.js).

**Setup:** in the Shelly web interface, add the probe under Add-on as temperature 100, paste the
script under Scripts, switch on "Run on startup" and start it. Leave the Shelly's password
protection off: the integration writes the set point without logging in.

**In Home Assistant:** enter the IP address of the Shelly in the batch as the "heater".

---

## Setting up the ESPHome boxes

All ESPHome boxes share one `secrets.yaml` in the [`esphome/`](esphome) folder:

```bash
cd boxen/esphome
cp secrets.yaml.example secrets.yaml     # enter WiFi, setup password, API key
esphome run tankbox.yaml                 # first time via USB, then over WiFi
```

In the ESPHome dashboard of Home Assistant: copy the YAML file and the `pakete/` folder into the
ESPHome folder and add `ap_password` and `api_encryption_key` to the existing `secrets.yaml`
there.

**Which board:** the Tankbox, Waagebox and Flaschenbox take display, light and pins from a board
package, at the top of the YAML under `packages: board:`.

| Device | Package |
|---|---|
| AtomS3R from May 2026, ST7735 display (default) | `pakete/board-atoms3r.yaml` |
| early AtomS3R, GC9107 display | `pakete/board-atoms3r-gc9107.yaml` |
| AtomS3 (predecessor) | `pakete/board-atoms3.yaml` |

The boot log of the Gärbox firmware tells you which display an AtomS3R has; otherwise just try:
if the screen stays black or noisy, take the other package. The Kellerluftbox needs no package.

The displays have not been checked on a device yet. If the image is shifted or rotated, adjust
offset and rotation in the board package; if the colours are swapped, toggle `invert_colors` (on
the ST7735 with red and blue swapped: `use_bgr: true`).

## In the cellar: humidity, splashes, enclosures

- **Boxes at the tank and near the floor** (Tankbox, Waagebox, Flaschenbox): in an IP65 junction
  box made of polycarbonate with a clear lid, cables through cable glands, plus a pressure
  equalisation element (membrane). Without it, every change in temperature pumps humid air in,
  which condenses inside.
- **Gärbox:** keep it light. It counts the bubbles with its motion sensor; a heavy or stiff
  enclosure dampens exactly that signal. No metal: it shields the WiFi. A thin cover is enough
  against splashes.
- **Kellerluftbox:** the sensors need air, so do not seal it in; mount it low, but out of reach of
  the spray when the floor is cleaned.
- **Stainless steel belongs on the wine, not around the electronics:** probes in stainless steel
  thermowells.
- **Power supplies** outside the wet area, sockets behind a residual-current device (RCD).
