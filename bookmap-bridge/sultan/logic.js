// SULTAN SNIPER ENGINE - dashboard logic (v34)
// Polls /sultan_status.json (proxied from MT5's Common\Files by
// sultan_dashboard_server.py) every 800ms and updates the DOM. No
// TradingView/Pine dependency anywhere in this path - data comes straight
// from DD_ChainReaction_MultiTF_EA.mq5's WriteSultanStatus().

const POLL_MS = 800;
const REGIME_ORDER = [
  { key: "d1", label: "D1" },
  { key: "h4", label: "H4" },
  { key: "h1", label: "H1" },
  { key: "m30", label: "M30" },
  { key: "m15", label: "M15" },
  { key: "m5", label: "M5" },
];

function dirArrow(dir) {
  if (dir === "BUY") return '<span class="text-emerald-400">&#9650;</span>';
  if (dir === "SELL") return '<span class="text-rose-400">&#9660;</span>';
  return '<span class="text-slate-600">-</span>';
}
function dirColorClass(dir) {
  if (dir === "BUY") return "text-emerald-400";
  if (dir === "SELL") return "text-rose-400";
  return "text-slate-500";
}
function set(id, text, cls) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  // v52.8: also strip old bg-*-N classes (with optional /opacity suffix,
  // e.g. "bg-emerald-400/10") - the bmread-verdict badge is the first
  // caller to pass a bg- class alongside text-, and without this the old
  // color would never get removed, just added to on every poll.
  if (cls) el.className = el.className.replace(/(?:text|bg)-\S+-\d+(?:\/\d+)?/g, "").trim() + " " + cls;
}
// v37: "lo buat web dhasboard py nya lebih hidup biar gw gak bosan" -
// flash a value green/red on each real change (classic ticker feel).
const _prevFlashValues = {};
function flashIfChanged(id, rawValue) {
  const el = document.getElementById(id);
  if (!el || rawValue === undefined || rawValue === null || isNaN(rawValue)) return;
  const prev = _prevFlashValues[id];
  if (prev !== undefined && rawValue !== prev) {
    const cls = rawValue > prev ? "flash-up" : "flash-down";
    el.classList.remove("flash-up", "flash-down");
    void el.offsetWidth; // force reflow so the animation restarts even if the same class was just applied
    el.classList.add(cls);
  }
  _prevFlashValues[id] = rawValue;
}

function fmt(n, digits = 2) {
  if (n === undefined || n === null || isNaN(n)) return "-";
  return Number(n).toFixed(digits);
}

function setDots(cls) {
  const el = document.getElementById("online-dot-top");
  if (el) el.className = "inline-block w-1.5 h-1.5 rounded-full " + cls;
}

