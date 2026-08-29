/**
 * ═══════════════════════════════════════════════════════════════════════════
 *  COMMANDER DADANG — PURE CHARTING ENGINE APPLICATION (PHASE 1)
 *  Main Application Orchestrator & UI Event Controller
 * ═══════════════════════════════════════════════════════════════════════════
 */

import { WindowManager } from '../charts/WindowManager.js?v=20260829_11';

try {
  console.log("App.js Initializing...");
  // 1. Initialize Multi-Window Manager
  const windowManager = new WindowManager("#chart-grid-container");
  window.windowManager = windowManager;

  // 2. Bind Top Bar Layout Switchers
  document.querySelectorAll(".layout-btn[data-layout]").forEach(btn => {
    btn.addEventListener("click", () => {
      windowManager.setLayout(btn.dataset.layout);
    });
  });

  // 3. Bind Link Crosshair Toggle
  const btnLinkCrosshair = document.getElementById("btn-link-crosshair");
  if (btnLinkCrosshair) {
    btnLinkCrosshair.addEventListener("click", () => {
      const newState = !windowManager.isCrosshairLinked;
      windowManager.setCrosshairLinked(newState);
      windowManager.saveState();
      showToast(newState ? "🔗 Link Crosshair: AKTIF (Timestamp Sync)" : "⛓ Link Crosshair: NONAKTIF");
    });
  }

  // 4. Bind Left Drawing Toolbar Tools
  document.querySelectorAll(".draw-tool-btn[data-tool]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const tool = btn.dataset.tool;
      setActiveToolbarButton(btn);
      windowManager.setGlobalTool(tool);
    });
  });

  // Flyout submenu tool items
  document.querySelectorAll(".flyout-item[data-tool]").forEach(item => {
    item.addEventListener("click", (e) => {
      e.stopPropagation();
      const tool = item.dataset.tool;
      const parentBtn = item.closest(".tool-group")?.querySelector(".draw-tool-btn");
      if (parentBtn) setActiveToolbarButton(parentBtn);
      windowManager.setGlobalTool(tool);
    });
  });

  function setActiveToolbarButton(activeBtn) {
    document.querySelectorAll(".draw-tool-btn[data-tool]").forEach(b => b.classList.remove("active"));
    if (activeBtn) activeBtn.classList.add("active");
  }

  // 5. Magnet Mode Toggle
  const btnMagnet = document.getElementById("btn-magnet");
  if (btnMagnet) {
    btnMagnet.addEventListener("click", () => {
      let isMagnet = false;
      windowManager.windows.forEach(w => {
        if (w.drawingEngine) isMagnet = w.drawingEngine.toggleMagnet();
      });
      btnMagnet.classList.toggle("active", isMagnet);
      showToast(isMagnet ? "🧲 Magnet Mode: AKTIF (Snap OHLC)" : "Magnet Mode: NONAKTIF");
    });
  }

  // 6. Stay in Draw Mode Toggle
  const btnStayDraw = document.getElementById("btn-stay-draw");
  if (btnStayDraw) {
    btnStayDraw.addEventListener("click", () => {
      let isStay = false;
      windowManager.windows.forEach(w => {
        if (w.drawingEngine) isStay = w.drawingEngine.toggleStayInDrawMode();
      });
      btnStayDraw.classList.toggle("active", isStay);
      showToast(isStay ? "✏️ Stay in Draw Mode: AKTIF" : "Stay in Draw Mode: NONAKTIF");
    });
  }

  // 7. Lock All Drawings Toggle
  const btnLockDrawings = document.getElementById("btn-lock-drawings");
  if (btnLockDrawings) {
    btnLockDrawings.addEventListener("click", () => {
      const isLocked = window.globalDrawingStore.toggleLockAll();
      btnLockDrawings.classList.toggle("active", isLocked);
      showToast(isLocked ? "🔒 Semua Gambar Dikunci" : "🔓 Gambar Terbuka");
    });
  }

  // 8. Hide / Show Drawings Toggle
  const btnHideDrawings = document.getElementById("btn-hide-drawings");
  if (btnHideDrawings) {
    btnHideDrawings.addEventListener("click", () => {
      const isHidden = window.globalDrawingStore.toggleHideAll();
      btnHideDrawings.classList.toggle("active", isHidden);
      showToast(isHidden ? "👁️ Gambar Disembunyikan" : "👁️ Gambar Ditampilkan");
    });
  }

  // 9. Trash / Clear Drawings
  const btnTrashDrawings = document.getElementById("btn-trash-drawings");
  if (btnTrashDrawings) {
    btnTrashDrawings.addEventListener("click", () => {
      if (confirm("Hapus semua gambar pada semua chart?")) {
        window.globalDrawingStore.clearAll();
        showToast("🗑️ Semua gambar dibersihkan");
      }
    });
  }

  // 10. Global Fullscreen Toggle
  const btnFullscreen = document.getElementById("btn-fullscreen");
  if (btnFullscreen) {
    btnFullscreen.addEventListener("click", () => {
      toggleFullScreen();
    });
  }

  // 11. Go To Time Modal
  const btnGoToTime = document.getElementById("btn-goto-time");
  if (btnGoToTime) {
    btnGoToTime.addEventListener("click", () => {
      openGoToTimeModal();
    });
  }

  // 12. Reset All View
  const btnResetAll = document.getElementById("btn-reset-all");
  if (btnResetAll) {
    btnResetAll.addEventListener("click", () => {
      windowManager.windows.forEach(w => {
        w.chart.timeScale().fitContent();
      });
      showToast("⛶ View Reset (Auto Fit)");
    });
  }

  // 13. Toggle Right Cockpit Sidebar (Header Button & Floating Edge Tab)
  const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");
  const btnCockpitTab = document.getElementById("btn-cockpit-tab");
  const sidebarCockpit = document.getElementById("sidebar-cockpit");
  // Mobile Auto-Collapse Sidebar & Default View
  const isMobileScreen = window.innerWidth <= 900;
  if (isMobileScreen && sidebarCockpit) {
    sidebarCockpit.classList.add("collapsed");
    if (btnToggleSidebar) btnToggleSidebar.classList.remove("active");
  }

  window.addEventListener("resize", () => {
    if (window.windowManager && window.windowManager.windows) {
      window.windowManager.windows.forEach(w => w.resize());
    }
  });
  window.addEventListener("orientationchange", () => {
    setTimeout(() => {
      if (window.windowManager && window.windowManager.windows) {
        window.windowManager.windows.forEach(w => w.resize());
      }
    }, 200);
  });


  function toggleCockpit() {
    if (!sidebarCockpit) return;
    sidebarCockpit.classList.toggle("collapsed");
    const isCollapsed = sidebarCockpit.classList.contains("collapsed");
    if (btnToggleSidebar) btnToggleSidebar.classList.toggle("active", !isCollapsed);
    if (btnCockpitTab) btnCockpitTab.textContent = isCollapsed ? "◀" : "▶";
    try {
      localStorage.setItem("cd_cockpit_collapsed", isCollapsed ? "1" : "0");
    } catch (e) {}
    setTimeout(() => {
      windowManager.windows.forEach(w => w.resize());
    }, 260);
  }

  // Restore saved cockpit state
  try {
    const savedCockpit = localStorage.getItem("cd_cockpit_collapsed");
    if (savedCockpit === "1" && sidebarCockpit) {
      sidebarCockpit.classList.add("collapsed");
      if (btnToggleSidebar) btnToggleSidebar.classList.remove("active");
      if (btnCockpitTab) btnCockpitTab.textContent = "◀";
    }
  } catch (e) {}

  
  // ─────────────────────────────────────────────────────────────────────────
  // BULLETPROOF DRAG-TO-RESIZE COCKPIT SIDEBAR WITH LOCALSTORAGE PERSISTENCE
  // ─────────────────────────────────────────────────────────────────────────
  const cockpitResizer = document.getElementById("cockpit-resizer");

  if (cockpitResizer && sidebarCockpit) {
    let isResizing = false;
    let startX = 0;
    let startW = 380;

    const applyWidth = (w) => {
      const clamped = Math.max(280, Math.min(800, w));
      sidebarCockpit.style.setProperty("--cockpit-width", `${clamped}px`);
      sidebarCockpit.style.width = `${clamped}px`;
      return clamped;
    };

    // Restore saved width
    try {
      const saved = localStorage.getItem("cd_cockpit_width");
      if (saved && parseInt(saved, 10) >= 280) {
        applyWidth(parseInt(saved, 10));
      }
    } catch (e) {}

    cockpitResizer.addEventListener("mousedown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      isResizing = true;
      startX = e.clientX;
      startW = sidebarCockpit.getBoundingClientRect().width;
      cockpitResizer.classList.add("resizing");
      document.body.style.cursor = "ew-resize";
      document.body.style.userSelect = "none";
    });

    // Audit fix: dulu w.resize() (4 chart window, tiap resize() bikin
    // lightweight-charts re-layout+redraw) dipanggil di SETIAP event
    // mousemove mentah - bisa ratusan kali/detik pas drag cepat, jank.
    // Ditrotel ke requestAnimationFrame, sama kayak pola RAF yang udah
    // dipakai di tempat lain di file ini (_rafSDPending dkk).
    let cockpitResizeRafPending = false;
    window.addEventListener("mousemove", (e) => {
      if (!isResizing) return;
      const dx = startX - e.clientX;
      applyWidth(startW + dx);
      if (cockpitResizeRafPending) return;
      cockpitResizeRafPending = true;
      requestAnimationFrame(() => {
        cockpitResizeRafPending = false;
        if (window.windowManager && window.windowManager.windows) {
          window.windowManager.windows.forEach(w => w.resize());
        }
      });
    });

    window.addEventListener("mouseup", () => {
      if (isResizing) {
        isResizing = false;
        cockpitResizer.classList.remove("resizing");
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        try {
          const finalW = Math.round(sidebarCockpit.getBoundingClientRect().width);
          localStorage.setItem("cd_cockpit_width", finalW);
        } catch (e) {}
        if (window.windowManager && window.windowManager.windows) {
          window.windowManager.windows.forEach(w => w.resize());
        }
      }
    });
  }
  if (btnToggleSidebar) btnToggleSidebar.addEventListener("click", toggleCockpit);
  if (btnCockpitTab) btnCockpitTab.addEventListener("click", toggleCockpit);


  // 14. Indicators Modal Dialog Handling
  let targetIndicatorWindow = null;
  const indModal = document.getElementById("indicators-modal");
  const btnOpenIndModal = document.getElementById("btn-open-indicators");
  const btnCloseIndModal = document.getElementById("btn-close-ind-modal");
  const indSearchInput = document.getElementById("ind-search-input");

  window.openIndicatorsModalForWindow = function(win) {
    targetIndicatorWindow = win;
    if (indModal) {
      indModal.classList.add("show");
      if (indSearchInput) {
        indSearchInput.value = "";
        indSearchInput.focus();
        filterIndicators("");
      }
    }
  };

  if (btnOpenIndModal) {
    btnOpenIndModal.addEventListener("click", () => {
      window.openIndicatorsModalForWindow(windowManager.windows[0]);
    });
  }

  if (btnCloseIndModal && indModal) {
    btnCloseIndModal.addEventListener("click", () => indModal.classList.remove("show"));
    indModal.addEventListener("click", (e) => {
      if (e.target === indModal) indModal.classList.remove("show");
    });
  }

  function filterIndicators(query) {
    const q = query.toLowerCase();
    document.querySelectorAll(".ind-list-item").forEach(item => {
      const txt = item.textContent.toLowerCase();
      item.style.display = txt.includes(q) ? "flex" : "none";
    });
  }

  if (indSearchInput) {
    indSearchInput.addEventListener("input", (e) => {
      filterIndicators(e.target.value);
    });
  }

  // Add Configured Custom MA
  const btnAddCustomMA = document.getElementById("btn-add-custom-ma");
  if (btnAddCustomMA) {
    btnAddCustomMA.addEventListener("click", () => {
      const type = document.getElementById("custom-ma-type")?.value || "SMA";
      const period = parseInt(document.getElementById("custom-ma-period")?.value, 10) || 20;
      const color = document.getElementById("custom-ma-color")?.value || "#ffb703";

      windowManager.windows.forEach(w => {
        w.addIndicator(type, period, color);
      });
      if (indModal) indModal.classList.remove("show");
    });
  }

  // Preset Add Buttons
  document.querySelectorAll(".ind-list-item .ind-add-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const item = e.target.closest(".ind-list-item");
      if (!item) return;
      const type = item.dataset.type || "SMA";
      const period = parseInt(item.dataset.period, 10) || 20;
      const color = item.dataset.color || "#ffb703";

      windowManager.windows.forEach(w => {
        w.addIndicator(type, period, color);
      });
      if (indModal) indModal.classList.remove("show");
    });
  });

  // 15. Indicator Settings Modal Dialog
  let settingsTargetWin = null;
  let settingsTargetIndId = null;
  const settingsModal = document.getElementById("indicator-settings-modal");
  const btnCloseIndSettings = document.getElementById("btn-close-ind-settings");
  const btnSaveIndSettings = document.getElementById("btn-save-ind-settings");

  window.openIndicatorSettingsModal = function(win, indId) {
    settingsTargetWin = win;
    settingsTargetIndId = indId;
    const ind = win.activeIndicators.get(indId);
    if (!ind || !settingsModal) return;

    document.getElementById("edit-ind-id").value = ind.id;
    document.getElementById("edit-ind-type").value = ind.type;
    document.getElementById("edit-ind-period").value = ind.period;
    document.getElementById("edit-ind-color").value = ind.color;

    settingsModal.classList.add("show");
  };

  if (btnCloseIndSettings && settingsModal) {
    btnCloseIndSettings.addEventListener("click", () => settingsModal.classList.remove("show"));
    settingsModal.addEventListener("click", (e) => {
      if (e.target === settingsModal) settingsModal.classList.remove("show");
    });
  }

  if (btnSaveIndSettings) {
    btnSaveIndSettings.addEventListener("click", () => {
      if (!settingsTargetWin || !settingsTargetIndId) return;
      const newType = document.getElementById("edit-ind-type").value;
      const newPeriod = parseInt(document.getElementById("edit-ind-period").value, 10) || 20;
      const newColor = document.getElementById("edit-ind-color").value;

      windowManager.windows.forEach(w => {
        if (w.activeIndicators.has(settingsTargetIndId)) {
          w.updateIndicatorConfig(settingsTargetIndId, newType, newPeriod, newColor);
        }
      });
      if (settingsModal) settingsModal.classList.remove("show");
    });
  }

  // 16. Full TradingView Chart Settings Modal Dialog
  const chartSettingsModal = document.getElementById("chart-settings-modal");
  const btnOpenChartSettings = document.getElementById("btn-open-chart-settings");
  const btnCloseChartSettings = document.getElementById("btn-close-chart-settings");
  const btnSaveChartSettings = document.getElementById("btn-save-chart-settings");
  const btnResetChartSettings = document.getElementById("btn-reset-chart-settings");


  function syncSettingsModalInputs() {
    const cfg = windowManager.globalChartConfig || {};
    if (document.getElementById("cfg-candle-up")) document.getElementById("cfg-candle-up").value = cfg.candleUp || "#00e676";
    if (document.getElementById("cfg-candle-down")) document.getElementById("cfg-candle-down").value = cfg.candleDown || "#ff334b";
    if (document.getElementById("cfg-wick-up")) document.getElementById("cfg-wick-up").value = cfg.wickUp || "#00e676";
    if (document.getElementById("cfg-wick-down")) document.getElementById("cfg-wick-down").value = cfg.wickDown || "#ff334b";
    if (document.getElementById("cfg-countdown-toggle")) document.getElementById("cfg-countdown-toggle").checked = cfg.showCountdown !== false;
    if (document.getElementById("cfg-last-price-label")) document.getElementById("cfg-last-price-label").checked = cfg.showLastPrice !== false;
    if (document.getElementById("cfg-ohlc-legend-toggle")) document.getElementById("cfg-ohlc-legend-toggle").checked = cfg.showOHLC !== false;
    if (document.getElementById("cfg-volume-toggle")) document.getElementById("cfg-volume-toggle").checked = cfg.showVolume !== false;
    if (document.getElementById("cfg-chart-bg")) document.getElementById("cfg-chart-bg").value = cfg.chartBg || "#07090e";
    if (document.getElementById("cfg-grid-color")) document.getElementById("cfg-grid-color").value = cfg.gridColor || "#161c28";
    if (document.getElementById("cfg-grid-toggle")) document.getElementById("cfg-grid-toggle").checked = cfg.showGrid !== false;
    if (document.getElementById("cfg-crosshair-style")) document.getElementById("cfg-crosshair-style").value = cfg.crosshairStyle || "dashed";
  }

  if (btnOpenChartSettings && chartSettingsModal) {
    btnOpenChartSettings.addEventListener("click", () => {
      syncSettingsModalInputs();
      chartSettingsModal.classList.add("show");
    });
  }

  if (btnCloseChartSettings && chartSettingsModal) {
    btnCloseChartSettings.addEventListener("click", () => chartSettingsModal.classList.remove("show"));
    chartSettingsModal.addEventListener("click", (e) => {
      if (e.target === chartSettingsModal) chartSettingsModal.classList.remove("show");
    });
  }

  // Settings Tab Switching
  document.querySelectorAll(".settings-tab-btn[data-tab]").forEach(tabBtn => {
    tabBtn.addEventListener("click", () => {
      document.querySelectorAll(".settings-tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
      tabBtn.classList.add("active");
      const targetPane = document.getElementById(`tab-${tabBtn.dataset.tab}`);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  if (btnSaveChartSettings) {
    btnSaveChartSettings.addEventListener("click", () => {
      const cfg = {
        candleUp: document.getElementById("cfg-candle-up")?.value || "#00e676",
        candleDown: document.getElementById("cfg-candle-down")?.value || "#ff334b",
        wickUp: document.getElementById("cfg-wick-up")?.value || "#00e676",
        wickDown: document.getElementById("cfg-wick-down")?.value || "#ff334b",
        showCountdown: document.getElementById("cfg-countdown-toggle")?.checked ?? true,
        showLastPrice: document.getElementById("cfg-last-price-label")?.checked ?? true,
        showOHLC: document.getElementById("cfg-ohlc-legend-toggle")?.checked ?? true,
        showVolume: document.getElementById("cfg-volume-toggle")?.checked ?? true,
        chartBg: document.getElementById("cfg-chart-bg")?.value || "#07090e",
        gridColor: document.getElementById("cfg-grid-color")?.value || "#161c28",
        showGrid: document.getElementById("cfg-grid-toggle")?.checked ?? true,
        crosshairStyle: document.getElementById("cfg-crosshair-style")?.value || "dashed"
      };
      windowManager.applyGlobalChartConfig(cfg);
      if (chartSettingsModal) chartSettingsModal.classList.remove("show");
    });
  }

  if (btnResetChartSettings) {
    btnResetChartSettings.addEventListener("click", () => {
      const defaultCfg = {
        candleUp: "#00e676",
        candleDown: "#ff334b",
        wickUp: "#00e676",
        wickDown: "#ff334b",
        showCountdown: true,
        showLastPrice: true,
        showOHLC: true,
        showVolume: true,
        chartBg: "#07090e",
        gridColor: "rgba(255, 255, 255, 0.04)",
        showGrid: true,
        crosshairStyle: "dashed"
      };
      windowManager.applyGlobalChartConfig(defaultCfg);
      syncSettingsModalInputs();
      if (chartSettingsModal) chartSettingsModal.classList.remove("show");
    });
  }



  // 17. Replay/Backtest Modal & Control Bar - Dadang: "semua data history
  // harus ke save biar bisa buat bactes n replay" (candle MT5 asli +
  // histori DNA Vault, lihat WindowManager.js startReplay() dkk).
  const replayModal = document.getElementById("replay-modal");
  const btnOpenReplay = document.getElementById("btn-open-replay");
  const btnCloseReplayModal = document.getElementById("btn-close-replay-modal");
  const replayDateList = document.getElementById("replay-date-list");

  async function openReplayModal() {
    if (!replayModal) return;
    replayModal.classList.add("show");
    if (replayDateList) replayDateList.innerHTML = `<div style="color:var(--text-secondary,#94a3b8);font-size:12px;padding:10px;">Memuat daftar tanggal...</div>`;
    const dates = await windowManager.loadReplayDates();
    if (!replayDateList) return;
    if (dates.length === 0) {
      replayDateList.innerHTML = `<div style="color:var(--text-secondary,#94a3b8);font-size:12px;padding:10px;">Belum ada histori DNA Vault. EA harus jalan dulu (nulis 1x/menit).</div>`;
      return;
    }
    replayDateList.innerHTML = dates.slice().reverse().map(d =>
      `<div class="replay-date-item" data-date="${d.date}"><span>📅 ${d.date}</span><span class="count">${d.snapshot_count} snapshot</span></div>`
    ).join("");
    replayDateList.querySelectorAll(".replay-date-item").forEach(item => {
      item.addEventListener("click", async () => {
        replayModal.classList.remove("show");
        const ok = await windowManager.startReplay(item.dataset.date);
        if (ok && replayBar) replayBar.style.display = "flex";
      });
    });
  }

  if (btnOpenReplay) btnOpenReplay.addEventListener("click", openReplayModal);
  if (btnCloseReplayModal && replayModal) {
    btnCloseReplayModal.addEventListener("click", () => replayModal.classList.remove("show"));
    replayModal.addEventListener("click", (e) => {
      if (e.target === replayModal) replayModal.classList.remove("show");
    });
  }

  const replayBar = document.getElementById("replay-bar");
  const btnReplayStepBack = document.getElementById("replay-step-back-btn");
  const btnReplayPlay = document.getElementById("replay-play-btn");
  const btnReplayStepFwd = document.getElementById("replay-step-fwd-btn");
  const replaySlider = document.getElementById("replay-slider");
  const replaySpeedSelect = document.getElementById("replay-speed-select");
  const btnExitReplay = document.getElementById("btn-exit-replay");

  if (btnReplayStepBack) btnReplayStepBack.addEventListener("click", () => { windowManager.replayPause(); windowManager.replayStep(-1); });
  if (btnReplayStepFwd) btnReplayStepFwd.addEventListener("click", () => { windowManager.replayPause(); windowManager.replayStep(1); });
  if (btnReplayPlay) btnReplayPlay.addEventListener("click", () => {
    if (!windowManager.replayState) return;
    if (windowManager.replayState.playing) windowManager.replayPause();
    else windowManager.replayPlay();
  });
  if (replaySlider) replaySlider.addEventListener("input", (e) => {
    windowManager.replayPause();
    windowManager.replayGoTo(parseInt(e.target.value, 10));
  });
  if (replaySpeedSelect) replaySpeedSelect.addEventListener("change", (e) => {
    windowManager.setReplaySpeed(parseInt(e.target.value, 10));
  });
  if (btnExitReplay) btnExitReplay.addEventListener("click", () => windowManager.stopReplay());

  // Global Keyboard Shortcuts
  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;

    if (e.key === "Escape") {
      if (indModal && indModal.classList.contains("show")) {
        indModal.classList.remove("show");
        return;
      }
      setActiveToolbarButton(document.querySelector('.draw-tool-btn[data-tool="cursor"]'));
      windowManager.setGlobalTool("cursor");
    } else if (e.key === "1") {
      windowManager.setLayout("SINGLE");
    } else if (e.key === "2") {
      windowManager.setLayout("DUAL_VERT");
    } else if (e.key === "4") {
      windowManager.setLayout("QUAD");
    } else if (e.key === "+" || e.key === "=") {
      windowManager.windows.forEach(w => w.zoom(0.75));
    } else if (e.key === "-" || e.key === "_") {
      windowManager.windows.forEach(w => w.zoom(1.35));
    } else if (e.key === "0") {
      windowManager.windows.forEach(w => w.chart.timeScale().fitContent());
    } else if (e.key === "c" || e.key === "C") {
      toggleCockpit();
    } else if (e.key === "i" || e.key === "I") {
      window.openIndicatorsModalForWindow(windowManager.windows[0]);
    }
  });




// ─────────────────────────────────────────────────────────────────────────────
// HELPER UTILITIES
// ─────────────────────────────────────────────────────────────────────────────
window.showToast = showToast;
function showToast(msg, isError = false) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = msg;
  toast.style.borderColor = isError ? "#ff334b" : "#00f0ff";
  toast.className = "toast-msg show";
  setTimeout(() => {
    toast.className = "toast-msg";
  }, 3000);
}

function toggleFullScreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    }
  }
}

