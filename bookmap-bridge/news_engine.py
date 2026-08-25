"""
News & Catalyst Engine - Kitco gold news fetcher + lightweight tone tagging.

Dadang, 2026-08-23: "kita cari cara lain bro karena gw juga butuh data
news" (after AiTrados's own login/registration service turned out to be
down/unreliable - confirmed by both Dadang and a direct check here).
Kitco needs zero signup/API key and is precious metals' own reference
wire (decades-old reputation), so it's the more dependable choice for
something this session already got burned chasing once.

The "RSS" URL below is NOT actually machine-readable RSS/XML despite the
name and its "RSS News | KITCO" page title - it's a Next.js page that
LOOKS like an RSS reader. Confirmed by inspecting the raw response:
Content-Type is text/html, and parsing it as XML fails immediately. The
real data lives embedded in a <script id="__NEXT_DATA__"> JSON blob in
that same HTML (Next.js's standard SSR hydration payload) - richer than
RSS would have been anyway: full teaser snippets, category tags, and
(for NewsArticle-typed items) a real createdAt timestamp.

Feeds the new "News & Catalyst" web tab (bookmap-bridge/sultan/news.html) -
a SEPARATE tab from the main Chain Reaction dashboard, not a panel row on
it (Dadang was explicit: "bukan panel tapi buat aja 1 tab baru kusus
news"). Writes news_feed.json straight into sultan/ - that folder is
already served statically by sultan_dashboard_server.py, so no server
route change is needed for this file (unlike today_calendar.json, which
has to come from the EA's own MT5 sandbox and therefore needs a proxy).

Standalone process, deliberately NOT folded into udp_listener.py's loop -
this has nothing to do with Bookmap/MT5 at all, and touching that
already-running process risks the exact "jangan restart Bookmap bridge"
mistake flagged before (CVD/wall history there is cumulative; a restart
zeroes it). Run this as its own script instead.

The tone tagging below is a plain keyword count, not real NLP/AI
analysis - deliberately simple and inspectable (every article shows
which words tripped its tag) rather than a black box. Good enough for
"which way is the recent headline mix leaning", not a substitute for
Dadang's own reading of the actual articles.

2026-08-23 - Dadang: "dia bisa nyesuain data kita dari bookmap atau
gimana bro... area SNR global yang di tandai fund manager kan biasanya
di news juga ada." Added _extract_price_levels()/_load_our_zones()/
_find_confluences(): pulls dollar figures mentioned in a headline
("gold smashes $4,600/oz") and checks them against OUR OWN live
POC/VAH/VAL/wall levels (straight from the EA's sultan_status.json,
the same file this whole session already reads for debugging) - when
a level the market/media is watching lines up with a level our own
order-flow data independently flagged, that agreement is worth more
than either signal alone. Reads XAUUSD's OWN scale (sultan_status.json
prices are already offset-converted by the EA), no GCZ6 basis
conversion needed here. Gated on symbol containing "XAU" so a gold
headline's price never gets compared against, say, a BTCUSD wall by
mistake if the terminal happens to be on a different chart.

2026-08-23 - Dadang: "news narasi bisa lo convert ke bahasa indonesia
aja gwk bro hahaha." Tried the free unofficial Google Translate
endpoint first (translate.googleapis.com, no key needed) - it 429'd
immediately. Then tried Dadang's local Qwen3-8B (llama-server, port
8080) - worked, but heavy on the RX580 ("local kan berat bro"). He
then supplied his own key for a friend's gateway
(balitechsolution.com, OpenAI-compatible, proxies to several models
under a "bt/" prefix) - the first model tried (bt/haiku) 401'd
("Kunci API tidak valid"), which looked like a dead key, but testing
every model in the account (Dadang: "apa lo udah coba semua curl
nya") showed 11 of 13 actually work fine - haiku and the router alias
just aren't included in this free-member-tier key. Settled on
bt/deepseek-flash: fast (~4s for a full paragraph) and good
Indonesian quality. Key/base URL read from .env (bookmap-bridge/.env,
gitignored - see root .gitignore's ".env" / ".env.*" entries, never
committed to the GitHub backup). One batched LLM call per fetch cycle
translates every headline+summary at once (cheaper than N separate
calls), with a hard fallback to the original English if the API call
fails or the response doesn't parse - translation is a nice-to-have
here, not something this whole feature should break over.
"""

