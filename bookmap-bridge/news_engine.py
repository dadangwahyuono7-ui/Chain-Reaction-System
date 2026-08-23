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

import json
import os
import re
import time
import urllib.request

KITCO_PAGE_URL = "https://www.kitco.com/news/category/mining/rss"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sultan", "news_feed.json")
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


def _call_translate_api(system: str, user_content: str, model_key: str, default_model: str):
    """Shared API caller for both translation and AI analysis - re-reads
    .env every call (not once at import) so a key/model saved via
    news.html's settings form takes effect on the NEXT fetch cycle
    without this long-lived process needing a restart. Returns the
    response text, or None on any failure (no key configured, API error,
    timeout) - logged, never raised, since neither caller should take the
    whole news feed down over this."""
    env = _load_env()
    api_base = env.get("TRANSLATE_API_BASE", "").rstrip("/")
    api_key = env.get("TRANSLATE_API_KEY", "")
    model = env.get(model_key, default_model)
    if not api_key or not api_base:
        print(f"[News Engine] API call skipped: TRANSLATE_API_KEY/TRANSLATE_API_BASE not set in .env", flush=True)
        return None

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
    }
    try:
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
    except Exception as e:
        print(f"[News Engine] API call failed (model={model}, base={api_base}): {e}", flush=True)
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
    system = (
        "Kamu analis pasar gold (XAUUSD) buat Commander Dadang, seorang trader retail yang "
        "membangun sistem sendiri bernama 'Chain Reaction System' - doktrin ini membaca arah "
        "market lewat rangkaian breakout candle-close yang saling mengonfirmasi di beberapa "
        "timeframe berurutan (H4 jadi master arah, lalu dikonfirmasi ulang di timeframe lebih "
        "kecil sebelum dipercaya) - sebuah 'reaksi berantai' breakout, bukan indikator "
        "tradisional. JANGAN PERNAH sebut istilah teknis mentah (jangan tulis 'CMP', 'VR', "
        "atau 'CF') - selalu bahasakan sebagai 'doktrin Chain Reaction System' atau 'rangkaian "
        "konfirmasi timeframe miliknya' saja. Sapa dia 'Commander Dadang', bukan 'Dang' atau "
        "nama santai lain. Tugasmu: baca berita gold terbaru + kalender event hari ini + apa "
        "yang lagi dibaca sistem Chain Reaction miliknya sendiri, terus kasih analisa singkat "
        "dalam Bahasa Indonesia casual (gak usah formal banget) yang JUJUR - kalau berita dan "
        "sistemnya SEPAKAT bilang aja, kalau BERTENTANGAN bilang juga apa adanya, jangan "
        "dipaksain nyambung. Ini BUKAN sinyal entry - jangan pernah bilang 'BUY sekarang' atau "
        "kasih harga TP/SL. Ini konteks buat bantu dia mikir, keputusan tetap di dia. Maksimal "
        "4-5 kalimat, jangan bertele-tele."
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


def _load_today_calendar():
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
