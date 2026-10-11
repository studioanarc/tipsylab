// TIPSYlab web UI: dashboard, settings and first-time setup. No dependencies.
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);

  const api = {
    get: (url) => fetch(url).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }),
    post: (url) => fetch(url, { method: 'POST' }).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); }),
    postJson: (url, body) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); }),
    postForm: (url, form) => fetch(url, { method: 'POST', body: new URLSearchParams(new FormData(form)) })
      .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); }),
  };

  function setText(id, text) { const el = $(id); if (el) el.textContent = text; }
  function setStatus(id, ok, text) {
    const el = $(id); if (!el) return;
    el.textContent = text;
    el.className = 'status-value ' + (ok ? 'success' : 'error');
  }
  function message(text, type) {
    const el = $('status-message'); if (!el) return;
    el.textContent = text;
    el.className = type || 'success';
    clearTimeout(message.timer);
    message.timer = setTimeout(() => el.classList.add('hidden'), 8000);
  }
  function fmtUptime(s) {
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    return (d ? d + 'd ' : '') + h + 'h ' + m + 'm';
  }

  // ---- sensor settings (sliders shared by dashboard and settings page) ----
  const SETTING_KEYS = ['gyro_threshold', 'min_activity_threshold', 'debounce_time'];

  function bindSliders() {
    document.querySelectorAll('input[type="range"]').forEach((s) => {
      const out = $(s.id + '_value'); if (!out) return;
      out.textContent = s.value;
      s.addEventListener('input', () => { out.textContent = s.value; });
    });
  }
  function fillSettings(cfg) {
    SETTING_KEYS.forEach((k) => {
      const s = $(k); if (!s || cfg[k] === undefined) return;
      s.value = cfg[k];
      const out = $(k + '_value'); if (out) out.textContent = s.value;
    });
    const lt = $('legacy_topics'); if (lt) lt.checked = !!cfg.legacy_topics;
  }
  function readSettings() {
    const o = {
      gyro_threshold: parseFloat($('gyro_threshold').value),
      min_activity_threshold: parseFloat($('min_activity_threshold').value),
      debounce_time: parseInt($('debounce_time').value, 10),
    };
    const lt = $('legacy_topics'); if (lt) o.legacy_topics = lt.checked ? 1 : 0;
    return o;
  }
  function saveSettings() {
    return api.postJson('/api/update-settings', readSettings())
      .then(() => message('Sensor settings saved.', 'success'))
      .catch((e) => { message('Could not save settings: ' + e.message, 'error'); throw e; });
  }

  // ---- dashboard ----
  function initDashboard() {
    const refreshStatus = () => api.get('/api/status').then((s) => {
      setStatus('wifi-status', s.wifi_connected, s.wifi_connected ? 'Connected' : (s.ap_active ? 'Setup AP active' : 'Disconnected'));
      setStatus('mqtt-status', s.mqtt_connected, s.mqtt_connected ? 'Connected' : 'Disconnected');
      setText('ip-address', s.ip_address || '-');
      setText('hostname', s.hostname + '.local');
      setText('device-id', s.device_id);
      setText('rssi', s.wifi_connected ? s.rssi + ' dBm' : '-');
      setText('fw-version', s.fw);
      setText('uptime', fmtUptime(s.uptime));
      setText('bubble-count', s.bubble_count);
      setText('bubble-rate', s.bubbles_last_interval + ' /min');
      setText('total-bubbles', s.total_bubbles);
      setText('next-send', s.seconds_to_send + ' s');
      setStatus('temp1', s.temp1_connected, s.temp1_connected ? s.temp1.toFixed(1) + ' °C' : 'not connected');
      setStatus('temp2', s.temp2_connected, s.temp2_connected ? s.temp2.toFixed(1) + ' °C' : 'not connected');
      setText('noise-floor', s.calibrating ? 'calibrating…' : s.noise_floor.toFixed(3) + ' °/s');
      setText('last-peak', s.last_peak.toFixed(2) + ' °/s');
      setText('sample-rate', s.sample_rate + ' Hz');
      if (s.autocal) {
        const a = s.autocal;
        const txt = a.phase === 'wait_still' ? 'waiting for the device to be still…'
                  : a.phase === 'quiet'  ? 'keep still… ' + a.seconds_left + ' s'
                  : a.phase === 'active' ? 'make blops! ' + a.seconds_left + ' s (' + a.blops + ' seen)'
                  : a.phase === 'done'   ? 'done: ' + a.message
                  : a.phase === 'failed' ? 'failed: ' + a.message
                  : 'idle';
        setStatus('autocal-status', a.phase !== 'failed', txt);
        if (a.phase === 'done' && refreshStatus.lastPhase !== 'done') fillSettings({ gyro_threshold: a.trigger, min_activity_threshold: a.release });
        refreshStatus.lastPhase = a.phase;
      }
    }).catch(() => setStatus('wifi-status', false, 'no response'));

    const refreshHistory = () => api.get('/api/history').then((h) => {
      TipsyCharts.bars($('bubble-chart'), h.bubbles);
      TipsyCharts.lines($('temp-chart'), [
        { values: h.temp1, color: '#4682b4', label: 'T1' },
        { values: h.temp2, color: '#ff9800', label: 'T2' },
      ], '°');
    }).catch(() => {});

    api.get('/api/config').then(fillSettings).catch(() => {});
    refreshStatus(); refreshHistory();
    setInterval(refreshStatus, 2000);
    setInterval(refreshHistory, 60000);
    window.addEventListener('resize', refreshHistory);

    $('save-settings').addEventListener('click', () => saveSettings().catch(() => {}));
    $('autocal-btn').addEventListener('click', () => api.post('/api/autocal')
      .then(() => message('Auto-calibration started: keep the device still for 10 s, then make blops for 20 s.', 'success'))
      .catch((e) => message('Failed: ' + e.message, 'error')));
    $('calibrate-btn').addEventListener('click', () => api.post('/api/calibrate')
      .then(() => message('Baseline is being relearned - keep the device still for a second.', 'success'))
      .catch((e) => message('Failed: ' + e.message, 'error')));
  }

  // ---- settings page ----
  function initSettings() {
    api.get('/api/config').then((cfg) => {
      ['wifi_ssid', 'mqtt_server', 'mqtt_port', 'mqtt_user', 'mqtt_client_id', 'hostname'].forEach((k) => { if ($(k)) $(k).value = cfg[k] ?? ''; });
      fillSettings(cfg);
      setText('device-id', cfg.device_id);
      setText('fw-version', cfg.fw);
      setText('ota-host', cfg.hostname + '.local' + (cfg.ota_protected ? ' (password protected)' : ' (no password!)'));
      showLogo(!!cfg.logo);
    }).catch((e) => message('Could not load configuration: ' + e.message, 'error'));

    // display logo
    function showLogo(has) {
      const img = $('logo-preview'); if (!img) return;
      img.style.display = has ? 'block' : 'none';
      if (has) img.src = '/logo?' + Date.now();
      setText('logo-status', has ? 'Logo stored on the device' : 'No logo - a dot flashes for each blop');
    }
    $('logo-upload-btn').addEventListener('click', () => {
      const file = $('logo-file').files[0];
      if (!file) { message('Choose a PNG or JPEG file first.', 'error'); return; }
      const fd = new FormData();
      fd.append('logo', file, file.name);
      fetch('/api/logo', { method: 'POST', body: fd })
        .then((r) => r.text().then((t) => { if (!r.ok) throw new Error(t || 'HTTP ' + r.status); }))
        .then(() => { message('Logo uploaded - it flashes with the next blop.', 'success'); setTimeout(() => showLogo(true), 1500); })
        .catch((e) => message('Upload failed: ' + e.message, 'error'));
    });
    $('logo-delete-btn').addEventListener('click', () => {
      if (!confirm('Remove the logo from the device?')) return;
      api.post('/api/logo-delete')
        .then(() => { message('Logo removed.', 'success'); showLogo(false); })
        .catch((e) => message('Failed: ' + e.message, 'error'));
    });

    $('config-form').addEventListener('submit', (ev) => {
      ev.preventDefault();
      saveSettings()
        .then(() => api.postForm('/save-config', ev.target))
        .then((t) => message(t + ' Reload this page in ~20 s.', 'success'))
        .catch((e) => message('Save failed: ' + e.message, 'error'));
    });
    $('restart-btn').addEventListener('click', () => {
      if (!confirm('Restart the device?')) return;
      api.post('/api/restart').then(() => message('Restarting…', 'success')).catch((e) => message('Failed: ' + e.message, 'error'));
    });
  }

  // ---- first-time setup (served on the setup access point) ----
  function initSetup() {
    $('setup-form').addEventListener('submit', (ev) => {
      ev.preventDefault();
      api.postForm('/save-config', ev.target)
        .then((t) => message(t + ' You can close this page.', 'success'))
        .catch((e) => message('Save failed: ' + e.message, 'error'));
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindSliders();
    if ($('bubble-chart')) initDashboard();
    else if ($('config-form')) initSettings();
    else if ($('setup-form')) initSetup();
  });
})();
