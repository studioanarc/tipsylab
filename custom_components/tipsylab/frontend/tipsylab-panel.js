/* TIPSYLAB-Panel für Home Assistant: Heute, Messung, Ziel und, bei Charmat, Tank.
 *
 * Ohne Build-Schritt und ohne Abhängigkeiten. Daten kommen über den WebSocket-Befehl
 * tipsylab/batches (alle 30 s und nach jeder Eingabe), Vorschauen über tipsylab/preview.
 * Eingaben gehen an die Services add_measurement, add_event und update_settings.
 * Gestaltung wie docs/ui-entwurf: Papier-Rosé, Ultramarin, keine runden Ecken.
 * Sprachen: Deutsch, Englisch, Französisch. Jeder Text steht an seiner Stelle als
 * L(Deutsch, Englisch, Französisch), wie in tools/make_translations.py. */

const P = await import(new URL(`./physics.js${new URL(import.meta.url).search}`, import.meta.url).href);

const POLL_MS = 30000;
const DAY = 864e5;
const HOUR = 36e5;
const LANGS = ["de", "fr", "en"];
const LOCALE = { de: "de-DE", en: "en-GB", fr: "fr-FR" };
let LANG = "de";
const L = (de, en, fr) => (LANG === "en" ? en : LANG === "fr" ? fr : de);
const langOf = (code) => {
  const c = String(code || "").slice(0, 2).toLowerCase();
  return LANGS.includes(c) ? c : "en";
};
const WD = {
  de: ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"],
  en: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
  fr: ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."],
};
const wd = (d) => WD[LANG][d.getDay()];
const modeLabel = (mode) => ({ petnat: "Pet Nat", still: L("Naturwein", "Natural wine", "Vin nature"), charmat: "Charmat" })[mode];
const kinds = () => ({
  brix: {
    label: L("Refraktometer", "Refractometer", "Réfractomètre"),
    unit: "°Bx",
    placeholder: nf(7.7),
    help: L(
      "Probe entgast, Gerät mit Temperaturausgleich. Der Alkohol wird herausgerechnet.",
      "Degassed sample, instrument with temperature compensation. The alcohol is corrected for.",
      "Échantillon dégazé, appareil compensé en température. L'alcool est corrigé.",
    ),
  },
  density: {
    label: L("Dichte", "Density", "Densité"),
    unit: null,
    help: L(
      `Hydrometer oder Dichtemeter, auf 20 °C bezogen. Unter ${nf(1, 3)} wird Oechsle negativ.`,
      `Hydrometer or density meter, referenced to 20 °C. Below ${nf(1, 3)}, Oechsle turns negative.`,
      `Densimètre ou densitomètre, ramené à 20 °C. Sous ${nf(1, 3)}, l'Oechsle devient négatif.`,
    ),
  },
  sugar: {
    label: L("Labor", "Lab", "Labo"),
    unit: "g/L",
    placeholder: "14",
    help: L(
      "Laborwert Restzucker (Glucose + Fructose). Steht im Befund auch der Alkohol, unten eintragen: Das macht den Alkohol fürs Etikett genau.",
      "Lab residual sugar (glucose + fructose). If the report also gives the alcohol, enter it below: it makes the label alcohol exact.",
      "Sucre résiduel du labo (glucose + fructose). Si le bulletin donne aussi l'alcool, saisis-le en dessous : il rend l'alcool de l'étiquette exact.",
    ),
  },
  malic: {
    label: L("Äpfelsäure", "Malic acid", "Acide malique"),
    unit: "g/L",
    placeholder: nf(1.5),
    help: L(
      "Enzymatisch oder mit Teststreifen. Fällt sie, läuft die Malo.",
      "Enzymatic or with test strips. If it falls, malolactic is under way.",
      "Enzymatique ou par bandelettes. Si elle baisse, la malo est en cours.",
    ),
  },
  ph: {
    label: "pH",
    unit: "",
    placeholder: nf(3.4),
    help: L("Steigt während der Malo meist leicht an.", "Usually rises slightly during malolactic.", "Monte en général un peu pendant la malo."),
  },
  bottle_pressure: {
    label: L("Flaschendruck", "Bottle pressure", "Pression bouteille"),
    unit: "bar",
    placeholder: nf(2.4),
    help: L(
      "Aphrometer an der Messflasche, dazu ihre Temperatur. Die App rechnet auf 20 °C um und vergleicht mit dem erwarteten Druck.",
      "Aphrometer on the measurement bottle, plus its temperature. The app converts to 20 °C and compares with the expected pressure.",
      "Aphromètre sur la bouteille témoin, avec sa température. L'app ramène à 20 °C et compare à la pression attendue.",
    ),
  },
});
const densityUnits = () => ({ oe: { label: "°Oe", placeholder: `−${nf(1.8)}` }, sg: { label: "SG", placeholder: nf(0.998, 3) } });
const events = () => ({
  racking: L("Abstich", "Racking", "Soutirage"),
  volume: L("Volumen", "Volume", "Volume"),
  cooling: L("Kühlen", "Cooling", "Refroidir"),
  heating: L("Heizen", "Heating", "Chauffer"),
  bottled: L("Abgefüllt", "Bottled", "Mis en bouteille"),
  closed: L("Abgeschlossen", "Closed", "Clôturé"),
  note: L("Notiz", "Note", "Note"),
});
const category = (cat) =>
  ({
    still: L("unter 1 bar: Stillwein", "below 1 bar: still wine", "moins de 1 bar : vin tranquille"),
    semi_sparkling: L(
      `frisante · Perlwein (1–${nf(2.5)} bar bei 20 °C)`,
      `frisante · semi-sparkling (1–${nf(2.5)} bar at 20 °C)`,
      `vin pétillant (1–${nf(2.5)} bar à 20 °C)`,
    ),
    gap: L(`${nf(2.5)}–3 bar: keine EU-Kategorie`, `${nf(2.5)}–3 bar: no EU category`, `${nf(2.5)}–3 bar : pas de catégorie UE`),
    sparkling: L(
      "espumante · Schaumwein (ab 3 bar bei 20 °C)",
      "espumante · sparkling wine (from 3 bar at 20 °C)",
      "vin mousseux (dès 3 bar à 20 °C)",
    ),
    quality_sparkling: L(
      `espumante · Schaumwein (ab ${nf(3.5)} bar bei 20 °C)`,
      `espumante · sparkling wine (from ${nf(3.5)} bar at 20 °C)`,
      `vin mousseux (dès ${nf(3.5)} bar à 20 °C)`,
    ),
  })[cat];
const WORDS = {
  de: { 1: "einem Tag", 1.5: "anderthalb Tagen", 2: "zwei Tagen", 2.5: "zweieinhalb Tagen", 3: "drei Tagen", 3.5: "dreieinhalb Tagen",
    4: "vier Tagen", 4.5: "viereinhalb Tagen", 5: "fünf Tagen", 5.5: "fünfeinhalb Tagen", 6: "sechs Tagen", 7: "einer Woche" },
  en: { 1: "a day", 1.5: "a day and a half", 2: "two days", 2.5: "two and a half days", 3: "three days", 3.5: "three and a half days",
    4: "four days", 4.5: "four and a half days", 5: "five days", 5.5: "five and a half days", 6: "six days", 7: "a week" },
  fr: { 1: "un jour", 1.5: "un jour et demi", 2: "deux jours", 2.5: "deux jours et demi", 3: "trois jours", 3.5: "trois jours et demi",
    4: "quatre jours", 4.5: "quatre jours et demi", 5: "cinq jours", 5.5: "cinq jours et demi", 6: "six jours", 7: "une semaine" },
};
const notesText = (codes, e) => {
  const n = e.weight_steps || 0;
  const text = {
    weight_steps: L(
      `Waage: ${n} ${n === 1 ? "Sprung" : "Sprünge"} herausgerechnet (Probe, Abstich?)`,
      `Scale: ${n} ${n === 1 ? "jump" : "jumps"} removed (sample, racking?)`,
      `Balance : ${n} ${n === 1 ? "saut retiré" : "sauts retirés"} (prélèvement, soutirage ?)`,
    ),
    weight_third: L(
      "Waage zeigt etwa ein Drittel: mit Testgewicht in der Deckelmitte eichen",
      "Scale shows about a third: calibrate with a test weight in the middle of the lid",
      "La balance indique environ un tiers : étalonner avec un poids test au centre du couvercle",
    ),
    weight_mismatch: L(
      "Waage passt nicht zu den Messungen: Eichung prüfen",
      "Scale does not match the measurements: check the calibration",
      "La balance ne correspond pas aux mesures : vérifier l'étalonnage",
    ),
    spindle_house: L(
      "Spindel nach ihrem Hauswert, noch ohne eigenen Abgleich",
      "Hydrometer by its house value, not yet matched for this batch",
      "Densimètre selon sa valeur maison, pas encore recalé pour cette cuvée",
    ),
    bubbles_saturated: L(
      "Blasenzähler war gesättigt: Blasen zählen erst nach der nächsten Messung wieder",
      "Bubble counter was saturated: bubbles count again after the next measurement",
      "Le compteur de bulles était saturé : les bulles comptent à nouveau après la prochaine mesure",
    ),
    bubbles_house: L(
      "Blasen nach dem Hauswert dieser Gärbox, noch ohne eigene Eichung",
      "Bubbles by this Gärbox's house value, not yet calibrated for this batch",
      "Bulles selon la valeur maison de cette Gärbox, pas encore étalonnées pour cette cuvée",
    ),
    linear_trend: L(
      "Prognose aus dem linearen Trend, noch keine Kurvenanpassung",
      "Forecast from the linear trend, no curve fit yet",
      "Prévision d'après la tendance linéaire, pas encore d'ajustement de courbe",
    ),
    no_recent: L("Noch keine aktuellen Werte", "No current readings yet", "Pas encore de valeurs actuelles"),
    dry_unconfirmed: L(
      "Trocken laut Schätzung; mit einer Messung bestätigen",
      "Dry according to the estimate; confirm with a measurement",
      "Sec selon l'estimation ; à confirmer par une mesure",
    ),
    stuck: L("Zucker fällt kaum, ohne dass es kühler wurde", "Sugar barely falls although it did not get cooler", "Le sucre baisse à peine sans refroidissement"),
  };
  return codes.map((c) => text[c] || c);
};
/* „Nicht gespeichert: …“ und Verwandte */
const notDone = (what, err) => {
  const why = errText(err);
  const t = {
    save: L("Nicht gespeichert", "Not saved", "Non enregistré"),
    add: L("Nicht eingetragen", "Not added", "Non ajouté"),
    delete: L("Nicht gelöscht", "Not deleted", "Non supprimé"),
    close: L("Nicht abgeschlossen", "Not closed", "Non clôturée"),
    apply: L("Nicht übernommen", "Not applied", "Non appliqué"),
  }[what];
  return `${t}${LANG === "fr" ? " :" : ":"} ${why}`;
};
/* Abweichung der Prognose im Nachhinein: „genau“ oder „3 h zu spät“ */
const offBy = (errH) => {
  if (Math.abs(errH) < 1) return L("genau", "spot on", "exacte");
  const n = Math.round(Math.abs(errH));
  return errH > 0 ? L(`${n} h zu spät`, `${n} h late`, `${n} h en retard`) : L(`${n} h zu früh`, `${n} h early`, `${n} h en avance`);
};
const abvEnd = () => L("Alkohol am Ende", "Alcohol at the end", "Alcool final");
const worst20 = () => L("Ungünstig, 20 °C", "Worst case, 20 °C", "Pire cas, 20 °C");
const sourceName = (code) =>
  ({
    gravity: L("Spindel", "hydrometer", "densimètre"),
    temperature: L("Temperatur", "temperature", "température"),
    weight: L("Waage", "scale", "balance"),
    pressure: L("Tankdruck", "tank pressure", "pression de cuve"),
    bubbles: L("Blasenzähler", "bubble counter", "compteur de bulles"),
    bottle_pressure: L("Messflasche", "measurement bottle", "bouteille témoin"),
    bottle_temperature: L("Flaschentemperatur", "bottle temperature", "température de la bouteille"),
  })[code] || code;
