// Dependency-free canvas charts for the dashboard: bars (bubbles/min) and lines (temperatures).
window.TipsyCharts = (function () {
  'use strict';
  const PAD = { l: 42, r: 12, t: 14, b: 26 };

  function prepare(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 400, h = canvas.clientHeight || 300;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.font = '12px system-ui, sans-serif';
    return { ctx, w, h };
  }

  function niceCeil(v) {
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
  }

  function frame(ctx, w, h, yMin, yMax, fmt) {
    const x0 = PAD.l, x1 = w - PAD.r, y0 = PAD.t, y1 = h - PAD.b;
    ctx.strokeStyle = '#e4e4e4';
    ctx.fillStyle = '#666';
    ctx.lineWidth = 1;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) {
      const v = yMin + (yMax - yMin) * i / 4;
      const y = y1 - (y1 - y0) * i / 4;
      ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
      ctx.fillText(fmt(v), x0 - 6, y);
    }
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    [[0, '-60 min'], [0.5, '-30 min'], [1, 'now']].forEach(([f, t]) => ctx.fillText(t, x0 + (x1 - x0) * f, y1 + 6));
    return { x0, x1, y0, y1 };
  }

  function bars(canvas, values) {
    if (!canvas || !values) return;
    const { ctx, w, h } = prepare(canvas);
    const n = values.length;
    const max = niceCeil(Math.max(1, ...values.map((v) => v || 0)));
    const f = frame(ctx, w, h, 0, max, (v) => String(Math.round(v)));
    const slot = (f.x1 - f.x0) / n;
    ctx.fillStyle = '#4682b4';
    values.forEach((v, i) => {
      if (!(v > 0)) return;
      const bh = (f.y1 - f.y0) * v / max;
      ctx.fillRect(f.x0 + i * slot + 1, f.y1 - bh, Math.max(1, slot - 2), bh);
    });
  }

  function lines(canvas, series, unit) {
    if (!canvas || !series || !series.length) return;
    const { ctx, w, h } = prepare(canvas);
    const isNum = (v) => typeof v === 'number' && isFinite(v);
    const all = series.flatMap((s) => s.values || []).filter(isNum);
    let lo = all.length ? Math.min(...all) : 18, hi = all.length ? Math.max(...all) : 22;
    if (hi - lo < 2) { const m = (hi + lo) / 2; lo = m - 1; hi = m + 1; }
    lo = Math.floor(lo); hi = Math.ceil(hi);
    const f = frame(ctx, w, h, lo, hi, (v) => v.toFixed(0) + (unit || ''));
    const n = series[0].values.length;
    const xs = (i) => f.x0 + (f.x1 - f.x0) * (n === 1 ? 0.5 : i / (n - 1));
    const ys = (v) => f.y1 - (f.y1 - f.y0) * (v - lo) / (hi - lo);

    series.forEach((s) => {
      ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.beginPath();
      let pen = false;
      (s.values || []).forEach((v, i) => {
        if (!isNum(v)) { pen = false; return; }
        if (pen) ctx.lineTo(xs(i), ys(v)); else ctx.moveTo(xs(i), ys(v));
        pen = true;
      });
      ctx.stroke();
    });

    ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    let lx = f.x0 + 6;
    series.forEach((s) => {
      ctx.fillStyle = s.color; ctx.fillRect(lx, f.y0 - 10, 12, 4);
      ctx.fillStyle = '#666'; ctx.fillText(s.label, lx + 16, f.y0 - 8);
      lx += 16 + ctx.measureText(s.label).width + 14;
    });
  }

  return { bars, lines };
})();
