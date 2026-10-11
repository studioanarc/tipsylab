// TIPSYLAB · Heizregler für Heizmanschetten (PLAN 3.8 und 3.13)
//
// Shelly 1PM Gen3/Gen4 mit Shelly Plus Add-on und DS18B20 im Wein (Tauchhülse).
// Home Assistant schreibt die Solltemperatur des Temperaturplans in den KVS-Eintrag
// "tipsylab_soll" (Integration TIPSYLAB, Feld "Heizung: Shelly-Adresse"). Geregelt wird hier,
// auf dem Shelly; fällt Home Assistant aus, gilt der letzte Sollwert weiter.
//
// Sicherheit, auch ohne Home Assistant:
//   - über MAX_TEMP (26 °C) oder ohne Fühlerwert: aus
//   - jedes Einschalten mit Rückfall-Timer: bleibt das Skript stehen, geht die Heizung nach
//     DEADMAN_S von selbst aus
//
// Einrichten: Shelly-Weboberfläche -> Scripts -> Create script, diesen Text einfügen, speichern,
// "Run on startup" einschalten, starten. Den Fühler unter Add-on als Temperatur 100 anlegen.

let CFG = {
  sensorId: 100,        // temperature:100 = erster DS18B20 am Add-on
  switchId: 0,          // Relais der Heizmanschette
  kvsKey: "tipsylab_soll",
  hysteresis: 0.3,      // °C um den Sollwert
  maxTemp: 26.0,        // °C, darüber nie heizen
  minSoll: 5.0,         // plausible Sollwerte
  maxSoll: 25.0,
  periodS: 30,          // Regelzyklus
  deadmanS: 120,        // Rückfall-Timer beim Einschalten
  kvsEveryS: 60,        // Sollwert so oft neu lesen
};

let soll = null;
let heating = false;
let lastKvs = 0;
let lastReason = "";

function log(reason) {
  if (reason !== lastReason) {
    print("TIPSYLAB Heizung: " + reason);
    lastReason = reason;
  }
}

function readSoll() {
  Shelly.call("KVS.Get", { key: CFG.kvsKey }, function (res, err) {
    if (err !== 0 || !res) {
      soll = null;            // kein Sollwert von Home Assistant: nicht heizen
      return;
    }
    let v = res.value;
    if (typeof v === "string") v = Number(v);
    if (typeof v === "number" && v >= CFG.minSoll && v <= CFG.maxSoll) soll = v;
    else soll = null;
  });
}

function setHeating(on) {
  if (on) {
    // Bei jedem Zyklus neu, damit der Rückfall-Timer nur abläuft, wenn das Skript steht
    Shelly.call("Switch.Set", { id: CFG.switchId, on: true, toggle_after: CFG.deadmanS });
  } else if (heating || isOn()) {
    Shelly.call("Switch.Set", { id: CFG.switchId, on: false });
  }
  heating = on;
}

function isOn() {
  let sw = Shelly.getComponentStatus("switch", CFG.switchId);
  return sw !== null && sw.output === true;
}

function control() {
  let now = Shelly.getUptimeMs() / 1000;
  if (lastKvs === 0 || now - lastKvs >= CFG.kvsEveryS) {
    lastKvs = now;
    readSoll();
  }
  let st = Shelly.getComponentStatus("temperature", CFG.sensorId);
  let t = st !== null && typeof st.tC === "number" ? st.tC : null;
  if (t === null) {
    log("Fühler fehlt, aus");
    setHeating(false);
    return;
  }
  if (t >= CFG.maxTemp) {
    log("über " + CFG.maxTemp + " °C, aus");
    setHeating(false);
    return;
  }
  if (soll === null) {
    log("kein Sollwert, aus");
    setHeating(false);
    return;
  }
  let on = heating;
  if (t < soll - CFG.hysteresis) on = true;
  else if (t > soll + CFG.hysteresis) on = false;
  log((on ? "heizt" : "aus") + ", Wein " + t + " °C, Soll " + soll + " °C");
  setHeating(on);
}

heating = isOn();
readSoll();
Timer.set(CFG.periodS * 1000, true, control);
Timer.set(3000, false, control);   // erster Durchlauf, sobald der Sollwert gelesen ist
