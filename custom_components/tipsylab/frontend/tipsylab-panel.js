/* TIPSYLAB-Panel für Home Assistant: Heute, Messung, Ziel und, bei Charmat, Tank.
 *
 * Ohne Build-Schritt und ohne Abhängigkeiten. Daten kommen über den WebSocket-Befehl
 * tipsylab/batches (alle 30 s und nach jeder Eingabe), Vorschauen über tipsylab/preview.
 * Eingaben gehen an die Services add_measurement, add_event und update_settings.
 * Gestaltung wie docs/ui-entwurf: Papier-Rosé, Ultramarin, keine runden Ecken. */

const P = await import(new URL(`./physics.js${new URL(import.meta.url).search}`, import.meta.url).href);

const POLL_MS = 30000;
const DAY = 864e5;
const HOUR = 36e5;
const WD = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const MODE_LABEL = { petnat: "Pet Nat", still: "Naturwein", charmat: "Charmat" };
const KINDS = {
  brix: {
    label: "Refraktometer",
    unit: "°Bx",
    placeholder: "7,7",
    help: "Probe entgast, Gerät mit Temperaturausgleich. Der Alkohol wird herausgerechnet.",
  },
  density: {
    label: "Dichte",
    unit: null,
    help: "Hydrometer oder Dichtemeter, auf 20 °C bezogen. Unter 1,000 wird Oechsle negativ.",
  },
  sugar: {
    label: "Labor",
    unit: "g/L",
    placeholder: "14",
    help: "Laborwert Restzucker (Glucose + Fructose). Steht im Befund auch der Alkohol, unten eintragen: Das macht den Alkohol fürs Etikett genau.",
  },
  malic: {
    label: "Äpfelsäure",
    unit: "g/L",
    placeholder: "1,5",
    help: "Enzymatisch oder mit Teststreifen. Fällt sie, läuft die Malo.",
  },
  ph: { label: "pH", unit: "", placeholder: "3,4", help: "Steigt während der Malo meist leicht an." },
  bottle_pressure: {
    label: "Flaschendruck",
    unit: "bar",
    placeholder: "2,4",
    help: "Aphrometer an der Messflasche, dazu ihre Temperatur. Die App rechnet auf 20 °C um und vergleicht mit dem erwarteten Druck.",
  },
};
const DENSITY_UNITS = { oe: { label: "°Oe", placeholder: "−1,8" }, sg: { label: "SG", placeholder: "0,998" } };
const EVENTS = {
  racking: "Abstich",
  volume: "Volumen",
  cooling: "Kühlen",
  heating: "Heizen",
  bottled: "Abgefüllt",
  closed: "Abgeschlossen",
  note: "Notiz",
};
const CATEGORY = {
  still: "unter 1 bar: Stillwein",
  semi_sparkling: "frisante · Perlwein (1–2,5 bar bei 20 °C)",
  gap: "2,5–3 bar: keine EU-Kategorie",
  sparkling: "espumante · Schaumwein (ab 3 bar bei 20 °C)",
  quality_sparkling: "espumante · Schaumwein (ab 3,5 bar bei 20 °C)",
};
const WORDS = {
  1: "einem Tag",
  1.5: "anderthalb Tagen",
  2: "zwei Tagen",
  2.5: "zweieinhalb Tagen",
  3: "drei Tagen",
  3.5: "dreieinhalb Tagen",
  4: "vier Tagen",
  4.5: "viereinhalb Tagen",
  5: "fünf Tagen",
  5.5: "fünfeinhalb Tagen",
  6: "sechs Tagen",
  7: "einer Woche",
};

/* ---------- Hilfen ---------- */
const nf = (x, d = 1) =>
  x == null || !Number.isFinite(Number(x))
    ? "–"
    : Number(x).toLocaleString("de-DE", { minimumFractionDigits: d, maximumFractionDigits: d });
const nfs = (x) => nf(x, Math.abs(x) < 10 ? 1 : 0);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const num = (s) => (s == null ? NaN : parseFloat(String(s).trim().replace(/\s/g, "").replace(",", ".").replace("−", "-")));
const inputNum = (x, d = 1) => (x == null ? "" : String(Math.round(x * 10 ** d) / 10 ** d).replace(".", ","));
const pad = (n) => String(n).padStart(2, "0");
const q15 = (d) => new Date(Math.round(d.getTime() / 9e5) * 9e5);
const fmtDay = (d) => {
  const r = q15(d);
  return `${WD[r.getDay()]} ${pad(r.getDate())}.${pad(r.getMonth() + 1)}.`;
};
const fmtHM = (d) => {
  const r = q15(d);
  return `${pad(r.getHours())}:${pad(r.getMinutes())}`;
};
const roundHour = (d) => {
  const r = new Date(d.getTime() + 30 * 60e3);
  r.setMinutes(0, 0, 0);
  return r;
};
const toDate = (iso) => (iso ? new Date(iso) : null);
const ago = (t, now = Date.now()) => {
  const s = Math.max(0, (now - t) / 1000);
  if (s < 90) return "gerade eben";
  if (s < 5400) return `vor ${Math.round(s / 60)} min`;
  if (s < 172800) return `vor ${Math.round(s / 3600)} h`;
  return `vor ${Math.round(s / 86400)} Tagen`;
};
function inWords(hours) {
  if (hours < 0.75) return "In weniger als einer Stunde.";
  if (hours < 1.5) return "In etwa einer Stunde.";
  if (hours < 30) return `In etwa ${Math.round(hours)} Stunden.`;
  const half = Math.round(hours / 12) / 2;
  return `In etwa ${WORDS[half] || `${nf(half, half % 1 ? 1 : 0)} Tagen`}.`;
}
function windowText(start, end) {
  if (!start || !end) return null;
  const a = q15(start);
  const b = q15(end);
  return a.toDateString() === b.toDateString()
    ? `${WD[a.getDay()]} ${pad(a.getHours())}–${pad(b.getHours())} Uhr`
    : `${WD[a.getDay()]} ${pad(a.getHours())} – ${WD[b.getDay()]} ${pad(b.getHours())} Uhr`;
}
const startOfDay = (t) => {
  const d = new Date(t);
  d.setHours(0, 0, 0, 0);
  return d;
};
const nextDay = (d) => {
  const n = new Date(d);
  n.setDate(n.getDate() + 1);
  return n;
};
const store = {
  get(key) {
    try {
      return localStorage.getItem(`tipsylab.${key}`);
    } catch {
      return null;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(`tipsylab.${key}`, value);
    } catch {
      /* privates Fenster */
    }
  },
};
function navigate(path) {
  history.pushState(null, "", path);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
}
const errText = (err) => err?.message || err?.code || String(err);

function injectFonts(base) {
  if (document.getElementById("tipsylab-fonts")) return;
  const style = document.createElement("style");
  style.id = "tipsylab-fonts";
  style.textContent = `
@font-face{font-family:"TL Rubik Mono One";src:url("${base}/fonts/rubik-mono-one-latin.woff2") format("woff2");font-weight:400;font-display:swap}
@font-face{font-family:"TL Fraunces";src:url("${base}/fonts/fraunces-latin.woff2") format("woff2");font-weight:100 900;font-display:swap}
@font-face{font-family:"TL JetBrains Mono";src:url("${base}/fonts/jetbrains-mono-latin.woff2") format("woff2");font-weight:100 800;font-display:swap}`;
  document.head.appendChild(style);
}