function render(data) {
  if (!data || data.error) {
    set("online-text", "NO DATA", "text-slate-500");
    setDots("bg-slate-600");
    return;
  }

  document.getElementById("ea-version").textContent = data.ea_version || "v?";
  const online = !!data.online;
  setDots(online ? "bg-emerald-400 pulse-dot" : "bg-slate-600");
  set("online-text", online ? "Bookmap Live" : "Bookmap Offline", online ? "text-emerald-400" : "text-slate-500");

  // 1. MARKET REGIME
  const regime = data.regime || {};
  const tbody = document.getElementById("regime-tbody");
  tbody.innerHTML = REGIME_ORDER.map(({ key, label }) => {
    const dir = regime[key] || "WAIT";
    return `<tr>
      <td class="py-1 text-slate-300">${label}</td>
      <td class="py-1">${dirArrow(dir)}</td>
      <td class="py-1 font-bold ${dirColorClass(dir)}">${dir}</td>
    </tr>`;
  }).join("");
  set("regime-alignment", fmt(regime.alignment_pct, 0) + "%");
  set("regime-bias", regime.htf_bias || "-", regime.htf_bias === "BULLISH" ? "text-emerald-400" : regime.htf_bias === "BEARISH" ? "text-rose-400" : "text-slate-400");
  set("regime-m5status", (regime.m5_status || "-").replace("_", " "), regime.m5_status === "WITH_TREND" ? "text-emerald-400" : regime.m5_status === "COUNTER_TREND" ? "text-amber-400" : "text-slate-400");
  // v52.17: Dadang - "itu trending sell atau trending buy bro" (same
  // question asked of the MT5 panel, same fix here) - TRENDING already
  // means H4/M30/M5 all agree (that's what alignment_pct=100 means), so the
  // direction is just regime.h4. No new field needed - already in the JSON.
  const regimeTxt = regime.regime === "TRENDING" ? `TRENDING ${regime.h4 || ""}`.trim() : (regime.regime || "-");
  set("regime-label", "REGIME — " + regimeTxt, regime.regime === "TRENDING" ? "text-emerald-400" : "text-amber-400");

  // 2. BOOKMAP FLOW
  const flow = data.flow || {};
  set("flow-cvd", (flow.cvd >= 0 ? "+" : "") + fmt(flow.cvd, 1), flow.cvd >= 0 ? "text-emerald-400" : "text-rose-400");
  flashIfChanged("flow-cvd", flow.cvd);
  set("flow-delta1m", (flow.delta_1m >= 0 ? "+" : "") + fmt(flow.delta_1m, 1), flow.delta_1m >= 0 ? "text-emerald-400" : "text-rose-400");
  flashIfChanged("flow-delta1m", flow.delta_1m);
  set("flow-volratio", fmt(flow.vol_ratio_buy_pct, 0) + "% BUY / " + fmt(100 - (flow.vol_ratio_buy_pct || 50), 0) + "% SELL");
  set("flow-pulse", fmt(flow.pulse_pct, 1) + "%");
  flashIfChanged("flow-pulse", flow.pulse_pct);
  set("flow-absorb", flow.absorption || "NONE", (flow.absorption && flow.absorption !== "NONE") ? "text-amber-400" : "text-slate-400");
  set("flow-dominant", "FLOW — " + (flow.flow_dominant || "-") + " DOMINANT", flow.flow_dominant === "BUY" ? "text-emerald-400" : "text-rose-400");
  drawDeltaChart(flow.delta_history || []);
  updatePulseGauge(flow.pulse_pct);

  // 3. LIQUIDITY
  const liq = data.liquidity || {};
  set("liq-bidwall", liq.bid_wall_price ? `${fmt(liq.bid_wall_price)} ${fmt(liq.bid_wall_ratio, 1)}x` : "-");
  set("liq-askwall", liq.ask_wall_price ? `${fmt(liq.ask_wall_price)} ${fmt(liq.ask_wall_ratio, 1)}x` : "-");
  set("liq-nearest", liq.nearest_wall_side ? `${liq.nearest_wall_side} +${fmt(liq.nearest_wall_distance)}` : "-",
      liq.nearest_wall_side === "BID" ? "text-emerald-400" : "text-rose-400");
  set("liq-imbalance", fmt(liq.wall_imbalance, 2), liq.wall_imbalance >= 0 ? "text-emerald-400" : "text-rose-400");
  set("liq-bidcount", liq.bid_wall_count ?? "-");
  set("liq-askcount", liq.ask_wall_count ?? "-");
  set("liq-bidtotal", fmt(liq.bid_wall_total_lot, 0) + " lot");
  set("liq-asktotal", fmt(liq.ask_wall_total_lot, 0) + " lot");
  renderLadder(liq.ask_ladder || [], liq.bid_ladder || [], data.price);

  // v52.26/v52.69: WALL SWEEP + reversal - Dadang: "ide gila lagi bro?" ->
  // stop-hunt/liquidity-grab detection. v52.69: EA-side now tracks a
  // PERSISTENT record (`active`) that stays true until the level is
  // genuinely broken by a candle close, not a 20-min time window - Dadang:
  // "selama belum kejebol masih tercatat di panel". Read `active` straight
  // from the EA instead of re-deriving a local time cutoff here, so this
  // dashboard never disagrees with the MT5 panel/chart.
  const sweep = data.wall_sweep || {};
  const sweepFresh = !!sweep.active;
  if (sweepFresh) {
    const tag = sweep.status === "REVERSAL_CONFIRMED" ? "REVERSAL" : sweep.status === "CONTINUATION" ? "LANJUT" : "PENDING";
    const sweepTxt = `${sweep.side} ${fmt(sweep.size, 0)}L @ ${fmt(sweep.price)} — ${tag} (${fmt(sweep.since_sec, 0)}s)`;
    // v52.27: fixed sky-blue regardless of side/status (Dadang: "garis wal
    // lama sudah ijo dan merah, gimana mata gw bedain dengan cepat") - same
    // "sweep = blue, walls = green/red" split as the MT5 chart arrow/panel
    // row, so all 3 surfaces teach one color association.
    set("sweep-label", "WALL SWEEP — " + sweepTxt, "text-sky-400");
  } else {
    set("sweep-label", "WALL SWEEP — —", "text-slate-500");
  }

  // 4. LOCATION
  const loc = data.location || {};
  set("loc-poc", fmt(loc.poc));
  set("loc-va", loc.val ? `${fmt(loc.val)} - ${fmt(loc.vah)}` : "-");
  set("loc-price", fmt(loc.current_price));
  flashIfChanged("loc-price", loc.current_price);
  const posLabel = (loc.position || "-").replace("_", " ");
  set("loc-position", posLabel, loc.position === "INSIDE_VA" ? "text-amber-400" : loc.position === "ABOVE_VA" ? "text-emerald-400" : loc.position === "BELOW_VA" ? "text-rose-400" : "text-slate-400");
  // v52.36: 5-state POC/VA bias - same reads as the MT5 panel's "VA Bias"
  // row (BUY (breakout) / POTENTIAL BUY / SIDEWAYS / POTENTIAL SELL /
  // SELL (breakout)) - see DD_ChainReaction_MultiTF_EA_v2.mq5's
  // ComputeVaLocation().
  const vaBias = loc.va_bias || "-";
  const vaBiasClr = vaBias.includes("SELL") ? "text-rose-400" : vaBias.includes("BUY") ? "text-emerald-400" : "text-slate-400";
  set("loc-vabias", vaBias, vaBiasClr);
  set("loc-distpoc", loc.distance_to_poc !== undefined ? `${fmt(loc.distance_to_poc)} (${fmt(loc.distance_to_poc_pct, 0)}%)` : "-");
  set("loc-range", fmt(loc.range_24h));
  set("loc-atr", fmt(loc.atr14));
  document.getElementById("loc-val-label").textContent = loc.val ? `Low ${fmt(loc.val)}` : "Low";
  document.getElementById("loc-vah-label").textContent = loc.vah ? `High ${fmt(loc.vah)}` : "High";
  if (loc.val && loc.vah && loc.vah > loc.val && loc.current_price) {
    const span = loc.vah - loc.val;
    const padded = span * 1.5; // extra room so the price marker isn't stuck at the edge when outside VA
    const lo = loc.val - padded * 0.25, hi = loc.vah + padded * 0.25;
    const pricePct = Math.min(100, Math.max(0, ((loc.current_price - lo) / (hi - lo)) * 100));
    document.getElementById("loc-price-marker").style.left = pricePct + "%";
  }

  // 5. CONTEXT SUMMARY
  const ctx = data.context || {};
  set("ctx-bias", ctx.htf_bias || "-", ctx.htf_bias === "BULLISH" ? "text-emerald-400" : ctx.htf_bias === "BEARISH" ? "text-rose-400" : "text-slate-400");
  set("ctx-flow", ctx.flow || "-", ctx.flow === "BUY" ? "text-emerald-400" : "text-rose-400");
  set("ctx-liquidity", (ctx.liquidity || "-").replace("_", " "), "text-slate-300");
  set("ctx-location", (ctx.location || "-").replace("_", " "), "text-slate-300");
  set("ctx-regime", ctx.regime || "-", ctx.regime === "TRENDING" ? "text-emerald-400" : "text-amber-400");
  set("ctx-action", "CONTEXT — " + (ctx.action || "-").replace("_", " / "));

  // v44: conviction. The direction is NOT decided here - it's whatever the
  // M30 cascade says. This reports how many independent factors agree and
  // names the ones that don't, so a thin setup is visible before entry.
  const conv = data.conviction || {};
  // v44.3: mode (TREND/SCALP) and trigger readiness are separate questions.
  // Counter-HTF is a trade TYPE per doctrine, not a low-quality setup.
  // v45: the chain ladder leads - how far the M5 breakouts have propagated
  // upward (M5>M15>M30>H1>H4>D1). Flow is the confirmation layer on top.
  const gradeClass = conv.grade === "SIAP" ? "text-emerald-400"
                   : conv.grade === "HATI-HATI" ? "text-amber-400"
                   : (conv.grade === "FLOW LAWAN" || conv.grade === "TAHAN - NEWS") ? "text-rose-400"
                   : "text-slate-400";
  if (conv.dir === "BUY" || conv.dir === "SELL") {
    set("conv-headline", `${conv.dir}  RANTAI ${conv.score}/${conv.max}  ·  ${conv.grade || ""}`, gradeClass);
  } else {
    set("conv-headline", "NO SETUP — M5 WAIT", "text-slate-500");
  }
  const againstEl = document.getElementById("conv-against");
  if (againstEl) {
    const done = (conv.chain_done || "").split(">").filter(Boolean);
    const pending = (conv.chain_pending || "").split(" ").filter(Boolean);
    const ladder = done.map(t => `<span class="text-emerald-400">${t}</span>`)
      .concat(pending.map(t => `<span class="text-slate-600">${t}</span>`)).join(
        '<span class="text-slate-700"> › </span>');
    const modeLine = `<div class="text-slate-400">${conv.mode || ""}${
      conv.flow_max ? ` · flow ${conv.flow_score}/${conv.flow_max}` : ""}</div>`;
    const list = conv.against || [];
    againstEl.innerHTML = (ladder ? `<div class="mb-0.5">${ladder}</div>` : "") + modeLine +
      (list.length ? list.map(a => `<div>${a}</div>`).join("") : "");
  }

  // 6. DATA STATUS
  const ds = data.data_status || {};
  set("ds-bookmap", ds.bookmap_online ? "LIVE" : "OFFLINE", ds.bookmap_online ? "text-emerald-400" : "text-slate-500");
  set("ds-latency", ds.bridge_latency_ms >= 0 ? Math.round(ds.bridge_latency_ms) + "ms" : "-");
  set("ds-balance", `$${fmt(data.balance)} / $${fmt(data.equity)}`);

  // v43.2: USD fundamental, straight from MT5 (DXY with EURUSD fallback) plus
  // the economic calendar. Stated as its effect on gold - weak dollar lifts
  // gold, strong dollar pressures it - rather than graded against the setup.
  const usd = data.usd || {};
  const usdClass = usd.bias === "WEAK" ? "text-emerald-400"
                 : usd.bias === "STRONG" ? "text-rose-400" : "text-slate-400";
  if (usd.bias) {
    set("ds-macro", `${usd.symbol || ""} ${usd.dir || ""} · ${usd.bias}`, usdClass);
    set("ds-macro-verdict", usd.gold_effect || "-", usdClass);
  } else {
    set("ds-macro", usd.dir === "STALE" ? "data basi" : "-", "text-slate-500");
    set("ds-macro-verdict", "-", "text-slate-500");
  }
  // Next high-impact USD release - red inside 30 min, amber inside 2 hours.
  if (usd.next_mins !== undefined && usd.next_mins >= 0) {
    const m = usd.next_mins;
    const cd = m >= 60 ? `${Math.floor(m / 60)}j${m % 60}m` : `${m}m`;
    set("ds-news", `${cd} · ${usd.next_event || ""}`,
        m <= 30 ? "text-rose-400" : m <= 120 ? "text-amber-400" : "text-slate-400");
  } else {
    set("ds-news", "-", "text-slate-500");
  }
  if (data.timestamp) {
    const d = new Date(data.timestamp * 1000);
    set("ds-updated", d.toUTCString().split(" ")[4] + " UTC");
  }

  // v52.6-v52.8: BACAAN BOOKMAP - straight passthrough of the EA's narrated
  // 5-step read (see ComputeBookmapNarrative() in DD_ChainReaction_MultiTF_EA_v2.mq5).
  // No logic duplicated here - the verdict is whatever the EA already
  // decided, this just displays it and colors it. v52.8: 5 small tiles
  // (was 1 wrapped text line) - Dadang: "buat yang bagus dong bro jngan
  // norak gitu" - each tile gets its own semantic color, matching how
  // every other stat-value on this dashboard is colored (never the tile
  // background - just the value, same visual language throughout).
  const bmr = data.bookmap_read || {};
  set("bmread-wall", bmr.wall || "-");
  const cvdTxt = bmr.cvd || "-";
  set("bmread-cvd", cvdTxt, cvdTxt.startsWith("-") ? "text-rose-400" : cvdTxt !== "-" ? "text-emerald-400" : "text-slate-500");
  const absorbTxt = bmr.absorption || "-";
  set("bmread-absorb", absorbTxt, absorbTxt === "-" ? "text-slate-500" : "text-amber-400");
  const iceTxt = bmr.iceberg || "-";
  set("bmread-iceberg", iceTxt, iceTxt === "-" ? "text-slate-500" : "text-fuchsia-400");
  const locTxt = bmr.location || "-";
  set("bmread-location", locTxt, (locTxt === "IN" || locTxt === "-") ? "text-slate-200" : "text-amber-400");
  const verdict = bmr.verdict || "-";
  const verdictClass = verdict.startsWith("BUY") ? "bg-emerald-400/10 text-emerald-400"
                      : verdict.startsWith("SELL") ? "bg-rose-400/10 text-rose-400"
                      : verdict === "OFFLINE" ? "bg-slate-800/70 text-slate-600" : "bg-slate-800/70 text-slate-400";
  set("bmread-verdict", verdict, verdictClass);

  // 7. SIGNALS & TIMING - v52.59: 1 compact line per item (was a 3-row
  // block + a 6-cell grid - Dadang: "kalo mau lihat semuanya harus kecilin
  // dan tak terlihat bro"). Barrier is now ONE "AWAS ..." line covering all
  // 5 tracked TFs (M5-H4), pre-formatted EA-side (barrier_warning) so this
  // is a straight passthrough, same as "Bacaan Bookmap" above - never
  // disagrees with what the EA itself is acting on.
  const sig = data.signals || {};
  const warnTxt = sig.barrier_warning || "-";
  set("sig-barrier", warnTxt, warnTxt === "-" ? "text-slate-500" : "text-amber-400");
  const fusion = sig.fusion || {};
  const fusionTxt = fusion.status && fusion.status !== "-" ? fusion.status : "-";
  const fusionClass = fusionTxt.startsWith("IN POSITION") ? "text-emerald-400"
                     : fusionTxt.startsWith("VR ARMED") ? "text-amber-400" : "text-slate-500";
  set("sig-fusion", fusionTxt, fusionClass);
  const mom = sig.momentum_m5 || {};
  set("sig-momentum", mom.text || "-", dirColorClass(mom.dir));
  const cd = sig.countdown || {};
  const cdTxt = [
    ["H4", cd.h4], ["H1", cd.h1], ["M30", cd.m30], ["M15", cd.m15], ["M5", cd.m5], ["M1", cd.m1],
  ].map(([label, sec]) => `${label} ${fmtCountdown(sec)}`).join("  ·  ");
  set("sig-countdown", cdTxt);
}

