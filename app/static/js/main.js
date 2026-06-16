(() => {
  "use strict";

  // --- DOM Refs ---
  const luxValueEl = document.getElementById("val-lux");
  const waveValueEl = document.getElementById("val-wl");
  const colorValueEl = document.getElementById("val-color");
  const luxBar = document.getElementById("bar-lux");
  const spectrumNeedle = document.getElementById("spectrum-needle");
  const colorSwatch = document.getElementById("color-swatch");
  
  // --- Camera Selector DOM Refs ---
  const cameraSelector = document.getElementById("camera-selector");
  const btnCameraToggle = document.getElementById("btn-camera-toggle");
  const cameraDropdown = document.getElementById("camera-dropdown");
  const cameraListEl = document.getElementById("camera-list");
  const btnCameraRefresh = document.getElementById("btn-camera-refresh");
  const cameraActiveName = document.getElementById("camera-active-name");
  const cameraStatusBadge = document.getElementById("camera-status-badge");

  const btnStart = document.getElementById("btn-start");
  const btnStop = document.getElementById("btn-stop");
  const btnReset = document.getElementById("btn-reset");
  const btnCalibrate = document.getElementById("btn-calibrate");
  const statusHint = document.getElementById("status-hint");
  
  // --- Progress Stepper ---
  const step1 = document.getElementById("step-1");
  const step2 = document.getElementById("step-2");
  const step3 = document.getElementById("step-3");
  const progBlank = document.getElementById("prog-blank");
  const progRef = document.getElementById("prog-ref");
  const progSample = document.getElementById("prog-sample");

  // --- History & Chart ---
  const historyList = document.getElementById("history-list");
  const absorbanceSection = document.getElementById("absorbance-section");
  const statsAbsorbance = document.getElementById("stats-absorbance");

  const POLL_MS = 400;
  const LUX_CEIL = 1000;
  const SPECTRUM_MIN = 380;
  const SPECTRUM_MAX = 700;

  let chartInstances = {};
  let lastRenderedCount = 0;

  // --- Camera Management ---
  let cameraDropdownOpen = false;

  btnCameraToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    cameraDropdownOpen = !cameraDropdownOpen;
    if (cameraDropdownOpen) {
      cameraDropdown.classList.remove("hidden");
      loadCameraList();
    } else {
      cameraDropdown.classList.add("hidden");
    }
  });

  document.addEventListener("click", (e) => {
    if (cameraDropdownOpen && !cameraSelector.contains(e.target)) {
      cameraDropdownOpen = false;
      cameraDropdown.classList.add("hidden");
    }
  });

  btnCameraRefresh.addEventListener("click", (e) => {
    e.stopPropagation();
    loadCameraList(true);
  });

  async function loadCameraList(forceRefresh = false) {
    if (forceRefresh) {
      cameraListEl.innerHTML = '<div class="camera-list-loading">Mendeteksi kamera…</div>';
    }

    try {
      const url = forceRefresh ? "/api/camera/list?refresh=true" : "/api/camera/list";
      const res = await fetch(url);
      const data = await res.json();

      if (!data.cameras || data.cameras.length === 0) {
        cameraListEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--c-danger)">Tidak ada kamera terdeteksi</div>';
        updateCameraBadge(false, null, "No Camera");
        return;
      }

      cameraListEl.innerHTML = "";
      let activeName = "Camera";
      data.cameras.forEach((cam) => {
        const isActive = cam.index === data.active_index;
        if (isActive) activeName = cam.name;
        const item = document.createElement("div");
        item.className = `camera-item${isActive ? " active" : ""}`;
        item.innerHTML = `
          <div class="camera-item-dot"></div>
          <div class="camera-item-info">
            <span class="camera-item-name">${cam.name}</span>
            <span class="camera-item-res">${cam.resolution}</span>
          </div>
        `;
        item.addEventListener("click", () => switchCamera(cam.index));
        cameraListEl.appendChild(item);
      });

      updateCameraBadge(data.is_connected, data.active_index, activeName);
    } catch (_) {
      cameraListEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--c-danger)">Gagal memuat daftar kamera</div>';
    }
  }

  let isSwitching = false;
  async function switchCamera(index) {
    isSwitching = true;
    cameraListEl.innerHTML = '<div class="camera-list-loading">Berpindah kamera…</div>';
    try {
      const res = await fetch(`/api/camera/switch/${index}`, { method: "POST" });
      const data = await res.json();
      if (!data.success) {
        alert(data.message);
      }
      await loadCameraList();
    } catch (_) {
      alert("Gagal berpindah kamera.");
      await loadCameraList();
    } finally {
      isSwitching = false;
    }
  }

  function updateCameraBadge(isConnected, activeIndex, activeName = "Camera") {
    cameraActiveName.textContent = activeName;
    if (isConnected) {
      cameraStatusBadge.className = "badge badge--ok";
      cameraStatusBadge.innerHTML = '<div class="badge-dot"></div><span>Connected</span>';
    } else {
      cameraStatusBadge.className = "badge badge--error";
      cameraStatusBadge.innerHTML = '<div class="badge-dot" style="animation:none;"></div><span>Disconnected</span>';
    }
  }

  async function checkCameraHealth() {
    if (isSwitching) return;
    try {
      const res = await fetch("/api/camera/status");
      const data = await res.json();
      if (data.is_connected) {
         updateCameraBadge(true, data.active_index, cameraActiveName.textContent);
      } else {
         updateCameraBadge(false, null, "No Camera");
      }
    } catch (_) {}
  }
  setInterval(checkCameraHealth, 5000);
  checkCameraHealth();
  loadCameraList();

  // --- Utilities ---
  function nmToRgb(nm) {
    let r = 0, g = 0, b = 0;
    if (nm >= 380 && nm < 440) { r = -(nm - 440) / (440 - 380); b = 1; }
    else if (nm >= 440 && nm < 490) { g = (nm - 440) / (490 - 440); b = 1; }
    else if (nm >= 490 && nm < 510) { g = 1; b = -(nm - 510) / (510 - 490); }
    else if (nm >= 510 && nm < 580) { r = (nm - 510) / (580 - 510); g = 1; }
    else if (nm >= 580 && nm < 645) { r = 1; g = -(nm - 645) / (645 - 580); }
    else if (nm >= 645 && nm <= 700) { r = 1; }
    let f = 1;
    if (nm >= 380 && nm < 420) f = 0.3 + (0.7 * (nm - 380)) / (420 - 380);
    else if (nm > 645 && nm <= 700) f = 0.3 + (0.7 * (700 - nm)) / (700 - 645);
    r = Math.round(255 * Math.pow(r * f, 0.8));
    g = Math.round(255 * Math.pow(g * f, 0.8));
    b = Math.round(255 * Math.pow(b * f, 0.8));
    return { r, g, b };
  }

  function getWavelengthName(nm) {
    if (nm < 400) return "Ultraviolet";
    if (nm >= 400 && nm < 450) return "Ungu";
    if (nm >= 450 && nm < 490) return "Biru";
    if (nm >= 490 && nm < 520) return "Sian";
    if (nm >= 520 && nm < 560) return "Hijau";
    if (nm >= 560 && nm < 590) return "Kuning";
    if (nm >= 590 && nm < 630) return "Oranye";
    if (nm >= 630 && nm <= 700) return "Merah";
    return "Inframerah";
  }

  // --- Sensor Polling ---
  async function pollSensor() {
    try {
      const res = await fetch("/api/data");
      if (!res.ok) return;
      const data = await res.json();
      const lux = data.intensity_lux ?? 0;
      const nm = data.wavelength ?? 0;

      luxValueEl.textContent = lux.toFixed(1);
      waveValueEl.textContent = nm.toFixed(1);
      luxBar.style.width = `${Math.min((lux / LUX_CEIL) * 100, 100)}%`;

      const pct = ((nm - SPECTRUM_MIN) / (SPECTRUM_MAX - SPECTRUM_MIN)) * 100;
      spectrumNeedle.style.left = `${Math.max(0, Math.min(pct, 100))}%`;

      const rgb = nmToRgb(nm);
      const colorHex = `rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`;
      const colorName = getWavelengthName(nm);
      
      if (colorValueEl) {
        colorValueEl.textContent = colorName;
        colorValueEl.style.color = colorHex;
        colorValueEl.style.textShadow = `0 0 15px rgba(${rgb.r},${rgb.g},${rgb.b},0.6)`;
      }
      if (colorSwatch) {
        colorSwatch.style.background = colorHex;
        colorSwatch.style.boxShadow = `0 0 15px rgba(${rgb.r},${rgb.g},${rgb.b},0.6)`;
      }
    } catch (_) {}
  }
  setInterval(pollSensor, POLL_MS);
  pollSensor();

  // --- Experiment State ---
  function updateControls(state) {
    const td = state.total_done;
    
    // Update Stepper Progress
    let blankDone = Math.min(3, td);
    let refDone = Math.max(0, Math.min(3, td - 3));
    let sampleDone = Math.max(0, Math.min(3, td - 6));

    progBlank.textContent = `${blankDone}/3`;
    progRef.textContent = `${refDone}/3`;
    progSample.textContent = `${sampleDone}/3`;

    step1.className = `step ${td >= 3 ? 'done' : (td >= 0 && td < 3 ? 'active' : '')}`;
    step2.className = `step ${td >= 6 ? 'done' : (td >= 3 && td < 6 ? 'active' : '')}`;
    step3.className = `step ${td >= 9 ? 'done' : (td >= 6 && td < 9 ? 'active' : '')}`;

    if (state.recording) {
      btnStart.classList.add("hidden");
      btnStop.classList.remove("hidden");
      statusHint.textContent = "Merekam data intensitas...";
    } else {
      btnStart.classList.remove("hidden");
      btnStop.classList.add("hidden");
      
      if (td >= 9) {
        btnStart.classList.add("hidden");
        statusHint.textContent = "Semua 9 percobaan selesai. Lihat grafik absorbansi.";
      } else {
        const nextLabel = state.next_label || "Percobaan Berikutnya";
        statusHint.textContent = `Lanjutkan ke: ${nextLabel}`;
        btnStart.innerHTML = `<i class="ph-fill ph-play-circle"></i> <span>Mulai ${nextLabel}</span>`;
      }
    }
  }

  // --- Buttons Action ---
  btnStart.addEventListener("click", async () => {
    btnStart.disabled = true;
    try {
      const res = await fetch("/api/experiment/capture", { method: "POST" });
      const capData = await res.json();
      if (!capData.success) await customAlert(capData.message);
      lastRenderedCount = 0;
      await fetchStatus();
    } finally {
      btnStart.disabled = false;
    }
  });

  if (btnCalibrate) {
    btnCalibrate.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/experiment/calibrate_dark", { method: "POST" });
        const calData = await res.json();
        if (calData.success) {
          await customAlert(`Berhasil kalibrasi gelap. Intensitas dikunci pada 0 Lux (Offset: ${calData.offset} Lux)`);
        } else {
          await customAlert(calData.message || "Gagal kalibrasi gelap.");
        }
      } catch (_) {
        await customAlert("Terjadi kesalahan jaringan.");
      }
    });
  }

  btnStop.addEventListener("click", async () => {
    // We didn't have a stop endpoint in the original design if capture was synchronous.
    // The previous design used /api/experiment/capture which blocked or recorded silently.
    // If capture is synchronous, this button might not even be needed. 
    // Assuming we just call capture again or it auto finishes.
  });

  btnReset.addEventListener("click", async () => {
    const isConfirm = await customConfirm("Reset semua percobaan? Data dan gambar akan dihapus.");
    if (!isConfirm) return;
    try {
      const res = await fetch("/api/experiment/reset", { method: "POST" });
      await res.json();
      lastRenderedCount = 0;
      await fetchStatus();
    } catch (_) {}
    Object.values(chartInstances).forEach((c) => c.destroy());
    chartInstances = {};
    historyList.innerHTML = "";
    absorbanceSection.classList.add("hidden");
    if (transChart) {
      transChart.destroy();
      transChart = null;
    }
    transRendered = false;
    lastRenderedCount = 0;
    await fetchStatus();
  });

  // --- History Rendering ---
  function renderHistory(experiments) {
    if (!experiments || experiments.length === 0) {
      historyList.innerHTML = '<div style="padding:12px;color:var(--c-text-muted)">Belum ada data riwayat.</div>';
      return;
    }

    if (experiments.length === lastRenderedCount) return;
    lastRenderedCount = experiments.length;
    historyList.innerHTML = "";

    Object.values(chartInstances).forEach((c) => c.destroy());
    chartInstances = {};

    let currentGroup = "";
    experiments.forEach((exp, i) => {
      if (exp.group !== currentGroup) {
        currentGroup = exp.group;
        const groupTitle = document.createElement("div");
        groupTitle.className = "history-group-title";
        groupTitle.innerHTML = `<i class="ph-fill ph-folder"></i> ${currentGroup}`;
        historyList.appendChild(groupTitle);
      }

      const samples = exp.samples || [];
      let avgLux = 0;
      let maxLux = 0;
      let avgWl = 0;
      if (samples.length > 0) {
        const sumLux = samples.reduce((s, x) => s + x.lux, 0);
        const sumWl = samples.reduce((s, x) => s + x.wl, 0);
        avgLux = sumLux / samples.length;
        avgWl = sumWl / samples.length;
        maxLux = Math.max(...samples.map((x) => x.lux));
      }
      const canvasId = `chart-history-${i}`;

      const card = document.createElement("div");
      card.className = "history-card";
      card.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:8px;">
          ${exp.has_image ? `<img src="/api/experiment/image/${exp.index}?t=${exp.updated_at}" class="history-thumb" data-index="${exp.index}" alt="thumb">` : `<div class="history-thumb" style="background:#111;display:flex;align-items:center;justify-content:center;color:#444;"><i class="ph ph-image-broken" style="font-size:24px"></i></div>`}
        </div>
        <div class="history-info" style="flex:1; display:flex; flex-direction:column; min-width:0;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px;">
            <div>
              <div class="history-name" style="font-size: 1.05rem; margin-bottom:4px;">${exp.label}</div>
              <div style="display:flex; gap:12px; font-family:var(--font-mono); font-size:0.75rem; color:var(--c-text-muted);">
                <span>Avg: <strong style="color:var(--c-text)">${avgLux.toFixed(1)}</strong> Lux</span>
                <span>Max: <strong style="color:var(--c-lux)">${maxLux.toFixed(1)}</strong> Lux</span>
                <span>Avg &lambda;: <strong style="color:var(--c-text)">${avgWl.toFixed(1)}</strong> nm</span>
              </div>
            </div>
            <div style="display:flex; gap:6px;">
              <a href="/api/experiment/excel/${exp.index}" class="btn-icon" title="Unduh Excel" target="_blank"><i class="ph ph-download-simple" style="color:var(--c-success)"></i></a>
              <button class="btn-icon btn-redo-trial" data-index="${exp.index}" title="Ulangi"><i class="ph ph-arrow-counter-clockwise"></i></button>
              <button class="btn-icon btn-delete-trial" data-index="${exp.index}" title="Hapus"><i class="ph ph-trash" style="color:var(--c-danger)"></i></button>
            </div>
          </div>
          <div style="height:480px; position:relative; width:100%;"><canvas id="${canvasId}"></canvas></div>
        </div>
      `;
      historyList.appendChild(card);
      requestAnimationFrame(() => drawMiniChart(canvasId, samples));
    });
  }

  function getSpectrumGradient(context, alpha = 0.8) {
    const chart = context.chart;
    const { ctx, chartArea } = chart;
    if (!chartArea) return null;
    const gradient = ctx.createLinearGradient(chartArea.left, 0, chartArea.right, 0);
    gradient.addColorStop(0.00, `rgba(138, 43, 226, ${alpha})`); // Violet
    gradient.addColorStop(0.16, `rgba(0, 0, 255, ${alpha})`);    // Blue
    gradient.addColorStop(0.33, `rgba(0, 255, 255, ${alpha})`);  // Cyan
    gradient.addColorStop(0.50, `rgba(0, 255, 0, ${alpha})`);    // Green
    gradient.addColorStop(0.66, `rgba(255, 255, 0, ${alpha})`);  // Yellow
    gradient.addColorStop(0.83, `rgba(255, 127, 0, ${alpha})`);  // Orange
    gradient.addColorStop(1.00, `rgba(255, 0, 0, ${alpha})`);    // Red
    return gradient;
  }

  function drawMiniChart(canvasId, samples) {
    const el = document.getElementById(canvasId);
    if (!el || samples.length === 0) return;
    const step = Math.max(1, Math.floor(samples.length / 80));
    const filtered = samples.filter((_, i) => i % step === 0);
    const ctx = el.getContext("2d");
    chartInstances[canvasId] = new Chart(ctx, {
      type: "line",
      data: {
        labels: filtered.map((s) => s.wl),
        datasets: [{
          data: filtered.map((s) => s.lux),
          borderColor: (c) => getSpectrumGradient(c, 1) || "rgba(255,255,255,0.4)",
          backgroundColor: (c) => getSpectrumGradient(c, 0.4) || "transparent",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
          fill: true
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { 
          legend: { display: false }, 
          tooltip: { enabled: true, mode: 'index', intersect: false } 
        },
        scales: { 
          x: { 
            display: true, 
            title: { display: true, text: 'Panjang Gelombang (nm)', color: '#a1a1aa' },
            ticks: { color: "#a1a1aa", maxTicksLimit: 10 },
            grid: { display: false }
          }, 
          y: { 
            display: true, 
            beginAtZero: true,
            title: { display: true, text: 'Intensitas (Lux)', color: '#a1a1aa' },
            ticks: { color: "#a1a1aa" },
            grid: { color: "rgba(255,255,255,0.05)" }
          } 
        }
      }
    });
  }

  // --- Absorbance ---
  let transChart = null;
  let transRendered = false;

  async function fetchAbsorbance() {
    try {
      const res = await fetch("/api/experiment/absorbance");
      if (!res.ok) return;
      const absData = await res.json();
      if (!absData.success) {
        absorbanceSection.classList.add("hidden");
        return;
      }
      if (transRendered) return;
      transRendered = true;
      renderAbsorbance(absData);
    } catch (_) {}
  }

  function renderAbsorbance(data) {
    absorbanceSection.classList.remove("hidden");
    const trans = data.absorbance;
    if (transChart) transChart.destroy();
    const ctx = document.getElementById("chart-absorbance").getContext("2d");
    transChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: trans.map((p) => p.wl.toFixed(1)),
        datasets: [{
          label: "Absorbansi (A)",
          data: trans.map((p) => p.A),
          borderColor: (c) => getSpectrumGradient(c, 1) || "#f43f5e",
          backgroundColor: (c) => getSpectrumGradient(c, 0.3) || "rgba(244, 63, 94, 0.1)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 600, easing: 'easeOutQuart' },
        plugins: { 
          legend: { display: false },
          tooltip: { enabled: true, mode: 'index', intersect: false }
        },
        scales: {
          x: { 
            title: { display: true, text: 'Panjang Gelombang (nm)', color: '#a1a1aa' },
            ticks: { color: "#a1a1aa" }, 
            grid: { display: false } 
          },
          y: { 
            title: { display: true, text: 'Absorbansi (A)', color: '#a1a1aa' },
            ticks: { color: "#a1a1aa" }, 
            grid: { color: "rgba(255,255,255,0.05)" }, 
            beginAtZero: true 
          },
        },
      },
    });

    const avgA = trans.reduce((s, p) => s + p.A, 0) / trans.length;
    const maxA = Math.max(...trans.map((p) => p.A));
    const minA = Math.min(...trans.map((p) => p.A));
    
    statsAbsorbance.innerHTML = `
      <div class="stat-item">
        <span class="stat-lbl">Average</span>
        <span class="stat-val">${avgA.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-lbl">Maximum</span>
        <span class="stat-val">${maxA.toFixed(4)}</span>
      </div>
      <div class="stat-item">
        <span class="stat-lbl">Minimum</span>
        <span class="stat-val">${minA.toFixed(4)}</span>
      </div>
    `;
  }

  // --- API Calls ---
  async function fetchStatus() {
    try {
      const res = await fetch("/api/experiment/status");
      if (!res.ok) return;
      const state = await res.json();
      updateControls(state);
      renderHistory(state.experiments.filter((e) => e.sample_count > 0));

      if (state.total_done >= 9 && !state.recording) {
        fetchAbsorbance();
      } else {
        absorbanceSection.classList.add("hidden");
        transRendered = false;
      }
    } catch (_) {}
  }

  fetchStatus();
  setInterval(fetchStatus, 2000);

  // --- Lightbox ---
  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  const lightboxClose = document.getElementById("lightbox-close");

  historyList.addEventListener("click", async (e) => {
    if (e.target.closest(".history-thumb")) {
      const idx = e.target.closest(".history-thumb").dataset.index;
      if (idx) {
        lightboxImg.src = `/api/experiment/image/${idx}`;
        const downloadBtn = document.getElementById("lightbox-download");
        if (downloadBtn) {
          downloadBtn.href = `/api/experiment/image/${idx}?download=1`;
        }
        lightbox.classList.add("active");
      }
    }
    const redoBtn = e.target.closest(".btn-redo-trial");
    const deleteBtn = e.target.closest(".btn-delete-trial");

    if (redoBtn) {
      const idx = parseInt(redoBtn.getAttribute("data-index"));
      if (!(await customConfirm(`Apakah Anda yakin ingin mengulang Percobaan ${idx + 1}?`))) return;
      try {
        const res = await fetch(`/api/experiment/redo/${idx}`, { method: "POST" });
        const redoData = await res.json();
        if (!redoData.success) await customAlert(redoData.message);
        lastRenderedCount = 0;
        await fetchStatus();
      } catch (_) { await customAlert("Terjadi kesalahan."); }
    }

    if (deleteBtn) {
      const idx = parseInt(deleteBtn.getAttribute("data-index"));
      if (!(await customConfirm(`Hapus data Percobaan ${idx + 1}?`))) return;
      try {
        const res = await fetch(`/api/experiment/delete/${idx}`, { method: "POST" });
        const delData = await res.json();
        if (!delData.success) await customAlert(delData.message);
        lastRenderedCount = 0;
        await fetchStatus();
      } catch (_) { await customAlert("Terjadi kesalahan."); }
    }
  });

  lightboxClose.addEventListener("click", () => {
    lightbox.classList.remove("active");
  });
  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) lightbox.classList.remove("active");
  });

  // --- Custom Modals ---
  const modalOverlay = document.getElementById("custom-modal-overlay");
  const modalTitle = document.getElementById("modal-title");
  const modalMessage = document.getElementById("modal-message");
  const modalBtnCancel = document.getElementById("modal-btn-cancel");
  const modalBtnConfirm = document.getElementById("modal-btn-confirm");

  function showModal(title, message, isAlert = false) {
    return new Promise((resolve) => {
      modalTitle.innerHTML = title;
      modalMessage.textContent = message;
      
      if (isAlert) {
        modalBtnCancel.style.display = "none";
        modalBtnConfirm.textContent = "OK";
        modalBtnConfirm.className = "btn-glow btn-primary";
      } else {
        modalBtnCancel.style.display = "block";
        modalBtnConfirm.textContent = "Ya";
        modalBtnConfirm.className = "btn-glow btn-danger";
      }

      modalOverlay.classList.remove("hidden");

      const handleConfirm = () => {
        cleanup();
        resolve(true);
      };

      const handleCancel = () => {
        cleanup();
        resolve(false);
      };

      const cleanup = () => {
        modalBtnConfirm.removeEventListener("click", handleConfirm);
        modalBtnCancel.removeEventListener("click", handleCancel);
        modalOverlay.classList.add("hidden");
      };

      modalBtnConfirm.addEventListener("click", handleConfirm);
      if (!isAlert) {
        modalBtnCancel.addEventListener("click", handleCancel);
      }
    });
  }

  window.customAlert = (msg) => showModal('<i class="ph-fill ph-warning-circle" style="color:var(--c-lux);"></i> Peringatan', msg, true);
  window.customConfirm = (msg) => showModal('<i class="ph-fill ph-question" style="color:var(--c-text);"></i> Konfirmasi', msg, false);
})();