import datetime
import json
import os
import re
import time
import urllib.request

KITCO_PAGE_URL = "https://www.kitco.com/news/category/mining/rss"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sultan", "news_feed.json")
# 2026-08-25 - ForexFactory calendar, replacing today_calendar.json (the
# EA's MT5-native export) as the source for the News tab's "Katalis Hari
# Ini". Dadang: "calender news kalo bisa lo tarik ke web kita" - confirmed
# feasible 2026-08-24, built now on his go-ahead ("kerjakan forex faktori").
# Strictly richer than the MT5 calendar it replaces: ALL currencies (not
# just USD - Jackson Hole/ECB/BOJ-type events matter for gold too), the
# WHOLE WEEK (not just today), forecast/previous as clean strings, and
# zero EA/MT5 dependency (works even if the terminal isn't running).
# No key/signup needed - unofficial but stable, re-verified live 2026-08-25
# before wiring this in (same "record/verify before trusting" discipline
# as everything else built from a single feed test this session).
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FF_CALENDAR_OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sultan", "ff_calendar.json")
FETCH_INTERVAL_SEC = 600   # news doesn't need per-second polling like Bookmap
HEADLINE_LIMIT = 15
REQUEST_TIMEOUT_SEC = 10


def _load_env():
    """Tiny .env reader - no new pip dependency for just two values."""
    env = {}
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

SULTAN_STATUS_FILE = r"C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files\sultan_status.json"
TODAY_CALENDAR_FILE = r"C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files\today_calendar.json"
CONFLUENCE_THRESHOLD_USD = 15.0   # same order of magnitude as the EA's own InpWallSearchRangeUsd
_PRICE_RE = re.compile(r'\$\s?([\d,]{3,7}(?:\.\d{1,2})?)')

TRANSLATE_TIMEOUT_SEC = 60   # one batched call for the whole headline list - deepseek-flash is fast enough this doesn't need llama.cpp's 180s budget
_ITEM_BLOCK_RE = re.compile(r"===ITEM (\d+)===\s*JUDUL:\s*(.*?)\s*RINGKASAN:\s*(.*?)(?=\s*===ITEM \d+===|\Z)", re.S)

# "OffTheWire" items are generic Reuters/AP wire content (SEC enforcement
# actions, power-grid costs, etc.) that happens to get syndicated into
# Kitco's mining category feed but has nothing to do with gold - pure
# noise for a gold narrative. NewsArticle (Kitco's own staff reporting)
# and Commentary (contributor opinion, still metals-focused) are the two
# types actually worth reading.
INCLUDED_TYPES = ("NewsArticle", "Commentary")

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

# Gold/macro-specific phrases that actually show up in Kitco's own
# headlines/summaries (confirmed by eye against the live feed before
# writing this list) - not a generic finance wordlist.
BULLISH_WORDS = [
    "surge", "surges", "rally", "rallies", "jump", "jumps", "gain", "gains",
    "rise", "rises", "higher", "climb", "climbs", "breakout", "record high",
    "safe-haven demand", "weaker dollar", "weaker u.s. dollar", "rate cut",
    "rate cuts", "bullish", "extend the rally", "bolster",
]
BEARISH_WORDS = [
    "fall", "falls", "drop", "drops", "decline", "declines", "slump",
    "lower", "sink", "sinks", "sell-off", "selloff", "sold off",
    "stronger dollar", "stronger u.s. dollar", "rate hike", "rate hikes",
    "profit-taking", "profit taking", "bearish", "retreat", "retreats",
]