function fmtCountdown(sec) {
  if (sec === undefined || sec === null || isNaN(sec)) return "-";
  sec = Math.max(0, Math.round(sec));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  if (h > 0) return `${h}h${m}m`;
  if (m > 0) return `${m}m${s}s`;
  return `${s}s`;
}

// Vertical DOM-style wall ladder: red asks above the current price, green
// bids below, matching the reference screenshot's layout. Built from the
// same "significant wall" data as the Liquidity section (>=10 lot), not a
// full continuous order book - MT5 only has wall-filtered data to send.
// v37: Dadang - "harga di wall itu harusnya naik turun menuju wall nya atau
// ketika harga mendekati area wall itu pulse berkedip" - a wall row pulses
// (glowing border, see .wall-near in index.html) once price is within this
// many USD of it, so you can see at a glance which wall is "in play" right
// now instead of a static list.
const WALL_NEAR_THRESHOLD_USD = 5.0;

function renderLadder(askLadder, bidLadder, currentPrice) {
  const el = document.getElementById("wall-ladder");
  if (!el) return;
  const asks = [...askLadder].sort((a, b) => b[0] - a[0]); // farthest/highest first
  const bids = [...bidLadder].sort((a, b) => b[0] - a[0]); // nearest first

  const row = (px, sz, cls) => {
    const near = currentPrice && Math.abs(currentPrice - px) <= WALL_NEAR_THRESHOLD_USD;
    return `<div class="flex justify-between px-1.5 py-0.5 ${cls} ${near ? "wall-near" : ""}"><span>${fmt(px, 2)}</span><span>${Math.round(sz)}</span></div>`;
  };

  let html = asks.map(([px, sz]) => row(px, sz, "text-rose-400")).join("");
  html += `<div class="text-center px-1.5 py-1 my-0.5 bg-amber-400/10 border-y border-amber-400/30 text-amber-200 font-bold price-row-live">${currentPrice ? fmt(currentPrice, 2) : "-"}</div>`;
  html += bids.map(([px, sz]) => row(px, sz, "text-emerald-400")).join("");

  el.innerHTML = html || '<div class="text-center text-slate-600 py-6">No significant walls</div>';
}