/* ---------- Gestaltung ---------- */
const CSS = `
:host {
  --paper: #f9e3e7; --screen: #fdf1f3; --ink: #2b2c78; --red: #d24e35; --grain-opacity: .07;
  --muted: color-mix(in srgb, var(--ink) 66%, var(--paper));
  --rule: color-mix(in srgb, var(--ink) 38%, transparent);
  --band: color-mix(in srgb, var(--ink) 13%, transparent);
  --redband: color-mix(in srgb, var(--red) 20%, transparent);
  --font-display: "TL Rubik Mono One", "Arial Black", system-ui, sans-serif;
  --font-body: "TL Fraunces", Georgia, "Times New Roman", serif;
  --font-mono: "TL JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
  --grain: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  display: block; min-height: 100vh; background: var(--paper); color: var(--ink);
  font-family: var(--font-body); font-optical-sizing: auto; font-variation-settings: "SOFT" 40, "WONK" 1;
  font-size: 16px; line-height: 1.5; -webkit-font-smoothing: antialiased;
}
:host([dark]) { --paper: #17184a; --screen: #1f2160; --ink: #f7dfe4; --red: #ff876b; --grain-opacity: .04; color-scheme: dark; }
* { box-sizing: border-box; border-radius: 0; }
[hidden] { display: none !important; }
.root { container-type: inline-size; position: relative; max-width: 1500px; margin: 0 auto; padding: 16px 16px 48px; }
.root::before { content: ""; position: fixed; inset: 0; pointer-events: none; background-image: var(--grain); opacity: var(--grain-opacity); }
.root > * { position: relative; }

.top { display: flex; align-items: center; gap: 12px; min-height: 48px; }
.top ha-menu-button { margin-left: -8px; color: var(--ink); }
.logo { width: 42px; height: 40px; flex: none; background: currentColor; -webkit-mask: var(--logo) center / contain no-repeat; mask: var(--logo) center / contain no-repeat; }
.batch { display: grid; min-width: 0; line-height: 1.2; }
.kicker { font-family: var(--font-mono); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.batch b { font-family: var(--font-display); font-weight: 400; font-size: clamp(18px, 5vw, 26px); line-height: 1.1; overflow-wrap: anywhere; }
.live { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: 10px; letter-spacing: .16em; }
.live i { width: 8px; height: 8px; background: var(--red); animation: blink 1.6s steps(1) infinite; }
@keyframes blink { 50% { opacity: .25; } }
.offline { margin: 10px 0 0; padding: 6px 10px; font-family: var(--font-mono); font-size: 12px; color: var(--red); border: 2px solid var(--red); }

.seg { display: flex; border: 2px solid var(--ink); margin-top: 6px; }
.seg button { flex: 1; min-width: 0; padding: 9px 6px; font-family: var(--font-mono); font-size: 12px; line-height: 1.25; color: var(--ink); background: transparent; border: 0; cursor: pointer; }
.seg button + button { border-left: 2px solid var(--ink); }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--screen); font-weight: 700; }
.seg small { display: block; font-size: 10px; font-weight: 400; opacity: .8; }
.seg.grid3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 2px; padding: 0; background: var(--ink); }
.seg.grid3 button { background: var(--screen); border: 0; }
.seg.grid3 button[aria-pressed="true"] { background: var(--ink); }
.seg.tight button { font-size: 11px; padding: 6px 4px; }
.batches { margin-top: 14px; overflow-x: auto; }
.batches button { flex: 1 0 auto; padding: 8px 14px; text-align: left; }
.tabs { margin-top: 14px; position: sticky; top: 0; z-index: 2; background: var(--paper); }
.tabs button { padding: 11px 6px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }

.screens { display: grid; gap: 28px; margin-top: 18px; align-items: start; }
.screen { display: none; width: 100%; max-width: 460px; margin-inline: auto; min-width: 0; background: var(--screen); border: 2px solid var(--ink); box-shadow: 6px 6px 0 var(--ink); padding: 14px 18px 22px; }
.screen.active, .screen.solo { display: block; }
.screen h2 { margin: 0; font-family: var(--font-mono); font-size: 12px; letter-spacing: .16em; text-transform: uppercase; color: var(--muted); }
@container (min-width: 1020px) {
  .tabs { display: none; }
  .screens.cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .screens.cols-2 { grid-template-columns: repeat(2, minmax(0, 460px)); justify-content: center; }
  .screen { display: block; max-width: none; }
}
@container (max-width: 1019px) { .screen h2 { display: none; } }
@container (max-width: 380px) { .screen { padding: 12px 12px 18px; box-shadow: 4px 4px 0 var(--ink); } }

.eyebrow { margin: 20px 0 6px; font-family: var(--font-mono); font-size: 11px; letter-spacing: .16em; text-transform: uppercase; color: var(--muted); }
.screen > .eyebrow:first-of-type { margin-top: 6px; }
.answer { margin: 0; font-family: var(--font-display); font-weight: 400; font-size: clamp(30px, 9cqi, 42px); line-height: 1; letter-spacing: -.01em; overflow-wrap: anywhere; }
.answer-sub { margin: 8px 0 0; font-family: var(--font-mono); font-weight: 700; font-size: 15px; letter-spacing: .06em; font-variant-numeric: tabular-nums; }
.say { margin: 12px 0 0; font-size: 15px; line-height: 1.45; text-wrap: pretty; }
.hint { margin: 8px 0 0; font-family: var(--font-mono); font-size: 11.5px; line-height: 1.5; color: var(--red); }
.fine { margin: 8px 0 0; font-family: var(--font-mono); font-size: 10.5px; line-height: 1.5; color: var(--muted); }
.note { margin: 14px 0 0; font-size: 14px; line-height: 1.45; text-wrap: pretty; }

.windowbar { display: block; width: 100%; height: auto; margin-top: 16px; overflow: visible; }
.windowbar .axis { stroke: var(--ink); stroke-width: 1.5; }
.windowbar .tick { stroke: var(--rule); stroke-width: 1; }
.windowbar .band { fill: var(--band); stroke: var(--ink); stroke-width: 1.5; }
.windowbar .best { fill: var(--ink); }
.windowbar text { fill: var(--muted); font-family: var(--font-mono); font-size: 10px; }
.windowbar .nowlabel { fill: var(--ink); font-weight: 700; }

.control { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; margin-top: 16px; font-family: var(--font-mono); font-size: 12px; }
.control.two { grid-template-columns: 1fr auto; }
.control label { letter-spacing: .08em; text-transform: uppercase; }
.control output { font-weight: 700; min-width: 5ch; text-align: right; font-variant-numeric: tabular-nums; }
input[type="range"] { -webkit-appearance: none; appearance: none; width: 100%; height: 26px; margin: 0; background: transparent; cursor: pointer; }
input[type="range"]::-webkit-slider-runnable-track { height: 3px; background: var(--ink); }
input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; width: 18px; height: 18px; margin-top: -7.5px; background: var(--ink); border: 2px solid var(--screen); border-radius: 0; }
input[type="range"]::-moz-range-track { height: 3px; background: var(--ink); }
input[type="range"]::-moz-range-thumb { width: 16px; height: 16px; background: var(--ink); border: 2px solid var(--screen); border-radius: 0; }

.leaders { margin: 18px 0 0; display: grid; gap: 8px; font-family: var(--font-mono); font-size: 13px; }
.leaders > div { display: flex; align-items: baseline; gap: 6px; }
.leaders dt { flex: 1; display: flex; align-items: baseline; gap: 6px; min-width: 0; }
.leaders dt::after { content: ""; flex: 1; min-width: 10px; border-bottom: 2px dotted var(--rule); transform: translateY(-4px); }
.leaders dd { margin: 0; flex: none; font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
.leaders .warn dd, .leaders .warn dt { color: var(--red); }
.leaders small { font-weight: 400; color: var(--muted); }

.chart { display: block; width: 100%; height: auto; margin-top: 18px; }
.chart .grid { stroke: var(--rule); stroke-width: 1; }
.chart text { fill: var(--muted); font-family: var(--font-mono); font-size: 9px; }
.chart .measured { fill: none; stroke: var(--ink); stroke-width: 2.2; stroke-linejoin: miter; }
.chart .dot { fill: var(--ink); opacity: .55; }
.chart .forecast { fill: none; stroke: var(--ink); stroke-width: 2; stroke-dasharray: 4 4; }
.chart .setline { fill: none; stroke: var(--red); stroke-width: 1.5; stroke-dasharray: 5 3; }
.chart .cone { fill: var(--band); stroke: none; }
.chart .target { fill: var(--redband); stroke: none; }
.chart .targetlabel { fill: var(--red); font-weight: 700; }
.chart .nowline { stroke: var(--ink); stroke-width: 1.2; }
.chart .anchor { fill: var(--ink); stroke: var(--screen); stroke-width: 1.5; }
.chart .bubble { fill: var(--rule); }
.chart .label-ink { fill: var(--ink); font-weight: 700; }
.chart .empty { fill: var(--muted); font-size: 11px; }

.primary { display: block; width: 100%; margin-top: 18px; padding: 14px 18px; font-family: var(--font-display); font-size: 15px; letter-spacing: .04em; color: var(--screen); background: var(--ink); border: 2px solid var(--ink); cursor: pointer; }
.primary:active { transform: translate(2px, 2px); }
.primary:disabled { cursor: default; color: var(--muted); background: transparent; border-color: var(--rule); transform: none; }
.secondary { padding: 8px 12px; font-family: var(--font-mono); font-size: 12px; font-weight: 700; color: var(--ink); background: transparent; border: 2px solid var(--ink); cursor: pointer; }
.link { padding: 0; font-family: var(--font-mono); font-size: 12px; color: var(--muted); background: none; border: 0; border-bottom: 1px dotted var(--rule); cursor: pointer; }
button:focus-visible, input:focus-visible, select:focus-visible { outline: 3px solid var(--red); outline-offset: 3px; }
.status { margin: 14px 0 0; font-family: var(--font-mono); font-size: 10.5px; line-height: 1.5; color: var(--muted); text-align: center; }

.big-input { display: flex; align-items: baseline; gap: 10px; margin-top: 18px; padding-bottom: 6px; border-bottom: 3px solid var(--ink); }
.big-input input { width: 100%; min-width: 0; padding: 0; font-family: var(--font-display); font-size: 42px; line-height: 1.1; color: var(--ink); background: transparent; border: 0; font-variant-numeric: tabular-nums; }
.big-input input::placeholder { color: var(--rule); }
.big-input span { flex: none; font-family: var(--font-mono); font-size: 16px; font-weight: 700; }
.result { margin-top: 18px; padding: 14px 14px 16px; border: 2px dashed var(--rule); }
.result .eyebrow { margin-top: 0; }
.result .leaders { margin-top: 8px; }
.result .fine { margin-top: 4px; }
.toast { margin: 10px 0 0; min-height: 1.5em; font-family: var(--font-mono); font-size: 11.5px; text-align: center; }

.scale { display: flex; justify-content: space-between; gap: 8px; margin-top: 6px; font-family: var(--font-mono); font-size: 10.5px; color: var(--muted); }
.category { margin: 10px 0 0; font-family: var(--font-mono); font-size: 12px; font-weight: 700; }
.category.off { color: var(--red); }
.field { display: grid; grid-template-columns: 1fr auto auto; align-items: baseline; gap: 8px; margin-top: 10px; font-family: var(--font-mono); font-size: 13px; }
.field input { width: 7ch; padding: 2px 0; font: inherit; font-weight: 700; text-align: right; color: var(--ink); background: transparent; border: 0; border-bottom: 2px solid var(--ink); }
.field.wide { grid-template-columns: auto 1fr; }
.field.wide input { width: 100%; min-width: 0; text-align: left; font-weight: 400; }
.field input[aria-invalid="true"] { border-bottom-color: var(--red); color: var(--red); }
.field input::placeholder { color: var(--rule); font-weight: 400; }

.log { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 6px; font-family: var(--font-mono); font-size: 12px; }
.log li { display: flex; gap: 10px; align-items: baseline; padding-bottom: 5px; border-bottom: 1px dotted var(--rule); }
.log time { flex: none; color: var(--muted); font-variant-numeric: tabular-nums; }
.log small { color: var(--muted); }
.event-row { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: end; margin-top: 8px; font-family: var(--font-mono); font-size: 13px; }
.event-row input, .event-row select { width: 100%; min-width: 0; padding: 4px 0; font: inherit; color: var(--ink); background: transparent; border: 0; border-bottom: 2px solid var(--ink); -webkit-appearance: none; appearance: none; border-radius: 0; }
.event-row select { padding-right: 14px; cursor: pointer; background-image: linear-gradient(45deg, transparent 50%, var(--ink) 50%), linear-gradient(135deg, var(--ink) 50%, transparent 50%); background-position: calc(100% - 7px) 55%, calc(100% - 2px) 55%; background-size: 5px 5px; background-repeat: no-repeat; }
.event-row .ev-value { grid-column: 1 / -1; }
.log span { flex: 1; min-width: 0; }
.log .del { flex: none; padding: 0 2px; font: inherit; color: var(--muted); background: none; border: 0; cursor: pointer; }
.log .del.armed { color: var(--red); font-weight: 700; }
.link.armed { color: var(--red); border-bottom-color: var(--red); }
.arch { margin-top: 14px; padding-top: 10px; border-top: 2px solid var(--ink); }
.arch-title { margin: 0; font-family: var(--font-mono); font-size: 13px; }
.arch-title small { color: var(--muted); }
.chart.spark { margin-top: 8px; }

.foot { display: flex; flex-wrap: wrap; gap: 18px; justify-content: center; margin-top: 32px; }
.loading { font-family: var(--font-mono); font-size: 12px; color: var(--muted); }
@media (prefers-reduced-motion: reduce) { .live i { animation: none; } .primary:active { transform: none; } }
`;

