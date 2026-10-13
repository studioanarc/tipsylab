/* ============================================================
   TIPSYLAB — tipsylab.js
   Fermentation, read live: real numbers from feed.json.

   feed.json is written by feed.php, which Home Assistant (TIPSYLAB
   integration, blueprint "DataWein-Feed") calls every 15 minutes.
   Without a feed the panel keeps running on the simulation from the
   original page and says so ("DEMO"), so it never looks broken.

   Contract with the page (unchanged): gauges g-sg, g-bpm, g-temp,
   g-abv, g-sugar, g-co2; lamps; chart #ferment-chart; label #g-batch.
   The sixth gauge shows the time until bottling instead of headspace
   CO₂, which TIPSYLAB does not measure.
   ============================================================ */
(function () {
  "use strict";

  const FEED_URL = "feed.json";
  const FEED_EVERY_MS = 60000;
  const STALE_MS = 2 * 60 * 60 * 1000; // older than two hours: show it as such

  const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const chart = document.getElementById("ferment-chart");
  if (!chart) return;

  /* ---------- Rendering helpers ---------- */
  function setGauge(id, value, min, max, label, unit) {
    const g = document.getElementById(id);
    if (!g) return;
    if (label) g.querySelector(".gauge__label").textContent = label;
    if (unit) g.querySelector(".gauge__unit").textContent = unit;
    g.querySelector(".gauge__value").textContent = value;
    const i = g.querySelector(".gauge__bar i");
    if (i) {
      const num = parseFloat(value);
      const pct = Number.isFinite(num) ? Math.max(0, Math.min(1, (num - min) / (max - min))) : 0;
      i.style.width = (pct * 100).toFixed(1) + "%";
    }
  }

  function setLamp(id, state) {
    const lamp = document.getElementById(id);
    if (!lamp) return;
    lamp.classList.remove("on", "warn", "off");
    lamp.classList.add(state);
  }

  function drawChart(values, caption) {
    const W = 600, H = 190;
    const padL = 44, padR = 30, padT = 12, padB = 24;
    const iw = W - padL - padR, ih = H - padT - padB;
    const n = Math.max(values.length, 2);
    const lo = Math.min(...values) - 0.002, hi = Math.max(...values) + 0.002;

    const x = (i) => padL + (i / (n - 1)) * iw;
    const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * ih;

    let gridLines = "";
    for (let r = 0; r <= 4; r++) {
      const gy = padT + (r / 4) * ih;
      gridLines += `<line x1="${padL}" y1="${gy}" x2="${W - padR}" y2="${gy}"/>`;
    }
    for (let c = 0; c <= 8; c++) {
      const gx = padL + (c / 8) * iw;
      gridLines += `<line x1="${gx}" y1="${padT}" x2="${gx}" y2="${H - padB}"/>`;
    }
    let labels = "";
    for (let r = 0; r <= 4; r++) {
      const v = hi - (r / 4) * (hi - lo);
      labels += `<text x="${padL - 6}" y="${padT + (r / 4) * ih + 3}" text-anchor="end">${v.toFixed(3)}</text>`;
    }
    labels += `<text x="${padL}" y="${H - 8}">${caption}</text>`;
    labels += `<text x="${W - padR}" y="${H - 8}" text-anchor="end">now</text>`;

    const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    const path = pts.length ? `<polyline class="series" points="${pts.join(" ")}"/>` : "";
    let end = "";
    if (values.length) {
      const lv = values[values.length - 1];
      const ex = x(values.length - 1), ey = y(lv);
      end = `<circle class="series-end" cx="${ex}" cy="${ey}" r="3.5"/>` +
            `<text class="series-label" x="${ex - 6}" y="${ey - 8}" text-anchor="end">${lv.toFixed(3)}</text>`;
    }
    chart.innerHTML = `<g class="grid">${gridLines}</g><g class="axis">${labels}</g>${path}${end}`;
  }

  /* ---------- Real data ---------- */
  function setFlag(live, stale, updated) {
    const flag = document.querySelector(".sim-flag");
    if (!flag) return;
    const dot = '<span class="dot"></span> ';
    if (!live) flag.innerHTML = dot + "Demonstration feed — numbers simulated in your browser";
    else if (stale) flag.innerHTML = dot + "Live feed paused — last reading " + new Date(updated).toLocaleString();
    else flag.innerHTML = dot + "Live feed — real numbers from the cellar, every 15 minutes";
  }

  function renderFeed(feed) {
    const b = feed.batches[0];
    const stale = Date.now() - Date.parse(feed.updated) > STALE_MS;
    setFlag(true, stale, feed.updated);
    const label = document.getElementById("g-batch");
    if (label) label.textContent = `${b.name} · DAY ${b.day ?? "–"}`;

    const sg = b.sg ?? null;
    const hist = (b.history || []).map((p) => p[1]).filter((v) => Number.isFinite(v));
    setGauge("g-sg", sg != null ? sg.toFixed(3) : "–", Math.min(...hist, 0.99), Math.max(...hist, 1.1));
    setGauge("g-bpm", b.bpm != null ? String(Math.round(b.bpm)) : "–", 0, 70);
    setGauge("g-temp", b.temp != null ? b.temp.toFixed(1) : "–", 6, 22);
    setGauge("g-abv", b.abv != null ? b.abv.toFixed(1) : "–", 0, 14);
    setGauge("g-sugar", b.sugar != null ? b.sugar.toFixed(0) : "–", 0, 250);
    const days = b.dub_h != null ? b.dub_h / 24 : null;
    setGauge("g-co2", days != null ? days.toFixed(1) : b.status === "bottled" ? "0" : "–", 0, 14, "Bottling in", "days");

    const active = ["fermenting", "approaching", "window"].includes(b.status) || (b.bpm ?? 0) > 4;
    setLamp("lamp-ferment", b.status === "stuck" ? "warn" : active ? "on" : "off");
    setLamp("lamp-temp", b.temp != null && b.temp > 6 && b.temp < 22 ? "on" : "warn");
    setLamp("lamp-o2", "on");

    if (hist.length >= 2) drawChart(hist, `last ${hist.length} readings`);
  }

  /* ---------- Demo fallback (the original simulation) ---------- */
  const OG = 1.048, FG = 1.006, HISTORY = 44;
  let progress = 0.35 + Math.random() * 0.3;
  const history = [];
  const sgAt = (p) => OG - (OG - FG) / (1 + Math.exp(-9 * (p - 0.45)));

  function tick() {
    progress = Math.min(1, progress + 0.004 + Math.random() * 0.004);
    if (progress >= 1) {
      progress = 0.05;
      history.length = 0;
    }
    const sg = sgAt(progress) + (Math.random() - 0.5) * 0.0006;
    const rate = sgAt(Math.max(0, progress - 0.02)) - sg;
    history.push(sg);
    if (history.length > HISTORY) history.shift();
    return {
      sg,
      bpm: Math.max(0, Math.round(rate * 42000 + (Math.random() - 0.5) * 6)),
      temp: 14.2 + Math.sin(Date.now() / 90000) * 0.9 + (Math.random() - 0.5) * 0.2,
      abv: Math.max(0, (OG - sg) * 131.25),
      sugar: Math.max(0, (sg - FG) * 2600),
      co2: Math.min(10, 2.5 + Math.random() * 0.4),
    };
  }

  function renderDemo(v) {
    setFlag(false);
    const label = document.getElementById("g-batch");
    if (label) label.textContent = "DEMO · SIMULATED";
    setGauge("g-sg", v.sg.toFixed(3), FG, OG);
    setGauge("g-bpm", String(v.bpm), 0, 70);
    setGauge("g-temp", v.temp.toFixed(1), 10, 20);
    setGauge("g-abv", v.abv.toFixed(1), 0, 6);
    setGauge("g-sugar", v.sugar.toFixed(0), 0, 120);
    setGauge("g-co2", v.co2.toFixed(1), 0, 10);
    setLamp("lamp-ferment", v.bpm > 4 ? "on" : "warn");
    setLamp("lamp-temp", v.temp > 12 && v.temp < 17 ? "on" : "warn");
    setLamp("lamp-o2", "on");
    drawChart(history, `-${HISTORY} readings`);
  }

  /* ---------- Boot ---------- */
  let live = false;
  let demoTimer = null;

  async function load() {
    try {
      const res = await fetch(FEED_URL, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      const feed = await res.json();
      if (!feed || !Array.isArray(feed.batches) || !feed.batches.length) throw new Error("empty");
      live = true;
      if (demoTimer) {
        clearInterval(demoTimer);
        demoTimer = null;
      }
      renderFeed(feed);
    } catch (err) {
      if (!live) startDemo();
    }
  }

  function startDemo() {
    if (demoTimer || prefersReduced) {
      if (!history.length) {
        for (let i = 0; i < HISTORY * 0.7; i++) tick();
        renderDemo(tick());
      }
      return;
    }
    for (let i = 0; i < HISTORY * 0.7; i++) tick();
    renderDemo(tick());
    demoTimer = setInterval(() => {
      if (!document.hidden) renderDemo(tick());
    }, 2500);
  }

  load();
  setInterval(() => {
    if (!document.hidden) load();
  }, FEED_EVERY_MS);
})();