def _fetch_next_data():
    req = urllib.request.Request(KITCO_PAGE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
        raw = resp.read().decode("utf-8")
    m = _NEXT_DATA_RE.search(raw)
    if not m:
        raise RuntimeError("__NEXT_DATA__ block not found - Kitco page structure may have changed")
    data = json.loads(m.group(1))
    return data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]["nodeListByCategory"]["items"]


def _tag_tone(title: str, summary: str):
    text = (title + " " + summary).lower()
    bull_hits = [w for w in BULLISH_WORDS if w in text]
    bear_hits = [w for w in BEARISH_WORDS if w in text]
    if len(bull_hits) > len(bear_hits):
        return "BULLISH", bull_hits
    if len(bear_hits) > len(bull_hits):
        return "BEARISH", bear_hits
    return "NEUTRAL", []


def _extract_price_levels(text: str):
    levels = []
    for m in _PRICE_RE.finditer(text or ""):
        try:
            val = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if 500 <= val <= 20000:   # plausible XAUUSD order of magnitude - filters out stray "$5 million"-type mentions that slipped past the OffTheWire filter
            levels.append(val)
    return levels


def _load_our_zones():
    """Our own live POC/VAH/VAL + wall levels, straight from the EA's
    sultan_status.json. Returns None (not []) when the terminal isn't on
    XAUUSD or the file can't be read - callers should skip the
    cross-reference entirely in that case, not silently compare against
    an empty/wrong-symbol zone list."""
    try:
        with open(SULTAN_STATUS_FILE, "r", encoding="ascii") as f:
            data = json.load(f)
    except Exception:
        return None
    if "XAU" not in (data.get("symbol") or "").upper():
        return None

    zones = []
    loc = data.get("location") or {}
    for key, label in (("poc", "POC"), ("vah", "VAH"), ("val", "VAL")):
        v = loc.get(key)
        if v:
            zones.append((float(v), label))
    liq = data.get("liquidity") or {}
    for px, sz in (liq.get("bid_ladder") or []):
        if px:
            zones.append((float(px), f"Bid Wall {sz:.0f}L"))
    for px, sz in (liq.get("ask_ladder") or []):
        if px:
            zones.append((float(px), f"Ask Wall {sz:.0f}L"))
    return zones


def _find_confluences(levels, zones):
    if not levels or not zones:
        return []
    hits = []
    for lvl in levels:
        best = None
        for zpx, zlabel in zones:
            d = abs(lvl - zpx)
            if d <= CONFLUENCE_THRESHOLD_USD and (best is None or d < best[2]):
                best = (zpx, zlabel, d)
        if best:
            hits.append({"level": lvl, "matched_price": best[0], "matched_label": best[1], "distance": round(best[2], 2)})
    return hits


