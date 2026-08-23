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

SULTAN_STATUS_FILE = r"C:\Users\R O V A\AppData\Roaming\MetaQuotes\Terminal\Common\Files\sultan_status.json"
CONFLUENCE_THRESHOLD_USD = 15.0   # same order of magnitude as the EA's own InpWallSearchRangeUsd
_PRICE_RE = re.compile(r'\$\s?([\d,]{3,7}(?:\.\d{1,2})?)')

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
    return items


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


def write_snapshot():
    items = fetch_kitco_headlines()
    conclusion = build_conclusion(items)
    payload = {
        "updated_ts": time.time(),
        "source": "Kitco News (mining category)",
        "items": items,
        "conclusion": conclusion,
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
