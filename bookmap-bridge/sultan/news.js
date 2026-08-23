// News & Catalyst tab - polls /today_calendar.json (EA, via
// sultan_dashboard_server.py proxy) and /news_feed.json (news_engine.py,
// written straight into this sultan/ folder, no proxy needed) and renders
// both plus a combined kesimpulan (conclusion).

const REFRESH_MS = 60000;

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtMinsUntil(mins) {
  if (mins == null || mins < 0) return "-";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h}j ${m}m lagi` : `${m}m lagi`;
}

function fmtNewsTime(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleString("id-ID", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return "";
  }
}

async function loadCalendar() {
  const el = document.getElementById("calendar-list");
  try {
    const res = await fetch("/today_calendar.json", { cache: "no-store" });
    const events = await res.json();
    if (!Array.isArray(events) || events.length === 0) {
      el.innerHTML = `<p class="text-[11px] text-slate-500">Gak ada event high-impact USD hari ini (atau EA belum kebaca kalender - broker/tester bisa gak nyediain data ini).</p>`;
      return;
    }
    el.innerHTML = events.map((ev) => {
      const released = !!ev.released;
      const badge = released
        ? `<span class="chip chip-neu">SUDAH RILIS</span>`
        : `<span class="chip chip-red-flag">FLAG MERAH</span>`;
      const timing = released ? "" : `<div class="text-[10px] text-slate-500 mt-0.5">${fmtMinsUntil(ev.mins_until)}</div>`;
      return `
        <div class="flex items-start justify-between gap-3 pb-2 border-b border-slate-800/40 last:border-none last:pb-0">
          <div class="min-w-0">
            <div class="text-[12px] text-slate-200 font-medium truncate">${escapeHtml(ev.name)}</div>
            <div class="text-[10px] text-slate-500 font-mono mt-0.5">${escapeHtml(ev.time)}</div>
          </div>
          <div class="text-right shrink-0">
            ${badge}
            ${timing}
          </div>
        </div>`;
    }).join("");
  } catch (e) {
    el.innerHTML = `<p class="text-[11px] text-rose-400">Gagal baca kalender: ${escapeHtml(String(e))}</p>`;
  }
}

function verdictChipClass(verdict) {
  if (verdict === "BULLISH") return "chip-bull";
  if (verdict === "BEARISH") return "chip-bear";
  return "chip-neu";
}

function buildVerdictText(conclusion) {
  const { bullish_count, bearish_count, neutral_count, total, verdict } = conclusion;
  if (total === 0) return "Belum ada headline yang kebaca.";
  const base = `Dari ${total} headline gold terbaru: ${bullish_count} bullish, ${bearish_count} bearish, ${neutral_count} netral.`;
  if (verdict === "BULLISH") return `${base} Nada dominan condong BULLISH - lebih banyak berita nyebut kenaikan/rally/dolar lemah dibanding sebaliknya.`;
  if (verdict === "BEARISH") return `${base} Nada dominan condong BEARISH - lebih banyak berita nyebut penurunan/sell-off/dolar kuat dibanding sebaliknya.`;
  if (verdict === "MIXED") return `${base} Nada CAMPUR ADUK - gak ada sisi yang dominan jelas, hati-hati whipsaw.`;
  return `${base} Mayoritas netral, gak ada nada tegas dari headline terkini.`;
}

async function loadNews() {
  const listEl = document.getElementById("news-list");
  const badgeEl = document.getElementById("verdict-badge");
  const textEl = document.getElementById("verdict-text");
  const updatedEl = document.getElementById("updated-label");
  try {
    const res = await fetch("/news_feed.json", { cache: "no-store" });
    if (!res.ok) throw new Error("news_feed.json belum ada - jalanin news_engine.py dulu");
    const data = await res.json();
    const items = data.items || [];
    const conclusion = data.conclusion || { bullish_count: 0, bearish_count: 0, neutral_count: 0, total: 0, verdict: "NEUTRAL" };

    badgeEl.textContent = conclusion.verdict;
    badgeEl.className = "chip " + verdictChipClass(conclusion.verdict);
    textEl.textContent = buildVerdictText(conclusion);

    if (data.updated_ts) {
      const d = new Date(data.updated_ts * 1000);
      updatedEl.textContent = "update " + d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    }

    if (items.length === 0) {
      listEl.innerHTML = `<p class="text-[11px] text-slate-500">Belum ada headline.</p>`;
      return;
    }

    listEl.innerHTML = items.map((it) => {
      const toneChip = it.tone === "BULLISH" ? "chip-bull" : it.tone === "BEARISH" ? "chip-bear" : "chip-neu";
      const timeLabel = fmtNewsTime(it.created_at);
      return `
        <div class="news-item">
          <a href="${escapeHtml(it.link)}" target="_blank" rel="noopener noreferrer">
            <div class="flex items-center gap-2 mb-1">
              <span class="chip ${toneChip}">${it.tone}</span>
              ${it.category ? `<span class="text-[9px] text-slate-500 uppercase tracking-wide">${escapeHtml(it.category)}</span>` : ""}
              ${timeLabel ? `<span class="text-[9px] text-slate-600 font-mono ml-auto">${timeLabel}</span>` : ""}
            </div>
            <div class="news-title text-[13px] text-slate-100 font-medium leading-snug transition-colors">${escapeHtml(it.title)}</div>
            <div class="text-[11px] text-slate-400 mt-1 leading-relaxed">${escapeHtml(it.summary)}</div>
          </a>
        </div>`;
    }).join("");
  } catch (e) {
    listEl.innerHTML = `<p class="text-[11px] text-rose-400">Gagal baca berita: ${escapeHtml(String(e))}</p>`;
    textEl.textContent = "Data berita belum tersedia.";
  }
}

function refreshAll() {
  loadCalendar();
  loadNews();
}

refreshAll();
setInterval(refreshAll, REFRESH_MS);