// v38: Bookmap "Price Change" replica - semicircle dial + needle. pulse_pct
// arrives as buyer_aggression_pct (0..100, see market_pulse_engine.py's
// get_pulse() remap); this converts it back to Bookmap's own -100..+100
// "how close to max deviation seen in the training window" scale and points
// the needle accordingly. Dadang: "keliatan banget seller atau bayer yang
// lagi ngepus terkini dia" - this is instantaneous price-deviation pressure,
// NOT the same thing as the session-cumulative Vol Ratio stat above it.
function updatePulseGauge(pulsePct) {
  const needle = document.getElementById("pulse-needle");
  const label = document.getElementById("pulse-value");
  if (!needle || !label) return;
  const buyPct = (pulsePct === undefined || pulsePct === null || isNaN(pulsePct)) ? 50 : pulsePct;
  const pricePct = Math.max(-100, Math.min(100, (buyPct - 50) * 2));
  const angle = (pricePct / 100) * 90;
  needle.setAttribute("transform", `rotate(${angle} 70 62)`);
  label.textContent = (pricePct > 0 ? "+" : "") + Math.round(pricePct) + "%";
  label.setAttribute("fill", pricePct > 15 ? "#34d399" : pricePct < -15 ? "#f43f5e" : "#e2e8f0");
}