def _post_chat_completion(api_base: str, api_key: str, model: str, system: str, user_content: str):
    """One raw call - raises on any failure, caller decides what to do."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        f"{api_base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=TRANSLATE_TIMEOUT_SEC) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _call_translate_api(system: str, user_content: str, model_key: str, default_model: str):
    """Shared API caller for both translation and AI analysis - re-reads
    .env every call (not once at import) so a key/model saved via
    news.html's settings form takes effect on the NEXT fetch cycle
    without this long-lived process needing a restart. Returns the
    response text, or None on any failure (no key configured, API error,
    timeout) - logged, never raised, since neither caller should take the
    whole news feed down over this.

    2026-08-25 - Dadang gave a second ("free, unlimited") key specifically
    to rotate to if the primary ("pro") key dies - same balitech gateway,
    same models, just a different account behind it. TRANSLATE_API_KEY_BACKUP
    is tried automatically whenever the primary call fails for ANY reason
    (expired key, suspended account like the bt/sonnet4.5-thinking incident
    earlier tonight, network blip) - same model, same prompt, just a
    different key. No manual "which key is active" toggle needed."""
    env = _load_env()
    api_base = env.get("TRANSLATE_API_BASE", "").rstrip("/")
    primary_key = env.get("TRANSLATE_API_KEY", "")
    backup_key = env.get("TRANSLATE_API_KEY_BACKUP", "")
    model = env.get(model_key, default_model)
    if not primary_key or not api_base:
        print(f"[News Engine] API call skipped: TRANSLATE_API_KEY/TRANSLATE_API_BASE not set in .env", flush=True)
        return None

    try:
        return _post_chat_completion(api_base, primary_key, model, system, user_content)
    except Exception as e:
        print(f"[News Engine] primary key API call failed (model={model}, base={api_base}): {e}", flush=True)
        if not backup_key:
            return None
        try:
            print(f"[News Engine] retrying with backup key (model={model})", flush=True)
            return _post_chat_completion(api_base, backup_key, model, system, user_content)
        except Exception as e2:
            print(f"[News Engine] backup key API call also failed (model={model}, base={api_base}): {e2}", flush=True)
            return None


def _load_engine_context():
    """Snapshot of what OUR OWN system is currently saying - CMP cascade
    direction per TF, Chain Signal, momentum, POC/value-area position -
    straight from the EA's live sultan_status.json. Feeds generate_ai_
    analysis() so the AI's read is grounded in our actual live signals,
    not just the news in isolation. Returns None if the file can't be
    read (EA not attached, etc.) - the analysis prompt just omits this
    section rather than failing."""
    try:
        with open(SULTAN_STATUS_FILE, "r", encoding="ascii") as f:
            data = json.load(f)
    except Exception:
        return None
    regime = data.get("regime") or {}
    sig = data.get("signals") or {}
    loc = data.get("location") or {}
    return {
        "symbol": data.get("symbol"),
        "price": data.get("price"),
        "h4_dir": regime.get("h4"), "m30_dir": regime.get("m30"), "m5_dir": regime.get("m5"),
        "cmp_regime": regime.get("regime"),
        "chain_signal_layer": (sig.get("chain_signal") or {}).get("layer"),
        "chain_signal_dir": (sig.get("chain_signal") or {}).get("dir"),
        "momentum_m5": (sig.get("momentum_m5") or {}).get("text"),
        "poc": loc.get("poc"),
        "va_bias": loc.get("va_bias"),
        "position": loc.get("position"),
    }


def generate_ai_analysis(items, calendar_events, engine_ctx):
    """A real LLM-written narrative, not the keyword tally in
    build_conclusion(). Dadang: "kenapa gak lo buat setiap reload ai
    analisa bro kalo cuman translate kan saya [bisa sendiri]" -
    translation alone doesn't add anything he couldn't do himself;
    reading everything together (headlines + today's catalysts + what
    OUR OWN engine is currently reading) and actually reasoning about it
    is the part only an LLM can add. Uses whichever model is configured
    (default bt/sonnet4.5 - this is the one output per cycle worth
    spending a stronger model on, unlike the mechanical per-headline
    translation). Returns a plain-language fallback string (not None) on
    failure, since this is the tab's headline feature now, not a nice-
    to-have that should just go silent."""
    news_block = "\n".join(
        f"- [{it['tone']}] {it['title']}: {it['summary'][:200]}" for it in items[:8]
    ) or "(tidak ada headline)"
    cal_lines = []
    for ev in (calendar_events or []):
        timing = "sudah rilis" if ev["released"] else f"{ev['mins_until']} menit lagi"
        cal_lines.append(f"- {ev['name']} ({ev['time']}, {timing})")
    cal_block = "\n".join(cal_lines) or "(tidak ada event flag merah hari ini)"
    if engine_ctx:
        engine_block = (
            f"Simbol: {engine_ctx['symbol']} @ {engine_ctx['price']}\n"
            f"Arah per timeframe: H4={engine_ctx['h4_dir']} / M30={engine_ctx['m30_dir']} / M5={engine_ctx['m5_dir']} "
            f"(kondisi pasar: {engine_ctx['cmp_regime']})\n"
            f"Chain Signal (rangkaian breakout searah terkonfirmasi): layer {engine_ctx['chain_signal_layer']}, arah {engine_ctx['chain_signal_dir']}\n"
            f"Momentum M5: {engine_ctx['momentum_m5']}\n"
            f"POC: {engine_ctx['poc']} | Posisi harga: {engine_ctx['position']} | VA Bias: {engine_ctx['va_bias']}"
        )
    else:
        engine_block = "(data engine gak kebaca - EA mungkin belum attach atau bukan di XAUUSD)"

    # 2026-08-24 - Dadang: "ganti dang nya dengan comander dadang" + "doctrin
    # cmp vr cf lo ganti dengan doktrin chatin reaction system hilangin aja
    # kata cmp vr cf di narasi dia" - address him properly, and describe the
    # doctrine by its own branded name/mechanism, never the raw CMP/VR/CF
    # jargon (this text can end up on a page reachable from
    # trade.dadangchatai.com, same reasoning as never putting explicit
    # BUY/SELL signals on a public surface).
    #
    # 2026-08-25 - Dadang, after I flagged that "public page" reasoning
    # against naming actual entry zones: "beri NOT FINANSIAL ADVICE bro
    # zona pantau aja untuk entri buy atau sell area nya publik gak apa2
    # yang penting ada warning" - staying public is his explicit call, on
    # the condition of a disclaimer (added as a static banner in
    # news.html/index.html, not left to the model to remember every
    # time) + framing as a WATCH ZONE grounded in real levels the engine
    # already computed (POC/VAH/VAL/walls), never a bare command. Also,
    # separately: "lo buat ai jadi master analis bukan ai yang cupu" -
    # upgraded from a deliberately hedged, will-never-commit voice to one
    # that takes an actual position when the data supports it.
    system = (
        "Kamu MASTER ANALIS pasar gold (XAUUSD) buat Commander Dadang, seorang trader retail "
        "yang membangun sistem sendiri bernama 'Chain Reaction System' - doktrin ini membaca "
        "arah market lewat rangkaian breakout candle-close yang saling mengonfirmasi di "
        "beberapa timeframe berurutan (H4 jadi master arah, lalu dikonfirmasi ulang di "
        "timeframe lebih kecil sebelum dipercaya) - sebuah 'reaksi berantai' breakout, bukan "
        "indikator tradisional. JANGAN PERNAH sebut istilah teknis mentah (jangan tulis 'CMP', "
        "'VR', atau 'CF') - selalu bahasakan sebagai 'doktrin Chain Reaction System' atau "
        "'rangkaian konfirmasi timeframe miliknya' saja. Sapa dia 'Commander Dadang', bukan "
        "'Dang' atau nama santai lain.\n\n"
        "Kamu BUKAN AI yang plin-plan/cupu yang selalu jawab aman tanpa berani nentuin sikap - "
        "sebagai master analis, kalau data (berita + katalis + bacaan sistemnya sendiri + "
        "level POC/VAH/VAL/wall dari order-flow) cukup jelas condong ke satu arah, KATAKAN "
        "TEGAS condong kemana, jangan cuma \"bisa naik bisa turun\". Kamu BOLEH sebutkan ZONA "
        "PANTAU harga spesifik untuk potensi BUY atau SELL (contoh: 'zona pantau BUY di "
        "sekitar 4590-4600' atau 'kalau turun tembus 4570, waspada zona SELL') - TAPI angka "
        "zona itu HARUS diturunkan dari level yang beneran ada di data (POC/VAH/VAL/wall/harga "
        "sekarang), jangan pernah karang angka baru yang gak ada dasarnya. Framing-nya WAJIB "
        "'zona pantau'/'area yang diawasi sistem', BUKAN perintah eksekusi langsung seperti "
        "'BUY SEKARANG' atau 'ENTRI DI...', dan JANGAN kasih TP/SL spesifik (itu keputusan "
        "manajemen risiko dia sendiri, bukan urusanmu). Kalau berita dan sistemnya BERTENTANGAN "
        "arah, bilang apa adanya, jangan dipaksain nyambung.\n\n"
        "Tugasmu: baca berita gold terbaru + kalender event hari ini + apa yang lagi dibaca "
        "sistem Chain Reaction miliknya sendiri, kasih analisa dalam Bahasa Indonesia casual "
        "(gak usah formal banget) yang JUJUR dan TEGAS. WAJIB tutup analisamu dengan satu "
        "kalimat singkat: ini bukan saran finansial, keputusan dan risiko tetap di tangan "
        "Commander Dadang. Maksimal 6-7 kalimat total, jangan bertele-tele."
    )
    user = (
        f"BERITA GOLD TERBARU:\n{news_block}\n\n"
        f"KATALIS HARI INI:\n{cal_block}\n\n"
        f"BACAAN SISTEM CHAIN REACTION MILIK COMMANDER DADANG:\n{engine_block}\n\n"
        f"Kasih analisa singkat."
    )
    # 2026-08-24 - was bt/sonnet4.5 by default, but 2 of 3 test calls came
    # back with words glitched together (missing spaces, broken markdown,
    # dropped letters mid-word - classic stream-reassembly bug pattern,
    # not something on this end) while bt/deepseek-flash has been rock
    # solid across every translation call tonight. Reliability over a
    # marginally smarter model here - a garbled analysis is worse than a
    # clean one. Still overridable via the admin panel if a better model
    # proves stable later.
    text = _call_translate_api(system, user, model_key="ANALYSIS_MODEL", default_model="bt/deepseek-flash")
    if text is None:
        return "Analisa AI belum tersedia siklus ini (API gak kejangkau) - baca headline & katalis di atas manual dulu bro."
    return text.strip()


def _translate_batch(items):
    """Translates every item's title+summary to Indonesian in ONE API
    call (bt/deepseek-flash), matched back by explicit item index
    (robust against the model skipping/reordering a block) rather than
    by list position. Mutates and returns `items` with title_id/
    summary_id added when translation succeeds; items are left with only
    their original English on any failure (no key configured, API
    error, timeout, bad parse) - logged, never raised, since this must
    not take the news feed down."""
    if not items:
        return items

    blocks = "\n\n".join(
        f"===ITEM {i}===\nJUDUL: {it['title']}\nRINGKASAN: {it['summary']}"
        for i, it in enumerate(items)
    )
    system = (
        "Kamu penerjemah berita pasar emas/keuangan. Terjemahkan tiap JUDUL dan "
        "RINGKASAN di bawah ini ke Bahasa Indonesia yang natural dan lancar (bukan "
        "terjemahan kaku kata-per-kata). Angka, harga dolar, dan nama orang/lembaga "
        "tetap apa adanya. Balas PERSIS dengan format yang sama (===ITEM N===, "
        "JUDUL:, RINGKASAN:) untuk SETIAP item yang diberikan, tanpa komentar "
        "tambahan apapun di luar format itu."
    )
    text = _call_translate_api(system, blocks, model_key="TRANSLATE_MODEL", default_model="bt/deepseek-flash")
    if text is None:
        return items

    translated_count = 0
    for idx_str, title_id, summary_id in _ITEM_BLOCK_RE.findall(text):
        idx = int(idx_str)
        if 0 <= idx < len(items):
            items[idx]["title_id"] = title_id.strip()
            items[idx]["summary_id"] = summary_id.strip()
            translated_count += 1
    if translated_count < len(items):
        print(f"[News Engine] translation partial: {translated_count}/{len(items)} items parsed - "
              f"rest kept in English", flush=True)
    return items


def fetch_kitco_headlines(limit: int = HEADLINE_LIMIT):
    raw_items = [it for it in _fetch_next_data() if it and it.get("__typename") in INCLUDED_TYPES]
    our_zones = _load_our_zones()   # one snapshot per fetch cycle - all items in this batch compare against the same read

    items = []
    for it in raw_items[:limit]:
        title = (it.get("title") or "").strip()
        summary = (it.get("teaserSnippet") or "").strip()
        tone, hits = _tag_tone(title, summary)
        url_alias = it.get("urlAlias") or ""
        levels = _extract_price_levels(title + " " + summary)
        items.append({
            "title": title,
            "summary": summary,
            "created_at": it.get("createdAt") or "",
            "category": (it.get("category") or {}).get("name", ""),
            "link": f"https://www.kitco.com{url_alias}" if url_alias else "",
            "tone": tone,
            "tone_hits": hits,
            "mentioned_levels": levels,
            "confluences": _find_confluences(levels, our_zones) if our_zones else [],
        })
    return _translate_batch(items)


def build_conclusion(items):
    bull = sum(1 for it in items if it["tone"] == "BULLISH")
    bear = sum(1 for it in items if it["tone"] == "BEARISH")
    neutral = len(items) - bull - bear

    if bull == 0 and bear == 0:
        verdict = "NEUTRAL"
    elif bull > bear * 1.3:
        verdict = "BULLISH"
    elif bear > bull * 1.3:
        verdict = "BEARISH"
    else:
        verdict = "MIXED"

    return {
        "bullish_count": bull,
        "bearish_count": bear,
        "neutral_count": neutral,
        "total": len(items),
        "verdict": verdict,
    }


def _fetch_ff_calendar():
    """ALL impact levels (Low/Medium/High), but only USD + "All" (broad
    global) events - not every currency - in a rolling ~today window (6h
    back for recently-released ones still worth context, 24h forward).
    Returns the SAME shape the frontend already expects (name/time/
    released/mins_until) plus bonus fields (country/forecast/previous/
    impact) - old renderer keeps working untouched, news.js can pick up
    the extras when it wants to.

    2026-08-25: was HIGH-only at first, then briefly ALL currencies, both
    per Dadang's own asks - "sebaiknya bukan hanya yang merah deh biar
    web nya rame bro jadi kuning oren dan merah juga masukin aja" (all
    impact levels, box was empty most of the day with High-only), then
    immediately narrowed back on currency: "masud gw flagnya yang ada
    hubungan sama usd dan gold aja lainya gak usah bro yang gak ada
    korelasinya buat apa" - EUR/JPY/AUD-specific prints don't move
    XAUUSD, so showing them was just noise. Frontend colors the badge
    per impact level (Low=kuning, Medium=oren, High=merah) so it stays
    scannable.

    Deliberately NOT a strict "local calendar date" filter - the feed's
    own timestamps are in US Eastern, and this machine runs WIB (UTC+7):
    an event ForexFactory lists as "today" in Eastern terms can already be
    "tomorrow" once converted to local time (confirmed live 2026-08-25 -
    3 AUD CPI events at 21:30 Eastern landed on the WRONG local date and
    silently emptied the whole box). A rolling window sidesteps that
    timezone-boundary trap entirely instead of trying to get the "which
    calendar day" math exactly right."""
    req = urllib.request.Request(FF_CALENDAR_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
        raw_items = json.loads(resp.read().decode("utf-8"))

    now = datetime.datetime.now().astimezone()
    window_start = now - datetime.timedelta(hours=6)
    window_end = now + datetime.timedelta(hours=24)
    out = []
    for it in raw_items:
        impact = (it.get("impact") or "").strip().lower()
        if impact not in ("low", "medium", "high"):
            continue
        # 2026-08-25 - Dadang, right after asking for all impact levels:
        # "masud gw flagnya yang ada hubungan sama usd dan gold aja
        # lainya gak usah bro yang gak ada korelasinya buat apa" - showing
        # every currency just made the box noisy with EUR/JPY/AUD prints
        # that don't move XAUUSD. USD is the direct driver (gold is
        # quoted in it); "All" covers broad global events (Fed speeches,
        # Jackson Hole) that aren't tagged to one currency but move the
        # dollar/gold anyway. Everything else (EUR, JPY, GBP, AUD, CAD,
        # CHF, NZD, CNY-specific prints) dropped - only matters to gold
        # through 2-3 steps of indirection, which is what he's rejecting.
        country = (it.get("country") or "").strip().upper()
        if country not in ("USD", "ALL"):
            continue
        try:
            ev_time = datetime.datetime.fromisoformat(it["date"]).astimezone()
        except Exception:
            continue
        if not (window_start <= ev_time <= window_end):
            continue
        mins_until = int((ev_time - now).total_seconds() // 60)
        # the rolling window can span into tomorrow (or dip into
        # yesterday) - bare "HH:MM" would be ambiguous once that happens,
        # so only drop the date when it actually matches today.
        time_fmt = "%H:%M" if ev_time.date() == now.date() else "%d/%m %H:%M"
        out.append({
            "name": f"{it.get('country', '')} - {it.get('title', '')}".strip(" -"),
            "time": ev_time.strftime(time_fmt),
            "released": mins_until <= 0,
            "mins_until": mins_until,
            "country": it.get("country", ""),
            "forecast": it.get("forecast", ""),
            "previous": it.get("previous", ""),
            "impact": impact,
        })
    # High first among simultaneous/near-simultaneous events, then soonest -
    # a High 10 minutes out is more worth seeing above the fold than a Low
    # 2 minutes out once "rame" means dozens of rows instead of a handful.
    impact_rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda e: (e["mins_until"] // 30, impact_rank.get(e["impact"], 3), e["mins_until"]))
    return out


def _load_today_calendar():
    """2026-08-25: was the EA's MT5-native today_calendar.json (USD-only,
    HIGH-impact-only, no forecast/previous - MQL5's fixed-point scaling
    made those risky to export). Replaced with ForexFactory (see
    _fetch_ff_calendar()) - richer and has zero EA dependency. Falls back
    to the old EA export only if the ForexFactory fetch itself fails
    (network hiccup, feed moved) rather than leaving the tab empty."""
    try:
        events = _fetch_ff_calendar()
        os.makedirs(os.path.dirname(FF_CALENDAR_OUTPUT_FILE), exist_ok=True)
        tmp = FF_CALENDAR_OUTPUT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False)
        os.replace(tmp, FF_CALENDAR_OUTPUT_FILE)
        return events
    except Exception as e:
        print(f"[News Engine] ForexFactory calendar fetch failed, falling back to EA export: {e}", flush=True)
        try:
            with open(TODAY_CALENDAR_FILE, "r", encoding="ascii") as f:
                return json.load(f)
        except Exception:
            return []


def write_snapshot():
    items = fetch_kitco_headlines()
    conclusion = build_conclusion(items)
    calendar_events = _load_today_calendar()
    engine_ctx = _load_engine_context()
    ai_analysis = generate_ai_analysis(items, calendar_events, engine_ctx)
    payload = {
        "updated_ts": time.time(),
        "source": "Kitco News (mining category)",
        "items": items,
        "conclusion": conclusion,
        "ai_analysis": ai_analysis,
    }
    tmp = OUTPUT_FILE + ".tmp"
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, OUTPUT_FILE)
    return items, conclusion


def run_forever():
    print(f"[News Engine] writing to {OUTPUT_FILE}", flush=True)
    while True:
        try:
            items, conclusion = write_snapshot()
            print(f"[News Engine] {len(items)} headlines - verdict={conclusion['verdict']} "
                  f"(bull={conclusion['bullish_count']} bear={conclusion['bearish_count']})", flush=True)
        except Exception as e:
            print(f"[News Engine] fetch failed (non-fatal): {e}", flush=True)
        time.sleep(FETCH_INTERVAL_SEC)


if __name__ == "__main__":
    run_forever()