function openGoToTimeModal() {
  const inputStr = prompt("Masukkan Tanggal/Waktu (YYYY-MM-DD HH:MM) atau Timestamp:", new Date().toISOString().slice(0, 16).replace("T", " "));
  if (!inputStr) return;

  let targetTs = 0;
  if (/^\d+$/.test(inputStr.trim())) {
    targetTs = parseInt(inputStr.trim(), 10);
  } else {
    const dt = new Date(inputStr.trim());
    if (!isNaN(dt.getTime())) {
      targetTs = Math.floor(dt.getTime() / 1000);
    }
  }

  if (targetTs > 0 && windowManager) {
    windowManager.windows.forEach(w => {
      w.syncCrosshairTimestamp(targetTs);
      // Center timescale around targetTs
      const timeScale = w.chart.timeScale();
      const coord = timeScale.timeToCoordinate(targetTs);
      if (coord !== null) {
        timeScale.scrollToPosition(0, true);
      }
    });
    showToast(`Go to time: ${new Date(targetTs * 1000).toLocaleString()}`);
  } else {
    showToast("Format waktu tidak valid", true);
  }
}

} catch (e) {
  document.body.innerHTML += '<div style="color:red; background: black; padding: 20px; position: absolute; z-index: 9999; top: 0; left: 0; font-size: 20px;">ERROR: ' + e.stack + '</div>';
  console.error(e);
}