const bottleAction = (state) =>
  ({
    high: L(
      "Flaschen auf 0–2 °C kühlen und die Messflasche täglich ablesen.",
      "Cool the bottles to 0–2 °C and read the measurement bottle daily.",
      "Refroidir les bouteilles à 0–2 °C et relever la bouteille témoin chaque jour.",
    ),
    danger: L(
      "Sofort auf 0–2 °C kühlen. Flaschen nur mit Schutzbrille und Handschuhen anfassen.",
      "Cool to 0–2 °C at once. Handle the bottles only with safety glasses and gloves.",
      "Refroidir tout de suite à 0–2 °C. Manipuler les bouteilles uniquement avec lunettes et gants.",
    ),
  })[state] || "";

/* ---------- Hilfen ---------- */
const nf = (x, d = 1) =>
  x == null || !Number.isFinite(Number(x))
    ? "–"
    : Number(x).toLocaleString(LOCALE[LANG], { minimumFractionDigits: d, maximumFractionDigits: d });
const nfs = (x) => nf(x, Math.abs(x) < 10 ? 1 : 0);
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const num = (s) => (s == null ? NaN : parseFloat(String(s).trim().replace(/\s/g, "").replace(",", ".").replace("−", "-")));
const inputNum = (x, d = 1) => (x == null ? "" : String(Math.round(x * 10 ** d) / 10 ** d).replace(".", LANG === "en" ? "." : ","));
const pad = (n) => String(n).padStart(2, "0");
const q15 = (d) => new Date(Math.round(d.getTime() / 9e5) * 9e5);
const fmtDay = (d) => {
  const r = q15(d);
  return LANG === "de" ? `${wd(r)} ${pad(r.getDate())}.${pad(r.getMonth() + 1)}.` : `${wd(r)} ${pad(r.getDate())}/${pad(r.getMonth() + 1)}`;
};
const atHour = (h) => L(`${h} Uhr`, `${pad(h)}:00`, `${h} h`);
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
  if (s < 90) return L("gerade eben", "just now", "à l'instant");
  const [n, unit] = s < 5400 ? [Math.round(s / 60), "min"] : s < 172800 ? [Math.round(s / 3600), "h"] : [Math.round(s / 86400), null];
  if (unit) return L(`vor ${n} ${unit}`, `${n} ${unit} ago`, `il y a ${n} ${unit}`);
  return L(`vor ${n} Tagen`, `${n} days ago`, `il y a ${n} jours`);
};
function inWords(hours) {
  if (hours < 0.75) return L("In weniger als einer Stunde.", "In less than an hour.", "Dans moins d'une heure.");
  if (hours < 1.5) return L("In etwa einer Stunde.", "In about an hour.", "Dans environ une heure.");
  const h = Math.round(hours);
  if (hours < 30) return L(`In etwa ${h} Stunden.`, `In about ${h} hours.`, `Dans environ ${h} heures.`);
  const half = Math.round(hours / 12) / 2;
  const n = nf(half, half % 1 ? 1 : 0);
  const words = WORDS[LANG][half] || L(`${n} Tagen`, `${n} days`, `${n} jours`);
  return L(`In etwa ${words}.`, `In about ${words}.`, `Dans environ ${words}.`);
}
function windowText(start, end) {
  if (!start || !end) return null;
  const a = q15(start);
  const b = q15(end);
  if (LANG === "en")
    return a.toDateString() === b.toDateString()
      ? `${wd(a)} ${fmtHM(a)}–${fmtHM(b)}`
      : `${wd(a)} ${fmtHM(a)} – ${wd(b)} ${fmtHM(b)}`;
  const unit = L("Uhr", "", "h");
  return a.toDateString() === b.toDateString()
    ? `${wd(a)} ${pad(a.getHours())}–${pad(b.getHours())} ${unit}`
    : `${wd(a)} ${pad(a.getHours())} – ${wd(b)} ${pad(b.getHours())} ${unit}`;
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
/* Fehler der Integration: bekannte Schlüssel in der Sprache des Panels, sonst die Meldung von Home Assistant */
const errText = (err) => {
  const p = err?.translation_placeholders || {};
  const known = {
    bottling_needs_sugar: () =>
      L(
        "Zum Abfüllen braucht es einen aktuellen Restzucker: erst messen, dann abfüllen.",
        "Bottling needs a current residual sugar: measure first, then bottle.",
        "La mise en bouteille demande un sucre résiduel actuel : mesurer d'abord, puis mettre en bouteille.",
      ),
    pair_needs_both: () =>
      L("Für Refraktometer + Dichte braucht es beide Werte.", "Refractometer + density needs both values.", "Réfractomètre + densité demande les deux valeurs."),
    no_entry: () => L(`Kein Eintrag ${p.kind} um ${p.time}.`, `No ${p.kind} entry at ${p.time}.`, `Aucune entrée ${p.kind} à ${p.time}.`),
    unknown_batch: () => L("Diesen Ansatz gibt es nicht mehr.", "This batch no longer exists.", "Cette cuvée n'existe plus."),
  };
  const key = err?.translation_key || err?.error_key;
  if (known[key]) return known[key]();
  if (err?.code === "not_found") return L("Ansatz nicht gefunden.", "Batch not found.", "Cuvée introuvable.");
  return err?.message || err?.code || String(err);
};

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
.seg.grid3 button { padding: 9px 4px; font-size: 11px; background: var(--screen); border: 0; hyphens: auto; }
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
.answer.long { font-size: clamp(24px, 7cqi, 32px); }
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
.leaders > div { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0 6px; }
.leaders dt { flex: 1; display: flex; align-items: baseline; gap: 6px; min-width: 0; }
.leaders dt::after { content: ""; flex: 1; min-width: 10px; border-bottom: 2px dotted var(--rule); transform: translateY(-4px); }
.leaders dd { margin: 0; flex: none; font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
.leaders .warn dd, .leaders .warn dt { color: var(--red); }
.leaders small { font-weight: 400; color: var(--muted); }
.leaders dd.sub { flex-basis: 100%; font-size: 10.5px; font-weight: 400; }

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
.langs { display: flex; gap: 10px; }
.langs .link[aria-pressed="true"] { color: var(--ink); font-weight: 700; border-bottom-color: transparent; cursor: default; }
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
    const lang = store.get("lang") || langOf(hass?.language); // eigene Wahl im Panel, sonst die Sprache in Home Assistant
    if (lang !== LANG) {
      LANG = lang;
      if (!first) this._relabel();
    }
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
    root.innerHTML = `<style>${CSS}</style><div class="root" id="root" lang="${LANG}"><p class="loading">${L("TIPSYLAB lädt …", "TIPSYLAB is loading …", "TIPSYLAB se charge …")}</p></div>`;
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

  /* Sprache gewechselt: Gerüst neu bauen, Eingaben bleiben im Zustand */
  _relabel() {
    const root = this.$("root");
    if (root) root.lang = LANG;
    this._shape = "";
    this._render();
  }

  _langs() {
    return `<span class="langs" role="group" aria-label="${L("Sprache", "Language", "Langue")}">${LANGS.map(
      (k) => `<button class="link" type="button" data-act="lang" data-lang="${k}" aria-pressed="${k === LANG}" lang="${k}">${k.toUpperCase()}</button>`,
    ).join("")}</span>`;
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
    const today = ["today", L("Heute", "Today", "Aujourd'hui")];
    const measure = ["measure", L("Messung", "Measure", "Mesure")];
    if (b.mode === "charmat") return [["tank", L("Tank", "Tank", "Cuve")], measure];
    if (b.bottling) return [today, measure]; // nach dem Abfüllen ändert das Ziel nichts mehr
    return [today, measure, ["target", L("Ziel", "Target", "Objectif")]];
  }

  /* Gerüst neu bauen, wenn sich Ansätze, Auswahl oder Breite ändern; sonst nur Werte setzen,
     damit Eingaben beim Nachladen nicht verloren gehen. */
  _render() {
    if (!this.$("root")) return;
    const b = this._current();
    const shape = this._archive
      ? `archive#${(this._house?.archive || []).length}#${this._narrow}`
      : b
        ? `${this._batches.map((x) => `${x.entry_id}:${x.mode}:${x.name}:${x.bottling ? 1 : 0}:${x.closed ? 1 : 0}`).join("|")}#${b.entry_id}#${this._narrow}`
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
          <div class="batch"><span class="kicker">TIPSYLAB</span><b>${
            this._err ? L("Keine Verbindung", "No connection", "Pas de connexion") : L("Noch kein Ansatz", "No batch yet", "Aucune cuvée")
          }</b></div></header>
        <section class="screen solo" style="margin-top:18px">
          ${
            this._err
              ? `<p class="say">${L("Die Integration antwortet nicht:", "The integration does not answer:", "L'intégration ne répond pas :")} ${esc(this._err)}</p>
                 <button class="primary" type="button" data-act="retry">${L("Neu laden", "Reload", "Recharger")}</button>`
              : `<p class="say">${L(
                  "Leg einen Ansatz an: Name, Betriebsart, Start-Brix und Volumen. Spindel, Blasenzähler und Temperaturfühler verbindest du gleich mit.",
                  "Create a batch: name, mode, starting Brix and volume. You connect hydrometer, bubble counter and temperature probe right after.",
                  "Crée une cuvée : nom, mode, Brix de départ et volume. Densimètre, compteur de bulles et sonde de température se connectent juste après.",
                )}</p>
                 <button class="primary" type="button" data-act="add-batch">${L("Ansatz anlegen", "Create batch", "Créer une cuvée")}</button>`
          }
        </section>
        <footer class="foot">${this._langs()}</footer>`;
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
        ? `<nav class="seg batches" aria-label="${L("Ansatz", "Batch", "Cuvée")}">${this._batches
            .map(
              (x) =>
                `<button type="button" data-act="batch" data-id="${esc(x.entry_id)}" aria-pressed="${x.entry_id === b.entry_id}">${esc(x.name)}<small>${modeLabel(x.mode) || esc(x.mode)}</small></button>`,
            )
            .join("")}</nav>`
        : "";
    root.innerHTML = `
      <header class="top">${this._menuButton()}<span class="logo" aria-hidden="true"></span>
        <div class="batch"><span class="kicker" id="h-sub"></span><b>${esc(b.name)}</b></div>
        <span class="live" id="h-live" hidden><i></i>LIVE</span>
      </header>
      ${batches}
      <nav class="seg tabs" aria-label="${L("Ansicht", "View", "Vue")}">${tabs
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
        <button class="link" type="button" data-act="add-batch">${L("+ Neuer Ansatz", "+ New batch", "+ Nouvelle cuvée")}</button>
        <button class="link" type="button" data-act="open-integration">${L("Ansätze verwalten", "Manage batches", "Gérer les cuvées")}</button>
        <button class="link" type="button" data-act="archive">${L("Archiv", "Archive", "Archives")}${
          this._house?.archive?.length ? ` (${this._house.archive.length})` : ""
        }</button>
        ${this._langs()}
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
      <p class="eyebrow">${still ? L("Durchgegoren", "Fermented dry", "Fin de fermentation") : L("Abfüllen", "Bottling", "Mise en bouteille")}</p>
      <p class="answer" id="d-day">–</p>
      <p class="answer-sub" id="d-sub"></p>
      <p class="fine" id="d-window"></p>
      <p class="say" id="d-say"></p>
      <p class="hint" id="d-warn" hidden></p>
      <p class="hint" id="src-hint" hidden></p>
      <p class="fine" id="d-notes" hidden></p>
      <svg class="windowbar" id="d-wbar" viewBox="0 0 320 46" role="img" aria-label="${L("Fenster auf der Zeitachse", "Window on the time axis", "Fenêtre sur l'axe du temps")}"></svg>
      <div class="control">
        <label for="d-whatif">${L("Keller", "Cellar", "Cave")}</label>
        <input type="range" id="d-whatif" data-in="whatif" min="6" max="26" step="1" value="15">
        <output id="d-whatif-out" for="d-whatif">15 °C</output>
      </div>
      <p class="fine" id="d-whatif-line" hidden></p>
      <p class="hint" id="d-whatif-hint" hidden></p>
      <dl class="leaders">
        <div><dt>${L("Restzucker", "Residual sugar", "Sucre résiduel")}</dt><dd id="d-sugar">–</dd></div>
        <div><dt>${abvEnd()}</dt><dd id="d-abv">–</dd></div>
        <div><dt>${L("Gärung", "Fermentation", "Fermentation")}</dt><dd id="d-rate">–</dd></div>
        ${
          still
            ? `<div><dt>${L("Trocken unter", "Dry below", "Sec sous")}</dt><dd id="d-dry">–</dd></div>`
            : `<div id="d-pnow-row"><dt>${L("Druck, wenn jetzt", "Pressure if now", "Pression si maintenant")}</dt><dd id="d-pnow">–</dd><dd class="sub" id="d-pnow-sub" hidden></dd></div>
               <div><dt>${L("Ziel beim Öffnen", "Target at opening", "Objectif à l'ouverture")}</dt><dd id="d-ptarget">–</dd></div>`
        }
        <div id="d-plan-row" hidden><dt>${L("Solltemperatur", "Set temperature", "Consigne")}</dt><dd id="d-plan">–</dd></div>
      </dl>
      <p class="fine" id="d-abv-hint" hidden></p>
      <svg class="chart" id="d-chart" viewBox="0 0 320 196" role="img" aria-label="${L(
        "Restzucker der letzten Tage mit Prognose",
        "Residual sugar of the last days with forecast",
        "Sucre résiduel des derniers jours avec prévision",
      )}"></svg>
      <button class="primary" type="button" data-act="goto-measure">${L("+ Messung", "+ Measurement", "+ Mesure")}</button>
      <p class="status" id="d-status"></p>`;
  }

  _html_bottle(b) {
    const petnat = b.mode === "petnat";
    return `
      <p class="eyebrow" id="f-eyebrow">${L("In der Flasche", "In the bottle", "En bouteille")}</p>
      <p class="answer" id="f-answer">–</p>
      <p class="answer-sub" id="f-sub"></p>
      <p class="say" id="f-say"></p>
      <p class="hint" id="f-warn" hidden></p>
      <p class="hint" id="src-hint" hidden></p>
      <dl class="leaders">
        <div><dt>${L("Abgefüllt", "Bottled", "Mis en bouteille")}</dt><dd id="f-bottled">–</dd></div>
        ${
          petnat
            ? `<div><dt>${L("Erwartet beim Öffnen", "Expected at opening", "Attendu à l'ouverture")}</dt><dd id="f-expected">–</dd></div>
               <div id="f-worst-row"><dt>${worst20()}</dt><dd id="f-worst">–</dd></div>
               <div><dt>${L("Flaschengärung", "Bottle fermentation", "Prise de mousse")}</dt><dd id="f-progress">–</dd></div>`
            : ""
        }
        <div><dt>${abvEnd()}</dt><dd id="d-abv">–</dd></div>
      </dl>
      <p class="fine" id="d-abv-hint" hidden></p>
      ${
        petnat
          ? `<svg class="chart" id="f-chart" viewBox="0 0 320 170" role="img" aria-label="${L(
              "Druck der Messflasche bei 20 °C",
              "Pressure of the measurement bottle at 20 °C",
              "Pression de la bouteille témoin à 20 °C",
            )}"></svg>`
          : ""
      }
      <p class="fine" id="f-forecast" hidden></p>
      ${petnat && !b.closed ? `<button class="primary" type="button" data-act="goto-bottle">${L("+ Messflasche", "+ Measurement bottle", "+ Bouteille témoin")}</button>` : ""}
      <p class="status" id="f-status"></p>
      <p class="status"><button class="link" type="button" data-act="close-batch" id="f-close">${L("Ansatz abschließen", "Close batch", "Clôturer la cuvée")}</button></p>`;
  }

  _html_measure(b) {
    const m = this._m;
    const volume = L("Neues Volumen in Litern", "New volume in litres", "Nouveau volume en litres");
    const note = L("Notiz", "Note", "Note");
    return `
      ${
        b.closed
          ? `<p class="fine">${L(
              "Abgeschlossen und im Archiv. Löschst du „Abgeschlossen“ im Verlauf, lässt sich wieder messen.",
              "Closed and archived. Delete “Closed” in the history to measure again.",
              "Clôturée et archivée. Supprime « Clôturé » dans l'historique pour mesurer à nouveau.",
            )}</p>`
          : ""
      }
      <div${b.closed ? " hidden" : ""}>
      <p class="eyebrow">${L("Was hast du gemessen?", "What did you measure?", "Qu'as-tu mesuré ?")}</p>
      <div class="seg grid3" role="group" aria-label="${L("Messart", "Kind of measurement", "Type de mesure")}">${Object.entries(kinds())
        .map(([k, v]) => `<button type="button" data-act="mkind" data-kind="${k}" aria-pressed="${k === m.kind}">${v.label}</button>`)
        .join("")}</div>
      <div class="seg tight" id="m-units" role="group" aria-label="${L("Dichte in", "Density in", "Densité en")}">${Object.entries(densityUnits())
        .map(
          ([k, v]) =>
            `<button type="button" data-act="munit" data-unit="${k}" aria-pressed="${k === m.unit}">${L("Dichte in", "Density in", "Densité en")} ${v.label}</button>`,
        )
        .join("")}</div>
      <div class="big-input">
        <input id="m-value" data-in="mval" type="text" inputmode="decimal" autocomplete="off" aria-label="${L("Messwert", "Reading", "Valeur mesurée")}" value="${esc(m.value)}">
        <span id="m-unit"></span>
      </div>
      <p class="fine" id="m-help"></p>
      <div class="field" id="m-value2-row">
        <label for="m-value2" id="m-value2-label"></label>
        <input id="m-value2" data-in="mval2" type="text" inputmode="decimal" autocomplete="off" value="${esc(m.value2)}">
        <span id="m-unit2"></span>
      </div>
      <div class="field" id="m-temp-row">
        <label for="m-temp">${L("Temperatur der Flasche", "Bottle temperature", "Température de la bouteille")}</label>
        <input id="m-temp" data-in="mtemp" type="text" inputmode="decimal" autocomplete="off" value="${esc(m.temp)}">
        <span>°C</span>
      </div>
      <div class="field wide">
        <label for="m-time">${L("Gemessen", "Measured", "Mesuré le")}</label>
        <input id="m-time" data-in="mtime" type="datetime-local" value="${esc(m.time)}" aria-describedby="m-time-help">
      </div>
      <p class="fine" id="m-time-help">${L("Ohne Zeitangabe gilt jetzt.", "Without a time, it counts as now.", "Sans heure, c'est maintenant.")}</p>
      <div class="field wide">
        <label for="m-note">${note}</label>
        <input id="m-note" data-in="mnote" type="text" autocomplete="off" value="${esc(m.note)}" placeholder="${L("optional", "optional", "facultatif")}">
      </div>
      <div class="result" aria-live="polite">
        <p class="eyebrow">${L("Was sich ändert", "What changes", "Ce qui change")}</p>
        <dl class="leaders" id="m-leaders"></dl>
        <p class="fine" id="m-result-msg"></p>
      </div>
      <button class="primary" type="button" data-act="msave" id="m-save">${L("Speichern", "Save", "Enregistrer")}</button>
      <p class="toast" id="m-toast" aria-live="polite"></p>
      <p class="eyebrow">${L("Ereignis", "Event", "Événement")}</p>
      <div class="event-row">
        <select id="ev-kind" data-ch="evkind" aria-label="${L("Art des Ereignisses", "Kind of event", "Type d'événement")}">${Object.entries(events())
          .map(([k, v]) => `<option value="${k}"${k === this._ev.kind ? " selected" : ""}>${v}</option>`)
          .join("")}</select>
        <input id="ev-note" data-in="evnote" type="text" autocomplete="off" placeholder="${note}" aria-label="${L("Notiz zum Ereignis", "Note on the event", "Note sur l'événement")}" value="${esc(this._ev.note)}">
        <button class="secondary" type="button" data-act="esave">${L("Eintragen", "Add", "Ajouter")}</button>
        <input class="ev-value" id="ev-value" data-in="evval" type="text" inputmode="decimal" autocomplete="off" placeholder="${volume}" aria-label="${volume}" value="${esc(this._ev.value)}"${this._ev.kind === "volume" ? "" : " hidden"}>
      </div>
      <p class="toast" id="ev-toast" aria-live="polite"></p>
      </div>
      <p class="eyebrow">${L("Verlauf", "History", "Historique")}</p>
      <ol class="log" id="m-log"></ol>`;
  }

  _html_target(b) {
    const petnat = b.mode === "petnat";
    const field = (id, label, unit, key, opts = "") =>
      `<div class="field"${id === "t-malic" ? ' id="t-malic-row"' : ""}><label for="${id}">${label}</label><input id="${id}" data-in="tnum" data-field="${key}" ${opts} type="text" inputmode="decimal" autocomplete="off"><span>${unit}</span></div>`;
    const cap = L("Kronkorken bis", "crown cap up to", "capsule jusqu'à");
    const plan = L(
      "Leer lassen für keinen Plan. Die Prognose rechnet mit dem Plan;",
      "Leave empty for no plan. The forecast uses the plan;",
      "Laisser vide pour aucun plan. La prévision suit le plan ;",
    );
    const heater = b.has_heater
      ? L(
          "die Heizung bekommt die Solltemperatur von Home Assistant.",
          "the heater gets its set temperature from Home Assistant.",
          "le chauffage reçoit sa consigne de Home Assistant.",
        )
      : L(
          "mit einem Shelly an der Heizmanschette regelt Home Assistant danach.",
          "with a Shelly on the heating jacket, Home Assistant controls by it.",
          "avec un Shelly sur la ceinture chauffante, Home Assistant régule d'après lui.",
        );
    return `
      ${
        petnat
          ? `<p class="eyebrow">${L("Druck beim Öffnen, 10–20 °C", "Opening pressure, 10–20 °C", "Pression à l'ouverture, 10–20 °C")}</p>
             <p class="answer" id="t-big">–</p>
             <div class="control two">
               <input type="range" id="t-target" data-in="ttarget" min="1.5" max="4.5" step="0.1" aria-label="${L(
                 "Druck beim Öffnen bei 20 °C",
                 "Opening pressure at 20 °C",
                 "Pression à l'ouverture à 20 °C",
               )}">
               <output id="t-out" for="t-target"></output>
             </div>
             <div class="scale"><span>${nf(1.5)}</span><span>${L(`frisante bis ${nf(2.5)}`, `semi-sparkling ≤ ${nf(2.5)}`, `pétillant ≤ ${nf(2.5)}`)}</span><span>${L(
               "espumante ab 3",
               "sparkling ≥ 3",
               "mousseux ≥ 3",
             )}</span><span>${nf(4.5)}</span></div>
             <p class="category" id="t-cat"></p>
             <p class="eyebrow">${L("Flasche", "Bottle", "Bouteille")}</p>
             <div class="seg" role="group" aria-label="${L("Flasche", "Bottle", "Bouteille")}">
               <button type="button" data-act="bottle" data-bottle="330">330 ml<small>${cap} ${nf(4.5)} bar</small></button>
               <button type="button" data-act="bottle" data-bottle="750">750 ml<small>${cap} 6 bar</small></button>
             </div>
             <p class="eyebrow">${L("Malo in der Flasche", "Malolactic in the bottle", "Malo en bouteille")}</p>
             <div class="seg" role="group" aria-label="${L("Malo mitrechnen", "Count malolactic", "Compter la malo")}">
               <button type="button" data-act="malo" data-on="0">${L("Nicht mitrechnen", "Don't count", "Ne pas compter")}</button>
               <button type="button" data-act="malo" data-on="1">${L("Mitrechnen", "Count", "Compter")}</button>
             </div>
             ${field("t-malic", L("Äpfelsäure beim Abfüllen", "Malic acid at bottling", "Acide malique au tirage"), "g/L", "malic", 'data-min="0" data-max="10"')}`
          : `<p class="eyebrow">${L("Durchgären bis", "Ferment down to", "Fermenter jusqu'à")}</p>
             <p class="answer" id="t-big">–</p>
             ${field("t-dry", L("Trocken unter", "Dry below", "Sec sous"), "g/L", "dry", 'data-min="0" data-max="10"')}`
      }
      <p class="eyebrow">${L("Gefäß", "Vessel", "Cuve")}</p>
      ${field("t-vol", L("Volumen", "Volume", "Volume"), "L", "vol", 'data-min="1" data-max="100000"')}
      <p class="fine">${L(
        "Von Hand eingeben und nach jedem Abstich anpassen.",
        "Enter by hand and adjust after each racking.",
        "À saisir à la main et à ajuster après chaque soutirage.",
      )}</p>
      <p class="eyebrow">${L("Temperaturplan", "Temperature plan", "Plan de température")}</p>
      ${field("t-tstart", L("Zu Beginn", "At start", "Au début"), "°C", "tStart", 'data-min="-5" data-max="35" data-optional="1" placeholder="–"')}
      ${field("t-tswitch", L("Umschalten ab", "Switch at", "Changer à"), "g/L", "tSwitch", 'data-min="0" data-max="300" data-optional="1" placeholder="–"')}
      ${field("t-tlate", L("Danach", "Afterwards", "Ensuite"), "°C", "tLate", 'data-min="-5" data-max="35" data-optional="1" placeholder="–"')}
      <p class="fine" id="t-plan-note">${plan} ${heater}</p>
      ${
        petnat
          ? `<dl class="leaders">
               <div><dt>${L("Abfüllen bei", "Bottle at", "Tirer à")}</dt><dd id="t-sugar">–</dd></div>
               <div><dt>${L("Malo-Ausgleich", "Malolactic offset", "Correction malo")}</dt><dd id="t-malo">–</dd></div>
               <div><dt>${L("Öffnen bei 10 °C", "Opening at 10 °C", "Ouverture à 10 °C")}</dt><dd id="t-p10">–</dd></div>
               <div><dt>${L("Öffnen bei 20 °C", "Opening at 20 °C", "Ouverture à 20 °C")}</dt><dd id="t-p20">–</dd></div>
               <div id="t-limit-row"><dt>${worst20()}</dt><dd id="t-limit">–</dd></div>
             </dl>
             <p class="note">${L(
               "Gerechnet wird so, als würde der ganze Restzucker in der Flasche vergären. Mit Torulaspora ist das nicht sicher; dann wird es leiser.",
               "The calculation assumes all residual sugar ferments in the bottle. With Torulaspora that is not certain; then it comes out quieter.",
               "Le calcul suppose que tout le sucre résiduel fermente en bouteille. Avec Torulaspora ce n'est pas sûr ; le vin sera alors moins vif.",
             )}</p>
             <p class="fine">${L(
               "Die Faustregel „4 g/L pro bar“ stimmt nur bei etwa 12 °C. Grenzen: deine Werte für Kronkorken.",
               "The rule of thumb “4 g/L per bar” only holds at about 12 °C. Limits: your values for crown caps.",
               "La règle « 4 g/L par bar » ne vaut qu'autour de 12 °C. Limites : tes valeurs pour les capsules.",
             )}</p>`
          : ""
      }
      <button class="primary" type="button" data-act="tsave" id="t-save" disabled>${L("Gespeichert", "Saved", "Enregistré")}</button>
      <p class="toast" id="t-toast" aria-live="polite"></p>`;
  }

  _html_tank() {
    return `
      <p class="eyebrow">${L("Sollwert jetzt", "Set point now", "Consigne actuelle")}</p>
      <p class="answer" id="c-big">–</p>
      <p class="answer-sub" id="c-sub"></p>
      <p class="say" id="c-say"></p>
      <p class="hint" id="src-hint" hidden></p>
      <div class="control">
        <label for="c-target">${L("Flasche", "Bottle", "Bouteille")}</label>
        <input type="range" id="c-target" data-in="ctarget" min="1.5" max="5" step="0.1" aria-label="${L(
          "Druck in der Flasche bei 20 °C",
          "Pressure in the bottle at 20 °C",
          "Pression en bouteille à 20 °C",
        )}">
        <output id="c-tout" for="c-target"></output>
      </div>
      <p class="fine" id="c-table"></p>
      <button class="primary" type="button" data-act="csave" id="c-save" hidden>${L("Ziel übernehmen", "Apply target", "Appliquer l'objectif")}</button>
      <p class="toast" id="c-toast" aria-live="polite"></p>
      <dl class="leaders">
        <div><dt>${L("CO₂-Ziel im Tank", "CO₂ target in tank", "Objectif CO₂ en cuve")}</dt><dd id="c-co2t">–</dd></div>
        <div><dt>${L("Gelöstes CO₂", "Dissolved CO₂", "CO₂ dissous")}</dt><dd id="c-co2">–</dd></div>
        <div><dt>${L("Tanktemperatur", "Tank temperature", "Température cuve")}</dt><dd id="c-temp">–</dd></div>
        <div id="c-prv-row"><dt>${L("Sicherheitsventil", "Safety valve", "Soupape")}</dt><dd id="c-prv">–</dd></div>
      </dl>
      <p class="note">${L(
        "Das mechanische Sicherheitsventil bleibt Pflicht. Die Regelung ersetzt es nicht.",
        "The mechanical safety valve remains mandatory. The control does not replace it.",
        "La soupape de sécurité mécanique reste obligatoire. La régulation ne la remplace pas.",
      )}</p>
      <svg class="chart" id="c-chart" viewBox="0 0 320 150" role="img" aria-label="${L(
        "Tankdruck der letzten drei Tage mit Sollwert",
        "Tank pressure of the last three days with set point",
        "Pression de cuve des trois derniers jours avec consigne",
      )}"></svg>
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

  /* Die große Antwort: Ein langes Wort („MAINTENANT“) bekommt eine kleinere Schrift statt zu brechen */
  _answer(id, text) {
    this._set(id, text);
    this.$(id)?.classList.toggle("long", Math.max(...text.split(/\s+/).map((w) => w.length)) > 8);
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
      err.textContent = this._err
        ? L(`Keine Verbindung, zeige den letzten Stand: ${this._err}`, `No connection, showing the last state: ${this._err}`, `Pas de connexion, dernier état affiché : ${this._err}`)
        : "";
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
    this._updateSources(b);
  }

  /* Quelle stumm oder Akku schwach: Warnung über den Zahlen (Koralle, weil man etwas tun muss) */
  _updateSources(b) {
    const parts = [];
    const silent = b.silent || [];
    const h = b.silent_after_h ?? 3;
    if (silent.length) {
      const names = silent.map(sourceName).join(", ");
      parts.push(
        L(
          `Seit über ${h} h keine Werte: ${names}. Strom, WLAN oder Bluetooth-Reichweite prüfen.`,
          `No readings for over ${h} h: ${names}. Check power, Wi-Fi or Bluetooth range.`,
          `Aucune valeur depuis plus de ${h} h : ${names}. Vérifier l'alimentation, le Wi-Fi ou la portée Bluetooth.`,
        ),
      );
    }
    if (b.battery_low && b.battery) {
      const [name, pct] = b.battery;
      parts.push(
        L(
          `Akku von ${name} bei ${Math.round(pct)} %: bald laden oder tauschen.`,
          `Battery of ${name} at ${Math.round(pct)} %: charge or replace it soon.`,
          `Batterie de ${name} à ${Math.round(pct)} % : la recharger ou la remplacer bientôt.`,
        ),
      );
    }
    this._set("src-hint", parts.join(" "));
    this._show("src-hint", parts.length > 0);
  }

  _newest(b) {
    const times = Object.values(b.latest || {})
      .filter(Boolean)
      .map((p) => Date.parse(p[0]));
    return times.length ? Math.max(...times) : null;
  }

  _updateHeader(b) {
    const parts = [modeLabel(b.mode) || b.mode];
    const start = Date.parse(b.start);
    if (Number.isFinite(start)) {
      const day = Math.max(0, Math.floor((Date.now() - start) / DAY));
      parts.push(L(`Tag ${day}`, `Day ${day}`, `Jour ${day}`));
    }
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
      day = L("STOCKT?", "STUCK?", "BLOQUÉE ?");
      sub = L("KAUM ABBAU", "BARELY MOVING", "PRESQUE À L'ARRÊT");
      say = L(
        "Der Zucker fällt kaum, ohne dass es kühler wurde. Eine Messung zeigt, ob die Gärung wirklich steht.",
        "The sugar barely falls although it did not get cooler. A measurement shows whether fermentation has really stopped.",
        "Le sucre baisse à peine sans que la température ait baissé. Une mesure montre si la fermentation est vraiment arrêtée.",
      );
    } else if (st === "dry") {
      day = L("TROCKEN", "DRY", "SEC");
      sub = `${nf(e.sugar)} G/L`;
      say = L(
        "Laut Schätzung durchgegoren. Eine Messung bestätigt es.",
        "Fermented dry according to the estimate. A measurement confirms it.",
        "Sec selon l'estimation. Une mesure le confirme.",
      );
    } else if (e.display_state === "late") {
      day = L("JETZT", "NOW", "MAINTENANT");
      sub = L("FENSTER VORBEI", "WINDOW PASSED", "FENÊTRE PASSÉE");
      const [t, n] = [nf(e.target_sugar), nfs(e.sugar)];
      win = L(`Ziel ${t} g/L, aktuell ${n} g/L`, `Target ${t} g/L, now ${n} g/L`, `Objectif ${t} g/L, actuel ${n} g/L`);
      const [a, z] = [nf(e.p_now_10), nf(e.p_now_20)];
      say = L(
        `Der Restzucker liegt schon unter dem Ziel. Jetzt abgefüllt gibt das beim Öffnen etwa ${a}–${z} bar.`,
        `The residual sugar is already below target. Bottled now, that gives about ${a}–${z} bar at opening.`,
        `Le sucre résiduel est déjà sous l'objectif. Mis en bouteille maintenant, cela donne environ ${a}–${z} bar à l'ouverture.`,
      );
    } else if (e.display_state === "now") {
      day = L("JETZT", "NOW", "MAINTENANT");
      if (end) {
        const until = `${fmtDay(end)} ${fmtHM(end)}`;
        sub = L(`BIS ${until}`, `UNTIL ${until}`, `JUSQU'À ${until}`).toUpperCase();
        win = L(`Fenster endet ${until}`, `Window ends ${until}`, `La fenêtre se ferme ${until}`);
      }
      say = still
        ? L("Fast trocken. Eine Messung bestätigt es.", "Almost dry. A measurement confirms it.", "Presque sec. Une mesure le confirme.")
        : L(
            "Du bist im Fenster. Eine letzte Messung bestätigt es.",
            "You are in the window. One last measurement confirms it.",
            "Tu es dans la fenêtre. Une dernière mesure le confirme.",
          );
    } else if (best) {
      day = fmtDay(best).toUpperCase();
      sub = `≈ ${atHour(roundHour(best).getHours())}`.toUpperCase();
      if (start && end) {
        const range = `${fmtDay(start)} ${fmtHM(start)} – ${fmtDay(end)} ${fmtHM(end)}`;
        win = L(`Fenster ${range}`, `Window ${range}`, `Fenêtre ${range}`);
      }
      say = inWords((best - now) / HOUR);
      if (e.measurement_recommended && e.window_h != null && e.window_h_measured != null && e.window_h - e.window_h_measured >= 2) {
        const [a, z] = [nf(e.window_h, 0), nf(e.window_h_measured, 0)];
        say += L(
          ` Eine Messung jetzt macht das Fenster von ±${a} h auf ±${z} h enger.`,
          ` A measurement now narrows the window from ±${a} h to ±${z} h.`,
          ` Une mesure maintenant resserre la fenêtre de ±${a} h à ±${z} h.`,
        );
      } else if (e.measurement_recommended)
        say += L(" Eine Messung jetzt macht das Fenster enger.", " A measurement now narrows the window.", " Une mesure maintenant resserre la fenêtre.");
    } else if (e.sugar != null) {
      day = L("GÄRT", "FERMENTING", "FERMENTE");
      if (b.s0) {
        const half = Math.round(b.s0 / 2);
        sub = L(`PROGNOSE AB ≈ ${half} G/L`, `FORECAST FROM ≈ ${half} G/L`, `PRÉVISION DÈS ≈ ${half} G/L`);
      }
      say = L(
        "Die Prognose beginnt, wenn etwa die Hälfte des Zuckers vergoren ist. Bis dahin hilft eine Messung pro Tag.",
        "The forecast starts once about half of the sugar has fermented. Until then, one measurement a day helps.",
        "La prévision commence quand environ la moitié du sucre a fermenté. D'ici là, une mesure par jour aide.",
      );
    } else {
      sub = L("NOCH KEINE WERTE", "NO READINGS YET", "PAS ENCORE DE VALEURS");
      say = L(
        "Trag eine Messung ein oder verbinde Spindel und Blasenzähler.",
        "Enter a measurement or connect hydrometer and bubble counter.",
        "Saisis une mesure ou connecte densimètre et compteur de bulles.",
      );
    }
    this._answer("d-day", day);
    this._set("d-sub", sub);
    this._set("d-window", win);
    this._set("d-say", say);

    const warn =
      !still && e.limit_ok === false
        ? L(
            "Im ungünstigen Fall über der Grenze der Flasche. Ziel senken oder die größere Flasche nehmen.",
            "In the worst case above the bottle's limit. Lower the target or use the larger bottle.",
            "Dans le pire cas au-dessus de la limite de la bouteille. Baisser l'objectif ou prendre la grande bouteille.",
          )
        : "";
    this._set("d-warn", warn);
    this._show("d-warn", Boolean(warn));
    const notes = ["fermenting", "approaching", "window"].includes(st) ? notesText(e.notes || [], e).join(" · ") : "";
    this._set("d-notes", notes);
    this._show("d-notes", Boolean(notes));

    this._set("d-sugar", e.sugar != null ? `${nfs(e.sugar)} ± ${nf(e.sigma)} g/L` : "–");
    this._updateAbv(e, still);
    this._set("d-rate", e.rate != null ? L(`${nf(e.rate)} g/L am Tag`, `${nf(e.rate)} g/L per day`, `${nf(e.rate)} g/L par jour`) : "–");
    if (still) this._set("d-dry", `${nf(b.settings.dry_sugar_g_l)} g/L`);
    else {
      const pnow = e.p_now_10 != null ? `${nf(e.p_now_10)}–${nf(e.p_now_20)} bar` : "–";
      let risk = "";
      // Wahrscheinlichkeiten nur, wenn das Abfüllen ansteht; vorher ist „zu früh“ ohnehin klar
      const due = ["soon", "now", "late"].includes(e.display_state);
      const pct = (x) => (x < 0.01 ? "< 1" : x > 0.99 ? "> 99" : Math.round(x * 100));
      // Wahrscheinlichkeit als eigene Zeile unter dem Wert, damit die Beschriftung nicht umbricht
      if (due && e.p_over_limit != null && e.p_over_limit >= 0.01) {
        const x = pct(e.p_over_limit);
        risk = L(`Risiko über der Grenze: ${x} %`, `risk over the limit: ${x} %`, `risque au-delà de la limite : ${x} %`);
      } else if (due && e.p_over_target != null && e.p_over_target >= 0.05) {
        const x = pct(e.p_over_target);
        risk = L(`Risiko über dem Ziel: ${x} %`, `risk over the target: ${x} %`, `risque au-delà de l'objectif : ${x} %`);
      }
      this._set("d-pnow", pnow);
      this._set("d-pnow-sub", risk);
      this._show("d-pnow-sub", Boolean(risk));
      this.$("d-pnow-row")?.classList.toggle(
        "warn",
        (e.p_now_20 != null && e.p_now_20 > b.settings.target_bar_20c + 0.3) || (due && (e.p_over_limit ?? 0) >= 0.01),
      );
      this._set("d-ptarget", e.p_target_10 != null ? `${nf(e.p_target_10)}–${nf(e.p_target_20)} bar` : "–");
    }
    const plan = (b.settings.temp_plan || []).length > 0 && e.planned_temp != null;
    this._show("d-plan-row", plan);
    if (plan) this._set("d-plan", `${nf(e.planned_temp, 0)} °C${b.has_heater ? L(" · Heizung", " · heater", " · chauffage") : ""}`);

    const h = b.history || {};
    const parts = [];
    if (h.bpm_now != null) parts.push(`${L("Blasen", "Bubbles", "Bulles")} ${nf(h.bpm_now, 0)}/min`);
    if (b.latest?.gravity) parts.push(`${L("Spindel", "Hydrometer", "Densimètre")} ${nf(b.latest.gravity[1], 3)}`);
    if (b.latest?.weight) parts.push(`${L("Waage", "Scale", "Balance")} ${nf(b.latest.weight[1], b.latest.weight[1] < 100 ? 2 : 1)} kg`);
    if (b.latest?.temps) parts.push(`${nf(b.latest.temps[1])} °C`);
    if (b.battery) parts.push(`${L("Akku", "battery", "batterie")} ${Math.round(b.battery[1])} %`);
    const newest = this._newest(b);
    if (newest != null) parts.push(ago(newest));
    this._set("d-status", parts.join(" · ") || L("Noch keine Sensorwerte", "No sensor readings yet", "Pas encore de valeurs des capteurs"));

    this._updateWhatIf(b);
    this._drawWindowBar(e, now);
    this._drawSugarChart(b, e, now);
  }

  _updateAbv(e, still) {
    this._set("d-abv", e.abv_end != null ? `${nf(e.abv_end)} ± ${nf(e.abv_end_sigma)} % vol` : "–");
    let abvHint = "";
    if (e.abv_end != null) {
      const label = nf(e.abv_label, e.abv_label % 1 ? 1 : 0);
      abvHint = `<strong>${L(`Etikett ${label} % vol`, `Label ${label} % vol`, `Étiquette ${label} % vol`)}</strong>`;
      if (e.abv_label_ok) abvHint += ".";
      else if ((still || e.category === "still") && !e.abv_labs)
        abvHint += L(
          ", für einen Stillwein nur mit Laboranalyse.",
          ", for a still wine only with a lab analysis.",
          ", pour un vin tranquille seulement avec une analyse de labo.",
        );
      else if (e.abv_pairs > 0 || e.abv_labs > 0)
        abvHint += L(
          ", noch knapp: ein weiteres Messpaar oder eine Laboranalyse.",
          ", still tight: one more measurement pair or a lab analysis.",
          ", encore juste : une paire de mesures de plus ou une analyse de labo.",
        );
      else
        abvHint += L(
          ", noch zu unsicher: Refraktometer und Dichte an derselben Probe messen, am besten kurz vor dem Abfüllen.",
          ", still too uncertain: measure refractometer and density on the same sample, ideally just before bottling.",
          ", encore trop incertain : mesurer réfractomètre et densité sur le même échantillon, idéalement juste avant la mise en bouteille.",
        );
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
    this._set("f-eyebrow", L(`In der Flasche · Tag ${days}`, `In the bottle · day ${days}`, `En bouteille · jour ${days}`));
    this._set("f-bottled", `${fmtDay(bottled)} · ${nfs(bt.sugar)} ± ${nf(bt.sigma)} g/L`);
    let answer = L("ABGEFÜLLT", "BOTTLED", "EN BOUTEILLE");
    let sub = `${fmtDay(bottled).toUpperCase()} ${fmtHM(bottled)}`;
    let say = L(
      "Der Restzucker beim Abfüllen ist festgehalten. Messungen danach ändern ihn nicht mehr.",
      "The residual sugar at bottling is recorded. Later measurements no longer change it.",
      "Le sucre résiduel à la mise en bouteille est figé. Les mesures suivantes ne le changent plus.",
    );
    let warn = "";
    if (f) {
      const last = f.readings[f.readings.length - 1];
      this._set("f-expected", `${nf(f.expected_10)}–${nf(f.expected_20)} bar`);
      const ok = f.worst_20 <= f.limit;
      this._set("f-worst", `${nf(f.worst_20)} / ${nf(f.limit)} bar ${ok ? "✓" : "✕"}`);
      this.$("f-worst-row")?.classList.toggle("warn", !ok);
      const pct = f.progress != null ? Math.round(Math.max(0, Math.min(1.5, f.progress)) * 100) : null;
      this._set("f-progress", f.done ? L("durch", "done", "terminée") : pct != null ? `${pct} %` : "–");
      if (last) {
        answer = `${nf(last[3])} BAR`;
        const exp = nf(f.expected_20);
        sub = L(`BEI 20 °C · ERWARTET ${exp}`, `AT 20 °C · EXPECTED ${exp}`, `À 20 °C · ATTENDU ${exp}`);
        if (f.state === "danger" || f.state === "high") {
          say =
            f.state === "danger"
              ? L(
                  "Die Messflasche nähert sich der Grenze der Flasche.",
                  "The measurement bottle is approaching the bottle's limit.",
                  "La bouteille témoin approche de la limite de la bouteille.",
                )
              : L(
                  "Mehr Druck als erwartet: In der Flasche gärt mehr Zucker als geschätzt.",
                  "More pressure than expected: more sugar is fermenting in the bottle than estimated.",
                  "Plus de pression que prévu : plus de sucre fermente en bouteille qu'estimé.",
                );
          warn = bottleAction(f.state);
        } else if (f.done) {
          say = L(
            "Durchgegoren. Zum Schluss einmal bei 10 und einmal bei 20 °C ablesen, dann den Ansatz abschließen: Die Messflasche eicht das Modell für die nächsten Ansätze.",
            "Fermented out. Finally read it once at 10 and once at 20 °C, then close the batch: the measurement bottle calibrates the model for the next batches.",
            "Prise de mousse terminée. Pour finir, relever une fois à 10 et une fois à 20 °C, puis clôturer la cuvée : la bouteille témoin étalonne le modèle pour les cuvées suivantes.",
          );
        } else {
          const x = pct ?? "–";
          say = L(
            `Flaschengärung zu ${x} %. Läuft wie erwartet.`,
            `Bottle fermentation ${x} % done. Going as expected.`,
            `Prise de mousse à ${x} %. Tout se passe comme prévu.`,
          );
        }
      } else {
        answer = L("ABLESEN", "READ IT", "À RELEVER");
        sub = L("MESSFLASCHE", "MEASUREMENT BOTTLE", "BOUTEILLE TÉMOIN");
        say = L(
          "Die Messflasche nach 3, 7 und 14 Tagen ablesen, immer mit ihrer Temperatur. Die App rechnet auf 20 °C um.",
          "Read the measurement bottle after 3, 7 and 14 days, always with its temperature. The app converts to 20 °C.",
          "Relever la bouteille témoin après 3, 7 et 14 jours, toujours avec sa température. L'app ramène à 20 °C.",
        );
      }
      this._drawBottleChart(f, bottled);
    }
    this._answer("f-answer", answer);
    this._set("f-sub", sub);
    this._set("f-say", say);
    this._set("f-warn", warn);
    this._show("f-warn", Boolean(warn));
    this._updateAbv(e, b.mode === "still");

    const fc = bt.forecast_check || {};
    const parts = ["48", "24", "12"]
      .filter((h) => fc[h])
      .map((h) => {
        const txt = offBy(fc[h].error_h);
        return L(`${h} h vorher ${txt}`, `${h} h before: ${txt}`, `${h} h avant : ${txt}`);
      });
    this._set("f-forecast", parts.length ? `${L("Prognose", "Forecast", "Prévision")} ${parts.join(" · ")}` : "");
    this._show("f-forecast", parts.length > 0);
    this._show("f-close", !b.closed);
    this._set(
      "f-status",
      b.closed
        ? L("Abgeschlossen und im Archiv.", "Closed and archived.", "Clôturée et archivée.")
        : b.has_bottle_sensor
          ? L("Flaschenbox verbunden", "Bottle box connected", "Flaschenbox connectée")
          : "",
    );
  }

  _drawBottleChart(f, bottled) {
    const svg = this.$("f-chart");
    if (!svg) return;
    const W = 320;
    const H = 170;
    const Lm = 30;
    const R = 8;
    const T = 10;
    const B = 22;
    const pts = f.readings.map((r) => [(Date.parse(r[0]) - bottled) / DAY, r[3]]);
    const span = Math.max(28, Math.ceil(Math.max(f.days, ...pts.map((p) => p[0]), 0)) + 2);
    const top = Math.max(f.limit, ...pts.map((p) => p[1])) * 1.05;
    const x = (d) => Lm + (d / span) * (W - Lm - R);
    const y = (p) => T + (1 - Math.max(0, p) / top) * (H - T - B);
    let out = "";
    for (let p = 0; p <= top; p += 1) out += `<line class="grid" x1="${Lm}" x2="${W - R}" y1="${y(p)}" y2="${y(p)}"/><text x="${Lm - 4}" y="${y(p) + 3}" text-anchor="end">${p}</text>`;
    const dUnit = LANG === "fr" ? "j" : "d";
    for (let d = 0; d <= span; d += 7) out += `<text x="${x(d)}" y="${H - 6}" text-anchor="${d + 7 > span ? "end" : "middle"}">${d} ${dUnit}</text>`;
    const limit = `${nf(f.limit)} bar`;
    out += `<line class="setline" x1="${Lm}" x2="${W - R}" y1="${y(f.limit)}" y2="${y(f.limit)}"/><text class="targetlabel" x="${W - R}" y="${y(f.limit) - 4}" text-anchor="end">${L(`Grenze ${limit}`, `limit ${limit}`, `limite ${limit}`)}</text>`;
    const exp = nf(f.expected_20);
    out += `<line class="forecast" x1="${Lm}" x2="${W - R}" y1="${y(f.expected_20)}" y2="${y(f.expected_20)}"/><text class="label-ink" x="${Lm + 4}" y="${y(f.expected_20) - 4}">${L(`erwartet ${exp}`, `expected ${exp}`, `attendu ${exp}`)}</text>`;
    if (pts.length > 1) out += `<polyline class="measured" points="${pts.map((p) => `${x(p[0])},${y(p[1])}`).join(" ")}"/>`;
    out += pts.map((p) => `<rect class="anchor" x="${x(p[0]) - 3.5}" y="${y(p[1]) - 3.5}" width="7" height="7"/>`).join("");
    if (!pts.length)
      out += `<text class="empty" x="${(Lm + W - R) / 2}" y="${H / 2}" text-anchor="middle">${L(
        "noch keine Messflasche",
        "no measurement bottle yet",
        "pas encore de bouteille témoin",
      )}</text>`;
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
      const when = `${fmtDay(best)} ≈ ${atHour(roundHour(best).getHours())}`;
      line = L(`Konstant ${T} °C: ${when}`, `Constant ${T} °C: ${when}`, `Constant ${T} °C : ${when}`);
      if (e.best) {
        const dh = Math.round((best - Date.parse(e.best)) / HOUR);
        if (dh > 0) line += L(` (${dh} h später)`, ` (${dh} h later)`, ` (${dh} h plus tard)`);
        else if (dh < 0) line += L(` (${-dh} h früher)`, ` (${-dh} h earlier)`, ` (${-dh} h plus tôt)`);
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
            ? L(
                `Nach dem Kühlen fallen die Blasen etwa ${hrs} h lang ab, weil der Wein CO₂ zurücklöst. Das ist kein Gärstopp.`,
                `After cooling, the bubbles drop for about ${hrs} h because the wine dissolves CO₂ again. That is no stop in fermentation.`,
                `Après refroidissement, les bulles baissent pendant environ ${hrs} h car le vin redissout du CO₂. Ce n'est pas un arrêt de fermentation.`,
              )
            : L(
                `Beim Aufwärmen gast CO₂ aus. Die Blasen zeigen etwa ${hrs} h lang zu viel.`,
                `When warming, CO₂ degasses. The bubbles read too high for about ${hrs} h.`,
                `En se réchauffant, le vin dégaze du CO₂. Les bulles indiquent trop pendant environ ${hrs} h.`,
              );
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
    const nowText = L("jetzt", "now", "maintenant");
    const nowEnd = x0 - 4 + nowText.length * 6.2; // Tagesnamen, die das „jetzt“ überdecken würden, entfallen
    for (let d = nextDay(startOfDay(t0)); d.getTime() < t0 + span; d = nextDay(d)) {
      const x = X(d.getTime());
      out += `<line x1="${x}" y1="13" x2="${x}" y2="27" class="tick"></line>`;
      const noon = d.getTime() + DAY / 2;
      if (noon < t0 + span && X(noon) - 12 > nowEnd) out += `<text x="${X(noon)}" y="42" text-anchor="middle">${wd(d)}</text>`;
    }
    out += `<text x="${x0 - 4}" y="42" class="nowlabel">${nowText}</text>`;
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
    const Lm = 30;
    const Rr = 312;
    const Tp = 12;
    const B = 150;
    const series = (e.series || []).map(([t, s]) => [Date.parse(t), s]);
    if (!series.length) {
      svg.innerHTML = `<text x="160" y="90" text-anchor="middle" class="empty">${L("Noch kein Verlauf", "No history yet", "Pas encore d'historique")}</text>`;
      return;
    }
    const tn = now.getTime();
    const t0 = Math.max(Date.parse(b.start) || tn - 2.5 * DAY, tn - 2.5 * DAY);
    const fc = (e.forecast || []).map(([t, s, hi, lo]) => [Date.parse(t), s, hi, lo]);
    const fEnd = fc.length ? fc[fc.length - 1][0] : tn;
    const t1 = Math.min(Math.max(fEnd, tn + 1.5 * DAY), tn + 7 * DAY);
    const X = (t) => Lm + ((t - t0) / (t1 - t0)) * (Rr - Lm);
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
      out += `<line x1="${Lm}" y1="${f1(Y(s))}" x2="${Rr}" y2="${f1(Y(s))}" class="grid"></line>`;
      out += `<text x="${Lm - 5}" y="${f1(Y(s) + 3)}" text-anchor="end">${s}</text>`;
    }
    out += `<text x="${Lm}" y="7">${L("Restzucker g/L", "Residual sugar g/L", "Sucre résiduel g/L")}</text>`;
    if (e.target_sugar != null) {
      const yHi = Y(target + delta);
      const yLo = Y(Math.max(0, target - delta));
      out += `<rect x="${f1(X(tn))}" y="${f1(yHi)}" width="${f1(Rr - X(tn))}" height="${f1(Math.max(1, yLo - yHi))}" class="target"></rect>`;
      out += `<text x="${Rr - 2}" y="${f1(yHi - 3)}" text-anchor="end" class="targetlabel">${L("Ziel", "Target", "Objectif")} ≈ ${nf(target)} g/L</text>`;
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
    out += `<text x="${f1(X(tn) + 4)}" y="${Tp + 8}" class="label-ink">${L("jetzt", "now", "maintenant")}</text>`;
    for (let d = nextDay(startOfDay(t0)); d.getTime() < t1; d = nextDay(d)) {
      const x = X(d.getTime());
      out += `<line x1="${f1(x)}" y1="${B}" x2="${f1(x)}" y2="${B + 4}" class="grid"></line>`;
      const noon = d.getTime() + DAY / 2;
      if (noon < t1) out += `<text x="${f1(X(noon))}" y="${B + 13}" text-anchor="middle">${wd(d)}</text>`;
    }
    const bub = ((b.history || {}).bubbles_bpm || []).map(([t, v]) => [Date.parse(t), v]).filter(([t]) => t >= t0 && t <= tn);
    if (bub.length) {
      const max = Math.max(1, ...bub.map((p) => p[1]));
      const bTop = B + 20;
      const bH = 22;
      out += `<text x="${Lm - 5}" y="${bTop + bH - 4}" text-anchor="end">${L("Bl.", "Bub.", "Bul.")}</text>`;
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
    const kind = kinds()[m.kind];
    const units = densityUnits();
    this._pressed("[data-act=mkind]", (el) => el.dataset.kind === m.kind);
    this._pressed("[data-act=munit]", (el) => el.dataset.unit === m.unit);
    const density = m.kind === "density";
    this._show("m-units", density || m.kind === "brix");
    this._set("m-unit", density ? units[m.unit].label : kind.unit);
    const input = this.$("m-value");
    if (input) input.placeholder = density ? units[m.unit].placeholder : kind.placeholder;
    this._set("m-help", kind.help);
    const lab = m.kind === "sugar";
    this._show("m-value2-row", m.kind === "brix" || lab);
    this._set(
      "m-value2-label",
      lab
        ? L("Alkohol derselben Probe (optional)", "Alcohol of the same sample (optional)", "Alcool du même échantillon (facultatif)")
        : L("Dichte derselben Probe (optional)", "Density of the same sample (optional)", "Densité du même échantillon (facultatif)"),
    );
    this._set("m-unit2", lab ? "% vol" : units[m.unit].label);
    const value2 = this.$("m-value2");
    if (value2) value2.placeholder = lab ? nf(11.5) : units[m.unit].placeholder;
    this._show("m-temp-row", m.kind === "bottle_pressure");

    const rows = [];
    let msg = "";
    const p = m.preview;
    const was = (x) => `<small>${L("war", "was", "avant")} ${x}</small>`;
    if (m.kind === "ph")
      msg = L(
        "Wird gespeichert und steht im Verlauf. Die Prognose ändert sich dadurch nicht.",
        "Saved and shown in the history. It does not change the forecast.",
        "Enregistré et visible dans l'historique. La prévision ne change pas.",
      );
    else if (m.kind === "bottle_pressure")
      msg = b.bottling
        ? L(
            "Zählt für die Messflasche: Die App rechnet auf 20 °C um und vergleicht mit dem erwarteten Druck.",
            "Counts for the measurement bottle: the app converts to 20 °C and compares with the expected pressure.",
            "Compte pour la bouteille témoin : l'app ramène à 20 °C et compare à la pression attendue.",
          )
        : L(
            "Zählt erst nach „Abgefüllt“: Dann vergleicht die App die Messflasche mit dem erwarteten Druck.",
            "Only counts after “Bottled”: then the app compares the measurement bottle with the expected pressure.",
            "Ne compte qu'après « Mis en bouteille » : l'app compare alors la bouteille témoin à la pression attendue.",
          );
    else if (b.mode === "charmat" && !b.s0)
      msg = L(
        "Wird gespeichert. Beim Charmat rechnet die App mit Tankdruck und Temperatur.",
        "Saved. For Charmat the app works with tank pressure and temperature.",
        "Enregistré. Pour le Charmat, l'app calcule avec la pression et la température de la cuve.",
      );
    else if (!p) msg = L("Wert eintippen, dann steht hier, was er ändert.", "Type a value to see what it changes.", "Saisis une valeur pour voir ce qu'elle change.");
    else if (p.error) {
      const why = errText({ error_key: p.error_key, message: p.error });
      msg = L(`Lässt sich nicht auswerten: ${why}`, `Cannot be evaluated: ${why}`, `Impossible à exploiter : ${why}`);
    } else if (m.kind === "malic") {
      const last = [...(b.measurements || [])].reverse().find((x) => x.kind === "malic");
      if (last) rows.push([L("Äpfelsäure zuletzt", "Malic acid last", "Acide malique, dernière"), `${nf(last.value)} g/L`]);
      if (b.settings.malo_in_bottle && p.target_sugar != null)
        rows.push([L("Zielzucker", "Target sugar", "Sucre visé"), `${nf(p.target_sugar)} g/L ${was(nf(b.estimate?.target_sugar))}`]);
      else
        msg = L(
          "Malo in der Flasche ist aus; der Zielzucker bleibt.",
          "Malolactic in the bottle is off; the target sugar stays.",
          "La malo en bouteille est désactivée ; le sucre visé ne change pas.",
        );
    } else if (p.plausible === false)
      msg = L(
        "Der Wert passt nicht zu diesem Ansatz. Einheit prüfen?",
        "The value does not fit this batch. Check the unit?",
        "La valeur ne correspond pas à cette cuvée. Vérifier l'unité ?",
      );
    else if (p.sugar != null) {
      rows.push([L("Restzucker", "Residual sugar", "Sucre résiduel"), `${nfs(p.sugar)} g/L${p.prev_sugar != null ? ` ${was(nfs(p.prev_sugar))}` : ""}`]);
      if (p.abv_measured != null) {
        rows.push([L("Alkohol jetzt", "Alcohol now", "Alcool actuel"), `${nf(p.abv_measured)} % vol <small>${L("gemessen", "measured", "mesuré")}</small>`]);
        if (p.abv_end != null) {
          const before = p.prev_abv_end_sigma != null ? nf(p.prev_abv_end_sigma) : null;
          const prev = before != null && before !== nf(p.abv_end_sigma) ? ` ${was(`± ${before}`)}` : "";
          rows.push([abvEnd(), `${nf(p.abv_end)} ± ${nf(p.abv_end_sigma)} % vol${prev}`]);
        }
      }
      if (p.spindle_offset != null && b.has_gravity) {
        const c = -p.spindle_offset * 1000;
        rows.push([L("Spindel-Korrektur", "Hydrometer correction", "Correction densimètre"), `${c >= 0 ? "+" : "−"}${nf(Math.abs(c))} °Oe`]);
      }
      let win = L("noch keine Prognose", "no forecast yet", "pas encore de prévision");
      if (p.display_state === "late") win = L("vorbei", "passed", "passée");
      else if (p.display_state === "now") win = L("jetzt", "now", "maintenant");
      else win = windowText(toDate(p.start), toDate(p.end)) || win;
      if (b.mode !== "charmat") rows.push([b.mode === "still" ? L("Trocken", "Dry", "Sec") : L("Fenster", "Window", "Fenêtre"), win]);
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
    const ev = events();
    const text = (x) => {
      if (!x.measurement) {
        const v = x.kind === "volume" && x.value != null ? ` ${nf(x.value, 0)} L` : "";
        return `${ev[x.kind] || esc(x.kind)}${v}`;
      }
      const u = x.unit || "sg";
      const unit = { sg: "", oe: " °Oe", baume: " °Bé", gcm3: " g/cm³" }[u] ?? "";
      const dens = (v) => (u === "sg" || u === "gcm3" ? nf(v, 3) : nf(v)) + unit;
      const refr = L("Refraktometer", "Refractometer", "Réfractomètre");
      switch (x.kind) {
        case "brix":
          return `${refr} ${nf(x.value)} °Bx`;
        case "brix_density":
          return `${refr} ${nf(x.value)} °Bx + ${L("Dichte", "density", "densité")} ${dens(x.value2)}`;
        case "density":
          return `${L("Dichte", "Density", "Densité")} ${dens(x.value)}`;
        case "sugar":
          return `${L("Labor", "Lab", "Labo")} ${nf(x.value)} g/L${x.value2 != null ? ` + ${nf(x.value2)} % vol` : ""}`;
        case "malic":
          return `${L("Äpfelsäure", "Malic acid", "Acide malique")} ${nf(x.value)} g/L`;
        case "ph":
          return `pH ${nf(x.value, 2)}`;
        case "bottle_pressure": {
          const t = x.temperature != null ? nf(x.temperature, 0) : null;
          const at = t != null ? L(` bei ${t} °C`, ` at ${t} °C`, ` à ${t} °C`) : "";
          return `${L("Flasche", "Bottle", "Bouteille")} ${nf(x.value)} bar${at}`;
        }
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
            return `<li><time datetime="${esc(x.time)}">${fmtDay(t)} ${fmtHM(t)}</time><span>${text(x)}${x.note ? ` <small>${esc(x.note)}</small>` : ""}</span><button class="del${armed ? " armed" : ""}" type="button" data-act="del" data-kind="${esc(x.kind)}" data-time="${esc(x.time)}" aria-label="${armed ? L("Wirklich löschen", "Really delete", "Vraiment supprimer") : L("Eintrag löschen", "Delete entry", "Supprimer l'entrée")}">${armed ? L("löschen?", "delete?", "supprimer ?") : "×"}</button></li>`;
          })
          .join("")
      : `<li><span class="fine">${L("Noch nichts eingetragen.", "Nothing entered yet.", "Rien de saisi pour l'instant.")}</span></li>`;
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
      m.toast = L(`Bitte eine Zahl eingeben, z. B. ${nf(7.7)}.`, `Please enter a number, e.g. ${nf(7.7)}.`, `Merci de saisir un nombre, p. ex. ${nf(7.7)}.`);
      this._updateMeasure(b);
      return;
    }
    if (m.kind === "bottle_pressure") {
      const temp = num(m.temp);
      if (!Number.isFinite(temp)) {
        m.toast = L("Bitte die Temperatur der Flasche angeben.", "Please give the bottle temperature.", "Merci d'indiquer la température de la bouteille.");
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
      m.toast =
        b.mode === "charmat"
          ? L("Gespeichert.", "Saved.", "Enregistré.")
          : L(
              "Gespeichert. „Heute“ rechnet jetzt mit deiner Messung.",
              "Saved. “Today” now uses your measurement.",
              "Enregistré. « Aujourd'hui » tient compte de ta mesure.",
            );
      Object.assign(m, { value: "", value2: "", temp: "", time: "", note: "", preview: null });
      ["m-value", "m-value2", "m-temp", "m-time", "m-note"].forEach((id) => {
        const el = this.$(id);
        if (el) el.value = "";
      });
    } catch (err) {
      m.toast = notDone("save", err);
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
        ev.toast = L("Bitte das neue Volumen in Litern angeben.", "Please give the new volume in litres.", "Merci d'indiquer le nouveau volume en litres.");
        this._updateMeasure(b);
        return;
      }
      data.value = v;
    }
    if (ev.note.trim()) data.note = ev.note.trim();
    if (ev.kind === "note" && !data.note) {
      ev.toast = L("Bitte eine Notiz eingeben.", "Please enter a note.", "Merci de saisir une note.");
      this._updateMeasure(b);
      return;
    }
    try {
      await this._hass.callService("tipsylab", "add_event", data);
      const what = events()[ev.kind];
      ev.toast = L(`${what} eingetragen.`, `Added: ${what}.`, `Ajouté : ${what}.`);
      ev.value = "";
      ev.note = "";
      ["ev-value", "ev-note"].forEach((id) => {
        const el = this.$(id);
        if (el) el.value = "";
      });
    } catch (err) {
      ev.toast = notDone("add", err);
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
      this._ev.toast = L("Gelöscht.", "Deleted.", "Supprimé.");
    } catch (err) {
      this._ev.toast = notDone("delete", err);
    }
    this._updateMeasure(this._current());
    await this._fetch();
  }

  async _closeBatch(el) {
    if (!el.classList.contains("armed")) {
      el.classList.add("armed");
      el.textContent = L("Wirklich abschließen? Ins Archiv", "Really close? To the archive", "Vraiment clôturer ? Aux archives");
      return;
    }
    const b = this._current();
    try {
      await this._hass.callService("tipsylab", "add_event", { config_entry_id: b.entry_id, kind: "closed" });
    } catch (err) {
      el.textContent = notDone("close", err);
      return;
    }
    await this._fetch();
  }

  /* ---------- Archiv ---------- */
  _buildArchive(root) {
    root.innerHTML = `
      <header class="top">${this._menuButton()}<span class="logo" aria-hidden="true"></span>
        <div class="batch"><span class="kicker">TIPSYLAB</span><b>${L("Archiv", "Archive", "Archives")}</b></div></header>
      <section class="screen solo" style="margin-top:18px">
        <p class="eyebrow">${L("Was wir gelernt haben", "What we have learned", "Ce que nous avons appris")}</p>
        <dl class="leaders" id="a-learned"></dl>
        <p class="fine" id="a-learned-note"></p>
        <p class="eyebrow">${L("Frühere Ansätze", "Earlier batches", "Cuvées précédentes")}</p>
        <div id="a-list"></div>
        <button class="primary" type="button" data-act="archive-back">${L("Zurück", "Back", "Retour")}</button>
      </section>
      <footer class="foot">${this._langs()}</footer>`;
    this._wireMenu();
  }

  _updateArchive() {
    const h = this._house || { values: {}, archive: [] };
    const v = h.values || {};
    const rows = [];
    const learned = (x) => {
      if (!(x && x.n)) return `<small>${L("Startwert", "starting value", "valeur initiale")}</small>`;
      const one = x.n === 1;
      return `<small>${L(`aus ${x.n} ${one ? "Ansatz" : "Ansätzen"}`, `from ${x.n} ${one ? "batch" : "batches"}`, `sur ${x.n} ${one ? "cuvée" : "cuvées"}`)}</small>`;
    };
    if (v.saturation)
      rows.push([
        L("CO₂ beim Abfüllen", "CO₂ at bottling", "CO₂ au tirage"),
        `${Math.round(v.saturation.mean * 100)} ± ${Math.round(v.saturation.sigma * 100)} % ${learned(v.saturation)}`,
      ]);
    if (v.g_sugar_per_abv)
      rows.push([
        L("Zucker je % vol", "Sugar per % vol", "Sucre par % vol"),
        `${nf(v.g_sugar_per_abv.mean)} ± ${nf(v.g_sugar_per_abv.sigma)} g/L ${learned(v.g_sugar_per_abv)}`,
      ]);
    const dev = h.devices || {};
    for (const [id, x] of Object.entries(dev.bubbles_per_g || {}))
      rows.push([`${L("Blasen je g CO₂", "Bubbles per g CO₂", "Bulles par g CO₂")} <small>${esc(id)}</small>`, `${nf(x.mean, 0)} ± ${nf(x.sigma, 0)} ${learned(x)}`]);
    for (const [id, x] of Object.entries(dev.spindle_offset || {}))
      rows.push([
        `${L("Spindel-Versatz", "Hydrometer offset", "Décalage densimètre")} <small>${esc(id.replace(/^sensor\./, ""))}</small>`,
        `${x.mean >= 0 ? "+" : "−"}${nf(Math.abs(x.mean) * 1000)} ± ${nf(x.sigma * 1000)} °Oe ${learned(x)}`,
      ]);
    this._html("a-learned", rows.map(([dt, dd]) => `<div><dt>${dt}</dt><dd>${dd}</dd></div>`).join(""));
    const any = Object.values(v).some((x) => x.n);
    this._set(
      "a-learned-note",
      any
        ? L(
            "Gelöstes CO₂ beim Abfüllen in % der Sättigung, aus durchgegorenen Messflaschen; Zucker je % vol aus Laborwerten; Blasen und Spindel je Gerät, solange ein Ansatz noch nicht selbst geeicht ist. Neue Ansätze rechnen damit.",
            "Dissolved CO₂ at bottling in % of saturation, from fermented-out measurement bottles; sugar per % vol from lab results; bubbles and hydrometer per device, until a batch is calibrated by itself. New batches use these.",
            "CO₂ dissous au tirage en % de la saturation, d'après les bouteilles témoins terminées ; sucre par % vol d'après les résultats de labo ; bulles et densimètre par appareil, tant qu'une cuvée n'est pas étalonnée elle-même. Les nouvelles cuvées en tiennent compte.",
          )
        : L(
            "Noch Startwerte aus der Literatur. Durchgegorene Messflaschen und Laborwerte von abgeschlossenen Ansätzen eichen sie.",
            "Still starting values from the literature. Fermented-out measurement bottles and lab results of closed batches calibrate them.",
            "Encore les valeurs initiales de la littérature. Les bouteilles témoins terminées et les résultats de labo des cuvées clôturées les étalonnent.",
          ),
    );
    const list = (h.archive || []).map((r) => {
      const start = toDate(r.start);
      const closed = toDate(r.closed);
      const bt = r.bottling;
      const bo = r.bottle;
      const last = bo?.readings?.[bo.readings.length - 1];
      const fc = bt?.forecast_check?.["48"];
      const dl = [];
      if (bt) dl.push([L("Abgefüllt bei", "Bottled at", "Tirée à"), `${nfs(bt.sugar)} ± ${nf(bt.sigma)} g/L`]);
      const exp = nf(bo?.expected_20);
      if (bo)
        dl.push(
          last
            ? [L("Messflasche 20 °C", "Meas. bottle 20 °C", "Bouteille témoin 20 °C"), `${nf(last[3])} bar <small>${L(`erwartet ${exp}`, `expected ${exp}`, `attendu ${exp}`)}</small>`]
            : [L("Erwartet bei 20 °C", "Expected at 20 °C", "Attendu à 20 °C"), `${exp} bar`],
        );
      if (fc) dl.push([L("Prognose 48 h vorher", "Forecast 48 h before", "Prévision 48 h avant"), offBy(fc.error_h)]);
      if (r.abv) {
        const label = nf(r.abv.label, r.abv.label % 1 ? 1 : 0);
        dl.push([L("Alkohol", "Alcohol", "Alcool"), `${nf(r.abv.value)} ± ${nf(r.abv.sigma)} % vol <small>${L(`Etikett ${label}`, `label ${label}`, `étiquette ${label}`)}</small>`]);
      }
      return `<article class="arch"><p class="arch-title"><b>${esc(r.name)}</b> <small>${modeLabel(r.mode) || esc(r.mode)} · ${start ? fmtDay(start) : ""}–${closed ? fmtDay(closed) : ""} ${closed ? closed.getFullYear() : ""}</small></p>
        ${this._sparkline(r.series || [])}
        <dl class="leaders">${dl.map(([dt, dd]) => `<div><dt>${dt}</dt><dd>${dd}</dd></div>`).join("")}</dl></article>`;
    });
    this._html(
      "a-list",
      list.length
        ? list.join("")
        : `<p class="fine">${L(
            "Noch kein Ansatz abgeschlossen. „Ansatz abschließen“ steht nach dem Abfüllen unter „Heute“.",
            "No batch closed yet. “Close batch” appears under “Today” after bottling.",
            "Aucune cuvée clôturée. « Clôturer la cuvée » apparaît sous « Aujourd'hui » après la mise en bouteille.",
          )}</p>`,
    );
  }

  _sparkline(series) {
    if (series.length < 2) return "";
    const W = 320;
    const H = 46;
    const t0 = Date.parse(series[0][0]);
    const t1 = Date.parse(series[series.length - 1][0]);
    const top = Math.max(...series.map((p) => p[1]), 1);
    const pts = series.map((p) => `${((Date.parse(p[0]) - t0) / Math.max(1, t1 - t0)) * (W - 4) + 2},${(1 - p[1] / top) * (H - 6) + 3}`);
    return `<svg class="chart spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="${L("Restzucker über die Gärung", "Residual sugar over the fermentation", "Sucre résiduel au fil de la fermentation")}"><polyline class="measured" points="${pts.join(" ")}"/></svg>`;
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
      this._answer("t-big", `${nf(p10)}–${nf(t.target)} BAR`);
      this._set("t-out", L(`${nf(t.target)} bar bei 20 °C`, `${nf(t.target)} bar at 20 °C`, `${nf(t.target)} bar à 20 °C`));
      const cat = P.euCategory(t.target);
      this._set("t-cat", category(cat));
      this.$("t-cat")?.classList.toggle("off", cat === "gap" || cat === "still");
      this._html("t-sugar", `≈ ${nf(sMid)} g/L <small>(${nf(sWorst)}–${nf(sMild)})</small>`);
      const malo = nf(P.maloSugarOffset(t.malic));
      this._set("t-malo", t.malo ? L(`−${malo} g/L Zucker`, `−${malo} g/L sugar`, `−${malo} g/L de sucre`) : L("aus", "off", "non"));
      this._set("t-p10", `${nf(p10)} bar`);
      this._set("t-p20", `${nf(p20)} bar`);
      const ok = worst <= bottle.limit;
      this._set("t-limit", `${nf(worst)} / ${nf(bottle.limit)} bar ${ok ? "✓" : "✕"}`);
      this.$("t-limit-row")?.classList.toggle("warn", !ok);
      this._pressed("[data-act=bottle]", (el) => el.dataset.bottle === t.bottle);
      this._pressed("[data-act=malo]", (el) => (el.dataset.on === "1") === t.malo);
      this._show("t-malic-row", t.malo);
    } else {
      this._answer("t-big", L(`UNTER ${nf(t.dry)} G/L`, `BELOW ${nf(t.dry)} G/L`, `SOUS ${nf(t.dry)} G/L`));
    }
    const save = this.$("t-save");
    if (save) {
      save.disabled = !t.dirty;
      save.textContent = t.dirty ? L("Ziel speichern", "Save target", "Enregistrer l'objectif") : L("Gespeichert", "Saved", "Enregistré");
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
    let toast = L("Nichts geändert.", "Nothing changed.", "Rien de modifié.");
    if (Object.keys(changes).length) {
      try {
        await this._hass.callService("tipsylab", "update_settings", { config_entry_id: b.entry_id, ...changes });
        toast = L("Gespeichert.", "Saved.", "Enregistré.");
      } catch (err) {
        this._set("t-toast", notDone("save", err));
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
    this._answer("c-big", sp != null ? `${nf(sp)} BAR` : "–");
    const ist = pIst != null ? nf(pIst) : null;
    const sub = [ist != null ? L(`IST ${ist} BAR`, `NOW ${ist} BAR`, `ACTUEL ${ist} BAR`) : null, temp != null ? `${nf(temp)} °C` : null].filter(Boolean);
    this._set("c-sub", sub.length ? sub.join(" · ") : L("KEINE SENSORWERTE", "NO SENSOR READINGS", "PAS DE VALEURS DES CAPTEURS"));
    const tgt = nf(c.target);
    this._set(
      "c-say",
      L(
        `Das Ventil hält den Druck, der in der Flasche ${tgt} bar bei 20 °C ergibt. Wird der Tank wärmer, steigt der Sollwert mit.`,
        `The valve holds the pressure that gives ${tgt} bar at 20 °C in the bottle. If the tank gets warmer, the set point rises with it.`,
        `La vanne maintient la pression qui donne ${tgt} bar à 20 °C en bouteille. Si la cuve se réchauffe, la consigne monte avec.`,
      ),
    );
    this._set("c-tout", `${tgt} bar`);
    const table = [8, 10, 12, 15, 18].map((t) => `${t}\u00a0°C\u00a0${nf(P.charmatSetpoint(co2, t))}`).join(" · ");
    this._set("c-table", `${L("Sollwert bei", "Set point at", "Consigne à")} ${table}\u00a0bar`);
    this._set("c-co2t", `${nf(co2, 2)} g/L`);
    this._set("c-co2", b.charmat?.dissolved != null ? `${nf(b.charmat.dissolved, 2)} g/L` : "–");
    this._set("c-temp", temp != null ? `${nf(temp)} °C` : "–");
    const prv = s.prv_bar;
    const ok = prv == null || sp == null || sp <= prv - 0.3;
    this._set(
      "c-prv",
      prv != null
        ? `${nf(prv)} bar ${L("mech.", "mech.", "méca.")} ${ok ? "✓" : `✕ ${L("zu knapp", "too tight", "trop juste")}`}`
        : L("nicht eingetragen", "not entered", "non saisie"),
    );
    this.$("c-prv-row")?.classList.toggle("warn", !ok);
    this._show("c-save", c.dirty);
    const newest = b.latest?.pressure ? Date.parse(b.latest.pressure[0]) : null;
    this._set(
      "c-status",
      newest
        ? `${L("Drucksensor", "Pressure sensor", "Capteur de pression")} · ${ago(newest)}`
        : L("Kein Drucksensor verbunden", "No pressure sensor connected", "Aucun capteur de pression connecté"),
    );
    this._drawTankChart(b, sp);
  }

  _drawTankChart(b, sp) {
    const svg = this.$("c-chart");
    if (!svg) return;
    const pts = ((b.history || {}).pressure || []).map(([t, v]) => [Date.parse(t), v]);
    const Lm = 30;
    const Rr = 312;
    const Tp = 12;
    const B = 128;
    const tn = Date.now();
    const t0 = tn - 72 * HOUR;
    const shown = pts.filter(([t]) => t >= t0);
    const yMax = Math.max(2, Math.ceil(Math.max(sp ?? 0, ...shown.map((p) => p[1])) + 0.6));
    const X = (t) => Lm + ((t - t0) / (tn - t0)) * (Rr - Lm);
    const Y = (p) => B - (Math.min(Math.max(p, 0), yMax) / yMax) * (B - Tp);
    const f1 = (v) => v.toFixed(1);
    let out = "";
    for (let p = 0; p <= yMax; p += 1) {
      out += `<line x1="${Lm}" y1="${f1(Y(p))}" x2="${Rr}" y2="${f1(Y(p))}" class="grid"></line>`;
      out += `<text x="${Lm - 5}" y="${f1(Y(p) + 3)}" text-anchor="end">${p}</text>`;
    }
    out += `<text x="${Lm}" y="7">${L("Tankdruck bar", "Tank pressure bar", "Pression cuve bar")}</text>`;
    if (sp != null) {
      out += `<line x1="${Lm}" y1="${f1(Y(sp))}" x2="${Rr}" y2="${f1(Y(sp))}" class="setline"></line>`;
      out += `<text x="${Rr - 2}" y="${f1(Y(sp) - 4)}" text-anchor="end" class="targetlabel">${L("Soll", "Set", "Consigne")} ${nf(sp)}</text>`;
    }
    if (shown.length > 1) out += `<polyline points="${shown.map(([t, p]) => `${f1(X(t))},${f1(Y(p))}`).join(" ")}" class="measured"></polyline>`;
    else
      out += `<text x="${(Lm + Rr) / 2}" y="${(Tp + B) / 2}" text-anchor="middle" class="empty">${L(
        "Noch kein Druckverlauf",
        "No pressure history yet",
        "Pas encore d'historique de pression",
      )}</text>`;
    for (const [h, label] of [[-72, "−72 h"], [-48, "−48 h"], [-24, "−24 h"], [0, L("jetzt", "now", "maintenant")]]) {
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
      this._set("c-toast", L("Übernommen. Der Regler bekommt den neuen Sollwert.", "Applied. The controller gets the new set point.", "Appliqué. Le régulateur reçoit la nouvelle consigne."));
    } catch (err) {
      this._set("c-toast", notDone("apply", err));
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
      case "lang":
        if (el.dataset.lang !== LANG) {
          LANG = el.dataset.lang;
          store.set("lang", LANG);
          this._relabel();
        }
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
