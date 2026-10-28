# Gärbox – TIPSYlab firmware (M5 AtomS3R / AtomS3)

Firmware for the **Gärbox** of [TIPSYLAB](../../README.md) (overview of all boxes:
[boxen/README.md](../README.md)): an [M5Stack AtomS3R](https://docs.m5stack.com/en/core/AtomS3R) (or the older AtomS3) that
sits on a fermenter airlock and counts "blops" with its built-in gyroscope, reads up to two
DS18B20 probes, optionally weighs the vessel with an HX711 load-cell amplifier, and publishes
everything over MQTT. Home Assistant picks the device up automatically (MQTT discovery); the
TIPSYLAB integration reads the raw messages and sends the time until bottling (DUB) back to the
display.

Firmware **2.3.0** – see [Changelog](#changelog).

## Hardware

| Part | Notes |
|---|---|
| M5 AtomS3R or AtomS3 | ESP32-S3, IMU (AtomS3R: BMI270, AtomS3: MPU6886), 128×128 display, one button |
| 1–2× DS18B20 | OneWire on **GPIO 2** (Grove port), 4.7 kΩ pull-up |
| optional: HX711 + load cell | DOUT on **GPIO 5**, SCK on **GPIO 6** (header pins), VCC 3.3 V; see [Scale](#scale-optional) |

The AtomS3 is end-of-life at M5Stack; buy the AtomS3R. Its display changed in May 2026 (GC9107 →
ST7735); M5GFX ≥ 0.2.32 detects both. Not yet run on an AtomS3R: the impulse detector sets its
trigger from the measured noise floor, so the BMI270 should work; check the noise floor once in
the status view.

## Quick start

```bash
cp secrets.ini.example secrets.ini      # WiFi, MQTT and the OTA password (git-ignored)
pio run -t upload                        # firmware, via USB
pio run -t uploadfs                      # web UI (data/), via USB
pio device monitor                       # optional: watch the boot log
```

With `secrets.ini` filled in the device boots straight onto your network. Without it, it opens
a setup access point **`TIPSYlab tipsy-xxxxxx`** with its own password, shown on the screen: each
box draws one the first time (`xxxxx-xxxxx`) and keeps it; a factory reset draws a new one.
Connect, and the setup page opens at `http://192.168.4.1`. For one fixed password on all your
boxes, set `TIPSY_AP_PASS` (8+ characters) in `secrets.ini`.

Each device gets a stable ID from its MAC address (`tipsy-a1b2c3`), shown on the screen and in
the dashboard. It is the default hostname, MQTT client ID and the key in every topic, so any
number of AtomS3s can share one broker.

### Over-the-air updates

After the first USB flash, every later update goes over WiFi:

```bash
pio run -e m5stack-atoms3-ota -t upload   --upload-port tipsy-a1b2c3.local   # firmware
pio run -e m5stack-atoms3-ota -t uploadfs --upload-port tipsy-a1b2c3.local   # web UI
```

`espota` needs the device to open a connection *back* to your PC. From a NAT'd environment
(ChromeOS Linux container, WSL, some VMs) that never arrives - use the HTTP push route instead,
which works from anywhere that can reach the device:

```bash
pio run -e m5stack-atoms3-http -t upload   --upload-port <box-ip>   # firmware
pio run -e m5stack-atoms3-http -t uploadfs --upload-port <box-ip>   # web UI
# or by hand:
curl -u admin:<ota password> -F "image=@.pio/build/m5stack-atoms3/firmware.bin" http://<box-ip>/update
```

The OTA password comes from `secrets.ini` (`TIPSY_OTA_PASS` / `ota_password`) and protects both
routes (HTTP basic auth, user `admin`). Settings live in NVS, so neither a firmware nor a
filesystem upload touches them.

## Web UI

`http://<hostname>.local/`

- **Dashboard** – live counts, temperatures, connection state, last-hour charts, and the three
  detection sliders. Shows the *noise floor* and *last bubble peak* so you can place the trigger
  between them.
- **Settings** (`/config`) – WiFi, MQTT, hostname, legacy-topic switch, restart, and the
  **display logo**: upload a PNG or JPEG (max 120 KB, scaled to fit 128×128 px). It flashes for
  `logo_flash_ms` (300 ms) with each blop, at most every `logo_gap_ms` (1.2 s) so the numbers stay
  readable at peak fermentation. The Tipsy logo is ready in `assets/logo-atoms3-128.png`. The file
  is stored as `/logo.png` or `/logo.jpg` on SPIFFS – the same names 1.x used, so a logo uploaded
  there survives a firmware-only update (not `uploadfs`, which rewrites the whole filesystem).
  Without a logo a sage dot flashes instead.
- **Screen** (2.1): three lines on Tipsy dark olive, digits in JetBrains Mono Bold:

  ```
  12        BPM     blops in the last 60 s, counted on the device
  1d 19h    DUB     time until bottling, from Home Assistant (DRY for still wine)
  13,1°             wine temperature (probe 1, else probe 2)
  ```

  DUB is green above 3 days, amber until the bottling window opens, coral while it is open and
  blinking coral once it has passed; `--` without a forecast or when Home Assistant has not
  sent one for an hour. A small coral square in the top corner means WiFi or MQTT is down.
  A short button press shows the diagnostics view (hostname, IP, RSSI, noise floor, effective
  trigger, last peak, send countdown) for 20 s; while the setup AP is up it also shows its password. Hold 5 s = factory reset (clears NVS, restarts
  into the setup AP). The baseline is relearned via `/api/calibrate` or the dashboard button.

## Scale (optional)

With an HX711 board and a load cell the Gärbox also weighs the vessel. Weight loss is escaped CO₂,
so the TIPSYLAB integration turns it into fermented sugar – without the saturation limit of the
bubble counter. Without an HX711 nothing changes (the device notices it within 3 s).

- **Demijohn:** single-point load cell under a plate.
- **Tank with three legs:** one compression load cell (or weigh module, ~500 kg) under one leg, the
  other two legs on rigid spacers of the same height (steel or POM, no wood or rubber). Three legs
  share the load by geometry alone, so one leg always carries the same fraction.
- Wiring: HX711 VCC → 3V3, GND → GND, DT → G5, SCK → G6; load cell E+/E−/A+/A− as labelled on the
  board. Other pins: `-DTIPSY_HX711_DOUT=7 -DTIPSY_HX711_SCK=8` in `secrets.ini` build flags.

**Calibrate once** on the settings page (`/config`, section *Scale*) or over MQTT:

1. *Tare* (`tipsy/<id>/set/scale_tare`) – the empty vessel, or the full one as it is.
2. Put a known weight on – on a tank in the middle of the lid – enter it and press *Calibrate*
   (`tipsy/<id>/set/scale_calibrate` with the weight in kg). Take the weight off again.
3. Optional *Set content* (`tipsy/<id>/set/scale_set` with the content in kg): the reading then shows
   the wine in kg.

On a tank, step 2 with the weight on the lid makes one leg read the whole vessel. The integration
calibrates again from your refractometer measurements anyway, so small errors do not matter.
Tare and factor are stored in NVS. The state message carries `weight_raw` (mean of the interval's
conversions) and, once calibrated, `weight_kg`; Home Assistant gets a **Weight** sensor and a
**Scale tare** button.

## MQTT

All topics use the device ID. `<id>` = `tipsy-a1b2c3`.

| Topic | Direction | Payload |
|---|---|---|
| `sensors/bubble/<id>` | publish, every 60 s | `{"sensor_id","bubbles","cumulative":false,"interval":60,"rate","total","total_all","rate_60s","boot_id","seq","suppressed","saturated","handling","weight_raw","weight_kg","temperature","rssi","uptime","noise","peak","trigger","sample_rate","free_heap","fw","timestamp"}` (weight only with a scale) |
| `sensors/temperature/<id>-1`, `…-2` | publish, every 60 s | `{"temperature": 21.31, "sensor_id": "<id>-1"}` (only while a probe is connected) |
| `tipsy/<id>/settings` | publish, retained | `{"gyro_threshold","min_activity_threshold","debounce_time","legacy_topics","logo_flash_ms","logo_gap_ms"}` |
| `tipsy/<id>/display` | subscribe, retained | `{"dub_h": 43.2, "state": "soon", "mode": "petnat", "status": "approaching", "measure": false}` from the TIPSYLAB integration |
| `tipsy/<id>/availability` | publish, retained, LWT | `online` / `offline` |
| `tipsy/<id>/set/<key>` | subscribe | single value, e.g. `0.6` |
| `tipsy/<id>/set` | subscribe | JSON with any of the setting keys |
| `homeassistant/{sensor,binary_sensor,number,button}/<id>/*/config` | publish, retained | HA discovery |

`bubbles` is the count in the last interval (not cumulative), `total` the count since boot and
`total_all` the count across restarts (kept in NVS, saved every 10 min and before planned
restarts). `boot_id` is random per boot and `seq` counts the messages of that boot: together they
let a receiver fill gaps from `total` within one boot, drop duplicates, recognise a restart, and
recover from `total_all` what was counted but never sent before a power cut.
`suppressed` counts separate impulses that arrived inside the blop spacing during the interval;
`saturated` is true when the airlock runs at the counting limit (rate ≥ 80 % of
60000 / `debounce_time` per minute, or many suppressed impulses) – the true rate is then higher
than counted. `handling` is true while the device is being moved and counting is paused.

**Legacy topics** (1.x; off by default since 2.1 – a device updated from 2.0 keeps its stored setting; switchable in Settings): `homeassistant/sensor/fermentation_bubbles`
`{"blops": N}`, `…/temperature_1|2` `{"temperature": x}`, and the device still listens on
`…/fermentation_sensitivity`, `…/fermentation_min_threshold`, `…/fermentation_debounce_time`.
Note that with several devices these shared topics mix their data – prefer the per-device ones.

### Home Assistant

Nothing to configure: with the MQTT integration set up, a device *"tipsy-a1b2c3"* appears with
sensors **Bubbles**, **Bubble rate**, **Bubbles total**, **Temperature 1/2**, diagnostics
**WiFi signal**, **Gyro noise floor**, **Last bubble peak**, **Counter saturated**, **Handling**, and
`number` sliders **Trigger threshold**, **Release threshold**, **Min. blop spacing**, **Logo per blop**
and **Logo spacing** that write straight to the device.

## Detection

The MPU6886 gyro has a zero-rate offset of up to several °/s, so raw values are useless for a
fixed threshold. The detector therefore:

1. learns the resting baseline from the first *still* window after boot (the last ~500 ms of
   raw samples span less than 1.5 °/s on every axis; after 10 s without stillness the window
   mean is used) and tracks it only in still windows afterwards, so handling the device cannot
   drag it away and a stale baseline recovers within about a second at rest. Under permanent
   vibration the window mean is followed slowly instead, so temperature drift is still tracked;
2. takes the magnitude of the deviation from that baseline on every sample (≈190 Hz);
3. counts a blop when the magnitude exceeds the **trigger threshold** *and* has risen sharply:
   by at least 60 % of the trigger within the last ~20 ms, and by at least half of the envelope of
   the ~100 ms before that. A blop is an impulse; the slow rocking of the cube after a strong knock
   (which stays above the release level for up to a second or more) therefore neither counts again
   nor hides the next blop, and a ring-down never counts twice;
4. counts again only after the **min. spacing** (default 150 ms, minimum 100, i.e. up to ~6
   blops/s).

While the signal envelope stays above 20× the trigger for half a second the device is being
moved or shaken, not bubbling: counting pauses (`handling` in `/api/status`, serial log) until it
has been calm for a second. The screen and the logo bar show a live **bubbles/min** figure, i.e.
the blops of the last 60 s (rolling); the dashboard additionally shows the running count of the
current minute and the last completed minute, which is what MQTT publishes.

Events (from a blop until the signal has stayed below the **release threshold** for 20 ms, or
1.5 s, or the next blop) only feed the diagnostics: peak, duration, auto-calibration.

**Defaults**: trigger 2.0 °/s, release 0.5 °/s, spacing 150 ms. Measured on an AtomS3 at rest the
magnitude noise floor is ≈0.2 °/s with peaks of 0.5–0.9 °/s; a finger tap on the desk gives a
2–13 °/s spike that rises within 5–10 ms. Devices that stored older defaults get the new ones once
at boot (config version 4).

**Noise guard and vibration floor**: whatever is configured, the effective trigger is never below
6× the measured noise floor (deviation from the window mean while still) nor below 1.3× the
*vibration level*, the median of the 50 ms bin maxima over the last 2 s (or the minimum of the
last 300 ms when a hum has just started). A fridge compressor, a washing machine or a rocking
shelf therefore raises the trigger above its own amplitude instead of being counted at the
spacing limit; isolated blops occupy one bin and do not raise it. All three levels are in
`/api/status` (`noise_floor`, `vibration_level`, `trigger_effective`), the trigger also in the
MQTT state and as *trig* on the screen.

**Auto-calibration** (dashboard button, `POST /api/autocal`, MQTT `tipsy/<id>/set/autocal`, or
the HA button entity): the device first waits until it has been still for a second (gives up
after 5 s), then measures its noise peaks for 10 s while you leave it alone (the two largest
50 ms bins are ignored, so a stray knock does not spoil it), then collects blop peaks for 20 s
while you make blops (tap the vessel, or let a lively airlock do it); only clear impulses
count during that phase. The trigger is placed at the geometric mean between the noise peaks and the
weakest quarter of the blops (at least 1.2× the noise peaks, at most 0.8× the weak blops), the
release at 30 % of the trigger but above 2.5× the mean noise; both are saved and published. It
fails, with the reason on the screen and dashboard, when fewer than 3 blops were seen or the
blops are not clearly above the noise. The screen shows the countdown and the blop count.

**Tuning**: watch *noise floor* and *last bubble peak* on the dashboard (or the HA diagnostics).
Trigger clearly above the noise peaks and clearly below the bubble peaks. `GET /api/trace` returns
the last ~4 s of the raw magnitude with event markers for a closer look.

## HTTP API

| Method | Path | |
|---|---|---|
| GET | `/api/status` | live values (polled every 2 s by the dashboard) |
| GET | `/api/config` | configuration without secrets |
| GET | `/api/history` | last 60 minutes: `bubbles[]`, `temp1[]`, `temp2[]` (null = no probe) |
| POST | `/api/update-settings` | JSON, any of the setting keys |
| POST | `/save-config` | form-encoded WiFi/MQTT/hostname; blank passwords keep the current ones; restarts |
| POST | `/api/calibrate` | relearn the baseline |
| POST | `/api/autocal` | start the auto-calibration (progress/result in `/api/status` → `autocal`) |
| GET | `/api/trace` | last ~4 s of the raw magnitude (`t` ms, `m` °/s, `e` flags: 1 in event, 2 blop) |
| GET | `/logo` | the stored display logo (404 if none) |
| POST | `/api/logo` | multipart `logo=@file.png` (PNG or JPEG, max 120 KB); shown within a second |
| POST | `/api/logo-delete` | remove the logo |
| POST | `/api/restart` | |
| POST | `/update` | multipart `image=@firmware.bin` or `spiffs.bin`; basic auth `admin:<ota password>` |

## Project layout

```
platformio.ini        build + OTA envs (partition table = board default, 2 OTA slots)
secrets.ini(.example) compile-time defaults and OTA password – never commit secrets.ini
src/main.cpp          firmware
include/tipsy_fonts.h display digits (JetBrains Mono Bold), generated by ../../tools/make_atom_font.py
data/                 web UI, flashed to SPIFFS with `pio run -t uploadfs`
```

## Changelog

### 2.3.0 (2026-10-28)

- **Setup password per box:** instead of one password shared by every Gärbox, each box draws its
  own the first time it opens the setup access point (`xxxxx-xxxxx`, no l/o/0/1, hardware random
  number), keeps it in NVS and shows it on the setup screen and, while the AP is up, in the
  diagnostics view. A factory reset draws a new one; `TIPSY_AP_PASS` in `secrets.ini` still sets
  one fixed password for all boxes.
- Display in the tipsy.pt colours: dark olive ground and sage digits instead of ultramarine and
  paper pink; `assets/logo-atoms3-128.png` follows.

### 2.2.1 (2026-10-16)

- AtomS3R with the ST7735 display (units from May 2026): M5GFX pinned to ≥ 0.2.32, which detects
  both AtomS3R displays and its LP5562 backlight. The AtomS3 is end-of-life at M5Stack.

### 2.2.0 (2026-10-12)

- Optional scale: HX711 on GPIO 5/6, tare, calibration with a known weight and "set content" on the
  settings page or over MQTT (`scale_tare`, `scale_calibrate`, `scale_set`), stored in NVS.
  `weight_raw` and `weight_kg` in the state message, **Weight** sensor and **Scale tare** button in
  Home Assistant, reading in the diagnostics view.
- State message buffer 640 bytes, with a warning in the log if it ever were too short.

### 2.1.0 (2026-10-11)

- New main view for TIPSYLAB: BPM, DUB and temperature on Tipsy ultramarine, digits in
  JetBrains Mono Bold (the tipsy.pt font) as a small bitmap font. DUB arrives retained on
  `tipsy/<id>/display` from the Home Assistant integration and is counted down locally; colour
  by state (green, amber, coral, blinking coral), `--` when missing or older than an hour.
- Each blop flashes the uploaded logo full screen (128×128) for 300 ms, at most every 1.2 s;
  both adjustable (`logo_flash_ms`, `logo_gap_ms`). The coloured circle and the logo-as-main-view
  are gone. Without a logo a paper-pink dot flashes.
- State payload: `total_all` (count across restarts in NVS, saved every 10 min), `boot_id`, `seq`,
  `suppressed`, `saturated`, `handling`. The integration uses them to count correctly across
  restarts, lost messages and power cuts during a WiFi outage.
- Legacy topics are off by default for new devices (they mix the data of several devices).
- HA discovery: binary sensors **Counter saturated** and **Handling**, numbers for the logo timing.

### 2.0.7 (2026-09-20)

- Legacy topics now include the format the deployed 1.x units really use:
  `<mqtt client id>/data` with `bubbles` (total since boot), `bubbles_last_60s`, `interval_ms`,
  `temperature`, `humidity`, `sensitivity`, `debounce`. Set the client ID to the old name (e.g.
  `FermentationMonitor`) when replacing a 1.x unit and the existing Home Assistant sensors keep
  working; the discovered entities are the better long-term option.

### 2.0.6 (2026-09-20)

- **Baseline from still windows**: the gyro bias is learned from the first still ~500 ms after
  boot and tracked only while still, with a slow fallback under permanent vibration. Fixes the
  offset that handling left behind (and the resulting lost sensitivity), the deadlock when blops
  kept the old tracker from ever training, and the noise floor ratcheting up with its own release
  level.
- **Vibration floor**: compressor hum, washing machines or a rocking shelf raise the effective
  trigger instead of being counted at the spacing limit (simulated: 20 Hz hum at 3 °/s went from
  ~130 counts per 20 s to 2 at onset).
- Auto-calibration waits for stillness, ignores two stray knocks in the quiet phase, and only
  collects clear impulses. `/api/status` reports `still` and `vibration_level`.

### 2.0.5 (2026-09-17)

- Web server task pinned to core 0: dashboard/API requests no longer pre-empt the gyro loop
  (30–160 ms gaps, dropped samples). `loop_max_ms` per stage in `/api/status` for diagnostics.
- Live **bubbles/min** (rolling 60 s) on the screen and logo bar, `bubbles_per_min` in
  `/api/status`, `rate_60s` in the MQTT state.
- Handling guard: sustained violent motion pauses counting instead of adding phantom blops.
- Min. spacing limited to ≥ 100 ms; config migration keeps calibrated trigger/release from
  2.0.x and no longer imports 1.x detector values; baseline relearn also resets the detector
  history; the bias never trains on the rocking right after a knock.

### 2.0.4 (2026-09-17)

- **Fix: at most ~1 blop per second after strong knocks.** Recorded traces show that after a
  strong knock the cube keeps rocking at 5–20 °/s for up to 1.5 s, so the level/hysteresis
  detector never saw the signal settle and merged everything into one event (1.5 s cap). Blops
  are now detected as impulses (sharp rise above trigger, standing out of the recent envelope)
  with a minimum spacing of 150 ms; the release level only serves the diagnostics.
- **Fix: phantom blops every ~1.6 s after handling.** The baseline tracker was dragged away by
  the large values between events and could not recover while events were open. It now learns
  only from steady samples outside events.
- `GET /api/trace` raw-signal dump for diagnostics; serial output can no longer stall the loop.
- The DS18B20 rescan no longer blocks the loop for ~150 ms every minute (plain 1-Wire search,
  `DallasTemperature::begin()` only when the probe count changed); MQTT connect timeouts reduced
  so an unreachable broker stalls the loop at most ~4 s per attempt instead of ~8 s.

### 2.0.3 (2026-09-17)

- **Auto-calibration**: 10 s quiet + 20 s blops → trigger/release derived from the measured noise
  and blop peaks. Dashboard button, `/api/autocal`, MQTT `set/autocal`, HA button entity, on-screen
  countdown and result.

### 2.0.2 (2026-09-17)

- **Fix: blops in quick succession were missed.** The 2.0.1 noise guard learned the floor from
  the ring-down of a blop and raised the effective trigger for 1–2 s; an over-long event also
  triggered a 1.5 s blind baseline relearn. The floor is now learned from quiet stretches only,
  over-long events are just closed, refractory default 100 ms, release hold 20 ms.
- **Calmer screen**: main view shows only the count, temperatures (if probes), WiFi/MQTT dots and
  the IP; the dense diagnostics moved to the button (20 s), which no longer relearns the baseline.

### 2.0.1 (2026-09-17)

- **Fix: counted continuously.** The 2.0.0 defaults (trigger 0.5, release 0.2 °/s) sit inside the
  MPU6886 noise (floor ≈0.2, peaks 0.5–0.9 °/s), so every noise peak was a "blop" and the release
  level was never held long enough to end an event. Defaults are now 2.0/0.5 °/s (the values the
  TIPSY CLAUDE firmware ran with), stored 2.0.0 values are migrated, and a noise guard keeps the
  effective levels above 6×/3× the measured floor even if lower values are configured.
- **Display logo** restored (1.x had one): upload on the settings page, stored as `/logo.png` or
  `/logo.jpg`, shown with a small status bar; short button press toggles to the status view.
- `/api/status` and the MQTT state report the effective trigger; the screen shows *trig* instead
  of the sample rate.

### 2.0.0 (2026-09)

- **Detection rewritten**: baseline/bias tracking, magnitude + hysteresis event detection, short
  refractory period instead of a 1 s dead time. (1.x averaged *signed* gyro axes over 10 samples,
  which cancels an oscillating vibration, and evaluated `getGyroData() == 0`, i.e. ran on stale
  data.)
- **Nothing blocks any more**: WiFi/MQTT reconnect with back-off, non-blocking DS18B20
  conversions (1.x blocked 750 ms per read, also inside web requests), display via sprite, no
  `delay()` in the bubble animation.
- **OTA updates** (firmware and web files) with mDNS; partition table switched from
  `huge_app` (single slot) to the board default with two OTA slots.
- **Per-device identity** from the MAC: unique hostname, client ID and topics, so several units
  no longer kick each other off the broker or write to the same topic.
- **Home Assistant MQTT discovery** incl. availability (LWT) and `number` entities for the
  thresholds; add-on-compatible `sensors/bubble/<id>` payload with ISO timestamps (NTP).
- Config moved from SPIFFS `config.json` to **NVS** (survives `uploadfs`; 1.x files are migrated).
- Compile-time defaults via git-ignored `secrets.ini`; no credentials in source.
- Web UI fixed: the 1.x setup form never submitted (no `method`/`action`, handler bound to the
  wrong path), the charts referenced a non-existent canvas and never loaded Chart.js; settings
  save and restart were stubs. Charts are now dependency-free canvas drawings.
- Captive portal (DNS) in setup mode, AP+STA fallback when the saved WiFi is unreachable,
  button: relearn baseline / factory reset.