function drawDeltaChart(history) {
  const canvas = document.getElementById("delta-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width;
  canvas.height = rect.height;
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  if (!history.length) return;

  const maxAbs = Math.max(10, ...history.map(v => Math.abs(v)));
  const midY = h / 2;
  const barW = w / history.length;
  const bodyW = Math.max(1, barW * 0.7);

  ctx.strokeStyle = "#334155";
  ctx.beginPath();
  ctx.moveTo(0, midY);
  ctx.lineTo(w, midY);
  ctx.stroke();

  history.forEach((v, i) => {
    const x = i * barW + (barW - bodyW) / 2;
    const barH = (Math.abs(v) / maxAbs) * (h / 2 - 8);
    ctx.fillStyle = v >= 0 ? "#10b981" : "#f43f5e";
    if (v >= 0) ctx.fillRect(x, midY - barH, bodyW, barH);
    else ctx.fillRect(x, midY, bodyW, barH);
  });

  ctx.fillStyle = "#64748b";
  ctx.font = "9px JetBrains Mono, monospace";
  ctx.fillText("+" + Math.round(maxAbs), 2, 10);
  ctx.fillText("-" + Math.round(maxAbs), 2, h - 3);
}

async function poll() {
  try {
    const res = await fetch("/sultan_status.json?t=" + Date.now(), { cache: "no-store" });
    const data = await res.json();
    render(data);
  } catch (e) {
    set("online-text", "SERVER UNREACHABLE", "text-rose-500");
  } finally {
    setTimeout(poll, POLL_MS);
  }
}

poll();