/* ---------- Panel ---------- */
class TipsylabPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._batches = [];
    this._sel = store.get("batch");
    this._tab = store.get("tab") || "today";
    this._err = null;
    this._shape = "";
    this._m = { kind: "brix", unit: "oe", value: "", value2: "", temp: "", time: "", note: "", preview: null, seq: 0, toast: "", busy: false };
    this._ev = { kind: "racking", value: "", note: "", toast: "" };
    this._t = null; // Ziel-Formular
    this._c = null; // Charmat-Formular
    this._whatIf = null;
    this._timer = null;
    this._onVisible = () => {
      if (!document.hidden) this._fetch();
    };
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    this.toggleAttribute("dark", Boolean(hass?.themes?.darkMode));
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = hass;
    if (first) this._init();
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = Boolean(value);
    if (this._hass) this._render();
  }

  set panel(value) {
    this._panel = value;
  }

  set route(_value) {}

  connectedCallback() {
    document.addEventListener("visibilitychange", this._onVisible);
    if (this._hass) {
      this._startPolling();
      this._fetch();
    }
  }

  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._onVisible);
    clearInterval(this._timer);
    this._timer = null;
  }

  $(id) {
    return this.shadowRoot.getElementById(id);
  }

  _init() {
    const base = this._panel?.config?.static || "/tipsylab_static";
    injectFonts(base);
    this.style.setProperty("--logo", `url("${base}/tipsy-logo.svg")`);
    const root = this.shadowRoot;
    root.innerHTML = `<style>${CSS}</style><div class="root" id="root"><p class="loading">TIPSYLAB lädt …</p></div>`;
    root.addEventListener("click", (e) => this._onClick(e));
    root.addEventListener("input", (e) => this._onInput(e));
    root.addEventListener("change", (e) => this._onChange(e));
    if (this.isConnected) this._startPolling();
    this._fetch();
  }

  _startPolling() {
    clearInterval(this._timer);
    this._timer = setInterval(() => {
      if (!document.hidden) this._fetch();
    }, POLL_MS);
  }

  async _fetch() {
    if (!this._hass) return;
    if (this._fetching) {
      this._again = true; // nach dem laufenden Abruf noch einmal, damit eine Eingabe sicher drin ist
      return;
    }
    this._fetching = true;
    try {
      const res = await this._hass.callWS({ type: "tipsylab/batches" });
      this._batches = res?.batches || [];
      this._house = res?.house || null;
      this._err = null;
    } catch (err) {
      this._err = errText(err);
    } finally {
      this._fetching = false;
    }
    this._render();
    if (this._again) {
      this._again = false;
      this._fetch();
    }
  }

  _current() {
    if (!this._batches.length) return null;
    let b = this._batches.find((x) => x.entry_id === this._sel);
    if (!b) {
      b = this._batches[0];
      this._sel = b.entry_id;
    }
    return b;
  }

  _tabs(b) {
    return b.mode === "charmat"
      ? [["tank", "Tank"], ["measure", "Messung"]]
      : [["today", "Heute"], ["measure", "Messung"], ["target", "Ziel"]];
  }

  /* Gerüst neu bauen, wenn sich Ansätze, Auswahl oder Breite ändern; sonst nur Werte setzen,
     damit Eingaben beim Nachladen nicht verloren gehen. */
  _render() {
    if (!this.$("root")) return;
    const b = this._current();
    const shape = this._archive
      ? `archive#${(this._house?.archive || []).length}#${this._narrow}`
      : b
        ? `${this._batches.map((x) => `${x.entry_id}:${x.mode}:${x.name}:${x.bottling ? 1 : 0}`).join("|")}#${b.entry_id}#${this._narrow}`
        : `none#${Boolean(this._err)}#${this._narrow}`;
    if (shape !== this._shape) {
      this._shape = shape;
      this._build(b);
    }
    if (this._archive) this._updateArchive();
    else this._update(b);
  }

  _menuButton() {
    return this._narrow ? "<ha-menu-button></ha-menu-button>" : "";
  }

  _build(b) {
    const root = this.$("root");
    if (this._archive) {
      this._buildArchive(root);
      return;
    }
    if (!b) {
      root.innerHTML = `
        <header class="top">${this._menuButton()}<span class="logo" aria-hidden="true"></span>
          <div class="batch"><span class="kicker">TIPSYLAB</span><b>${this._err ? "Keine Verbindung" : "Noch kein Ansatz"}</b></div></header>
        <section class="screen solo" style="margin-top:18px">
          ${
            this._err
              ? `<p class="say">Die Integration antwortet nicht: ${esc(this._err)}</p>
                 <button class="primary" type="button" data-act="retry">Neu laden</button>`
              : `<p class="say">Leg einen Ansatz an: Name, Betriebsart, Start-Brix und Volumen. Spindel, Blasenzähler und Temperaturfühler verbindest du gleich mit.</p>
                 <button class="primary" type="button" data-act="add-batch">Ansatz anlegen</button>`
          }
        </section>`;
      this._wireMenu();
      return;
    }
    if (this._formFor !== b.entry_id) {
      this._formFor = b.entry_id;
      this._t = null;
      this._c = null;
      this._whatIf = null;
      Object.assign(this._m, { preview: null, toast: "" });
    }
    const tabs = this._tabs(b);
    if (!tabs.some(([k]) => k === this._tab)) this._tab = tabs[0][0];
    const batches =
      this._batches.length > 1
        ? `<nav class="seg batches" aria-label="Ansatz">${this._batches
            .map(
              (x) =>
                `<button type="button" data-act="batch" data-id="${esc(x.entry_id)}" aria-pressed="${x.entry_id === b.entry_id}">${esc(x.name)}<small>${MODE_LABEL[x.mode] || esc(x.mode)}</small></button>`,
            )
            .join("")}</nav>`
        : "";
    root.innerHTML = `
      <header class="top">${this._menuButton()}<span class="logo" aria-hidden="true"></span>
        <div class="batch"><span class="kicker" id="h-sub"></span><b>${esc(b.name)}</b></div>
        <span class="live" id="h-live" hidden><i></i>LIVE</span>
      </header>
      ${batches}
      <nav class="seg tabs" aria-label="Ansicht">${tabs
        .map(([k, l]) => `<button type="button" data-act="tab" data-tab="${k}" aria-pressed="${k === this._tab}">${l}</button>`)
        .join("")}</nav>
      <p class="offline" id="h-err" hidden></p>
      <main class="screens cols-${tabs.length}">
        ${tabs
          .map(
            ([k, l]) =>
              `<section class="screen${k === this._tab ? " active" : ""}" data-screen="${k}" aria-label="${l}"><h2>${l}</h2>${this[`_html_${k}`](b)}</section>`,
          )
          .join("")}
      </main>
      <footer class="foot">
        <button class="link" type="button" data-act="add-batch">+ Neuer Ansatz</button>
        <button class="link" type="button" data-act="open-integration">Ansätze verwalten</button>
        <button class="link" type="button" data-act="archive">Archiv${
          this._house?.archive?.length ? ` (${this._house.archive.length})` : ""
        }</button>
      </footer>`;
    this._wireMenu();
  }

  _wireMenu() {
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    }
  }

  /* ---------- Gerüste der Screens ---------- */
  _html_today(b) {
    if (b.bottling) return this._html_bottle(b);
    const still = b.mode === "still";
    return `
      <p class="eyebrow">${still ? "Durchgegoren" : "Abfüllen"}</p>
      <p class="answer" id="d-day">–</p>
      <p class="answer-sub" id="d-sub"></p>
      <p class="fine" id="d-window"></p>
      <p class="say" id="d-say"></p>
      <p class="hint" id="d-warn" hidden></p>
      <p class="fine" id="d-notes" hidden></p>
      <svg class="windowbar" id="d-wbar" viewBox="0 0 320 46" role="img" aria-label="Fenster auf der Zeitachse"></svg>
      <div class="control">
        <label for="d-whatif">Keller</label>
        <input type="range" id="d-whatif" data-in="whatif" min="6" max="26" step="1" value="15">
        <output id="d-whatif-out" for="d-whatif">15 °C</output>
      </div>
      <p class="fine" id="d-whatif-line" hidden></p>
      <p class="hint" id="d-whatif-hint" hidden></p>
      <dl class="leaders">
        <div><dt>Restzucker</dt><dd id="d-sugar">–</dd></div>
        <div><dt>Alkohol am Ende</dt><dd id="d-abv">–</dd></div>
        <div><dt>Gärung</dt><dd id="d-rate">–</dd></div>
        ${
          still
            ? `<div><dt>Trocken unter</dt><dd id="d-dry">–</dd></div>`
            : `<div id="d-pnow-row"><dt>Druck, wenn jetzt</dt><dd id="d-pnow">–</dd></div>
               <div><dt>Ziel beim Öffnen</dt><dd id="d-ptarget">–</dd></div>`
        }
        <div id="d-plan-row" hidden><dt>Solltemperatur</dt><dd id="d-plan">–</dd></div>
      </dl>
      <p class="fine" id="d-abv-hint" hidden></p>
      <svg class="chart" id="d-chart" viewBox="0 0 320 196" role="img" aria-label="Restzucker der letzten Tage mit Prognose"></svg>
      <button class="primary" type="button" data-act="goto-measure">+ Messung</button>
      <p class="status" id="d-status"></p>`;
  }

  _html_bottle(b) {
    const petnat = b.mode === "petnat";
    return `
      <p class="eyebrow" id="f-eyebrow">In der Flasche</p>
      <p class="answer" id="f-answer">–</p>
      <p class="answer-sub" id="f-sub"></p>
      <p class="say" id="f-say"></p>
      <p class="hint" id="f-warn" hidden></p>
      <dl class="leaders">
        <div><dt>Abgefüllt</dt><dd id="f-bottled">–</dd></div>
        ${
          petnat
            ? `<div><dt>Erwartet beim Öffnen</dt><dd id="f-expected">–</dd></div>
               <div id="f-worst-row"><dt>Ungünstig bei 20 °C</dt><dd id="f-worst">–</dd></div>
               <div><dt>Flaschengärung</dt><dd id="f-progress">–</dd></div>`
            : ""
        }
        <div><dt>Alkohol am Ende</dt><dd id="d-abv">–</dd></div>
      </dl>
      <p class="fine" id="d-abv-hint" hidden></p>
      ${petnat ? `<svg class="chart" id="f-chart" viewBox="0 0 320 170" role="img" aria-label="Druck der Messflasche bei 20 °C"></svg>` : ""}
      <p class="fine" id="f-forecast" hidden></p>
      ${petnat ? `<button class="primary" type="button" data-act="goto-bottle">+ Messflasche</button>` : ""}
      <p class="status" id="f-status"></p>
      <p class="status"><button class="link" type="button" data-act="close-batch" id="f-close">Ansatz abschließen</button></p>`;
  }

  _html_measure() {
    const m = this._m;
    return `
      <p class="eyebrow">Was hast du gemessen?</p>
      <div class="seg grid3" role="group" aria-label="Messart">${Object.entries(KINDS)
        .map(([k, v]) => `<button type="button" data-act="mkind" data-kind="${k}" aria-pressed="${k === m.kind}">${v.label}</button>`)
        .join("")}</div>
      <div class="seg tight" id="m-units" role="group" aria-label="Dichte in">${Object.entries(DENSITY_UNITS)
        .map(([k, v]) => `<button type="button" data-act="munit" data-unit="${k}" aria-pressed="${k === m.unit}">Dichte in ${v.label}</button>`)
        .join("")}</div>
      <div class="big-input">
        <input id="m-value" data-in="mval" type="text" inputmode="decimal" autocomplete="off" aria-label="Messwert" value="${esc(m.value)}">
        <span id="m-unit"></span>
      </div>
      <p class="fine" id="m-help"></p>
      <div class="field" id="m-value2-row">
        <label for="m-value2" id="m-value2-label">Dichte derselben Probe (optional)</label>
        <input id="m-value2" data-in="mval2" type="text" inputmode="decimal" autocomplete="off" value="${esc(m.value2)}">
        <span id="m-unit2"></span>
      </div>
      <div class="field" id="m-temp-row">
        <label for="m-temp">Temperatur der Flasche</label>
        <input id="m-temp" data-in="mtemp" type="text" inputmode="decimal" autocomplete="off" value="${esc(m.temp)}">
        <span>°C</span>
      </div>
      <div class="field wide">
        <label for="m-time">Gemessen</label>
        <input id="m-time" data-in="mtime" type="datetime-local" value="${esc(m.time)}" aria-describedby="m-time-help">
      </div>
      <p class="fine" id="m-time-help">Ohne Zeitangabe gilt jetzt.</p>
      <div class="field wide">
        <label for="m-note">Notiz</label>
        <input id="m-note" data-in="mnote" type="text" autocomplete="off" value="${esc(m.note)}" placeholder="optional">
      </div>
      <div class="result" aria-live="polite">
        <p class="eyebrow">Was sich ändert</p>
        <dl class="leaders" id="m-leaders"></dl>
        <p class="fine" id="m-result-msg"></p>
      </div>
      <button class="primary" type="button" data-act="msave" id="m-save">Speichern</button>
      <p class="toast" id="m-toast" aria-live="polite"></p>
      <p class="eyebrow">Ereignis</p>
      <div class="event-row">
        <select id="ev-kind" data-ch="evkind" aria-label="Art des Ereignisses">${Object.entries(EVENTS)
          .map(([k, v]) => `<option value="${k}"${k === this._ev.kind ? " selected" : ""}>${v}</option>`)
          .join("")}</select>
        <input id="ev-note" data-in="evnote" type="text" autocomplete="off" placeholder="Notiz" aria-label="Notiz zum Ereignis" value="${esc(this._ev.note)}">
        <button class="secondary" type="button" data-act="esave">Eintragen</button>
        <input class="ev-value" id="ev-value" data-in="evval" type="text" inputmode="decimal" autocomplete="off" placeholder="Neues Volumen in Litern" aria-label="Neues Volumen in Litern" value="${esc(this._ev.value)}"${this._ev.kind === "volume" ? "" : " hidden"}>
      </div>
      <p class="toast" id="ev-toast" aria-live="polite"></p>
      <p class="eyebrow">Verlauf</p>
      <ol class="log" id="m-log"></ol>`;
  }

  _html_target(b) {
    const petnat = b.mode === "petnat";
    const field = (id, label, unit, key, opts = "") =>
      `<div class="field"${id === "t-malic" ? ' id="t-malic-row"' : ""}><label for="${id}">${label}</label><input id="${id}" data-in="tnum" data-field="${key}" ${opts} type="text" inputmode="decimal" autocomplete="off"><span>${unit}</span></div>`;
    return `
      ${
        petnat
          ? `<p class="eyebrow">Druck beim Öffnen, 10–20 °C</p>
             <p class="answer" id="t-big">–</p>
             <div class="control two">
               <input type="range" id="t-target" data-in="ttarget" min="1.5" max="4.5" step="0.1" aria-label="Druck beim Öffnen bei 20 °C">
               <output id="t-out" for="t-target"></output>
             </div>
             <div class="scale"><span>1,5</span><span>frisante bis 2,5</span><span>espumante ab 3</span><span>4,5</span></div>
             <p class="category" id="t-cat"></p>
             <p class="eyebrow">Flasche</p>
             <div class="seg" role="group" aria-label="Flasche">
               <button type="button" data-act="bottle" data-bottle="330">330 ml<small>Kronkorken bis 4,5 bar</small></button>
               <button type="button" data-act="bottle" data-bottle="750">750 ml<small>Kronkorken bis 6 bar</small></button>
             </div>
             <p class="eyebrow">Malo in der Flasche</p>
             <div class="seg" role="group" aria-label="Malo mitrechnen">
               <button type="button" data-act="malo" data-on="0">Nicht mitrechnen</button>
               <button type="button" data-act="malo" data-on="1">Mitrechnen</button>
             </div>
             ${field("t-malic", "Äpfelsäure beim Abfüllen", "g/L", "malic", 'data-min="0" data-max="10"')}`
          : `<p class="eyebrow">Durchgären bis</p>
             <p class="answer" id="t-big">–</p>
             ${field("t-dry", "Trocken unter", "g/L", "dry", 'data-min="0" data-max="10"')}`
      }
      <p class="eyebrow">Gefäß</p>
      ${field("t-vol", "Volumen", "L", "vol", 'data-min="1" data-max="100000"')}
      <p class="fine">Von Hand eingeben und nach jedem Abstich anpassen.</p>
      <p class="eyebrow">Temperaturplan</p>
      ${field("t-tstart", "Zu Beginn", "°C", "tStart", 'data-min="-5" data-max="35" data-optional="1" placeholder="–"')}
      ${field("t-tswitch", "Umschalten ab", "g/L", "tSwitch", 'data-min="0" data-max="300" data-optional="1" placeholder="–"')}
      ${field("t-tlate", "Danach", "°C", "tLate", 'data-min="-5" data-max="35" data-optional="1" placeholder="–"')}
      <p class="fine" id="t-plan-note">Leer lassen für keinen Plan. Die Prognose rechnet mit dem Plan; ${
        b.has_heater ? "die Heizung bekommt die Solltemperatur von Home Assistant." : "mit einem Shelly an der Heizmanschette regelt Home Assistant danach."
      }</p>
      ${
        petnat
          ? `<dl class="leaders">
               <div><dt>Abfüllen bei</dt><dd id="t-sugar">–</dd></div>
               <div><dt>Malo-Ausgleich</dt><dd id="t-malo">–</dd></div>
               <div><dt>Öffnen bei 10 °C</dt><dd id="t-p10">–</dd></div>
               <div><dt>Öffnen bei 20 °C</dt><dd id="t-p20">–</dd></div>
               <div id="t-limit-row"><dt>Ungünstig, 20 °C</dt><dd id="t-limit">–</dd></div>
             </dl>
             <p class="note">Gerechnet wird so, als würde der ganze Restzucker in der Flasche vergären. Mit Torulaspora ist das nicht sicher; dann wird es leiser.</p>
             <p class="fine">Die Faustregel „4 g/L pro bar“ stimmt nur bei etwa 12 °C. Grenzen: deine Werte für Kronkorken.</p>`
          : ""
      }
      <button class="primary" type="button" data-act="tsave" id="t-save" disabled>Gespeichert</button>
      <p class="toast" id="t-toast" aria-live="polite"></p>`;
  }

  _html_tank() {
    return `
      <p class="eyebrow">Sollwert jetzt</p>
      <p class="answer" id="c-big">–</p>
      <p class="answer-sub" id="c-sub"></p>
      <p class="say" id="c-say"></p>
      <div class="control">
        <label for="c-target">Flasche</label>
        <input type="range" id="c-target" data-in="ctarget" min="1.5" max="5" step="0.1" aria-label="Druck in der Flasche bei 20 °C">
        <output id="c-tout" for="c-target"></output>
      </div>
      <p class="fine" id="c-table"></p>
      <button class="primary" type="button" data-act="csave" id="c-save" hidden>Ziel übernehmen</button>
      <p class="toast" id="c-toast" aria-live="polite"></p>
      <dl class="leaders">
        <div><dt>CO₂-Ziel im Tank</dt><dd id="c-co2t">–</dd></div>
        <div><dt>Gelöstes CO₂</dt><dd id="c-co2">–</dd></div>
        <div><dt>Tanktemperatur</dt><dd id="c-temp">–</dd></div>
        <div id="c-prv-row"><dt>Sicherheitsventil</dt><dd id="c-prv">–</dd></div>
      </dl>
      <p class="note">Das mechanische Sicherheitsventil bleibt Pflicht. Die Regelung ersetzt es nicht.</p>
      <svg class="chart" id="c-chart" viewBox="0 0 320 150" role="img" aria-label="Tankdruck der letzten drei Tage mit Sollwert"></svg>
      <p class="status" id="c-status"></p>`;
  }

  /* ---------- Werte setzen ---------- */
  _set(id, text) {
    const el = this.$(id);
    if (el && el.textContent !== text) el.textContent = text;
  }

  _html(id, html) {
    const el = this.$(id);
    if (el && el.innerHTML !== html) el.innerHTML = html;
  }

  _show(id, visible) {
    const el = this.$(id);
    if (el) el.hidden = !visible;
  }

  _pressed(selector, test) {
    this.shadowRoot.querySelectorAll(selector).forEach((el) => el.setAttribute("aria-pressed", String(test(el))));
  }

  _update(b) {
    const err = this.$("h-err");
    if (err) {
      err.hidden = !this._err;
      err.textContent = this._err ? `Keine Verbindung, zeige den letzten Stand: ${this._err}` : "";
    }
    if (!b) return;
    this._updateHeader(b);
    if (b.mode === "charmat") this._updateTank(b);
    else {
      if (b.bottling) this._updateBottle(b);
      else this._updateToday(b);
      this._updateTarget(b);
    }
    this._updateMeasure(b);
  }

  _newest(b) {
    const times = Object.values(b.latest || {})
      .filter(Boolean)
      .map((p) => Date.parse(p[0]));
    return times.length ? Math.max(...times) : null;
  }

  _updateHeader(b) {
    const parts = [MODE_LABEL[b.mode] || b.mode];
    const start = Date.parse(b.start);
    if (Number.isFinite(start)) parts.push(`Tag ${Math.max(0, Math.floor((Date.now() - start) / DAY))}`);
    if (b.volume_l) parts.push(`${nf(b.volume_l, 0)} L`);
    this._set("h-sub", parts.join(" · "));
    const newest = this._newest(b);
    this._show("h-live", newest != null && Date.now() - newest < 15 * 60e3);
  }

  /* ---------- Heute ---------- */
  _updateToday(b) {
    const e = b.estimate || {};
    const still = b.mode === "still";
    const now = e.now ? new Date(e.now) : new Date();
    const best = toDate(e.best);
    const start = toDate(e.start);
    const end = toDate(e.end);
    const st = e.status || "waiting";
    let day = "–";
    let sub = "";
    let win = "";
    let say = "";
    if (st === "stuck") {
      day = "STOCKT?";
      sub = "KAUM ABBAU";
      say = "Der Zucker fällt kaum, ohne dass es kühler wurde. Eine Messung zeigt, ob die Gärung wirklich steht.";
    } else if (st === "dry") {
      day = "TROCKEN";
      sub = `${nf(e.sugar)} G/L`;
      say = "Laut Schätzung durchgegoren. Eine Messung bestätigt es.";
    } else if (e.display_state === "late") {
      day = "JETZT";
      sub = "FENSTER VORBEI";
      win = `Ziel ${nf(e.target_sugar)} g/L, aktuell ${nfs(e.sugar)} g/L`;
      say = `Der Restzucker liegt schon unter dem Ziel. Jetzt abgefüllt gibt das beim Öffnen etwa ${nf(e.p_now_10)}–${nf(e.p_now_20)} bar.`;
    } else if (e.display_state === "now") {
      day = "JETZT";
      if (end) {
        sub = `BIS ${fmtDay(end).toUpperCase()} ${fmtHM(end)}`;
        win = `Fenster endet ${fmtDay(end)} ${fmtHM(end)}`;
      }
      say = still ? "Fast trocken. Eine Messung bestätigt es." : "Du bist im Fenster. Eine letzte Messung bestätigt es.";
    } else if (best) {
      day = fmtDay(best).toUpperCase();
      sub = `≈ ${roundHour(best).getHours()} UHR`;
      if (start && end) win = `Fenster ${fmtDay(start)} ${fmtHM(start)} – ${fmtDay(end)} ${fmtHM(end)}`;
      say = inWords((best - now) / HOUR);
      if (e.measurement_recommended) say += " Eine Messung jetzt macht das Fenster enger.";
    } else if (e.sugar != null) {
      day = "GÄRT";
      if (b.s0) sub = `PROGNOSE AB ≈ ${Math.round(b.s0 / 2)} G/L`;
      say = "Die Prognose beginnt, wenn etwa die Hälfte des Zuckers vergoren ist. Bis dahin hilft eine Messung pro Tag.";
    } else {
      sub = "NOCH KEINE WERTE";
      say = "Trag eine Messung ein oder verbinde Spindel und Blasenzähler.";
    }
    this._set("d-day", day);
    this._set("d-sub", sub);
    this._set("d-window", win);
    this._set("d-say", say);

    const warn = !still && e.limit_ok === false ? "Im ungünstigen Fall über der Grenze der Flasche. Ziel senken oder die größere Flasche nehmen." : "";
    this._set("d-warn", warn);
    this._show("d-warn", Boolean(warn));
    const notes = ["fermenting", "approaching", "window"].includes(st) ? (e.notes || []).join(" · ") : "";
    this._set("d-notes", notes);
    this._show("d-notes", Boolean(notes));

    this._set("d-sugar", e.sugar != null ? `${nfs(e.sugar)} ± ${nf(e.sigma)} g/L` : "–");
    this._updateAbv(e, still);
    this._set("d-rate", e.rate != null ? `${nf(e.rate)} g/L am Tag` : "–");
    if (still) this._set("d-dry", `${nf(b.settings.dry_sugar_g_l)} g/L`);
    else {
      this._set("d-pnow", e.p_now_10 != null ? `${nf(e.p_now_10)}–${nf(e.p_now_20)} bar` : "–");
      this.$("d-pnow-row")?.classList.toggle("warn", e.p_now_20 != null && e.p_now_20 > b.settings.target_bar_20c + 0.3);
      this._set("d-ptarget", e.p_target_10 != null ? `${nf(e.p_target_10)}–${nf(e.p_target_20)} bar` : "–");
    }
    const plan = (b.settings.temp_plan || []).length > 0 && e.planned_temp != null;
    this._show("d-plan-row", plan);
    if (plan) this._set("d-plan", `${nf(e.planned_temp, 0)} °C${b.has_heater ? " · Heizung" : ""}`);

    const h = b.history || {};
    const parts = [];
    if (h.bpm_now != null) parts.push(`Blasen ${nf(h.bpm_now, 0)}/min`);
    if (b.latest?.gravity) parts.push(`Spindel ${nf(b.latest.gravity[1], 3)}`);
    if (b.latest?.weight) parts.push(`Waage ${nf(b.latest.weight[1], b.latest.weight[1] < 100 ? 2 : 1)} kg`);
    if (b.latest?.temps) parts.push(`${nf(b.latest.temps[1])} °C`);
    const newest = this._newest(b);
    if (newest != null) parts.push(ago(newest));
    this._set("d-status", parts.join(" · ") || "Noch keine Sensorwerte");

    this._updateWhatIf(b);
    this._drawWindowBar(e, now);
    this._drawSugarChart(b, e, now);
  }

  _updateAbv(e, still) {
    this._set("d-abv", e.abv_end != null ? `${nf(e.abv_end)} ± ${nf(e.abv_end_sigma)} % vol` : "–");
    let abvHint = "";
    if (e.abv_end != null) {
      abvHint = `<strong>Etikett ${nf(e.abv_label, e.abv_label % 1 ? 1 : 0)} % vol</strong>`;
      if (e.abv_label_ok) abvHint += ".";
      else if ((still || e.category === "still") && !e.abv_labs) abvHint += ", für einen Stillwein nur mit Laboranalyse.";
      else if (e.abv_pairs > 0 || e.abv_labs > 0) abvHint += ", noch knapp: ein weiteres Messpaar oder eine Laboranalyse.";
      else abvHint += ", noch zu unsicher: Refraktometer und Dichte an derselben Probe messen, am besten kurz vor dem Abfüllen.";
    }
    this._html("d-abv-hint", abvHint);
    this._show("d-abv-hint", Boolean(abvHint));
  }

  /* ---------- In der Flasche ---------- */
  _updateBottle(b) {
    const e = b.estimate || {};
    const bt = b.bottling;
    const f = b.bottle;
    const bottled = new Date(bt.time);
    const days = Math.max(0, Math.floor((Date.now() - bottled) / DAY));
    this._set("f-eyebrow", `In der Flasche · Tag ${days}`);
    this._set("f-bottled", `${fmtDay(bottled)} · ${nfs(bt.sugar)} ± ${nf(bt.sigma)} g/L`);
    let answer = "ABGEFÜLLT";
    let sub = `${fmtDay(bottled).toUpperCase()} ${fmtHM(bottled)}`;
    let say = "Der Restzucker beim Abfüllen ist festgehalten. Messungen danach ändern ihn nicht mehr.";
    let warn = "";
    if (f) {
      const last = f.readings[f.readings.length - 1];
      this._set("f-expected", `${nf(f.expected_10)}–${nf(f.expected_20)} bar`);
      this._html("f-worst", `${nf(f.worst_20)} bar <small>Grenze ${nf(f.limit)}</small>`);
      this.$("f-worst-row")?.classList.toggle("warn", f.worst_20 > f.limit);
      const pct = f.progress != null ? Math.round(Math.max(0, Math.min(1.5, f.progress)) * 100) : null;
      this._set("f-progress", f.done ? "durch" : pct != null ? `${pct} %` : "–");
      if (last) {
        answer = `${nf(last[3])} BAR`;
        sub = `BEI 20 °C · ERWARTET ${nf(f.expected_20)}`;
        if (f.state === "danger" || f.state === "high") {
          say = f.state === "danger" ? "Die Messflasche nähert sich der Grenze der Flasche." : "Mehr Druck als erwartet: In der Flasche gärt mehr Zucker als geschätzt.";
          warn = f.action;
        } else if (f.done) {
          say = "Durchgegoren. Zum Schluss einmal bei 10 und einmal bei 20 °C ablesen, dann den Ansatz abschließen: Die Messflasche eicht das Modell für die nächsten Ansätze.";
        } else {
          say = `Flaschengärung zu ${pct ?? "–"} %. Läuft wie erwartet.`;
        }
      } else {
        answer = "ABLESEN";
        sub = "MESSFLASCHE";
        say = "Die Messflasche nach 3, 7 und 14 Tagen ablesen, immer mit ihrer Temperatur. Die App rechnet auf 20 °C um.";
      }
      this._drawBottleChart(f, bottled);
    }
    this._set("f-answer", answer);
    this._set("f-sub", sub);
    this._set("f-say", say);
    this._set("f-warn", warn);
    this._show("f-warn", Boolean(warn));
    this._updateAbv(e, b.mode === "still");

    const fc = bt.forecast_check || {};
    const parts = ["48", "24", "12"]
      .filter((h) => fc[h])
      .map((h) => {
        const err = fc[h].error_h;
        const txt = Math.abs(err) < 1 ? "genau" : `${Math.round(Math.abs(err))} h zu ${err > 0 ? "spät" : "früh"}`;
        return `${h} h vorher ${txt}`;
      });
    this._set("f-forecast", parts.length ? `Prognose ${parts.join(" · ")}` : "");
    this._show("f-forecast", parts.length > 0);
    this._show("f-close", !b.closed);
    this._set("f-status", b.closed ? "Abgeschlossen und im Archiv." : b.has_bottle_sensor ? "Flaschenbox verbunden" : "");
  }

  _drawBottleChart(f, bottled) {
    const svg = this.$("f-chart");
    if (!svg) return;
    const W = 320;
    const H = 170;
    const L = 30;
    const R = 8;
    const T = 10;
    const B = 22;
    const pts = f.readings.map((r) => [(Date.parse(r[0]) - bottled) / DAY, r[3]]);
    const span = Math.max(28, Math.ceil(Math.max(f.days, ...pts.map((p) => p[0]), 0)) + 2);
    const top = Math.max(f.limit, ...pts.map((p) => p[1])) * 1.05;
    const x = (d) => L + (d / span) * (W - L - R);
    const y = (p) => T + (1 - Math.max(0, p) / top) * (H - T - B);
    let out = "";
    for (let p = 0; p <= top; p += 1) out += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(p)}" y2="${y(p)}"/><text x="${L - 4}" y="${y(p) + 3}" text-anchor="end">${p}</text>`;
    for (let d = 0; d <= span; d += 7) out += `<text x="${x(d)}" y="${H - 6}" text-anchor="${d + 7 > span ? "end" : "middle"}">${d} d</text>`;
    out += `<line class="setline" x1="${L}" x2="${W - R}" y1="${y(f.limit)}" y2="${y(f.limit)}"/><text class="targetlabel" x="${W - R}" y="${y(f.limit) - 4}" text-anchor="end">Grenze ${nf(f.limit)} bar</text>`;
    out += `<line class="forecast" x1="${L}" x2="${W - R}" y1="${y(f.expected_20)}" y2="${y(f.expected_20)}"/><text class="label-ink" x="${L + 4}" y="${y(f.expected_20) - 4}">erwartet ${nf(f.expected_20)}</text>`;
    if (pts.length > 1) out += `<polyline class="measured" points="${pts.map((p) => `${x(p[0])},${y(p[1])}`).join(" ")}"/>`;
    out += pts.map((p) => `<rect class="anchor" x="${x(p[0]) - 3.5}" y="${y(p[1]) - 3.5}" width="7" height="7"/>`).join("");
    if (!pts.length) out += `<text class="empty" x="${(L + W - R) / 2}" y="${H / 2}" text-anchor="middle">noch keine Messflasche</text>`;
    svg.innerHTML = out;
  }

  _updateWhatIf(b) {
    const e = b.estimate || {};
    const slider = this.$("d-whatif");
    if (!slider) return;
    const tNow = b.latest?.temps?.[1];
    if (this._whatIf == null) {
      this._whatIf = Math.min(26, Math.max(6, Math.round(tNow ?? e.planned_temp ?? 15)));
      slider.value = String(this._whatIf);
    }
    const T = this._whatIf;
    this._set("d-whatif-out", `${T} °C`);
    const moved = tNow == null || Math.round(tNow) !== T;
    const forecastable =
      e.fit_k > 0 && e.sugar != null && e.target_sugar != null && e.sugar > e.target_sugar &&
      !["stuck", "dry"].includes(e.status) && e.display_state !== "late";
    let line = "";
    if (moved && forecastable) {
      const days = Math.log(e.sugar / Math.max(e.target_sugar, 0.05)) / e.fit_k / P.thermalFactor(T, b.settings.q10);
      const best = new Date(Date.parse(e.now) + days * DAY);
      line = `Konstant ${T} °C: ${fmtDay(best)} ≈ ${roundHour(best).getHours()} Uhr`;
      if (e.best) {
        const dh = Math.round((best - Date.parse(e.best)) / HOUR);
        if (dh) line += dh > 0 ? ` (${dh} h später)` : ` (${-dh} h früher)`;
      }
    }
    this._set("d-whatif-line", line);
    this._show("d-whatif-line", Boolean(line));
    let hint = "";
    if (moved && tNow != null && forecastable && Math.abs(T - tNow) >= 1) {
      const dC = Math.abs(P.henry(T) - P.henry(tNow));
      const prod = P.YIELD_CO2_SUGAR * e.fit_k * e.sugar * P.thermalFactor(T, b.settings.q10);
      if (prod > 0) {
        const hrs = Math.max(1, Math.round((dC / prod) * 24));
        hint =
          T < tNow
            ? `Nach dem Kühlen fallen die Blasen etwa ${hrs} h lang ab, weil der Wein CO₂ zurücklöst. Das ist kein Gärstopp.`
            : `Beim Aufwärmen gast CO₂ aus. Die Blasen zeigen etwa ${hrs} h lang zu viel.`;
      }
    }
    this._set("d-whatif-hint", hint);
    this._show("d-whatif-hint", Boolean(hint));
  }

  _drawWindowBar(e, now) {
    const svg = this.$("d-wbar");
    if (!svg) return;
    const t0 = now.getTime();
    const span = 7 * DAY;
    const x0 = 14;
    const x1 = 312;
    const X = (t) => x0 + (Math.min(Math.max(t - t0, 0), span) / span) * (x1 - x0);
    let out = `<line x1="${x0}" y1="20" x2="${x1}" y2="20" class="axis"></line>`;
    for (let d = nextDay(startOfDay(t0)); d.getTime() < t0 + span; d = nextDay(d)) {
      const x = X(d.getTime());
      out += `<line x1="${x}" y1="13" x2="${x}" y2="27" class="tick"></line>`;
      const noon = d.getTime() + DAY / 2;
      if (noon < t0 + span) out += `<text x="${X(noon)}" y="42" text-anchor="middle">${WD[d.getDay()]}</text>`;
    }
    out += `<text x="${x0}" y="42" text-anchor="middle" class="nowlabel">jetzt</text>`;
    out += `<rect x="${x0 - 3.5}" y="16.5" width="7" height="7" class="best"></rect>`;
    const start = toDate(e.start);
    const end = toDate(e.end);
    const best = toDate(e.best);
    if (e.display_state !== "late" && start && end && start.getTime() < t0 + span) {
      const a = X(start.getTime());
      const b = X(end.getTime());
      out += `<rect x="${a}" y="12" width="${Math.max(3, b - a)}" height="16" class="band"></rect>`;
    }
    if (best && e.display_state !== "late") {
      if (best.getTime() <= t0 + span) out += `<rect x="${X(best.getTime()) - 5}" y="15" width="10" height="10" class="best"></rect>`;
      else out += `<text x="${x1}" y="9" text-anchor="end" class="nowlabel">→ ${fmtDay(best)}</text>`;
    }
    svg.innerHTML = out;
  }

  _drawSugarChart(b, e, now) {
    const svg = this.$("d-chart");
    if (!svg) return;
    const L = 30;
    const Rr = 312;
    const Tp = 12;
    const B = 150;
    const series = (e.series || []).map(([t, s]) => [Date.parse(t), s]);
    if (!series.length) {
      svg.innerHTML = `<text x="160" y="90" text-anchor="middle" class="empty">Noch kein Verlauf</text>`;
      return;
    }
    const tn = now.getTime();
    const t0 = Math.max(Date.parse(b.start) || tn - 2.5 * DAY, tn - 2.5 * DAY);
    const fc = (e.forecast || []).map(([t, s, hi, lo]) => [Date.parse(t), s, hi, lo]);
    const fEnd = fc.length ? fc[fc.length - 1][0] : tn;
    const t1 = Math.min(Math.max(fEnd, tn + 1.5 * DAY), tn + 7 * DAY);
    const X = (t) => L + ((t - t0) / (t1 - t0)) * (Rr - L);
    const pts = series.filter(([t]) => t >= t0 && t <= tn);
    const fcp = fc.filter(([t]) => t <= t1);
    const target = e.target_sugar ?? 0;
    const delta = Math.max(1, Math.sqrt((e.sigma || 0) ** 2 + 0.25));
    const top = Math.max(target + delta, ...pts.map((p) => p[1]), ...fcp.map((p) => Math.min(p[2], p[1] * 2)));
    const step = top > 60 ? 20 : top > 24 ? 10 : 5;
    const yMax = Math.max(step * 2, Math.ceil((top * 1.05) / step) * step);
    const Y = (s) => B - (Math.min(Math.max(s, 0), yMax) / yMax) * (B - Tp);
    const f1 = (v) => v.toFixed(1);
    let out = "";
    for (let s = 0; s <= yMax; s += step) {
      out += `<line x1="${L}" y1="${f1(Y(s))}" x2="${Rr}" y2="${f1(Y(s))}" class="grid"></line>`;
      out += `<text x="${L - 5}" y="${f1(Y(s) + 3)}" text-anchor="end">${s}</text>`;
    }
    out += `<text x="${L}" y="7">Restzucker g/L</text>`;
    if (e.target_sugar != null) {
      const yHi = Y(target + delta);
      const yLo = Y(Math.max(0, target - delta));
      out += `<rect x="${f1(X(tn))}" y="${f1(yHi)}" width="${f1(Rr - X(tn))}" height="${f1(Math.max(1, yLo - yHi))}" class="target"></rect>`;
      out += `<text x="${Rr - 2}" y="${f1(yHi - 3)}" text-anchor="end" class="targetlabel">Ziel ≈ ${nf(target)} g/L</text>`;
    }
    if (fcp.length > 1) {
      const up = fcp.map(([t, , hi]) => `${f1(X(t))},${f1(Y(hi))}`);
      const dn = fcp.map(([t, , , lo]) => `${f1(X(t))},${f1(Y(lo))}`).reverse();
      out += `<polygon points="${up.concat(dn).join(" ")}" class="cone"></polygon>`;
      out += `<polyline points="${fcp.map(([t, s]) => `${f1(X(t))},${f1(Y(s))}`).join(" ")}" class="forecast"></polyline>`;
    }
    out += pts.map(([t, s]) => `<circle cx="${f1(X(t))}" cy="${f1(Y(s))}" r="1.3" class="dot"></circle>`).join("");
    for (const [iso, s] of b.anchors || []) {
      const t = Date.parse(iso);
      if (t < t0 || t > tn) continue;
      const x = X(t);
      const y = Y(s);
      out += `<polygon points="${f1(x)},${f1(y - 5)} ${f1(x + 5)},${f1(y)} ${f1(x)},${f1(y + 5)} ${f1(x - 5)},${f1(y)}" class="anchor"></polygon>`;
    }
    out += `<line x1="${f1(X(tn))}" y1="${Tp - 2}" x2="${f1(X(tn))}" y2="${B}" class="nowline"></line>`;
    out += `<text x="${f1(X(tn) + 4)}" y="${Tp + 8}" class="label-ink">jetzt</text>`;
    for (let d = nextDay(startOfDay(t0)); d.getTime() < t1; d = nextDay(d)) {
      const x = X(d.getTime());
      out += `<line x1="${f1(x)}" y1="${B}" x2="${f1(x)}" y2="${B + 4}" class="grid"></line>`;
      const noon = d.getTime() + DAY / 2;
      if (noon < t1) out += `<text x="${f1(X(noon))}" y="${B + 13}" text-anchor="middle">${WD[d.getDay()]}</text>`;
    }
    const bub = ((b.history || {}).bubbles_bpm || []).map(([t, v]) => [Date.parse(t), v]).filter(([t]) => t >= t0 && t <= tn);
    if (bub.length) {
      const max = Math.max(1, ...bub.map((p) => p[1]));
      const bTop = B + 20;
      const bH = 22;
      out += `<text x="${L - 5}" y="${bTop + bH - 4}" text-anchor="end">Bl.</text>`;
      for (const [t, v] of bub) {
        const hgt = Math.max(1, (v / max) * bH);
        out += `<rect x="${f1(X(t))}" y="${f1(bTop + bH - hgt)}" width="${f1(Math.max(1, X(t + HOUR) - X(t) - 0.5))}" height="${f1(hgt)}" class="bubble"></rect>`;
      }
    }
    svg.innerHTML = out;
  }

  /* ---------- Messung ---------- */
  _updateMeasure(b) {
    const m = this._m;
    const kind = KINDS[m.kind];
    this._pressed("[data-act=mkind]", (el) => el.dataset.kind === m.kind);
    this._pressed("[data-act=munit]", (el) => el.dataset.unit === m.unit);
    const density = m.kind === "density";
    this._show("m-units", density || m.kind === "brix");
    this._set("m-unit", density ? DENSITY_UNITS[m.unit].label : kind.unit);
    const input = this.$("m-value");
    if (input) input.placeholder = density ? DENSITY_UNITS[m.unit].placeholder : kind.placeholder;
    this._set("m-help", kind.help);
    const lab = m.kind === "sugar";
    this._show("m-value2-row", m.kind === "brix" || lab);
    this._set("m-value2-label", lab ? "Alkohol derselben Probe (optional)" : "Dichte derselben Probe (optional)");
    this._set("m-unit2", lab ? "% vol" : DENSITY_UNITS[m.unit].label);
    const value2 = this.$("m-value2");
    if (value2) value2.placeholder = lab ? "11,5" : DENSITY_UNITS[m.unit].placeholder;
    this._show("m-temp-row", m.kind === "bottle_pressure");

    const rows = [];
    let msg = "";
    const p = m.preview;
    if (m.kind === "ph") msg = "Wird gespeichert und steht im Verlauf. Die Prognose ändert sich dadurch nicht.";
    else if (m.kind === "bottle_pressure")
      msg = b.bottling
        ? "Zählt für die Messflasche: Die App rechnet auf 20 °C um und vergleicht mit dem erwarteten Druck."
        : "Zählt erst nach „Abgefüllt“: Dann vergleicht die App die Messflasche mit dem erwarteten Druck.";
    else if (b.mode === "charmat" && !b.s0) msg = "Wird gespeichert. Beim Charmat rechnet die App mit Tankdruck und Temperatur.";
    else if (!p) msg = "Wert eintippen, dann steht hier, was er ändert.";
    else if (p.error) msg = `Lässt sich nicht auswerten: ${p.error}`;
    else if (m.kind === "malic") {
      const last = [...(b.measurements || [])].reverse().find((x) => x.kind === "malic");
      if (last) rows.push(["Äpfelsäure zuletzt", `${nf(last.value)} g/L`]);
      if (b.settings.malo_in_bottle && p.target_sugar != null)
        rows.push(["Zielzucker", `${nf(p.target_sugar)} g/L <small>war ${nf(b.estimate?.target_sugar)}</small>`]);
      else msg = "Malo in der Flasche ist aus; der Zielzucker bleibt.";
    } else if (p.plausible === false) msg = "Der Wert passt nicht zu diesem Ansatz. Einheit prüfen?";
    else if (p.sugar != null) {
      rows.push(["Restzucker", `${nfs(p.sugar)} g/L${p.prev_sugar != null ? ` <small>war ${nfs(p.prev_sugar)}</small>` : ""}`]);
      if (p.abv_measured != null) {
        rows.push(["Alkohol jetzt", `${nf(p.abv_measured)} % vol <small>gemessen</small>`]);
        if (p.abv_end != null) {
          const before = p.prev_abv_end_sigma != null ? nf(p.prev_abv_end_sigma) : null;
          const was = before != null && before !== nf(p.abv_end_sigma) ? ` <small>war ± ${before}</small>` : "";
          rows.push(["Alkohol am Ende", `${nf(p.abv_end)} ± ${nf(p.abv_end_sigma)} % vol${was}`]);
        }
      }
      if (p.spindle_offset != null && b.has_gravity) {
        const c = -p.spindle_offset * 1000;
        rows.push(["Spindel-Korrektur", `${c >= 0 ? "+" : "−"}${nf(Math.abs(c))} °Oe`]);
      }
      let win = "noch keine Prognose";
      if (p.display_state === "late") win = "vorbei";
      else if (p.display_state === "now") win = "jetzt";
      else win = windowText(toDate(p.start), toDate(p.end)) || win;
      if (b.mode !== "charmat") rows.push([b.mode === "still" ? "Trocken" : "Fenster", win]);
    }
    this._html("m-leaders", rows.map(([dt, dd]) => `<div><dt>${dt}</dt><dd>${dd}</dd></div>`).join(""));
    this._set("m-result-msg", msg);
    this._show("m-result-msg", Boolean(msg));
    this._set("m-toast", m.toast);
    const save = this.$("m-save");
    if (save) save.disabled = m.busy;
    this._set("ev-toast", this._ev.toast);
    this._drawLog(b);
  }

  _drawLog(b) {
    const items = [
      ...(b.measurements || []).map((x) => ({ ...x, measurement: true })),
      ...(b.events || []),
    ]
      .sort((a, c) => Date.parse(c.time) - Date.parse(a.time))
      .slice(0, 10);
    const text = (x) => {
      if (!x.measurement) {
        const v = x.kind === "volume" && x.value != null ? ` ${nf(x.value, 0)} L` : "";
        return `${EVENTS[x.kind] || esc(x.kind)}${v}`;
      }
      const u = x.unit || "sg";
      const unit = { sg: "", oe: " °Oe", baume: " °Bé", gcm3: " g/cm³" }[u] ?? "";
      const dens = (v) => (u === "sg" || u === "gcm3" ? nf(v, 3) : nf(v)) + unit;
      switch (x.kind) {
        case "brix":
          return `Refraktometer ${nf(x.value)} °Bx`;
        case "brix_density":
          return `Refraktometer ${nf(x.value)} °Bx + Dichte ${dens(x.value2)}`;
        case "density":
          return `Dichte ${dens(x.value)}`;
        case "sugar":
          return `Labor ${nf(x.value)} g/L${x.value2 != null ? ` + ${nf(x.value2)} % vol` : ""}`;
        case "malic":
          return `Äpfelsäure ${nf(x.value)} g/L`;
        case "ph":
          return `pH ${nf(x.value, 2)}`;
        case "bottle_pressure":
          return `Flasche ${nf(x.value)} bar${x.temperature != null ? ` bei ${nf(x.temperature, 0)} °C` : ""}`;
        default:
          return `${esc(x.kind)} ${nf(x.value)}`;
      }
    };
    const html = items.length
      ? items
          .map((x) => {
            const t = new Date(x.time);
            const key = `${x.kind}|${x.time}`;
            const armed = this._delArmed === key;
            return `<li><time datetime="${esc(x.time)}">${fmtDay(t)} ${fmtHM(t)}</time><span>${text(x)}${x.note ? ` <small>${esc(x.note)}</small>` : ""}</span><button class="del${armed ? " armed" : ""}" type="button" data-act="del" data-kind="${esc(x.kind)}" data-time="${esc(x.time)}" aria-label="${armed ? "Wirklich löschen" : "Eintrag löschen"}">${armed ? "löschen?" : "×"}</button></li>`;
          })
          .join("")
      : `<li><span class="fine">Noch nichts eingetragen.</span></li>`;
    this._html("m-log", html);
  }

  _schedulePreview() {
    clearTimeout(this._previewTimer);
    this._previewTimer = setTimeout(() => this._preview(), 300);
  }

  _measurementData(b) {
    const m = this._m;
    const value = num(m.value);
    if (!Number.isFinite(value)) return null;
    const data = { kind: m.kind, value };
    if (m.kind === "density") data.unit = m.unit;
    const value2 = num(m.value2);
    if (m.kind === "brix" && Number.isFinite(value2)) Object.assign(data, { kind: "brix_density", value2, unit: m.unit });
    if (m.kind === "sugar" && Number.isFinite(value2)) data.value2 = value2;
    return data;
  }

  async _preview() {
    const b = this._current();
    const m = this._m;
    const seq = ++m.seq;
    const data = this._measurementData(b);
    if (!b || !data || !["brix", "brix_density", "density", "sugar", "malic"].includes(data.kind)) {
      m.preview = null;
      if (b) this._updateMeasure(b);
      return;
    }
    try {
      const res = await this._hass.callWS({ type: "tipsylab/preview", entry_id: b.entry_id, ...data });
      if (seq === m.seq) m.preview = res;
    } catch (err) {
      if (seq === m.seq) m.preview = { error: errText(err) };
    }
    if (seq === m.seq) this._updateMeasure(this._current());
  }

  async _saveMeasurement() {
    const b = this._current();
    const m = this._m;
    const data = this._measurementData(b);
    if (!data) {
      m.toast = "Bitte eine Zahl eingeben, z. B. 7,7.";
      this._updateMeasure(b);
      return;
    }
    if (m.kind === "bottle_pressure") {
      const temp = num(m.temp);
      if (!Number.isFinite(temp)) {
        m.toast = "Bitte die Temperatur der Flasche angeben.";
        this._updateMeasure(b);
        return;
      }
      data.temperature = temp;
    }
    if (m.time) {
      const t = new Date(m.time);
      if (!Number.isNaN(t.getTime())) data.time = t.toISOString();
    }
    if (m.note.trim()) data.note = m.note.trim();
    m.busy = true;
    this._updateMeasure(b);
    try {
      await this._hass.callService("tipsylab", "add_measurement", { config_entry_id: b.entry_id, ...data });
      m.toast = b.mode === "charmat" ? "Gespeichert." : "Gespeichert. „Heute“ rechnet jetzt mit deiner Messung.";
      Object.assign(m, { value: "", value2: "", temp: "", time: "", note: "", preview: null });
      ["m-value", "m-value2", "m-temp", "m-time", "m-note"].forEach((id) => {
        const el = this.$(id);
        if (el) el.value = "";
      });
    } catch (err) {
      m.toast = `Nicht gespeichert: ${errText(err)}`;
    }
    m.busy = false;
    this._updateMeasure(this._current());
    await this._fetch();
  }

  async _saveEvent() {
    const b = this._current();
    const ev = this._ev;
    const data = { config_entry_id: b.entry_id, kind: ev.kind };
    if (ev.kind === "volume") {
      const v = num(ev.value);
      if (!Number.isFinite(v) || v <= 0) {
        ev.toast = "Bitte das neue Volumen in Litern angeben.";
        this._updateMeasure(b);
        return;
      }
      data.value = v;
    }
    if (ev.note.trim()) data.note = ev.note.trim();
    if (ev.kind === "note" && !data.note) {
      ev.toast = "Bitte eine Notiz eingeben.";
      this._updateMeasure(b);
      return;
    }
    try {
      await this._hass.callService("tipsylab", "add_event", data);
      ev.toast = `${EVENTS[ev.kind]} eingetragen.`;
      ev.value = "";
      ev.note = "";
      ["ev-value", "ev-note"].forEach((id) => {
        const el = this.$(id);
        if (el) el.value = "";
      });
    } catch (err) {
      ev.toast = `Nicht eingetragen: ${errText(err)}`;
    }
    this._updateMeasure(this._current());
    await this._fetch();
  }

  async _deleteEntry(kind, time) {
    const b = this._current();
    const key = `${kind}|${time}`;
    if (this._delArmed !== key) {
      this._delArmed = key; // erster Tipp: nachfragen
      this._drawLog(b);
      return;
    }
    this._delArmed = null;
    try {
      await this._hass.callService("tipsylab", "remove_entry", { config_entry_id: b.entry_id, kind, time });
      this._ev.toast = "Gelöscht.";
    } catch (err) {
      this._ev.toast = `Nicht gelöscht: ${errText(err)}`;
    }
    this._updateMeasure(this._current());
    await this._fetch();
  }

  async _closeBatch(el) {
    if (!el.classList.contains("armed")) {
      el.classList.add("armed");
      el.textContent = "Wirklich abschließen? Ins Archiv";
      return;
    }
    const b = this._current();
    try {
      await this._hass.callService("tipsylab", "add_event", { config_entry_id: b.entry_id, kind: "closed" });
    } catch (err) {
      el.textContent = `Nicht abgeschlossen: ${errText(err)}`;
      return;
    }
    await this._fetch();
  }

  /* ---------- Archiv ---------- */
  _buildArchive(root) {
    root.innerHTML = `
      <header class="top">${this._menuButton()}<span class="logo" aria-hidden="true"></span>
        <div class="batch"><span class="kicker">TIPSYLAB</span><b>Archiv</b></div></header>
      <section class="screen solo" style="margin-top:18px">
        <p class="eyebrow">Was wir gelernt haben</p>
        <dl class="leaders" id="a-learned"></dl>
        <p class="fine" id="a-learned-note"></p>
        <p class="eyebrow">Frühere Ansätze</p>
        <div id="a-list"></div>
        <button class="primary" type="button" data-act="archive-back">Zurück</button>
      </section>`;
    this._wireMenu();
  }

  _updateArchive() {
    const h = this._house || { values: {}, archive: [] };
    const v = h.values || {};
    const rows = [];
    const learned = (x) => (x && x.n ? `<small>aus ${x.n} ${x.n === 1 ? "Ansatz" : "Ansätzen"}</small>` : "<small>Startwert</small>");
    if (v.saturation) rows.push(["CO₂ beim Abfüllen", `${Math.round(v.saturation.mean * 100)} ± ${Math.round(v.saturation.sigma * 100)} % ${learned(v.saturation)}`]);
    if (v.g_sugar_per_abv) rows.push(["Zucker je % vol", `${nf(v.g_sugar_per_abv.mean)} ± ${nf(v.g_sugar_per_abv.sigma)} g/L ${learned(v.g_sugar_per_abv)}`]);
    this._html("a-learned", rows.map(([dt, dd]) => `<div><dt>${dt}</dt><dd>${dd}</dd></div>`).join(""));
    const any = Object.values(v).some((x) => x.n);
    this._set(
      "a-learned-note",
      any
        ? "Gelöstes CO₂ beim Abfüllen in % der Sättigung, aus durchgegorenen Messflaschen; Zucker je % vol aus Laborwerten. Neue Ansätze rechnen damit."
        : "Noch Startwerte aus der Literatur. Durchgegorene Messflaschen und Laborwerte von abgeschlossenen Ansätzen eichen sie.",
    );
    const list = (h.archive || []).map((r) => {
      const start = toDate(r.start);
      const closed = toDate(r.closed);
      const bt = r.bottling;
      const bo = r.bottle;
      const last = bo?.readings?.[bo.readings.length - 1];
      const fc = bt?.forecast_check?.["48"];
      const dl = [];
      if (bt) dl.push(["Abgefüllt bei", `${nfs(bt.sugar)} ± ${nf(bt.sigma)} g/L`]);
      if (bo) dl.push(last ? ["Messflasche 20 °C", `${nf(last[3])} bar <small>erwartet ${nf(bo.expected_20)}</small>`] : ["Erwartet bei 20 °C", `${nf(bo.expected_20)} bar`]);
      if (fc) dl.push(["Prognose 48 h vorher", Math.abs(fc.error_h) < 1 ? "genau" : `${Math.round(Math.abs(fc.error_h))} h zu ${fc.error_h > 0 ? "spät" : "früh"}`]);
      if (r.abv) dl.push(["Alkohol", `${nf(r.abv.value)} ± ${nf(r.abv.sigma)} % vol <small>Etikett ${nf(r.abv.label, r.abv.label % 1 ? 1 : 0)}</small>`]);
      return `<article class="arch"><p class="arch-title"><b>${esc(r.name)}</b> <small>${MODE_LABEL[r.mode] || esc(r.mode)} · ${start ? fmtDay(start) : ""}–${closed ? fmtDay(closed) : ""} ${closed ? closed.getFullYear() : ""}</small></p>
        ${this._sparkline(r.series || [])}
        <dl class="leaders">${dl.map(([dt, dd]) => `<div><dt>${dt}</dt><dd>${dd}</dd></div>`).join("")}</dl></article>`;
    });
    this._html("a-list", list.length ? list.join("") : `<p class="fine">Noch kein Ansatz abgeschlossen. „Ansatz abschließen“ steht nach dem Abfüllen unter „Heute“.</p>`);
  }

  _sparkline(series) {
    if (series.length < 2) return "";
    const W = 320;
    const H = 46;
    const t0 = Date.parse(series[0][0]);
    const t1 = Date.parse(series[series.length - 1][0]);
    const top = Math.max(...series.map((p) => p[1]), 1);
    const pts = series.map((p) => `${((Date.parse(p[0]) - t0) / Math.max(1, t1 - t0)) * (W - 4) + 2},${(1 - p[1] / top) * (H - 6) + 3}`);
    return `<svg class="chart spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Restzucker über die Gärung"><polyline class="measured" points="${pts.join(" ")}"/></svg>`;
  }

  /* ---------- Ziel ---------- */
  _updateTarget(b) {
    const s = b.settings;
    if (!this._t || !this._t.dirty) {
      this._t = {
        dirty: false,
        target: s.target_bar_20c,
        bottle: String(s.bottle),
        malo: Boolean(s.malo_in_bottle),
        malic: s.malic_g_l ?? 0,
        vol: b.volume_l ?? null,
        tStart: s.temp_start ?? null,
        tSwitch: s.temp_switch_sugar ?? null,
        tLate: s.temp_late ?? null,
        dry: s.dry_sugar_g_l,
      };
      const t = this._t;
      const put = (id, v) => {
        const el = this.$(id);
        if (el && this.shadowRoot.activeElement !== el) {
          el.value = v;
          el.removeAttribute("aria-invalid");
        }
      };
      put("t-target", String(t.target));
      put("t-malic", inputNum(t.malic));
      put("t-dry", inputNum(t.dry));
      put("t-vol", inputNum(t.vol, 0));
      put("t-tstart", inputNum(t.tStart));
      put("t-tswitch", inputNum(t.tSwitch));
      put("t-tlate", inputNum(t.tLate));
    }
    this._renderTarget(b);
  }

  _renderTarget(b) {
    const t = this._t;
    if (!t) return;
    if (b.mode === "petnat") {
      const bottle = P.BOTTLES[t.bottle] || P.BOTTLES[750];
      const mal = t.malo ? t.malic : 0;
      const fill = P.fills(b.settings.saturation ?? P.FILL.mid.sat); // gelernte Sättigung beim Abfüllen
      const sMid = P.sugarForPressure(t.target, 20, bottle, fill.mid, mal);
      const sWorst = P.sugarForPressure(t.target, 20, bottle, fill.worst, mal);
      const sMild = P.sugarForPressure(t.target, 20, bottle, fill.mild, mal);
      const p10 = P.bottlePressure(sMid, 10, bottle, fill.mid, mal);
      const p20 = P.bottlePressure(sMid, 20, bottle, fill.mid, mal);
      const worst = P.bottlePressure(sMid, 20, bottle, fill.worst, mal);
      this._set("t-big", `${nf(p10)}–${nf(t.target)} BAR`);
      this._set("t-out", `${nf(t.target)} bar bei 20 °C`);
      const cat = P.euCategory(t.target);
      this._set("t-cat", CATEGORY[cat]);
      this.$("t-cat")?.classList.toggle("off", cat === "gap" || cat === "still");
      this._html("t-sugar", `≈ ${nf(sMid)} g/L <small>(${nf(sWorst)}–${nf(sMild)})</small>`);
      this._set("t-malo", t.malo ? `−${nf(P.maloSugarOffset(t.malic))} g/L Zucker` : "aus");
      this._set("t-p10", `${nf(p10)} bar`);
      this._set("t-p20", `${nf(p20)} bar`);
      const ok = worst <= bottle.limit;
      this._set("t-limit", `${nf(worst)} / ${nf(bottle.limit)} bar ${ok ? "✓" : "✕"}`);
      this.$("t-limit-row")?.classList.toggle("warn", !ok);
      this._pressed("[data-act=bottle]", (el) => el.dataset.bottle === t.bottle);
      this._pressed("[data-act=malo]", (el) => (el.dataset.on === "1") === t.malo);
      this._show("t-malic-row", t.malo);
    } else {
      this._set("t-big", `UNTER ${nf(t.dry)} G/L`);
    }
    const save = this.$("t-save");
    if (save) {
      save.disabled = !t.dirty;
      save.textContent = t.dirty ? "Ziel speichern" : "Gespeichert";
    }
  }

  async _saveTarget() {
    const b = this._current();
    const s = b.settings;
    const t = this._t;
    const changes = {};
    if (b.mode === "petnat") {
      if (t.target !== s.target_bar_20c) changes.target_bar_20c = t.target;
      if (t.bottle !== String(s.bottle)) changes.bottle = t.bottle;
      if (t.malo !== Boolean(s.malo_in_bottle)) changes.malo_in_bottle = t.malo;
      if (t.malo && t.malic !== s.malic_g_l) changes.malic_g_l = t.malic;
    } else if (t.dry !== s.dry_sugar_g_l) changes.dry_sugar_g_l = t.dry;
    if (t.vol != null && t.vol !== b.volume_l) changes.volume_l = t.vol;
    if (t.tStart !== (s.temp_start ?? null)) changes.temp_start = t.tStart;
    if (t.tSwitch !== (s.temp_switch_sugar ?? null)) changes.temp_switch_sugar = t.tSwitch;
    if (t.tLate !== (s.temp_late ?? null)) changes.temp_late = t.tLate;
    let toast = "Nichts geändert.";
    if (Object.keys(changes).length) {
      try {
        await this._hass.callService("tipsylab", "update_settings", { config_entry_id: b.entry_id, ...changes });
        toast = "Gespeichert.";
      } catch (err) {
        this._set("t-toast", `Nicht gespeichert: ${errText(err)}`);
        return;
      }
    }
    t.dirty = false;
    this._set("t-toast", toast);
    await this._fetch();
  }

  /* ---------- Tank (Charmat) ---------- */
  _updateTank(b) {
    const s = b.settings;
    if (!this._c || !this._c.dirty) {
      this._c = { dirty: false, target: s.target_bar_20c };
      const slider = this.$("c-target");
      if (slider) slider.value = String(s.target_bar_20c);
    }
    const c = this._c;
    const temp = b.latest?.temps?.[1];
    const pIst = b.latest?.pressure?.[1];
    const co2 = P.charmatCo2Target(c.target, s.filling_loss ?? 0.08);
    const sp = temp != null ? P.charmatSetpoint(co2, temp) : null;
    this._set("c-big", sp != null ? `${nf(sp)} BAR` : "–");
    const sub = [pIst != null ? `IST ${nf(pIst)} BAR` : null, temp != null ? `${nf(temp)} °C` : null].filter(Boolean);
    this._set("c-sub", sub.length ? sub.join(" · ") : "KEINE SENSORWERTE");
    this._set(
      "c-say",
      `Das Ventil hält den Druck, der in der Flasche ${nf(c.target)} bar bei 20 °C ergibt. Wird der Tank wärmer, steigt der Sollwert mit.`,
    );
    this._set("c-tout", `${nf(c.target)} bar`);
    this._set("c-table", `Sollwert bei ${[8, 10, 12, 15, 18].map((t) => `${t}\u00a0°C\u00a0${nf(P.charmatSetpoint(co2, t))}`).join(" · ")}\u00a0bar`);
    this._set("c-co2t", `${nf(co2, 2)} g/L`);
    this._set("c-co2", b.charmat?.dissolved != null ? `${nf(b.charmat.dissolved, 2)} g/L` : "–");
    this._set("c-temp", temp != null ? `${nf(temp)} °C` : "–");
    const prv = s.prv_bar;
    const ok = prv == null || sp == null || sp <= prv - 0.3;
    this._set("c-prv", prv != null ? `${nf(prv)} bar mech. ${ok ? "✓" : "✕ zu knapp"}` : "nicht eingetragen");
    this.$("c-prv-row")?.classList.toggle("warn", !ok);
    this._show("c-save", c.dirty);
    const newest = b.latest?.pressure ? Date.parse(b.latest.pressure[0]) : null;
    this._set("c-status", newest ? `Drucksensor · ${ago(newest)}` : "Kein Drucksensor verbunden");
    this._drawTankChart(b, sp);
  }

  _drawTankChart(b, sp) {
    const svg = this.$("c-chart");
    if (!svg) return;
    const pts = ((b.history || {}).pressure || []).map(([t, v]) => [Date.parse(t), v]);
    const L = 30;
    const Rr = 312;
    const Tp = 12;
    const B = 128;
    const tn = Date.now();
    const t0 = tn - 72 * HOUR;
    const shown = pts.filter(([t]) => t >= t0);
    const yMax = Math.max(2, Math.ceil(Math.max(sp ?? 0, ...shown.map((p) => p[1])) + 0.6));
    const X = (t) => L + ((t - t0) / (tn - t0)) * (Rr - L);
    const Y = (p) => B - (Math.min(Math.max(p, 0), yMax) / yMax) * (B - Tp);
    const f1 = (v) => v.toFixed(1);
    let out = "";
    for (let p = 0; p <= yMax; p += 1) {
      out += `<line x1="${L}" y1="${f1(Y(p))}" x2="${Rr}" y2="${f1(Y(p))}" class="grid"></line>`;
      out += `<text x="${L - 5}" y="${f1(Y(p) + 3)}" text-anchor="end">${p}</text>`;
    }
    out += `<text x="${L}" y="7">Tankdruck bar</text>`;
    if (sp != null) {
      out += `<line x1="${L}" y1="${f1(Y(sp))}" x2="${Rr}" y2="${f1(Y(sp))}" class="setline"></line>`;
      out += `<text x="${Rr - 2}" y="${f1(Y(sp) - 4)}" text-anchor="end" class="targetlabel">Soll ${nf(sp)}</text>`;
    }
    if (shown.length > 1) out += `<polyline points="${shown.map(([t, p]) => `${f1(X(t))},${f1(Y(p))}`).join(" ")}" class="measured"></polyline>`;
    else out += `<text x="${(L + Rr) / 2}" y="${(Tp + B) / 2}" text-anchor="middle" class="empty">Noch kein Druckverlauf</text>`;
    for (const [h, label] of [[-72, "−72 h"], [-48, "−48 h"], [-24, "−24 h"], [0, "jetzt"]]) {
      const anchor = h === -72 ? "start" : h === 0 ? "end" : "middle";
      out += `<text x="${f1(X(tn + h * HOUR))}" y="${B + 13}" text-anchor="${anchor}">${label}</text>`;
    }
    svg.innerHTML = out;
  }

  async _saveCharmat() {
    const b = this._current();
    try {
      await this._hass.callService("tipsylab", "update_settings", { config_entry_id: b.entry_id, target_bar_20c: this._c.target });
      this._c.dirty = false;
      this._set("c-toast", "Übernommen. Der Regler bekommt den neuen Sollwert.");
    } catch (err) {
      this._set("c-toast", `Nicht übernommen: ${errText(err)}`);
      return;
    }
    await this._fetch();
  }

  /* ---------- Ereignisse ---------- */
  _onClick(e) {
    const el = e.target.closest("[data-act]");
    if (!el || el.disabled) return;
    const b = this._current();
    switch (el.dataset.act) {
      case "batch":
        this._sel = el.dataset.id;
        store.set("batch", this._sel);
        this._render();
        break;
      case "tab":
        this._setTab(el.dataset.tab);
        break;
      case "goto-measure":
        this._setTab("measure");
        this.$("m-value")?.focus();
        break;
      case "goto-bottle":
        Object.assign(this._m, { kind: "bottle_pressure", value2: "", preview: null, toast: "" });
        this._setTab("measure");
        this._updateMeasure(b);
        this.$("m-value")?.focus();
        break;
      case "del":
        this._deleteEntry(el.dataset.kind, el.dataset.time);
        break;
      case "close-batch":
        this._closeBatch(el);
        break;
      case "archive":
        this._archive = true;
        this._render();
        break;
      case "archive-back":
        this._archive = false;
        this._render();
        break;
      case "mkind": {
        // Das zweite Feld bedeutet je Messart etwas anderes (Dichte oder Alkohol): beim Wechsel leeren
        const v2 = el.dataset.kind !== this._m.kind ? "" : this._m.value2;
        Object.assign(this._m, { kind: el.dataset.kind, value2: v2, preview: null, toast: "" });
        const input2 = this.$("m-value2");
        if (input2) input2.value = v2;
        this._updateMeasure(b);
        this._schedulePreview();
        break;
      }
      case "munit":
        this._m.unit = el.dataset.unit;
        this._updateMeasure(b);
        this._schedulePreview();
        break;
      case "msave":
        this._saveMeasurement();
        break;
      case "esave":
        this._saveEvent();
        break;
      case "bottle":
        Object.assign(this._t, { bottle: el.dataset.bottle, dirty: true });
        this._renderTarget(b);
        break;
      case "malo":
        Object.assign(this._t, { malo: el.dataset.on === "1", dirty: true });
        this._renderTarget(b);
        break;
      case "tsave":
        this._saveTarget();
        break;
      case "csave":
        this._saveCharmat();
        break;
      case "add-batch":
        navigate("/config/integrations/dashboard/add?domain=tipsylab");
        break;
      case "open-integration":
        navigate("/config/integrations/integration/tipsylab");
        break;
      case "retry":
        this._fetch();
        break;
      default:
        break;
    }
  }

  _setTab(tab) {
    this._tab = tab;
    store.set("tab", tab);
    this.shadowRoot.querySelectorAll("[data-screen]").forEach((s) => s.classList.toggle("active", s.dataset.screen === tab));
    this._pressed("[data-act=tab]", (el) => el.dataset.tab === tab);
  }

  _onInput(e) {
    const el = e.target;
    const key = el?.dataset?.in;
    if (!key) return;
    const b = this._current();
    const m = this._m;
    switch (key) {
      case "whatif":
        this._whatIf = Number(el.value);
        this._updateWhatIf(b);
        break;
      case "mval":
        Object.assign(m, { value: el.value, toast: "" });
        this._schedulePreview();
        break;
      case "mval2":
        m.value2 = el.value;
        this._schedulePreview();
        break;
      case "mtemp":
        m.temp = el.value;
        break;
      case "mtime":
        m.time = el.value;
        break;
      case "mnote":
        m.note = el.value;
        break;
      case "evval":
        this._ev.value = el.value;
        break;
      case "evnote":
        this._ev.note = el.value;
        break;
      case "ttarget":
        Object.assign(this._t, { target: Number(el.value), dirty: true });
        this._renderTarget(b);
        break;
      case "tnum": {
        const empty = el.value.trim() === "";
        const v = empty ? null : num(el.value);
        const lo = Number(el.dataset.min);
        const hi = Number(el.dataset.max);
        const valid = empty ? el.dataset.optional === "1" : Number.isFinite(v) && v >= lo && v <= hi;
        if (valid) el.removeAttribute("aria-invalid");
        else {
          el.setAttribute("aria-invalid", "true");
          break;
        }
        Object.assign(this._t, { [el.dataset.field]: v, dirty: true });
        this._renderTarget(b);
        break;
      }
      case "ctarget":
        Object.assign(this._c, { target: Number(el.value), dirty: true });
        this._updateTank(b);
        break;
      default:
        break;
    }
  }

  _onChange(e) {
    const el = e.target;
    if (el?.dataset?.ch === "evkind") {
      this._ev.kind = el.value;
      this._ev.toast = "";
      this._show("ev-value", el.value === "volume");
      this._set("ev-toast", "");
    }
  }
}

if (!customElements.get("tipsylab-panel")) customElements.define("tipsylab-panel", TipsylabPanel);
