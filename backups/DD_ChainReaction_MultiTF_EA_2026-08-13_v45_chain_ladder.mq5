//+------------------------------------------------------------------+
//| DD_ChainReaction_MultiTF_EA.mq5                                  |
//| Reads CMP from DD_CMP_Indicator.mq5 - EA itself NEVER computes    |
//| CMP (per Dadang's TASK ORDER: "EA tidak menghitung CMP. EA hanya |
//| membaca status CMP yang dihasilkan indikator MT5.")               |
//|                                                                   |
//| DOCTRINE (H4->M30->M5 cascade, Dadang's own rule dictated verbatim|
//| 2026-08-09 after re-reading D:\bunga\TEHINIX BERIKUTNYA in full   |
//| + 3 hand-drawn diagrams - NO M15/H1 anywhere, M15 confirmed to be |
//| leftover test scaffolding, not doctrine: "M15 itu hanya uji gate  |
//| gw sebenarnya teknik gw kan H4 M30 M5"):                          |
//|   - H4 (Master) sets the outer regime. A flip is a full reset -   |
//|     close everything, start the M30/M5 cascade fresh.             |
//|   - M30's OWN live CMP is the direction actually being traded -   |
//|     "kita akan cari sell jika M30 sell" - independent of whether  |
//|     M30 currently agrees or disagrees with H4 (that agreement/    |
//|     disagreement only affects which SL/TP/BE tier + tag is used,  |
//|     see isScalp in TryOpen calls below).                          |
//|   - FIRE: every fresh M5 BREAKOUT EVENT (DD_CMP_Indicator buffer  |
//|     7, BreakoutEventTimeBuffer - updates on EVERY individual      |
//|     break past the latest pullback, not just the first state      |
//|     flip) that matches M30's current direction = one entry each.  |
//|     "kita entri sell setiap ada BO sell" - repeats/layers as long |
//|     as fresh M5 breakouts keep coming in that direction.          |
//|   - STOP (pause, not reverse): the instant M5's own CMP flips     |
//|     AGAINST M30's direction - "kita stop ketika M5 flip".         |
//|   - RESUME: checked ONLY at the open of a fresh M30 bar - if M30  |
//|     is still the same direction (hasn't flipped away) AND M5      |
//|     already confirms that direction again, firing resumes -       |
//|     "setelah flip dan close candle M30 masih sama belum flip,     |
//|     ketika open M30 dan BO searah master, M30 gas lagi lah entri".|
//|   - REVERSAL: M30's own CMP genuinely flipping to the opposite    |
//|     direction - cuts any position trading the old direction and   |
//|     starts tracking the new one fresh (re-arm required before any |
//|     new entry, same STOP/RESUME rules apply to the new direction).|
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
#include <Canvas\Canvas.mqh>
CTrade trade;

// Version tag - bump this MANUALLY every time the code changes, shown on
// panel + startup Print so Dadang can visually confirm a freshly compiled
// .ex5 actually loaded (vs a stale cached one MT5 didn't reload properly).
// Simple v1/v2/v3... - easier to eyeball than a compile timestamp.
#define EA_VERSION "v45"

// v43: symbol used as the USD fundamental proxy. Declared up here because
// #define is a sequential preprocessor directive - OnInit() references it
// long before the panel code where the rest of the USD block lives.
#define USD_SYMBOL "EURUSD"

enum ENUM_TRADE_DIRECTION
{
   DIR_BOTH      = 0,   // BUY & SELL
   DIR_BUY_ONLY  = 1,   // BUY only
   DIR_SELL_ONLY = 2    // SELL only
};

input group "=== TIMEFRAME PAIR (H4 -> M30 -> M5, no M15/H1 per doktrin) ==="
input ENUM_TIMEFRAMES     InpMasterTF     = PERIOD_H4;     // H4 Master - regime bias, flip = full reset
input ENUM_TIMEFRAMES     InpScalpMasterTF= PERIOD_M30;     // M30 - arah yang BENERAN ditrading (live, independen dari H4)
input ENUM_TIMEFRAMES     InpScalpEntryTF = PERIOD_M5;      // M5 - trigger entry, fire tiap fresh breakout event

input group "=== ENTRI ==="
input bool                InpAllowScalpEntries = true;     // Safety valve - false = infrastruktur jalan tapi gak ada posisi beneran dibuka

input group "=== LOT / RISK MANAGEMENT ==="
input bool                InpUseRisk      = false;         // Pakai risk % dari balance (bukan lot fixed)
input double              InpLot          = 0.01;           // Lot fixed (dipakai kalau InpUseRisk=false)
input double              InpRiskPct      = 1.0;            // Risk % balance per trade (kalau InpUseRisk=true)

input group "=== POSISI ==="
input long                InpMagic        = 20260807;       // Magic number
input int                 InpMaxOpenPos   = 0;              // Maximum posisi terbuka bersamaan (0 = unlimited) - verified 2026-08-09: aturan Dadang "setiap M5/M15 BO searah Master, entri" = layering, bukan one-shot
input bool                InpAllowMultiple= true;           // Boleh entry baru walau udah ada posisi searah - WAJIB true buat layering (default lama false = cuma 1 layer, melanggar aturan)
input ENUM_TRADE_DIRECTION InpTradeDir    = DIR_BOTH;       // Filter arah trading

input group "=== STOP LOSS / TAKE PROFIT (NORMAL tier) ==="
input double              InpSL_Pips      = 200;            // Stop Loss FALLBACK (pips, 0 = tanpa SL) - dipakai kalau structural SL gak valid/off
input double              InpTP_Pips      = 150;             // Take Profit NORMAL (pips, 0 = tanpa TP) - verified 2026-08-09 SL/TP/BE sweep
input bool                InpUseStructuralSL = true;         // SL di area CMP M30 (bukan pip tetap) - Dadang: "kita coba SL di area CMP M30"
input double              InpStructuralSL_MinPips = 30;      // Minimal jarak SL struktural M30 - kalau lebih deket dari ini, fallback ke InpSL_Pips

input group "=== TRAILING STOP / BREAK EVEN (WITH-H4 tier - Dadang 2026-08-09: 'yang searah H4 harus lebar' - trend-following, jangan dikunci cepet kayak SCALP) ==="
input bool                InpUseTrailing  = true;           // Aktifkan trailing stop WITH-H4
input double              InpTrailStartPips= 150;            // Trailing mulai aktif setelah profit sekian pip - v15 sempet dipersempit ke 40 samain SCALP, TERBUKTI SALAH (profit tier ini anjlok $73->$10) - dibalikin lebar
input double              InpTrailStepPips = 70;             // Jarak trailing dari harga sekarang (pip) - dibalikin lebar sama alasan di atas
input bool                InpUseBreakEven = true;           // Aktifkan break-even WITH-H4
input double              InpBE_TriggerPips= 50;             // BE aktif setelah profit sekian pip - dibalikin lebar (v15's 15pip cocok buat SCALP doang, motong trend WITH-H4 yang harusnya lari jauh)
input double              InpBE_LockPips   = 2;              // SL dikunci sejauh ini dari entry (pip) pas BE - verified 2026-08-09

input group "=== SCALP TP / SL / TRAILING / BE (tier terpisah, counter-trend R:R) ==="
input double              InpScalpSL_Pips        = 90;       // SL SCALP FIXED (pips) - retuned 2026-08-09: MAE analysis nunjukin trade yang AKHIRNYA MENANG bisa minus dulu sampe ~61pip (90th percentile) sebelum recover - SL 20pip lama motong 90% calon winner sebelum sempet balik
input double              InpScalpTP_Pips        = 150;      // TP SCALP (pips) - dilebarin 2026-08-09, proteksi sekarang dari BE-lock dini + trailing, bukan dari rasio SL:TP ketat kayak dulu
input bool                InpScalpUseBreakEven   = true;     // Aktifkan BE SCALP
input double              InpScalpBE_TriggerPips = 15;       // BE SCALP aktif setelah profit sekian pip - retuned 2026-08-09, sama alasan kayak NORMAL tier di atas
input double              InpScalpBE_LockPips    = 2;        // SL dikunci sejauh ini pas BE SCALP
input bool                InpScalpUseTrailing    = true;     // Aktifkan trailing SCALP - WAJIB ON, verified headless: payoff anjlok 1.52->0.71 kalau dimatiin (TP55 kasih ruang trailing kerja beneran, beda dari TP25 lama)
input double              InpScalpTrailStartPips = 40;       // Trailing SCALP mulai aktif setelah profit sekian pip - retuned 2026-08-09
input double              InpScalpTrailStepPips  = 20;       // Jarak trailing SCALP - retuned 2026-08-09

input group "=== RSI / ADX FILTER (eksperimen di luar doktrin CMP murni, default ON - verified 2026-08-09: WR64.9%/PF1.042 vs WR63.7%/PF0.979 tanpa filter) ==="
input bool                InpUseADX         = true;     // Filter momentum ADX (skip entry kalau ADX < InpADX_MinLevel)
input int                 InpADX_Period     = 14;       // Periode ADX
input double              InpADX_MinLevel   = 20;       // ADX minimum buat entry (di bawah ini = choppy/lemah)
input bool                InpUseRSI         = true;     // Filter overbought/oversold RSI
input int                 InpRSI_Period     = 14;       // Periode RSI
input double              InpRSI_Overbought = 70;       // Skip BUY kalau RSI >= ini (dipake kalau InpRSI_UseNeutralZone=false)
input double              InpRSI_Oversold   = 30;       // Skip SELL kalau RSI <= ini (dipake kalau InpRSI_UseNeutralZone=false)
input bool                InpRSI_UseNeutralZone = true; // Dadang: "kita hanya entri ketika RSI di 50" - entry CUMA boleh kalau RSI deket 50, hindari kejebak overbought/oversold sama sekali (bukan cuma di ekstrem)
input double              InpRSI_NeutralBand    = 10;   // Lebar band di sekitar 50 (mis. 10 = RSI harus 40-60)

input group "=== M1 CONFIRMATION (eksperimen, Dadang: M1 ngawal pembentukan M5) ==="
input bool                InpUseM1Confirm = false;    // Wajib M1 udah searah sebelum entry SCALP (M5)

input group "=== M30 MOMENTUM CANDLE (Dadang: M30 close harus lewatin high/low candle sebelumnya) ==="
input bool                InpUseM30Momentum = true;   // Wajib M30 close di atas high (BUY) / bawah low (SELL) candle sebelumnya buat entry; posisi ke-exit kalau M30 malah close kuat ke arah lawan

input group "=== M5 TEST M30 (Dadang: M30 buy, tapi M5 sell dulu nguji, baru M5 balik buy, baru kita buy) ==="
input bool                InpUseM5TestM30 = true;   // Wajib M5 sempet SELL (lawan arah entry) dulu SEBELUM balik ke arah entry - bukti M30 udah "diuji" dan tetep kuat, bukan langsung searah dari awal

input group "=== HINDARI SNR TF BESAR (Dadang 2026-08-09: 'hindari entri di area SNR TF besar Weekly Daily H4, area itu pasti balik arah') ==="
input bool                InpAvoidBigSNR      = true;   // Skip entry kalau harga lagi deket zone SNR Weekly/Daily/H4 yang bakal ngelawan arah entry
input double              InpBigSNR_ZonePips  = 100;    // Lebar zone "deket" (pips) - dicek dari live sup (buat SELL) / res (buat BUY) di W1, D1, H4

input group "=== H1 GATE BUAT SCALP (eksperimen, default OFF - Dadang 2026-08-09: 'balikin ke M30 karena kalo H1 kita telat' - verified headless + out-of-sample: H1 gate bikin entry lebih lambat & profit sedikit lebih kecil di 2 periode data, gak ada bukti manfaat konsisten) ==="
input bool                InpRequireH1ForScalp = false;  // Wajib H1 CMP JUGA udah searah sebelum berani SCALP (lawan H4) - gak berlaku pas searah H4. Infrastruktur tetep ada buat eksperimen lanjut kalau perlu.

input group "=== BARRIER BE (Dadang: barrier lama = area pantul, begitu nyentuh langsung BE) ==="
input bool                InpUseBarrierBE     = true;   // Aktifkan barrier-BE (Master TF punya live res/sup lama)
input double              InpBarrierBE_LockPips = 0;    // SL dikunci sejauh ini dari entry pas kena barrier (0 = true breakeven)
input double              InpBarrierBE_MinProfitPips = 50;   // Minimal profit dulu sebelum barrier-BE boleh aktif - Dadang: "BE setelah lari minimal 50 pip"

input group "=== FILTER EKSEKUSI ==="
input double              InpMaxSpreadPips= 50;             // Spread filter (pips, 0 = tanpa filter)
input int                 InpSlippage     = 30;              // Slippage/deviation (points)

input group "=== BOOKMAP BRIDGE (live-only, Dadang: 'biar kita tau juga potensinya') ==="
input bool                InpShowBookmapPanel = true;    // Tampilin CVD/Pulse/Absorption Bookmap di panel
input double              InpBookmapStaleSec  = 30.0;    // Anggap data basi/Bookmap gak jalan kalau beda lebih dari ini (detik, dua arah - v24 dilebarin dari 5.0)
input bool                InpUseBookmapAbsorptionWarning = true;   // v23 2026-08-10: Absorption lawan arah -> kecilin lot (BUKAN block), sama persis pola bookmap-bridge: "BUY WARNING, buyer mulai ter-absorb, kurangi lot". LIVE ONLY - gak ngaruh ke backtest sama sekali (g_bookmapOnline selalu false offline)
input double              InpBookmapAbsorptionLotFactor  = 0.5;    // Lot dikali segini kalau absorption lawan arah entry
input bool                InpUsePocOverextendWarning = true;    // v30 2026-08-10: harga udah lari jauh dari POC (value area session) searah entry -> kecilin lot (BUKAN block), sama pola kayak Absorption. LIVE ONLY
input double              InpPocOverextendUsd        = 20.0;    // Jarak (USD) dari POC ke arah entry yang dianggap "overextended"
input double              InpPocOverextendLotFactor  = 0.5;     // Lot dikali segini kalau overextended dari POC
input bool                InpUsePocAlignWarning = true;    // v32 2026-08-10: harga di sisi SALAH POC relatif ke arah entry (BUY tapi harga < POC / SELL tapi harga > POC = belum "reclaim" value area) -> kecilin lot. Beda dari overextend (jarak) - ini soal SISI, berapapun jaraknya
input double              InpPocAlignLotFactor  = 0.5;     // Lot dikali segini kalau harga di sisi salah POC
input double              InpPocSidewaysZoneUsd = 3.0;     // Jarak (USD) dari POC yang dianggap "di POC" (bukan jelas di atas/bawah) - dipake buat panel BIAS BUY/SELL/SIDEWAYS

input group "=== PANEL ==="
input bool                 InpShowPanel    = true;           // Tampilkan dashboard di chart
input string                InpPanelName    = "CHAIN REACTION SYSTEM"; // Judul panel
input string                InpOwnerName    = "Commander Dadang Wahyuono"; // Nama pemilik

//======================================================================
string   g_masterDir        = "WAIT";   // H4
string   g_scalpMasterDir   = "WAIT";   // M30 - the direction actually being traded
string   g_scalpEntryDir    = "WAIT";   // M5
datetime g_masterChangeTime = 0;
datetime g_scalpMasterChangeTime = 0;   // M30's own regime-start time (Time Law reference)

// FIRE/STOP/RESUME state machine (Dadang's own rule, dictated verbatim
// 2026-08-09 - see header doctrine comment). g_m5FiringEnabled gates every
// entry: true = fire on each fresh M5 breakout event; false = paused. Only
// two things change it: M5 flipping against M30 (-> false) and a fresh M30
// bar opening while M30 hasn't flipped away and M5 already agrees (-> true).
bool     g_m5FiringEnabled = false;
datetime g_lastM30BarTime  = 0;    // detects a fresh M30 bar open (RESUME check point)
datetime g_lastM5EventTime = 0;    // last-seen BreakoutEventTimeBuffer value - detects each fresh M5 event

int      g_hMaster = INVALID_HANDLE;
int      g_hScalpMaster = INVALID_HANDLE;
int      g_hScalpEntry  = INVALID_HANDLE;
int      g_hWeekly = INVALID_HANDLE;   // W1 - for InpAvoidBigSNR only, not part of the trading cascade
int      g_hDaily  = INVALID_HANDLE;   // D1 - for InpAvoidBigSNR only, not part of the trading cascade
int      g_hH1     = INVALID_HANDLE;   // H1 - Daily zone's rejection-confirmation TF, InpAvoidBigSNR only

// v34: dedicated handles for the SULTAN SNIPER web dashboard export
// (WriteSultanStatus()) - deliberately SEPARATE from g_hDaily/g_hH1 above
// (those are conditional on InpAvoidBigSNR and used for trading-logic
// filters; these are always-loaded and export-only, zero risk of changing
// entry behavior). D1/H1/M15 read here purely for the "Market Regime"
// table - MT5 always has full history for these (unlike Bookmap's own
// tick-only CMP, which needs hours/days to warm up after every restart).
int      g_hExportD1  = INVALID_HANDLE;
int      g_hExportH1  = INVALID_HANDLE;
int      g_hExportM15 = INVALID_HANDLE;
int      g_hExportM1  = INVALID_HANDLE;   // v37: M1 passthrough for udp_listener.py's MT5 overlay (was Pine-only before)
int      g_hATR       = INVALID_HANDLE;   // ATR(14) on H1, for the LOCATION panel

// RSI/ADX filter handles - checked against M5 (the only entry trigger now).
int      g_hRSI_ScalpEntry = INVALID_HANDLE;
int      g_hADX_ScalpEntry = INVALID_HANDLE;

// M1 confirmation - one level below Scalp Entry (M5). Per Dadang's candle-
// formation doctrine, a lower TF's breakout direction tends to drag the
// parent TF's forming candle with it, so M1 breaking out first is read as
// an early confirmation that M5 is about to (or already did) follow suit.
int      g_hM1             = INVALID_HANDLE;

int      g_lastDealsTotal  = -1;
int      g_statTrades = 0, g_statWins = 0, g_statLosses = 0;
double   g_statTotalProfit = 0.0;

// Bookmap live-bridge state (read from Common\Files\bookmap_live_signal.csv,
// written by udp_listener.py - see that file's MT5_BRIDGE_FILE comment).
// Absorption wired into entry lot-sizing (v23), rest still informational.
bool     g_bookmapOnline    = false;
double   g_bookmapPrice     = 0.0;   // Bookmap's OWN instrument price (GCZ6 futures, NOT XAUUSD) - for wall price conversion
double   g_bookmapCvd       = 0.0;
double   g_bookmapPulsePct  = 0.0;   // = buyer_aggression_pct 0-100 (kekuatan buyer/seller)
string   g_bookmapAbsorption = "NONE";
// v29: Volume Profile (session, resets 07:00 WIB like CVD) - POC = price
// level with the most TOTAL traded volume this session, distinct from CVD
// (buy-sell delta) and from the wall ladder (resting order size, not volume
// that actually traded). VolRatio = session buy% of total traded volume.
double   g_bookmapPocPrice       = 0.0;   // Bookmap's OWN instrument price - needs offset conversion like walls
double   g_bookmapPocVolume      = 0.0;
double   g_bookmapVolRatioBuyPct = 50.0;
double   g_bookmapBuyVolSession  = 0.0;
double   g_bookmapSellVolSession = 0.0;
// v33: VAH/VAL (Value Area High/Low) - turns POC from a single line into the
// 70%-of-volume ZONE around it (both Bookmap's OWN price scale, need offset
// conversion like POC). Iceberg = hidden refilling order detected on either
// side (IcebergEngine) - price/displayed size/ratio, 0s if none detected.
// INFORMATIONAL ONLY - not wired into entry sizing yet (newest, least-proven
// signal - observe live first, same caution applied to everything else).
double   g_bookmapVal = 0.0, g_bookmapVah = 0.0;
double   g_bookmapBidIcePx = 0.0, g_bookmapBidIceSz = 0.0, g_bookmapBidIceRatio = 0.0;
double   g_bookmapAskIcePx = 0.0, g_bookmapAskIceSz = 0.0, g_bookmapAskIceRatio = 0.0;
#define WALL_SLOTS_PER_SIDE 10   // v29: 5 live-nearest + 5 historical(>1hr, may be far) - keep in sync with WALL_NEAR/HIST_SLOTS_PER_SIDE in udp_listener.py's write_mt5_bridge_file()
double   g_bookmapBidPx[WALL_SLOTS_PER_SIDE], g_bookmapBidSz[WALL_SLOTS_PER_SIDE];
double   g_bookmapAskPx[WALL_SLOTS_PER_SIDE], g_bookmapAskSz[WALL_SLOTS_PER_SIDE];

// v34: SULTAN SNIPER ENGINE web dashboard export - Dadang: "gak usah baca
// pine langsung mt5 aja" + "web dashboard buat semaximal mungkin". CVD
// minute-history ring buffer for the "Delta Progress" mini-chart (1-minute
// CVD deltas, newest last) - sampled once per real minute in OnTick(), NOT
// tied to chart timeframe/bars.
#define CVD_HIST_LEN 30
double   g_cvdMinuteSamples[CVD_HIST_LEN];   // raw g_bookmapCvd snapshots, one per minute
int      g_cvdSampleCount = 0;                // how many slots filled so far (<CVD_HIST_LEN early on)
int      g_lastCvdSampleMinute = -1;          // detects a real minute rollover (not chart-bar-based)
datetime g_lastSultanExportTime = 0;          // throttle WriteSultanStatus() to ~1/sec
double   g_bookmapAgeMs = -1.0;               // set in ReadBookmapBridge() - bridge latency for the dashboard

// v31: Strategy Tester replay of Bookmap history - Dadang: "siapin semuanya
// bro" (buat backtest weekend). The LIVE bridge file above can't be used
// during backtest by design (real wall-clock timestamp never matches
// simulated time). This instead loads udp_listener.py's own
// Common\Files\bookmap_history\bookmap_history_YYYY-MM-DD.csv archive (one
// row/5s, written continuously since 2026-08-10) and looks up the closest
// recorded row for each simulated bar's REAL timestamp - only produces
// results for date ranges that overlap with when that archive was actually
// being recorded (nothing before 2026-08-10). Wall ladder isn't in the
// archive (only CVD/Pulse/Absorption/POC), so no wall lines during replay -
// only Absorption + POC-overextend (the two TryOpen() actually uses) get to
// participate in backtests going forward.
bool     g_bmHistLoaded = false;
int      g_bmHistCount  = 0;
datetime g_bmHistTime[];
double   g_bmHistBmPrice[];
double   g_bmHistCvd[];
double   g_bmHistPulse[];
string   g_bmHistAbsorb[];
double   g_bmHistPocPrice[];
double   g_bmHistPocVolume[];
double   g_bmHistVal[];    // v33
double   g_bmHistVah[];    // v33
#define BM_HIST_DIR "bookmap_history\\"
#define BM_HIST_GLOB "bookmap_history_v2_*.csv"   // v33: schema bumped v2 (val/vah/iceberg columns added) - glob only matches v2+ files, skips today's older v1-schema file (would desync the fixed-column reader)

#define DASH_PREFIX "DD_DASH_"
#define WALL_PREFIX "DD_WALL_"
// v39: panel geometry/palette globals now live next to CreatePanel()/
// UpdatePanel() themselves (Canvas-rendered panel) - see PNL_* below.

//--- pip size. 3/5-digit forex brokers: 1 pip = 10 points. XAUUSD is
//--- typically quoted 2-digit (e.g. 3330.92) where the same 1-pip-=-10-point
//--- gold convention applies (1 pip = $0.10) - NOT 1 point = 1 pip like a
//--- plain 2-digit forex quote. Without this, all *_Pips inputs (SL,
//--- trailing) come out 10x too tight and get hunted by normal noise.
double PipSize()
{
   return (_Digits == 3 || _Digits == 5 || _Digits == 2) ? _Point * 10.0 : _Point;
}

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);

   g_hMaster      = iCustom(_Symbol, InpMasterTF,      "DD_CMP_Indicator");
   g_hScalpMaster = iCustom(_Symbol, InpScalpMasterTF, "DD_CMP_Indicator");
   g_hScalpEntry  = iCustom(_Symbol, InpScalpEntryTF,  "DD_CMP_Indicator");
   if(g_hMaster == INVALID_HANDLE || g_hScalpMaster == INVALID_HANDLE || g_hScalpEntry == INVALID_HANDLE)
   {
      Print("ERROR: gagal load DD_CMP_Indicator - pastikan DD_CMP_Indicator.ex5 ada di folder Indicators.");
      return(INIT_FAILED);
   }
   if(InpUseRSI)  g_hRSI_ScalpEntry = iRSI(_Symbol, InpScalpEntryTF, InpRSI_Period, PRICE_CLOSE);
   if(InpUseADX)  g_hADX_ScalpEntry = iADX(_Symbol, InpScalpEntryTF, InpADX_Period);
   if(InpUseM1Confirm)
   {
      g_hM1 = iCustom(_Symbol, PERIOD_M1, "DD_CMP_Indicator");
      if(g_hM1 == INVALID_HANDLE)
         Print("WARNING: gagal load DD_CMP_Indicator buat M1 confirmation - filter M1 di-skip (bukan fatal).");
   }
   if(InpAvoidBigSNR)
   {
      g_hWeekly = iCustom(_Symbol, PERIOD_W1, "DD_CMP_Indicator");
      g_hDaily  = iCustom(_Symbol, PERIOD_D1, "DD_CMP_Indicator");
      if(g_hWeekly == INVALID_HANDLE || g_hDaily == INVALID_HANDLE)
         Print("WARNING: gagal load DD_CMP_Indicator buat W1/D1 - filter InpAvoidBigSNR di-skip (bukan fatal).");
   }
   if(InpAvoidBigSNR || InpRequireH1ForScalp)
   {
      g_hH1 = iCustom(_Symbol, PERIOD_H1, "DD_CMP_Indicator");   // dipake InpAvoidBigSNR (Daily zone confirm) DAN InpRequireH1ForScalp
      if(g_hH1 == INVALID_HANDLE)
         Print("WARNING: gagal load DD_CMP_Indicator buat H1 - filter yang butuh H1 di-skip (bukan fatal).");
   }

   // v34: always-on handles for the SULTAN SNIPER web dashboard export -
   // separate from the conditional ones above (trading-logic filters), so
   // toggling InpAvoidBigSNR/InpRequireH1ForScalp never affects what the
   // dashboard can show.
   g_hExportD1  = iCustom(_Symbol, PERIOD_D1,  "DD_CMP_Indicator");
   g_hExportH1  = iCustom(_Symbol, PERIOD_H1,  "DD_CMP_Indicator");
   g_hExportM15 = iCustom(_Symbol, PERIOD_M15, "DD_CMP_Indicator");
   g_hExportM1  = iCustom(_Symbol, PERIOD_M1,  "DD_CMP_Indicator");
   g_hATR       = iATR(_Symbol, PERIOD_H1, 14);

   // v43.1: prefer a real dollar index, fall back to EURUSD. The contract
   // month is discovered rather than hardcoded, so the September -> December
   // roll (DXY_U6 -> DXY_Z6) doesn't silently kill the reading. A candidate
   // only wins if it actually carries enough H4 history to compute CMP on.
   // Only the NAME is resolved here. MT5 loads a freshly selected symbol's
   // history asynchronously, so iBars() still reads 0 at OnInit time even
   // though DXY_U6 actually holds ~2962 H4 bars - gating on bar count here
   // rejected it every time and silently fell back to EURUSD. The bar check
   // moved into ReadUsdFundamental(), which adopts the candidate as soon as
   // its history has finished downloading.
   g_usdSymbol    = "";
   g_usdInverted  = false;
   g_usdCandidate = "";
   int symTotal = SymbolsTotal(false);
   for(int i = 0; i < symTotal; i++)
   {
      string nm = SymbolName(i, false);
      if(StringFind(nm, "DXY_") != 0) continue;
      if(StringFind(nm, ".") >= 0)    continue;   // skips equity tickers like DXYZ.NYSE-24
      if(!SymbolSelect(nm, true))     continue;
      g_usdCandidate = nm;
      iBars(nm, PERIOD_H4);                       // kick off the async history download
      break;
   }
   // Start on EURUSD (always loaded, always ticking) and upgrade to DXY later.
   g_usdSymbol   = USD_SYMBOL;
   g_usdInverted = true;
   SymbolSelect(g_usdSymbol, true);
   g_hEurUsdH4 = iCustom(g_usdSymbol, PERIOD_H4, "DD_CMP_Indicator");
   if(g_hEurUsdH4 == INVALID_HANDLE)
      Print("INFO: gagal load DD_CMP_Indicator buat ", g_usdSymbol,
            " - baris USD di panel bakal kosong (bukan fatal).");
   else
      Print("USD fundamental source: ", g_usdSymbol, g_usdInverted ? "  (inverted: naik = USD lemah)" : "  (direct: naik = USD kuat)");
   if(g_hExportD1 == INVALID_HANDLE || g_hExportH1 == INVALID_HANDLE || g_hExportM15 == INVALID_HANDLE || g_hExportM1 == INVALID_HANDLE || g_hATR == INVALID_HANDLE)
      Print("WARNING: gagal load salah satu handle export dashboard (D1/H1/M15/ATR) - beberapa field di web dashboard bisa kosong (bukan fatal).");

   if(InpShowPanel) CreatePanel();

   // v31: load recorded Bookmap history ONCE for Strategy Tester/Optimization
   // replay (Dadang: "siapin semuanya bro" buat backtest weekend) - never
   // touches the live path (ReadBookmapBridge() branches on tester mode).
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      LoadBookmapHistory();

   Print("DD Chain Reaction Multi-TF EA [", EA_VERSION, "] aktif: H4=", EnumToString(InpMasterTF),
         " -> M30=", EnumToString(InpScalpMasterTF), " -> M5=", EnumToString(InpScalpEntryTF),
         InpUseADX ? "  |  ADX filter ON" : "",
         InpUseRSI ? "  |  RSI filter ON" : "");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(g_hMaster != INVALID_HANDLE) IndicatorRelease(g_hMaster);
   if(g_hScalpMaster != INVALID_HANDLE) IndicatorRelease(g_hScalpMaster);
   if(g_hScalpEntry  != INVALID_HANDLE) IndicatorRelease(g_hScalpEntry);
   if(g_hRSI_ScalpEntry != INVALID_HANDLE) IndicatorRelease(g_hRSI_ScalpEntry);
   if(g_hADX_ScalpEntry != INVALID_HANDLE) IndicatorRelease(g_hADX_ScalpEntry);
   if(g_hM1             != INVALID_HANDLE) IndicatorRelease(g_hM1);
   if(g_hWeekly         != INVALID_HANDLE) IndicatorRelease(g_hWeekly);
   if(g_hDaily          != INVALID_HANDLE) IndicatorRelease(g_hDaily);
   if(g_hH1             != INVALID_HANDLE) IndicatorRelease(g_hH1);
   if(g_hExportD1       != INVALID_HANDLE) IndicatorRelease(g_hExportD1);
   if(g_hExportH1       != INVALID_HANDLE) IndicatorRelease(g_hExportH1);
   if(g_hExportM15      != INVALID_HANDLE) IndicatorRelease(g_hExportM15);
   if(g_hExportM1       != INVALID_HANDLE) IndicatorRelease(g_hExportM1);
   if(g_hATR            != INVALID_HANDLE) IndicatorRelease(g_hATR);
   if(g_hEurUsdH4       != INVALID_HANDLE) IndicatorRelease(g_hEurUsdH4);
   g_panelCanvas.Destroy();
   ObjectsDeleteAll(0, DASH_PREFIX);
   ObjectsDeleteAll(0, WALL_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| On-chart live panel - Canvas-rendered (raster bitmap), matching   |
//| the Sultan Sniper Engine web dashboard's visual language. v39:    |
//| Dadang pushed through several rounds on the standalone preview EA |
//| ("ternyata bisa keren... buat yang keren dong" -> "hurufnya masih |
//| kurang jelas" -> "produksi aja ke panel lama") - this replaces    |
//| the old flat OBJ_LABEL/OBJ_RECTANGLE_LABEL panel entirely: true   |
//| rounded corners, a soft drop shadow, a gold gradient top accent,  |
//| a real smooth-gradient semicircle Price Pressure gauge. v39.1:    |
//| Dadang: "sama aja rubah fontnya bro... rubah semua jenis font nya |
//| dan buat SOLID" - every piece of text that went missing used the  |
//| 4x-offset "fake bold" stamp (PnlTxtB); everything drawn with a    |
//| single TextOut call rendered fine regardless of font name. That   |
//| points at the stamping trick itself, not the font. Fix: ONE font  |
//| everywhere (Arial - the most universally-resolvable Windows font, |
//| safer than Segoe UI/Consolas/Lucida Console for Canvas's GDI      |
//| lookup), and PnlTxtB now just draws once at a bigger size instead |
//| of stamping - the exact same code path as PnlTxt(), which was     |
//| never in question. Row's value column also switched from a       |
//| computed-width right-align to a fixed offset, removing another    |
//| guess (monospace character-width assumption) from the render path.|
//+------------------------------------------------------------------+
color DirColor(string d) { return (d == "BUY") ? clrLime : (d == "SELL" ? clrTomato : clrSilver); }

CCanvas g_panelCanvas;
uint    g_lastPanelDrawMs = 0;

#define PNL_RGB(r,g,b) ((color)((uchar)(r) + ((uchar)(g) << 8) + ((uchar)(b) << 16)))
#define PNL_FONT "Arial"   // single font for the whole panel - most universally available on Windows

color PNL_GOLD    = C'217,180,101';
color PNL_EMERALD = C'52,211,153';
color PNL_ROSE    = C'251,113,133';
color PNL_SILVER  = C'139,149,167';
// v39.9: verified by screenshotting the live chart directly (not from a
// described symptom) - the outline bold from v39.8 IS rendering; values
// are visibly heavier than their labels. What still read as "tipis" was
// two other things: label text at 9px is simply tiny, and PNL_SILVER is
// too dim against the near-black panel. Labels get their own brighter
// tone here, and every font size steps up (see DrawPanel below), while
// the panel stays compact per "kecilin dikit".
// v40: Dadang pointed at the "BIAS — SIDEWAYS" line as the reference -
// "buat aja seperti ini soalnya warnanya itu redup tenggelam". That line
// was the one piece already drawn bold-with-outline in a bright tone;
// everything else used dim silver with no outline and sank into the dark
// panel. So: labels get near-white AND the same outline treatment as the
// values - no plain/dim text left anywhere in the panel.
// v40.1: Dadang - "lo putihkan teksnya coba atau itu sudah mentok" - it
// wasn't maxed; this was 214,222,235 (a slightly blue-tinted white). Now
// pure 255. The semantic colors (emerald/rose/gold on the VALUES) stay as
// they are - those encode direction and status, not emphasis.
color PNL_LABEL   = C'255,255,255';
color PNL_WHITE   = C'255,255,255';   // Dadang: "huruf putih masih redup, buat solid" - pure white
color PNL_BG      = C'14,16,23';
color PNL_RULE    = C'52,45,30';
color PNL_SHADOW  = C'0,0,0';

int PNL_PX = 12, PNL_PY = 18, PNL_W = 310, PNL_H = 765;
int PNL_MARGIN = 14, PNL_RADIUS = 10, PNL_BORDER = 2;
int PNL_VALUE_COL = 140; // fixed x-offset (from a row's left edge) where the value text starts

color PnlLerp(uchar r1, uchar g1, uchar b1, uchar r2, uchar g2, uchar b2, double t)
{
   t = MathMax(0.0, MathMin(1.0, t));
   uchar r = (uchar)MathRound(r1 + (r2 - r1) * t);
   uchar g = (uchar)MathRound(g1 + (g2 - g1) * t);
   uchar b = (uchar)MathRound(b1 + (b2 - b1) * t);
   return PNL_RGB(r, g, b);
}

//--- true rounded rectangle: 2 overlapping full rects leave the 4 corner
//--- squares blank, then a full circle centered on each corner's inner
//--- point fills exactly the quarter-disk that belongs there.
void PnlFillRoundedRect(int x1, int y1, int x2, int y2, int r, uint argb)
{
   g_panelCanvas.FillRectangle(x1 + r, y1, x2 - r, y2, argb);
   g_panelCanvas.FillRectangle(x1, y1 + r, x2, y2 - r, argb);
   g_panelCanvas.FillCircle(x1 + r, y1 + r, r, argb);
   g_panelCanvas.FillCircle(x2 - r, y1 + r, r, argb);
   g_panelCanvas.FillCircle(x1 + r, y2 - r, r, argb);
   g_panelCanvas.FillCircle(x2 - r, y2 - r, r, argb);
}

// v39.4: Dadang - "lo coba pikir ulang atau browsing dulu" - the real bug
// was never the font NAME. CCanvas::FontSet()'s 3rd parameter ("flags") IS
// the font weight itself (0-1000, Win32 GDI's LOGFONT.lfWeight - 400 is
// normal, 700 is bold), passed straight through to CreateFont(). Every
// earlier attempt left this at its default (0 = FW_DONTCARE, i.e. regular)
// and instead tried to bake "bold" into the face-NAME string ("Arial
// Bold", "Arial Black") - which is why nothing ever actually got heavier.
#define PNL_WEIGHT_NORMAL 400
#define PNL_WEIGHT_BOLD   700

void PnlTxt(int x, int y, string s, color clr, int size = 11, uint anchor = TA_LEFT | TA_TOP)
{
   g_panelCanvas.FontSet(PNL_FONT, size, PNL_WEIGHT_NORMAL);
   g_panelCanvas.TextOut(x, y, s, ColorToARGB(clr, 255), anchor);
}

// v39.7: pushed the outline (picked as "E" in the mockup A/B test) much
// harder - 2px ring (16 offset points, not 8) instead of 1px, deliberately
// exaggerated so the result is unambiguous either way. EA_VERSION was
// also bumped to "v39.7-BOLDTEST" (shows in the panel title) specifically
// so it's visually obvious whether this exact build is the one actually
// loaded - if the panel still says "v39" (no suffix), MT5 is running a
// stale/cached copy and that's the real problem, not this function.
void PnlTxtB(int x, int y, string s, color clr, int size = 14, uint anchor = TA_LEFT | TA_TOP)
{
   g_panelCanvas.FontSet(PNL_FONT, size, PNL_WEIGHT_BOLD);
   uint argbOutline = ColorToARGB(C'0,0,0', 255);
   uint argbFill    = ColorToARGB(clr, 255);
   for(int dx = -2; dx <= 2; dx++)
      for(int dy = -2; dy <= 2; dy++)
         if(dx != 0 || dy != 0)
            g_panelCanvas.TextOut(x + dx, y + dy, s, argbOutline, anchor);
   g_panelCanvas.TextOut(x, y, s, argbFill, anchor);
}

void PnlRule(int x, int y, int w) { g_panelCanvas.FillRectangle(x, y, x + w, y + 1, ColorToARGB(PNL_RULE, 255)); }

void PnlRow(int x, int y, int colW, string label, string value, color valueClr)
{
   PnlTxtB(x, y, label, PNL_LABEL, 11);
   PnlTxtB(x + PNL_VALUE_COL, y - 1, value, valueClr, 13);
}

//--- same as PnlRow() but with a small colored accent bar to the left,
//--- for the numbers that deserve to stand out (matches the web
//--- dashboard's accent-bid/accent-ask idiom).
void PnlAccentRow(int x, int y, int colW, string label, string value, color valueClr, color accentClr)
{
   g_panelCanvas.FillRectangle(x - 9, y, x - 6, y + 14, ColorToARGB(accentClr, 255));
   PnlRow(x, y, colW, label, value, valueClr);
}

void PnlStatusDot(int x, int y, color clr) { g_panelCanvas.FillCircle(x, y, 3, ColorToARGB(clr, 255)); }

void CreatePanel()
{
   ObjectsDeleteAll(0, DASH_PREFIX); // clean out leftover flat objects from pre-v39 versions

   int bmpW = PNL_W + PNL_MARGIN * 2, bmpH = PNL_H + PNL_MARGIN * 2;
   g_panelCanvas.CreateBitmapLabel(DASH_PREFIX + "CANVAS", PNL_PX - 10 - PNL_MARGIN, PNL_PY - 10 - PNL_MARGIN,
                                    bmpW, bmpH, COLOR_FORMAT_ARGB_NORMALIZE);
   ObjectSetInteger(0, DASH_PREFIX + "CANVAS", OBJPROP_CORNER, CORNER_LEFT_UPPER);
}

void RecalcStatsIfNeeded()
{
   if(!HistorySelect(0, TimeCurrent())) return;
   int total = HistoryDealsTotal();
   if(total == g_lastDealsTotal) return;
   g_lastDealsTotal = total;

   g_statTrades = 0; g_statWins = 0; g_statLosses = 0; g_statTotalProfit = 0.0;
   for(int i = 0; i < total; i++)
   {
      ulong dt = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(dt, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(dt, DEAL_SYMBOL) != _Symbol) continue;
      long entryFlag = HistoryDealGetInteger(dt, DEAL_ENTRY);
      if(entryFlag != DEAL_ENTRY_OUT && entryFlag != DEAL_ENTRY_OUT_BY) continue;

      double p = HistoryDealGetDouble(dt, DEAL_PROFIT) + HistoryDealGetDouble(dt, DEAL_SWAP) + HistoryDealGetDouble(dt, DEAL_COMMISSION);
      g_statTrades++;
      if(p >= 0) g_statWins++; else g_statLosses++;
      g_statTotalProfit += p;
   }
}

void UpdatePanel()
{
   if(!InpShowPanel) return;
   // v41: the per-position P&L loop and RecalcStatsIfNeeded() used to run
   // here to feed the Open/Float P&L, Closed (W/L) and Total Profit rows.
   // Those rows were replaced by the Bookmap liquidity block, so the whole
   // computation is dead weight on every redraw - dropped. (The stats
   // helpers themselves are kept intact in case those rows come back.)

   // v39: a Canvas redraw is a raster operation (dozens of fill/text calls,
   // the gauge alone loops 180x) - too expensive to run on every tick like
   // the old ObjectSetString version could. Throttled to ~2x/sec, same
   // spirit as the web dashboard's 800ms poll - still reads as live.
   uint nowMs = GetTickCount();
   if(nowMs - g_lastPanelDrawMs < 500) return;
   g_lastPanelDrawMs = nowMs;

   int ox = PNL_MARGIN, oy = PNL_MARGIN;
   g_panelCanvas.Erase(0);

   for(int s = 6; s >= 1; s--)
      PnlFillRoundedRect(ox + s, oy + s, ox + PNL_W + s, oy + PNL_H + s, PNL_RADIUS,
                          ColorToARGB(PNL_SHADOW, (uchar)(7 * (7 - s))));

   PnlFillRoundedRect(ox, oy, ox + PNL_W, oy + PNL_H, PNL_RADIUS, ColorToARGB(PNL_GOLD, 255));
   PnlFillRoundedRect(ox + PNL_BORDER, oy + PNL_BORDER, ox + PNL_W - PNL_BORDER, oy + PNL_H - PNL_BORDER,
                       // v39.8: alpha 255, NOT 245. The bold-text A/B mockup (where
                       // technique "E" visibly worked) filled its background fully
                       // opaque; production used 245, and on a COLOR_FORMAT_ARGB_NORMALIZE
                       // canvas the normalize pass washes out text stamped over
                       // semi-transparent pixels - which is why every bold attempt
                       // rendered identically here but not in the mockup.
                       PNL_RADIUS - PNL_BORDER, ColorToARGB(PNL_BG, 255));

   g_panelCanvas.FillRectangle(ox + PNL_RADIUS, oy, ox + PNL_W - PNL_RADIUS, oy + 4, ColorToARGB(PNL_GOLD, 255));
   for(int i = 0; i < 6; i++)
      g_panelCanvas.FillRectangle(ox + PNL_RADIUS, oy + 4 + i, ox + PNL_W - PNL_RADIUS, oy + 5 + i,
                                   ColorToARGB(PNL_GOLD, (uchar)(90 - i * 14)));

   int x0 = ox + 14, y = oy + 12, contentW = PNL_W - 28;

   PnlTxtB(x0, y, InpPanelName, PNL_GOLD, 14); y += 19;
   PnlTxtB(x0, y, "[ " + EA_VERSION + " ]  " + InpOwnerName, PNL_LABEL, 10); y += 15;
   PnlTxtB(x0, y, "Version: " + EA_VERSION, PNL_GOLD, 10); y += 17;
   PnlRule(x0, y, contentW); y += 10;

   bool withH4 = (g_scalpMasterDir == g_masterDir);
   string modeTxt = g_scalpMasterDir == "WAIT" ? "Mode: WAIT" : (withH4 ? "Mode: WITH H4" : "*** MODE: AGAINST H4 ***");
   color modeClr  = g_scalpMasterDir == "WAIT" ? PNL_LABEL : (withH4 ? PNL_EMERALD : PNL_ROSE);
   PnlStatusDot(x0 + 3, y + 6, modeClr);
   PnlTxtB(x0 + 13, y, modeTxt, modeClr, 12); y += 19;
   PnlTxtB(x0, y, StringFormat("%s  >  %s  >  %s", EnumToString(InpMasterTF), EnumToString(InpScalpMasterTF), EnumToString(InpScalpEntryTF)), PNL_WHITE, 11); y += 17;
   PnlRow(x0, y, contentW, "H4  (Master)",  g_masterDir, DirColor(g_masterDir)); y += 16;
   PnlRow(x0, y, contentW, "Firing", g_m5FiringEnabled ? "ON" : "PAUSED", g_m5FiringEnabled ? PNL_EMERALD : PNL_LABEL); y += 16;
   PnlRow(x0, y, contentW, "M30 (Cascade)", g_scalpMasterDir, DirColor(g_scalpMasterDir)); y += 16;
   PnlRow(x0, y, contentW, "M5  (Entry)",   g_scalpEntryDir,  DirColor(g_scalpEntryDir));  y += 18;
   PnlRule(x0, y, contentW); y += 10;

   // v41: Dadang - "ini lo ganti aja kecuali bal/equity dengan data
   // liquidity ini" (pointing at the web dashboard's LIQUIDITY panel).
   // Open/Float P&L, Closed W/L and Total Profit are out; the wall data
   // that was previously only exported to the web dashboard now shows on
   // the chart panel too. Same computation as WriteSultanStatus()'s
   // liquidity block - offset-converted from Bookmap's GCZ6 scale to MT5.
   double wOffset   = (g_bookmapPrice > 0) ? (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice) : 0.0;
   double wCurPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double wBidPx    = (g_bookmapBidPx[0] > 0) ? g_bookmapBidPx[0] + wOffset : 0.0;
   double wAskPx    = (g_bookmapAskPx[0] > 0) ? g_bookmapAskPx[0] + wOffset : 0.0;
   double wDistBid  = (wBidPx > 0) ? MathAbs(wCurPrice - wBidPx) : 999999.0;
   double wDistAsk  = (wAskPx > 0) ? MathAbs(wCurPrice - wAskPx) : 999999.0;
   string wNearSide = (wDistBid <= wDistAsk) ? "BID" : "ASK";
   double wNearDist = MathMin(wDistBid, wDistAsk);

   int wBidCount = 0, wAskCount = 0;
   double wBidLot = 0.0, wAskLot = 0.0;
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      if(g_bookmapBidPx[i] > 0) { wBidCount++; wBidLot += g_bookmapBidSz[i]; }
      if(g_bookmapAskPx[i] > 0) { wAskCount++; wAskLot += g_bookmapAskSz[i]; }
   }
   double wImbalance = (wBidLot + wAskLot > 0) ? (wBidLot - wAskLot) / MathMax(wBidLot, wAskLot) : 0.0;

   PnlAccentRow(x0, y, contentW, "Bid Wall · Nearest",
                wBidPx > 0 ? StringFormat("%.2f  %.1fx", wBidPx, g_bookmapBidSz[0] / 10.0) : "-",
                PNL_EMERALD, PNL_EMERALD); y += 16;
   PnlAccentRow(x0, y, contentW, "Ask Wall · Nearest",
                wAskPx > 0 ? StringFormat("%.2f  %.1fx", wAskPx, g_bookmapAskSz[0] / 10.0) : "-",
                PNL_ROSE, PNL_ROSE); y += 16;
   PnlRow(x0, y, contentW, "Nearest Wall",
          wNearDist < 999999.0 ? StringFormat("%s  %+.2f", wNearSide, wNearDist) : "-",
          wNearSide == "BID" ? PNL_EMERALD : PNL_ROSE); y += 16;
   PnlRow(x0, y, contentW, "Imbalance (A-B)", StringFormat("%+.2f", wImbalance),
          wImbalance >= 0 ? PNL_EMERALD : PNL_ROSE); y += 16;
   PnlRow(x0, y, contentW, "Bid / Ask Walls", StringFormat("%d  /  %d", wBidCount, wAskCount), PNL_WHITE); y += 16;
   PnlRow(x0, y, contentW, "Bid / Ask Lot", StringFormat("%.0f  /  %.0f", wBidLot, wAskLot), PNL_WHITE); y += 16;
   PnlRow(x0, y, contentW, "Bal / Equity", StringFormat("%.2f / %.2f", AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY)), PNL_WHITE); y += 18;
   PnlRule(x0, y, contentW); y += 10;

   if(InpShowBookmapPanel)
   {
      if(g_bookmapOnline)
      {
         PnlStatusDot(x0 + 3, y + 5, PNL_GOLD);
         PnlTxtB(x0 + 13, y, "BOOKMAP  ·  LIVE", PNL_GOLD, 11); y += 18;
         PnlRow(x0, y, contentW, "CVD", StringFormat("%+.1f", g_bookmapCvd), g_bookmapCvd >= 0 ? PNL_EMERALD : PNL_ROSE); y += 16;

         color pulseClr = (g_bookmapAbsorption != "NONE") ? C'251,191,36' : PNL_LABEL;
         PnlRow(x0, y, contentW, "Pulse / Absorb", StringFormat("%.1f%%  %s", g_bookmapPulsePct, g_bookmapAbsorption), pulseClr); y += 18;

         // v38/v39: Price Pressure gauge - remap buyer_aggression_pct
         // (0..100) back to Bookmap's own -100..+100 "Price Change" scale
         // (same formula as sultan/logic.js's updatePulseGauge()), a real
         // smooth gradient semicircle (ring of small filled circles
         // lerping red->gray->green) with a needle, not a flat 3-segment bar.
         double pricePct = MathMax(-100.0, MathMin(100.0, (g_bookmapPulsePct - 50.0) * 2.0));
         int gx = x0 + contentW / 2, gy = y + 50, gr = 48;
         for(double a = 180.0; a <= 360.0; a += 1.5)
         {
            double rad = a * M_PI / 180.0;
            int px2 = gx + (int)MathRound(gr * MathCos(rad));
            int py2 = gy + (int)MathRound(gr * MathSin(rad));
            double t = (a - 180.0) / 180.0;
            color c = (t < 0.5)
                        ? PnlLerp(150, 45, 60,  70, 70, 78,  t / 0.5)
                        : PnlLerp(70, 70, 78,  40, 140, 100, (t - 0.5) / 0.5);
            g_panelCanvas.FillCircle(px2, py2, 4, ColorToARGB(c, 235));
         }
         double needleAngle = 180.0 + ((pricePct + 100.0) / 200.0) * 180.0;
         double nrad = needleAngle * M_PI / 180.0;
         int tipx = gx + (int)MathRound(40 * MathCos(nrad));
         int tipy = gy + (int)MathRound(40 * MathSin(nrad));
         double ndx = tipx - gx, ndy = tipy - gy, nlen = MathSqrt(ndx * ndx + ndy * ndy);
         double nx = -ndy / nlen, ny = ndx / nlen;
         uint needleClr = ColorToARGB(PNL_WHITE, 255);
         g_panelCanvas.Line(gx, gy, tipx, tipy, needleClr);
         g_panelCanvas.Line((int)(gx + nx), (int)(gy + ny), (int)(tipx + nx), (int)(tipy + ny), needleClr);
         g_panelCanvas.Line((int)(gx - nx), (int)(gy - ny), (int)(tipx - nx), (int)(tipy - ny), needleClr);
         g_panelCanvas.FillCircle(gx, gy, 4, needleClr);

         color pressClr = (pricePct > 15.0) ? PNL_EMERALD : (pricePct < -15.0) ? PNL_ROSE : PNL_LABEL;
         PnlTxtB(x0, gy + gr + 10, "Price down", PNL_LABEL, 9);
         PnlTxtB(x0 + contentW - 56, gy + gr + 10, "Price up", PNL_LABEL, 9);
         PnlTxtB(gx - 24, gy + gr + 6, StringFormat("%+.0f%%", pricePct), pressClr, 15);
         y = gy + gr + 30;
         PnlRule(x0, y, contentW); y += 10;

         // v29: session Volume Ratio (buy% of total traded volume) + POC.
         PnlRow(x0, y, contentW, "Vol Ratio", StringFormat("%.0f%% BUY / %.0f%% SELL", g_bookmapVolRatioBuyPct, 100.0 - g_bookmapVolRatioBuyPct),
                g_bookmapVolRatioBuyPct >= 50.0 ? PNL_EMERALD : PNL_ROSE); y += 16;

         double bmOffset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
         string pocTxt = g_bookmapPocPrice > 0 ? StringFormat("%.2f (%.0f vol)", g_bookmapPocPrice + bmOffset, g_bookmapPocVolume) : "-";
         PnlRow(x0, y, contentW, "POC", pocTxt, PNL_GOLD); y += 16;

         // v33: VAH/VAL (Value Area - 70% of session volume around POC).
         string vaTxt = (g_bookmapVah > g_bookmapVal && g_bookmapVal > 0)
                          ? StringFormat("%.2f - %.2f", g_bookmapVal + bmOffset, g_bookmapVah + bmOffset) : "-";
         PnlRow(x0, y, contentW, "Value Area", vaTxt, PNL_GOLD); y += 16;

         // v33: strongest iceberg candidate (either side) - informational.
         string iceTxt; color iceClr;
         if(g_bookmapBidIcePx > 0 && g_bookmapBidIceRatio >= g_bookmapAskIceRatio)
         {
            iceTxt = StringFormat("BID @ %.2f (%.1fx)", g_bookmapBidIcePx + bmOffset, g_bookmapBidIceRatio);
            iceClr = clrMagenta;
         }
         else if(g_bookmapAskIcePx > 0)
         {
            iceTxt = StringFormat("ASK @ %.2f (%.1fx)", g_bookmapAskIcePx + bmOffset, g_bookmapAskIceRatio);
            iceClr = clrMagenta;
         }
         else { iceTxt = "none"; iceClr = PNL_LABEL; }
         PnlRow(x0, y, contentW, "Iceberg", iceTxt, iceClr); y += 18;
         PnlRule(x0, y, contentW); y += 12;

         // v32: BIAS BUY/SELL/SIDEWAYS - Dadang: "tambah tulisan bias buy
         // atau sell dan sideways agar lebih mantap" - see ComputeBias().
         // v42: macro row - 6E (Euro FX) as a dollar proxy. Informational
         // only, never gates an entry: it answers "is the dollar with me or
         // against me" for the direction the cascade is already working.
         // 6E up = EUR strong = USD weak = tailwind for gold.
         // v43: USD fundamental block. Two rows, both straight from MT5:
         // the dollar's own bias (via EURUSD's CMP) and the next high-impact
         // USD release. The verdict compares that bias against whatever
         // direction the cascade is working - still informational only.
         if(g_usdBias != "")
         {
            // v43.2: Dadang - "vs nya ke gold aja, jangan ke yang lain. USD
            // lemah gold naik, USD kuat gold turun, gitu aja." So this states
            // the dollar's implication for gold directly instead of grading it
            // against whatever direction the cascade happens to be working -
            // the relationship is a property of the market, not of the setup.
            string goldEffect = (g_usdBias == "WEAK")   ? "GOLD NAIK"
                              : (g_usdBias == "STRONG") ? "GOLD TURUN" : "-";
            color  effClr     = (g_usdBias == "WEAK")   ? PNL_EMERALD
                              : (g_usdBias == "STRONG") ? PNL_ROSE : PNL_LABEL;
            PnlRow(x0, y, contentW, "USD (" + g_usdSymbol + ")",
                   StringFormat("%s  %s", g_eurDir, g_usdBias), effClr); y += 16;
            PnlRow(x0, y, contentW, "Efek ke Gold", goldEffect, effClr); y += 16;
         }
         else
         {
            PnlRow(x0, y, contentW, "USD (" + g_usdSymbol + ")",
                   g_eurDir == "STALE" ? "data basi" : "-", PNL_LABEL); y += 16;
         }

         // Next high-impact USD release - the row that says "jangan entry
         // dulu" better than any indicator can.
         if(g_usdNextMins >= 0)
         {
            string cd = (g_usdNextMins >= 60)
                          ? StringFormat("%dj%dm", g_usdNextMins / 60, g_usdNextMins % 60)
                          : StringFormat("%dm", g_usdNextMins);
            string evName = g_usdNextEvent;
            if(StringLen(evName) > 16) evName = StringSubstr(evName, 0, 16);
            // Inside 30 minutes of a high-impact release, flag it red.
            color newsClr = (g_usdNextMins <= 30) ? PNL_ROSE
                            : (g_usdNextMins <= 120) ? C'251,191,36' : PNL_LABEL;
            PnlRow(x0, y, contentW, "USD News", StringFormat("%s  %s", cd, evName), newsClr); y += 18;
         }
         else
         {
            PnlRow(x0, y, contentW, "USD News", "-", PNL_LABEL); y += 18;
         }
         PnlRule(x0, y, contentW); y += 12;

         // v44: conviction block replaces the bare BIAS line - same headline
         // idea, but it now says how much of the collected evidence actually
         // backs the setup, and names what is arguing against it.
         color convClr = (g_convGrade == "SIAP")      ? PNL_EMERALD
                       : (g_convGrade == "HATI-HATI") ? C'251,191,36'
                       : (g_convGrade == "TAHAN - NEWS" || g_convGrade == "TUNGGU") ? PNL_ROSE : PNL_LABEL;
         if(g_convDir == "BUY" || g_convDir == "SELL")
         {
            // Chain depth leads (that IS the system), flow confirms on top.
            PnlTxtB(x0, y, StringFormat("%s  RANTAI %d/6  ·  %s", g_convDir,
                    g_chainLen, g_convGrade), convClr, 13); y += 17;
            PnlTxtB(x0, y, g_convMode + (g_flowMax > 0 ? StringFormat("   flow %d/%d", g_flowScore, g_flowMax) : ""),
                    PNL_LABEL, 10); y += 15;
            if(g_chainDone != "")
               { PnlTxtB(x0, y, "sudah: " + g_chainDone, PNL_EMERALD, 10); y += 15; }
            // Amber + outlined: these are the warnings, so they must not be
            // the faintest text on the panel - they were, at plain 9px grey.
            if(g_convAgainst1 != "") { PnlTxtB(x0, y, "lawan: " + g_convAgainst1, C'251,191,36', 10); y += 15; }
            if(g_convAgainst2 != "") { PnlTxtB(x0, y, "lawan: " + g_convAgainst2, C'251,191,36', 10); y += 15; }
            if(g_convAgainst3 != "") { PnlTxtB(x0, y, "lawan: " + g_convAgainst3, C'251,191,36', 10); }
         }
         else
         {
            PnlTxtB(x0, y, "NO SETUP — M30 WAIT", PNL_LABEL, 13);
         }
      }
      else
      {
         PnlStatusDot(x0 + 3, y + 5, clrGray);
         PnlTxtB(x0 + 13, y, "BOOKMAP: OFFLINE", clrGray, 11); y += 18;
         PnlTxtB(x0, y, "(gak jalan / backtest)", clrGray, 10); y += 20;
         PnlTxtB(x0, y, "BIAS — N/A", clrGray, 11);
      }
   }

   // v41.1: Dadang - "ini ga terlalu lebar, atau lo beri label chain
   // reaction system by dadang wahyuono yang keren". There was dead space
   // between the BIAS line and the panel's bottom edge. Rather than just
   // shrinking the panel, this fills it with a signature footer - and it's
   // pinned to the bottom edge (measured back from PNL_H) instead of
   // flowing after y, so it stays put whether Bookmap is live or offline
   // (those two branches end at different heights).
   // v44.1: the system name moved to the panel HEADER (InpPanelName is now
   // "CHAIN REACTION SYSTEM" - Dadang: "sistem gw dari awal namanya chain
   // reaction system"), so the footer no longer repeats it; just the byline.
   int footerY = oy + PNL_H - 34;
   PnlRule(x0, footerY, contentW);
   PnlTxtB(x0 + contentW / 2, footerY + 12, "by " + InpOwnerName, PNL_LABEL, 10, TA_CENTER | TA_TOP);

   g_panelCanvas.Update();
}

//--- reads buffer 2 (CMP dir) + buffer 3 (change time) of DD_CMP_Indicator
string ReadCMP(int handle, datetime &changeTime)
{
   double buf[1], tbuf[1];
   changeTime = 0;
   if(CopyBuffer(handle, 2, 0, 1, buf) <= 0) return "WAIT";
   if(CopyBuffer(handle, 3, 0, 1, tbuf) <= 0) tbuf[0] = 0;
   changeTime = (datetime)tbuf[0];
   if(buf[0] > 0.5)  return "BUY";
   if(buf[0] < -0.5) return "SELL";
   return "WAIT";
}

//--- reads buffer 5 (live sup) or 6 (live res) - these keep updating on
//--- EVERY new V/A-shape, unlike buffer 4 which freezes at the last flip.
double ReadLiveLevel(int handle, int bufferIndex)
{
   double buf[1];
   if(CopyBuffer(handle, bufferIndex, 0, 1, buf) <= 0) return 0.0;
   return buf[0];
}

//--- reads buffer 7 (BreakoutEventTimeBuffer) - the time of the MOST RECENT
//--- individual breakout past the latest pullback, repeating on EVERY such
//--- break (not just the first regime-flip like buffer 3/ChangeTimeBuffer).
//--- This is THE entry-firing signal per Dadang's rule (2026-08-09): compare
//--- against the last-seen value to detect each fresh event.
datetime ReadBreakoutEventTime(int handle)
{
   double buf[1];
   if(CopyBuffer(handle, 7, 0, 1, buf) <= 0) return 0;
   return (datetime)buf[0];
}

//--- Momentum filter (eksperimen, off by default): skip entry if ADX on the
//--- last CLOSED bar is below InpADX_MinLevel (market too choppy/weak).
//--- Always returns true if InpUseADX is off or the handle wasn't created.
bool ADXOk(int handle)
{
   if(!InpUseADX || handle == INVALID_HANDLE) return true;
   double buf[1];
   if(CopyBuffer(handle, 0, 1, 1, buf) <= 0) return true;   // main ADX line, last closed bar
   return buf[0] >= InpADX_MinLevel;
}

//--- RSI filter. Two modes:
//--- (a) InpRSI_UseNeutralZone=true (Dadang: "kita hanya entri ketika RSI
//---     di 50, jangan sampai kejebak di oversold atau overbought") - entry
//---     only allowed when RSI sits within InpRSI_NeutralBand of 50,
//---     REGARDLESS of direction. Stricter than just avoiding extremes.
//--- (b) InpRSI_UseNeutralZone=false - old behavior: only block BUY when
//---     already overbought, block SELL when already oversold.
//--- Always true if InpUseRSI is off or the handle wasn't created.
bool RSIOk(int handle, string dir)
{
   if(!InpUseRSI || handle == INVALID_HANDLE) return true;
   double buf[1];
   if(CopyBuffer(handle, 0, 1, 1, buf) <= 0) return true;   // last closed bar
   double rsi = buf[0];

   if(InpRSI_UseNeutralZone)
      return (MathAbs(rsi - 50.0) <= InpRSI_NeutralBand);

   if(dir == "BUY"  && rsi >= InpRSI_Overbought) return false;
   if(dir == "SELL" && rsi <= InpRSI_Oversold)   return false;
   return true;
}

//--- M1 confirmation (redesigned 2026-08-09 per Dadang's live observation:
//--- "kalo M5 BO buy kita entri dan M1 malah bikin BO sell, M5 balik arah
//--- flip sell, BE kita kena" - a plain snapshot check wasn't enough since
//--- M1 naturally lags M5's own fresh BO by a few ticks/bars. This version
//--- requires M1's OWN breakout to be FRESH too (tM1 >= sinceTime, i.e. at
//--- or after M5's fresh BO) - AND crucially, the caller must call this
//--- EVERY TICK without consuming the bar-gate until it passes, so the EA
//--- genuinely WAITS for M1 to catch up instead of giving up after one
//--- bar's snapshot (which was the old, ineffective behavior - see memory
//--- notes: M1Confirm previously just cut trade count with no quality
//--- gain, because it never actually waited).
//--- Always true kalau InpUseM1Confirm off atau handle-nya gagal load.
bool M1Ok(string dir, datetime sinceTime)
{
   if(!InpUseM1Confirm || g_hM1 == INVALID_HANDLE) return true;
   datetime tM1;
   string m1Dir = ReadCMP(g_hM1, tM1);
   if(m1Dir != dir) return false;
   return tM1 >= sinceTime;
}

//--- Bookmap live-bridge reader. Reads the tiny CSV udp_listener.py
//--- overwrites every write cycle (see that file's MT5_BRIDGE_FILE comment)
//--- via Common\Files so both processes can see it regardless of which
//--- MT5/Python instance is running. LIVE path only reachable outside
//--- Strategy Tester/Optimization (v31: those instead replay from the
//--- recorded archive - see ReadBookmapHistoryReplay() above - since the
//--- live file's real wall-clock timestamp never matches simulated time).
//--- Absorption (v23) and POC-overextend (v30) are wired into entry lot-
//--- sizing; the rest (CVD/Pulse/Vol Ratio/Wall) stays informational.
//--- v31: loads ONE day's bookmap_history_YYYY-MM-DD.csv into the g_bmHist*
//--- arrays (append-mode - safe to call once per file found). Schema (see
//--- udp_listener.py's log_cvd_history()): timestamp_utc,time_wib,price,
//--- cvd_session,pulse_pct,absorption,h4_cmp,poc_price,poc_volume,
//--- vol_ratio_buy_pct,buy_vol_session,sell_vol_session,best_bid_px,
//--- best_bid_sz,best_ask_px,best_ask_sz (16 columns) - only the first 8 are
//--- used here, rest read-and-discarded (kept for future use).
//--- v33 schema (24 columns, see udp_listener.py's log_cvd_history()):
//--- timestamp_utc,time_wib,price,cvd_session,pulse_pct,absorption,h4_cmp,
//--- poc_price,poc_volume,vol_ratio_buy_pct,buy_vol_session,sell_vol_session,
//--- val,vah,best_bid_px,best_bid_sz,best_ask_px,best_ask_sz,bid_ice_px,
//--- bid_ice_sz,bid_ice_ratio,ask_ice_px,ask_ice_sz,ask_ice_ratio. Only the
//--- fields TryOpen()/ComputeBias() actually use get parsed into arrays
//--- (ts/price/cvd/pulse/absorb/poc/pocVol/val/vah); the rest (top-of-book,
//--- iceberg) are read-and-discarded here - iceberg is informational-only
//--- this round, not replayed in backtest.
void LoadOneBookmapHistoryFile(string relPath)
{
   int handle = FileOpen(relPath, FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return;

   for(int i = 0; i < 24 && !FileIsEnding(handle); i++) FileReadString(handle);   // skip header row

   while(!FileIsEnding(handle))
   {
      double ts = StringToDouble(FileReadString(handle));
      if(FileIsEnding(handle)) break;   // trailing blank line guard
      FileReadString(handle);                              // time_wib (display-only, skip)
      double price   = StringToDouble(FileReadString(handle));
      double cvd     = StringToDouble(FileReadString(handle));
      double pulse   = StringToDouble(FileReadString(handle));
      string absorb  = FileReadString(handle);
      FileReadString(handle);                              // h4_cmp (not used here, skip)
      double poc     = StringToDouble(FileReadString(handle));
      double pocVol  = StringToDouble(FileReadString(handle));
      for(int i = 0; i < 3 && !FileIsEnding(handle); i++) FileReadString(handle);   // vol_ratio,buy_vol,sell_vol - skip
      double val     = StringToDouble(FileReadString(handle));
      double vah     = StringToDouble(FileReadString(handle));
      for(int i = 0; i < 9 && !FileIsEnding(handle); i++) FileReadString(handle);   // best_bid_px..ask_ice_sz - skip
      if(!FileIsEnding(handle)) FileReadString(handle);     // ask_ice_ratio (last column)

      if(ts <= 0) continue;

      int idx = g_bmHistCount;
      ArrayResize(g_bmHistTime,     idx + 1, 50000);
      ArrayResize(g_bmHistBmPrice,  idx + 1, 50000);
      ArrayResize(g_bmHistCvd,      idx + 1, 50000);
      ArrayResize(g_bmHistPulse,    idx + 1, 50000);
      ArrayResize(g_bmHistAbsorb,   idx + 1, 50000);
      ArrayResize(g_bmHistPocPrice, idx + 1, 50000);
      ArrayResize(g_bmHistPocVolume,idx + 1, 50000);
      ArrayResize(g_bmHistVal,      idx + 1, 50000);
      ArrayResize(g_bmHistVah,      idx + 1, 50000);

      g_bmHistTime[idx]      = (datetime)ts;
      g_bmHistBmPrice[idx]   = price;
      g_bmHistCvd[idx]       = cvd;
      g_bmHistPulse[idx]     = pulse;
      g_bmHistAbsorb[idx]    = absorb;
      g_bmHistPocPrice[idx]  = poc;
      g_bmHistPocVolume[idx] = pocVol;
      g_bmHistVal[idx]       = val;
      g_bmHistVah[idx]       = vah;
      g_bmHistCount++;
   }
   FileClose(handle);
}

//--- v31: scans Common\Files\bookmap_history\ for every bookmap_history_*.csv
//--- (FileFindNext returns them in filename order, which sorts chronologically
//--- since the date is ISO YYYY-MM-DD) and loads them all once at OnInit() -
//--- only relevant in Strategy Tester/Optimization, never called live (the
//--- live path keeps using the always-fresh single-row bridge file instead).
void LoadBookmapHistory()
{
   g_bmHistCount  = 0;
   g_bmHistLoaded = false;
   ArrayResize(g_bmHistTime, 0);
   ArrayResize(g_bmHistBmPrice, 0);
   ArrayResize(g_bmHistCvd, 0);
   ArrayResize(g_bmHistPulse, 0);
   ArrayResize(g_bmHistAbsorb, 0);
   ArrayResize(g_bmHistPocPrice, 0);
   ArrayResize(g_bmHistPocVolume, 0);
   ArrayResize(g_bmHistVal, 0);
   ArrayResize(g_bmHistVah, 0);

   string fname;
   long search = FileFindFirst(BM_HIST_DIR + BM_HIST_GLOB, fname, FILE_COMMON);
   if(search == INVALID_HANDLE)
   {
      Print("BookmapHistoryReplay: no files found in Common\\Files\\", BM_HIST_DIR,
            " - Absorption/POC-overextend warnings will stay inactive this backtest.");
      return;
   }
   int fileCount = 0;
   do
   {
      LoadOneBookmapHistoryFile(BM_HIST_DIR + fname);
      fileCount++;
   }
   while(FileFindNext(search, fname));
   FileFindClose(search);

   g_bmHistLoaded = (g_bmHistCount > 0);
   Print("BookmapHistoryReplay: loaded ", g_bmHistCount, " rows from ", fileCount,
         " file(s) - covers ",
         (g_bmHistCount > 0 ? TimeToString(g_bmHistTime[0], TIME_DATE|TIME_MINUTES) : "-"),
         " to ",
         (g_bmHistCount > 0 ? TimeToString(g_bmHistTime[g_bmHistCount-1], TIME_DATE|TIME_MINUTES) : "-"));
}

//--- v31: index of the latest recorded row at or before time t (binary
//--- search - g_bmHistTime[] is chronologically sorted by construction).
//--- Returns -1 if t is before the very first recorded row.
int FindBookmapHistoryIndex(datetime t)
{
   if(g_bmHistCount == 0 || t < g_bmHistTime[0]) return -1;
   int lo = 0, hi = g_bmHistCount - 1;
   while(lo < hi)
   {
      int mid = (lo + hi + 1) / 2;
      if(g_bmHistTime[mid] <= t) lo = mid; else hi = mid - 1;
   }
   return lo;
}

//--- v31: Strategy Tester substitute for the live bridge read - looks up the
//--- historical row closest to (at or before) the CURRENT SIMULATED time and
//--- treats it exactly like a live snapshot. Only "online" for backtest date
//--- ranges that overlap with when the archive was actually being recorded
//--- (nothing before 2026-08-10) - correctly stays offline outside that
//--- range, same spirit as the live path staying offline when the bridge
//--- file is stale. Wall ladder isn't in the archive, so wall arrays are
//--- left untouched (UpdateWallLines() naturally draws nothing for them).
void ReadBookmapHistoryReplay()
{
   g_bookmapOnline = false;
   if(!g_bmHistLoaded) return;

   int idx = FindBookmapHistoryIndex(TimeCurrent());
   if(idx < 0) return;

   double ageSec = (double)TimeCurrent() - (double)g_bmHistTime[idx];
   if(ageSec > InpBookmapStaleSec * 4.0) return;   // logged every 5s live - wider tolerance than the live staleness check to absorb gaps

   g_bookmapOnline     = true;
   g_bookmapPrice      = g_bmHistBmPrice[idx];
   g_bookmapCvd        = g_bmHistCvd[idx];
   g_bookmapPulsePct   = g_bmHistPulse[idx];
   g_bookmapAbsorption = g_bmHistAbsorb[idx];
   g_bookmapPocPrice   = g_bmHistPocPrice[idx];
   g_bookmapPocVolume  = g_bmHistPocVolume[idx];
   g_bookmapVal        = g_bmHistVal[idx];
   g_bookmapVah        = g_bmHistVah[idx];
}

//--- v42: macro correlation (6E Euro FX as a dollar-strength proxy), read
//--- from its OWN file. Kept separate from bookmap_live_signal.csv on
//--- purpose: that reader skips exactly totalFields header cells then reads
//--- positionally, so adding columns there would shift every field unless
//--- Python and the EA are updated in lockstep. A missing/stale file here
//--- just leaves g_macroActive=false and the panel shows "-".
//--- v43: USD FUNDAMENTAL. Dadang: "untuk tekanan CVD semuanya ikut gold,
//--- gw kan hanya butuh fundamentalnya USD, terserah data ambil dari mana,
//--- berita atau apa gitu." So this drops the order-flow angle entirely and
//--- reads two things straight out of MT5 - no Bookmap, no extra data
//--- subscription, nothing to rebuild:
//---   1. EURUSD's own CMP (same DD_CMP_Indicator doctrine as gold) -> a
//---      continuous dollar bias. EUR up = USD weak = tailwind for gold.
//---   2. MT5's built-in Economic Calendar -> the next HIGH-impact USD
//---      release and how long until it fires. This is the part that stops
//---      an entry 10 minutes before NFP/CPI, which no order-flow gauge can
//---      tell you. Also closes the "News calendar otomatis" backlog item.
//--- Calendar data isn't available in Strategy Tester and some brokers
//--- don't serve it, so every field degrades to "-" rather than failing.
int      g_hEurUsdH4     = INVALID_HANDLE;
string   g_usdBias       = "";      // WEAK / STRONG / NEUTRAL
string   g_eurDir        = "";      // source symbol's H4 CMP: BUY / SELL / WAIT

// v43.1: Dadang - "kenapa lo pakai EUR kalo mau baca DXY". Fair - and the
// assumption that the broker had no dollar index was never checked. It does:
// DXY_U6 (99.793 on H4, a real index value). Two caveats found by testing it:
//   - it has NO live tick stream (bid/ask both 0) - only bar data updates,
//     so it can go stale in a way EURUSD never does;
//   - the name carries the contract month, so DXY_U6 becomes DXY_Z6 at the
//     September roll and any hardcoded symbol silently dies.
// Hence: auto-detect the current DXY_* contract, use it when its bars are
// fresh, and fall back to EURUSD otherwise. The two read OPPOSITE ways -
// DXY up means a STRONG dollar, EURUSD up means a WEAK one - so the source
// carries an inversion flag rather than the mapping being assumed anywhere.
string   g_usdSymbol     = "";      // whichever symbol is actually in use
bool     g_usdInverted   = false;   // true when the symbol rises as USD weakens (EURUSD)
string   g_usdCandidate  = "";      // DXY contract found at init, adopted once its history loads
string   g_usdNextEvent  = "";
int      g_usdNextMins   = -1;      // minutes until next high-impact USD event
datetime g_lastCalScan   = 0;

void ReadUsdFundamental()
{
   //--- 0. Upgrade to the real dollar index once its history has loaded ---
   // (see the note in OnInit: MT5 downloads a newly-selected symbol's bars
   // asynchronously, so this can only be decided after the fact)
   if(g_usdCandidate != "" && g_usdSymbol != g_usdCandidate && iBars(g_usdCandidate, PERIOD_H4) >= 100)
   {
      int hNew = iCustom(g_usdCandidate, PERIOD_H4, "DD_CMP_Indicator");
      if(hNew != INVALID_HANDLE)
      {
         if(g_hEurUsdH4 != INVALID_HANDLE) IndicatorRelease(g_hEurUsdH4);
         g_hEurUsdH4   = hNew;
         g_usdSymbol   = g_usdCandidate;
         g_usdInverted = false;   // DXY rises when the dollar strengthens
         Print("USD fundamental source upgraded to ", g_usdSymbol, " (direct: naik = USD kuat)");
      }
   }

   //--- 1. Dollar bias from the chosen source symbol's H4 CMP ------------
   g_eurDir  = "";
   g_usdBias = "";
   if(g_hEurUsdH4 != INVALID_HANDLE)
   {
      datetime t;
      g_eurDir = ReadCMP(g_hEurUsdH4, t);
      // DXY rising = strong dollar; EURUSD rising = weak dollar. g_usdInverted
      // encodes which of the two we're actually reading.
      if(g_eurDir == "BUY")       g_usdBias = g_usdInverted ? "WEAK"   : "STRONG";
      else if(g_eurDir == "SELL") g_usdBias = g_usdInverted ? "STRONG" : "WEAK";
      else                        g_usdBias = "NEUTRAL";

      // DXY_* has no tick stream, so its bars can quietly stop advancing
      // while everything else keeps running. Anything older than two H4
      // bars is treated as no reading at all rather than a stale opinion.
      datetime lastBar = (datetime)SeriesInfoInteger(g_usdSymbol, PERIOD_H4, SERIES_LASTBAR_DATE);
      if(lastBar > 0 && (TimeCurrent() - lastBar) > 2 * PeriodSeconds(PERIOD_H4))
      {
         g_usdBias = "";
         g_eurDir  = "STALE";
      }
   }

   //--- 2. Economic Calendar: next HIGH-impact USD release ----------------
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION)) return;
   if(TimeCurrent() - g_lastCalScan < 60) return;   // calendar barely changes; scan once a minute
   g_lastCalScan = TimeCurrent();

   g_usdNextEvent = "";
   g_usdNextMins  = -1;

   MqlCalendarValue values[];
   int n = CalendarValueHistory(values, TimeCurrent(), TimeCurrent() + 3 * 86400, NULL, "USD");
   if(n <= 0) return;   // broker doesn't serve calendar data - stays "-"

   datetime bestTime = 0;
   for(int i = 0; i < n; i++)
   {
      if(values[i].time <= TimeCurrent()) continue;          // already released
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev)) continue;
      if(ev.importance != CALENDAR_IMPORTANCE_HIGH) continue;
      if(bestTime == 0 || values[i].time < bestTime)
      {
         bestTime = values[i].time;
         g_usdNextEvent = ev.name;
      }
   }
   if(bestTime > 0)
      g_usdNextMins = (int)((bestTime - TimeCurrent()) / 60);
}

bool     g_macroActive   = false;
string   g_macroDirection = "";
string   g_macroUsd      = "";
string   g_macroVerdict  = "";
double   g_macroCvd      = 0.0;
bool     g_macroFlowOk   = false;

void ReadMacroCorrelation()
{
   g_macroActive = false;
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION)) return;

   int h = FileOpen("macro_correlation.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(h == INVALID_HANDLE) return;

   for(int i = 0; i < 10 && !FileIsEnding(h); i++) FileReadString(h);   // skip header (10 cols)
   if(FileIsEnding(h)) { FileClose(h); return; }

   double ts        = StringToDouble(FileReadString(h));
   string activeStr = FileReadString(h);
   FileReadString(h);                                    // alias - not shown on the panel
   FileReadString(h);                                    // price - EUR quote, not useful next to gold
   FileReadString(h);                                    // change
   string dir       = FileReadString(h);
   string usd       = FileReadString(h);
   double cvd       = StringToDouble(FileReadString(h));
   string flowStr   = FileReadString(h);
   string verdict   = FileReadString(h);
   FileClose(h);

   // Same staleness rule as the main bridge - a file left behind by a dead
   // listener must not read as live.
   double ageSec = (double)TimeCurrent() - ts;
   if(ageSec > InpBookmapStaleSec || activeStr != "1") return;

   g_macroActive    = true;
   g_macroDirection = dir;
   g_macroUsd       = usd;
   g_macroCvd       = cvd;
   g_macroFlowOk    = (flowStr == "1");
   g_macroVerdict   = verdict;
}

//+------------------------------------------------------------------+
//| v44: CONVICTION SCORE                                            |
//| Dadang: "tugas lo buat EA dan web py gw buat kesimpulannya dengan|
//| data yang ada."                                                  |
//|                                                                   |
//| Deliberately NOT a second opinion on direction. The direction is  |
//| whatever M30's own CMP says - that is the doctrine and it stays   |
//| untouched. What this adds is: of the independent factors already  |
//| being collected, how many currently agree with that direction,    |
//| and - more useful - which ones don't. A trader who knows what     |
//| he is fighting sizes differently than one who only sees a verdict.|
//|                                                                   |
//| DISPLAY ONLY. Nothing here gates an entry, changes a lot size or  |
//| touches TryOpen(). Runs for a while first so its output can be    |
//| compared against real outcomes before it is ever trusted with     |
//| money.                                                            |
//+------------------------------------------------------------------+
string   g_convDir      = "";
int      g_convScore    = 0;
int      g_convMax      = 0;
string   g_convGrade    = "";
string   g_convMode     = "";   // AWAL / SCALP / BERKEMBANG / TREND / FULL CHAIN - depth of the chain
int      g_chainLen     = 0;    // how many rungs, M5 upward, have converted
string   g_chainDone    = "";   // e.g. "M5>M15>M30"
string   g_chainNext    = "";   // the first rung that hasn't flipped yet
string   g_chainPending = "";   // all rungs not yet converted
int      g_flowScore    = 0;    // order-flow / macro confirmation on top of the chain
int      g_flowMax      = 0;
string   g_convAgainst1 = "";
string   g_convAgainst2 = "";
string   g_convAgainst3 = "";
int      g_convAgainstN = 0;   // total opposing factors, including any beyond the 3 shown

// v44.2: was 2 slots, which hid the third blocker exactly when it mattered -
// at 5/8 three factors are failing but only two were ever printed, so the
// question "what would make this KUAT" was unanswerable from the panel.
void AddAgainst(string reason)
{
   g_convAgainstN++;
   if(g_convAgainst1 == "")      g_convAgainst1 = reason;
   else if(g_convAgainst2 == "") g_convAgainst2 = reason;
   else if(g_convAgainst3 == "") g_convAgainst3 = reason;
}

void ComputeConviction()
{
   g_convScore = 0; g_convMax = 0;
   g_convGrade = ""; g_convMode = "";
   g_chainLen = 0; g_chainDone = ""; g_chainNext = ""; g_chainPending = "";
   g_flowScore = 0; g_flowMax = 0;
   g_convAgainst1 = ""; g_convAgainst2 = ""; g_convAgainst3 = ""; g_convAgainstN = 0;

   //=== THE CHAIN ITSELF ===================================================
   // v45: Dadang, describing the mechanic the whole system is named after:
   //   "kita akan sell jika M5 BO sell terus, dan tiap bisa flip TF atasnya
   //    makin kuat. Contoh M5 sell terus berhasil merubah M15 jadi sell maka
   //    skor tambah, jika M30 juga ikut sell maka tambah lagi, jika H1 juga
   //    ikut tambah lagi, dan seterusnya."
   //
   // So strength is not "how many timeframes happen to agree" measured as a
   // static snapshot - it is HOW FAR UP THE LADDER the conversion has
   // actually propagated, starting from M5 and climbing. That reframes a
   // counter-daily setup correctly: it isn't a weak trade, it's an EARLY one.
   // The chain breaks at the first timeframe that hasn't converted yet, and
   // that timeframe is the next target - which is exactly the thing worth
   // watching, so it's surfaced by name.
   string tfName[6] = {"M5", "M15", "M30", "H1", "H4", "D1"};
   int    tfHandle[6];
   tfHandle[0] = g_hScalpEntry;    // M5  - where the chain starts
   tfHandle[1] = g_hExportM15;
   tfHandle[2] = g_hScalpMaster;   // M30
   tfHandle[3] = g_hExportH1;
   tfHandle[4] = g_hMaster;        // H4
   tfHandle[5] = g_hExportD1;

   string tfDir[6];
   datetime tTmp;
   for(int i = 0; i < 6; i++)
      tfDir[i] = (tfHandle[i] != INVALID_HANDLE) ? ReadCMP(tfHandle[i], tTmp) : "";

   // The direction is whatever M5 - the origin of the chain - is breaking.
   g_convDir = tfDir[0];
   if(g_convDir != "BUY" && g_convDir != "SELL")
   {
      g_convDir = g_scalpMasterDir;        // fall back to M30 while M5 is undecided
      if(g_convDir != "BUY" && g_convDir != "SELL") { g_convGrade = "NO SETUP"; return; }
   }
   bool isBuy = (g_convDir == "BUY");

   // Climb: count consecutive converted rungs, stop at the first that hasn't.
   for(int i = 0; i < 6; i++)
   {
      if(tfDir[i] == g_convDir)
      {
         g_chainLen++;
         g_chainDone += (g_chainDone == "" ? "" : ">") + tfName[i];
      }
      else
      {
         if(g_chainNext == "") g_chainNext = tfName[i];
         g_chainPending += (g_chainPending == "" ? "" : " ") + tfName[i];
      }
   }

   // Chain depth names the trade type. Deeper chain = the move has convinced
   // bigger timeframes = it can be given room. Shallow = take it, but quick.
   if(g_chainLen >= 5)      g_convMode = "FULL CHAIN";
   else if(g_chainLen == 4) g_convMode = "TREND";
   else if(g_chainLen == 3) g_convMode = "BERKEMBANG";
   else if(g_chainLen == 2) g_convMode = "SCALP";
   else                     g_convMode = "AWAL";

   if(g_chainNext != "")
      AddAgainst(g_chainNext + " belum flip - target berikutnya");

   //=== FLOW SUPPORT - does live order flow back the chain right now? ======
   //--- Bookmap-derived factors only count when the feed is actually live.
   if(g_bookmapOnline)
   {
      double bmOffset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
      double px = SymbolInfoDouble(_Symbol, SYMBOL_BID);

      //--- 1. Order flow (CVD) pointing the same way
      g_flowMax++;
      if((isBuy && g_bookmapCvd > 0) || (!isBuy && g_bookmapCvd < 0)) g_flowScore++;
      else AddAgainst(StringFormat("CVD %+.0f lawan", g_bookmapCvd));

      //--- 2. No absorption working against this direction
      g_flowMax++;
      bool absorbAgainst = (isBuy  && g_bookmapAbsorption == "BUYER_ABSORBED") ||
                           (!isBuy && g_bookmapAbsorption == "SELLER_ABSORBED");
      if(!absorbAgainst) g_flowScore++;
      else AddAgainst("Absorption: " + g_bookmapAbsorption);

      //--- 3. Path to target not blocked by a wall sitting right in front.
      //--- "Right in front" scales with volatility rather than a fixed number.
      double atrBuf[1]; double atr = 0.0;
      if(g_hATR != INVALID_HANDLE && CopyBuffer(g_hATR, 0, 0, 1, atrBuf) > 0) atr = atrBuf[0];
      double nearDist = MathMax(3.0, atr * 0.3);
      double blockPx = isBuy ? (g_bookmapAskPx[0] > 0 ? g_bookmapAskPx[0] + bmOffset : 0.0)
                             : (g_bookmapBidPx[0] > 0 ? g_bookmapBidPx[0] + bmOffset : 0.0);
      double blockSz = isBuy ? g_bookmapAskSz[0] : g_bookmapBidSz[0];
      g_flowMax++;
      if(blockPx <= 0 || MathAbs(blockPx - px) > nearDist) g_flowScore++;
      else AddAgainst(StringFormat("%s wall %.0f lot di jalur", isBuy ? "Ask" : "Bid", blockSz));

      //--- 4. Location: chasing an already-extended move is where entries
      //--- get filled right before the pullback.
      if(g_bookmapVah > g_bookmapVal && g_bookmapVal > 0)
      {
         double vah = g_bookmapVah + bmOffset, val = g_bookmapVal + bmOffset;
         g_flowMax++;
         bool extended = (isBuy && px > vah) || (!isBuy && px < val);
         if(!extended) g_flowScore++;
         else AddAgainst(isBuy ? "Harga udah di atas VAH" : "Harga udah di bawah VAL");
      }
   }

   //--- 5. USD backdrop counts as flow support too: weak dollar behind a
   //--- gold BUY is the macro equivalent of CVD pointing the right way.
   if(g_usdBias == "WEAK" || g_usdBias == "STRONG")
   {
      g_flowMax++;
      if((isBuy && g_usdBias == "WEAK") || (!isBuy && g_usdBias == "STRONG")) g_flowScore++;
      else AddAgainst("USD " + g_usdBias + " lawan");
   }

   //--- Headline strength: the chain is what the system is built on, so it
   //--- leads. Flow is the confirmation layer on top - a deep chain with
   //--- flow against it is still worth naming as such rather than hidden
   //--- inside one averaged number.
   g_convScore = g_chainLen;
   g_convMax   = 6;
   double flowPct = (g_flowMax > 0) ? (100.0 * g_flowScore / g_flowMax) : -1.0;

   if(g_chainLen <= 1)          g_convGrade = "AWAL";
   else if(flowPct < 0)         g_convGrade = "NO FLOW";     // Bookmap offline
   else if(flowPct >= 75.0)     g_convGrade = "SIAP";
   else if(flowPct >= 50.0)     g_convGrade = "HATI-HATI";
   else                         g_convGrade = "FLOW LAWAN";

   //--- News proximity overrides everything: no chain depth survives a bad
   //--- print, and spreads blow out regardless of direction.
   if(g_usdNextMins >= 0 && g_usdNextMins <= 30)
   {
      g_convGrade = "TAHAN - NEWS";
      AddAgainst(StringFormat("Rilis USD %dm lagi", g_usdNextMins));
   }
}

void ReadBookmapBridge()
{
   g_bookmapOnline = false;
   if(!InpShowBookmapPanel)
   {
      ObjectsDeleteAll(0, WALL_PREFIX);
      return;
   }

   // v31: Strategy Tester/Optimization can't use the live bridge file (real
   // wall-clock timestamp never matches simulated time) - replay from the
   // recorded archive instead, then return (skip the live-file read below,
   // which would immediately overwrite g_bookmapOnline=false anyway).
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
   {
      ReadBookmapHistoryReplay();
      return;
   }

   int handle = FileOpen("bookmap_live_signal.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) { ObjectsDeleteAll(0, WALL_PREFIX); return; }   // bridge never ran, or udp_listener.py isn't up

   int totalFields = 18 + WALL_SLOTS_PER_SIDE * 2 * 2;   // timestamp,price,cvd,pulse,absorption,poc_price,poc_volume,vol_ratio,buy_vol,sell_vol,val,vah,bid_ice_px,bid_ice_sz,bid_ice_ratio,ask_ice_px,ask_ice_sz,ask_ice_ratio + (bid+ask)*(px+sz) per slot
   for(int i = 0; i < totalFields && !FileIsEnding(handle); i++) FileReadString(handle);   // skip header row
   if(FileIsEnding(handle)) { FileClose(handle); ObjectsDeleteAll(0, WALL_PREFIX); return; }

   double ts    = StringToDouble(FileReadString(handle));
   double price = StringToDouble(FileReadString(handle));   // Bookmap's OWN instrument price (GCZ6, not XAUUSD)
   double cvd     = StringToDouble(FileReadString(handle));
   double pulse   = StringToDouble(FileReadString(handle));
   string absorb  = FileReadString(handle);
   double pocPrice   = StringToDouble(FileReadString(handle));
   double pocVolume  = StringToDouble(FileReadString(handle));
   double volRatio   = StringToDouble(FileReadString(handle));
   double buyVol     = StringToDouble(FileReadString(handle));
   double sellVol    = StringToDouble(FileReadString(handle));
   double val        = StringToDouble(FileReadString(handle));
   double vah         = StringToDouble(FileReadString(handle));
   double bidIcePx    = StringToDouble(FileReadString(handle));
   double bidIceSz    = StringToDouble(FileReadString(handle));
   double bidIceRatio = StringToDouble(FileReadString(handle));
   double askIcePx    = StringToDouble(FileReadString(handle));
   double askIceSz    = StringToDouble(FileReadString(handle));
   double askIceRatio = StringToDouble(FileReadString(handle));
   double bidPx[WALL_SLOTS_PER_SIDE], bidSz[WALL_SLOTS_PER_SIDE];
   double askPx[WALL_SLOTS_PER_SIDE], askSz[WALL_SLOTS_PER_SIDE];
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      bidPx[i] = StringToDouble(FileReadString(handle));
      bidSz[i] = StringToDouble(FileReadString(handle));
   }
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      askPx[i] = StringToDouble(FileReadString(handle));
      askSz[i] = StringToDouble(FileReadString(handle));
   }
   FileClose(handle);

   // v24 fix: use MathAbs() instead of requiring ageSec>=0 - the old check
   // rejected EVERYTHING if TimeGMT() ever lagged slightly behind Python's
   // system clock (ageSec goes negative), no matter how large
   // InpBookmapStaleSec was set. Small clock skew either direction should
   // still count as "fresh" - only genuinely stale/old data (large positive
   // gap) or a backtest (huge gap, real timestamp vs simulated time) should
   // be rejected.
   double ageSec = (double)TimeGMT() - ts;
   if(MathAbs(ageSec) > InpBookmapStaleSec) { ObjectsDeleteAll(0, WALL_PREFIX); return; }   // stale/offline/backtest

   g_bookmapAgeMs      = MathAbs(ageSec) * 1000.0;   // v34: for the SULTAN dashboard's bridge latency display
   g_bookmapOnline     = true;
   g_bookmapPrice      = price;
   g_bookmapCvd        = cvd;
   g_bookmapPulsePct   = pulse;
   g_bookmapAbsorption = absorb;
   g_bookmapPocPrice       = pocPrice;
   g_bookmapPocVolume      = pocVolume;
   g_bookmapVolRatioBuyPct = volRatio;
   g_bookmapBuyVolSession  = buyVol;
   g_bookmapSellVolSession = sellVol;
   g_bookmapVal            = val;
   g_bookmapVah            = vah;
   g_bookmapBidIcePx       = bidIcePx;
   g_bookmapBidIceSz       = bidIceSz;
   g_bookmapBidIceRatio    = bidIceRatio;
   g_bookmapAskIcePx       = askIcePx;
   g_bookmapAskIceSz       = askIceSz;
   g_bookmapAskIceRatio    = askIceRatio;
   ArrayCopy(g_bookmapBidPx, bidPx);
   ArrayCopy(g_bookmapBidSz, bidSz);
   ArrayCopy(g_bookmapAskPx, askPx);
   ArrayCopy(g_bookmapAskSz, askSz);
   UpdateWallLines();
   UpdatePocLine();
   UpdateValueAreaLines();
   UpdateIcebergLines();
}

//--- Maps wall size (10-1000 lot range) to a line width 1-5. Dadang 2026-08-10:
//--- "tidak bisa dibuat yang tampil mulai 10 lot sampai 1000 lot bro" - show
//--- the WHOLE range instead of a single on/off cutoff, bigger = more visually
//--- prominent (thicker + more saturated color) instead of just present/absent.
int WallWidth(double size)
{
   double frac = (size - 10.0) / (1000.0 - 10.0);
   frac = MathMax(0.0, MathMin(1.0, frac));
   return 1 + (int)MathRound(frac * 4.0);   // 1..5
}

//--- Interpolates from a faint/dim shade (small wall, ~10 lot) to the full
//--- vivid color (big wall, >=1000 lot). MQL5 color is 0x00BBGGRR (R = low
//--- byte), so R+G*256+B*65536 builds it directly - isBid picks green vs red.
color WallColor(bool isBid, double size)
{
   double frac = (size - 10.0) / (1000.0 - 10.0);
   frac = MathMax(0.0, MathMin(1.0, frac));
   int channel = 90 + (int)MathRound(frac * (255 - 90));   // 90 (dim) .. 255 (vivid)
   if(isBid) return (color)(channel * 256);                 // green channel only
   return (color)(channel);                                  // red channel only
}

//--- Draws (or updates) one Bookmap wall as a horizontal line on the MT5
//--- chart, width/color scaled by size (WallWidth/WallColor above).
//--- bookmapPrice comes straight from Bookmap's own instrument (e.g. GCZ6
//--- futures) - offset converts it to XAUUSD-equivalent. Deletes the object
//--- if this wall slot is empty (price<=0, sent that way by the Python side
//--- when fewer than 2 walls exist on that side).
void DrawWallLine(string key, double bookmapPrice, double size, double offset, bool isBid, string sideLabel, int barsAhead = 8)
{
   string name     = WALL_PREFIX + key;
   string textName = WALL_PREFIX + key + "_TXT";
   if(bookmapPrice <= 0 || size <= 0)
   {
      if(ObjectFind(0, name) >= 0)     ObjectDelete(0, name);
      if(ObjectFind(0, textName) >= 0) ObjectDelete(0, textName);
      return;
   }
   double mt5Price = bookmapPrice + offset;
   color  clr      = WallColor(isBid, size);
   int    width    = WallWidth(size);

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT,
      StringFormat("%s %.0f lot @ %.2f (bookmap %.2f)", sideLabel, size, mt5Price, bookmapPrice));

   // Dadang 2026-08-10: "tampilkan lotnya di mt5 juga bro di garisnya" - the
   // HLINE's OBJPROP_TEXT above is only a hover tooltip. Add an always-VISIBLE
   // text label anchored a few bars into the future (blank space right of the
   // latest candle), same price/color as the line, so the lot size is
   // readable at a glance without hovering.
   //
   // v35 fix - Dadang: "m5 masih keluar dari kotak card... bid ask di chart
   // ini bisa gak di buat lebih rapi" (garbled/overlapping wall labels).
   // Root cause: EVERY label used the exact same fixed 8-bar anchor, so
   // walls sitting close in PRICE (common - most of the 5 "near" slots per
   // side cluster near current price) rendered their text at the same X,
   // stacking on top of each other. barsAhead now staggers each slot
   // further right (see UpdateWallLines()'s per-slot offset) so nearby-price
   // walls land in different horizontal "lanes" instead of colliding.
   datetime labelTime = TimeCurrent() + PeriodSeconds(_Period) * barsAhead;
   if(ObjectFind(0, textName) < 0)
   {
      ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, mt5Price);
      ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_LEFT);
   }
   ObjectSetInteger(0, textName, OBJPROP_TIME, labelTime);
   ObjectSetDouble(0, textName, OBJPROP_PRICE, mt5Price);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, clrWhite);   // Dadang 2026-08-10: "hurufnya buat putih aja" - readable regardless of wall color/darkness
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 12 + (width - 1) * 2);   // Dadang: "besarin lotnya" - was 8-12, now 12-20
   ObjectSetString(0, textName, OBJPROP_TEXT, StringFormat(" %s: %.0f lot", sideLabel, size));
}

//--- Dadang 2026-08-10: "bisa gak berapa banyak lot di bookmap langsung
//--- tergaris di MT5 tapi harus lo cover sesuai harga bookmap nya" - Bookmap
//--- trades a DIFFERENT instrument (GCZ6 gold futures) than this EA's XAUUSD
//--- spot, so wall prices can't be plotted 1:1 - the futures/spot basis
//--- drifts over time, so the offset is recomputed EVERY update, never
//--- cached/hardcoded.
void UpdateWallLines()
{
   if(!g_bookmapOnline || g_bookmapPrice <= 0)
   {
      ObjectsDeleteAll(0, WALL_PREFIX);
      return;
   }
   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;

   // v35: stagger each slot's label 3 bars further right than the last -
   // walls close in PRICE (common among the "near" slots) land in different
   // horizontal lanes instead of stacking their text on top of each other.
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      string key   = StringFormat("BID%d", i+1);
      string label = StringFormat("BID WALL %d", i+1);
      DrawWallLine(key, g_bookmapBidPx[i], g_bookmapBidSz[i], offset, true, label, 8 + i * 3);
   }
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      string key   = StringFormat("ASK%d", i+1);
      string label = StringFormat("ASK WALL %d", i+1);
      DrawWallLine(key, g_bookmapAskPx[i], g_bookmapAskSz[i], offset, false, label, 8 + i * 3);
   }
}

//--- v29: POC (Point of Control) - price level with the most TOTAL traded
//--- volume this session (VolumeProfileEngine, Bookmap side) - distinct
//--- from the wall lines above (those are resting ORDER book size, this is
//--- volume that actually TRADED). Drawn as one solid gold line, uses the
//--- WALL_PREFIX namespace so it gets cleaned up by the same
//--- ObjectsDeleteAll(0, WALL_PREFIX) calls that clear wall lines when
//--- Bookmap goes offline/stale.
void UpdatePocLine()
{
   string name     = WALL_PREFIX + "POC";
   string textName = WALL_PREFIX + "POC_TXT";
   if(!g_bookmapOnline || g_bookmapPocPrice <= 0 || g_bookmapPocVolume <= 0)
   {
      if(ObjectFind(0, name) >= 0)     ObjectDelete(0, name);
      if(ObjectFind(0, textName) >= 0) ObjectDelete(0, textName);
      return;
   }
   double offset   = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   double mt5Price = g_bookmapPocPrice + offset;

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT,
      StringFormat("POC %.0f vol @ %.2f (bookmap %.2f)", g_bookmapPocVolume, mt5Price, g_bookmapPocPrice));

   // v35: own lane (40 bars) beyond the wall staircase (8-35 bars, see
   // UpdateWallLines()) so POC's label never collides with a nearby wall's.
   datetime labelTime = TimeCurrent() + PeriodSeconds(_Period) * 40;
   if(ObjectFind(0, textName) < 0)
   {
      ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, mt5Price);
      ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_LEFT);
   }
   ObjectSetInteger(0, textName, OBJPROP_TIME, labelTime);
   ObjectSetDouble(0, textName, OBJPROP_PRICE, mt5Price);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 14);
   ObjectSetString(0, textName, OBJPROP_TEXT, StringFormat(" POC: %.0f vol", g_bookmapPocVolume));
}

//--- v32/v33: 3-state BIAS derived from POC/Value-Area position + H4 CMP
//--- direction. Dadang: "kalo harga di atas poc kita gimana, kalo harga di
//--- bawah poc kita gimana" - above the value area = BUY territory; below =
//--- SELL territory; INSIDE the value area (or, before VAH/VAL exist yet,
//--- within InpPocSidewaysZoneUsd of POC) = no clear edge -> SIDEWAYS.
//--- v33: prefers the real VAH/VAL boundary (statistically grounded - 70% of
//--- session volume) over the flat $ zone once it's available; falls back to
//--- the old $3 zone early in the session before enough price spread has
//--- been recorded for a value area to form. When H4 (g_masterDir) disagrees
//--- with the implied side, treated as SIDEWAYS too (mixed signal, no
//--- consensus) - only shows a directional bias when they actually AGREE, or
//--- when H4 hasn't warmed up yet (POC/VA alone still valid).
string ComputeBias()
{
   if(!g_bookmapOnline || g_bookmapPocPrice <= 0 || g_bookmapPrice <= 0)
      return "N/A (Bookmap offline)";

   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   string pocSide;
   if(g_bookmapVah > g_bookmapVal && g_bookmapVal > 0)
   {
      double vahMt5 = g_bookmapVah + offset;
      double valMt5 = g_bookmapVal + offset;
      if(curPrice > vahMt5)      pocSide = "BUY";
      else if(curPrice < valMt5) pocSide = "SELL";
      else                       pocSide = "SIDEWAYS";
   }
   else
   {
      double pocMt5Price = g_bookmapPocPrice + offset;
      double diff = curPrice - pocMt5Price;
      if(diff > InpPocSidewaysZoneUsd)       pocSide = "BUY";
      else if(diff < -InpPocSidewaysZoneUsd) pocSide = "SELL";
      else                                   pocSide = "SIDEWAYS";
   }

   if(pocSide == "SIDEWAYS") return "SIDEWAYS";
   if(g_masterDir == "WAIT") return pocSide;        // H4 not warmed up yet - POC/VA alone still meaningful
   if(g_masterDir == pocSide) return pocSide;        // POC/VA + CMP agree - strongest read
   return "SIDEWAYS";                                 // POC/VA and CMP disagree - no clear consensus
}

//--- v34: SULTAN SNIPER ENGINE web dashboard export. Dadang: "gak usah baca
//--- pine langsung mt5 aja supaya bagus tv nya kita close" - MT5's own
//--- DD_CMP_Indicator always has full historical bars (unlike Bookmap's own
//--- tick-only CMP, which needs hours/days to warm up and resets on every
//--- udp_listener.py restart) - so this exports Market Regime directly from
//--- MT5, no TradingView/Pine dependency anywhere in this pipeline anymore.
//--- Writes Common\Files\sultan_status.json, read by the new web dashboard
//--- (sultan_dashboard_server.py + sultan/index.html) - throttled to ~1/sec.
//--- Formulas for "ratio"/"imbalance" fields are this EA's OWN reasonable
//--- interpretation (documented inline), not a reverse-engineered replica of
//--- any specific external mockup's exact numbers.
void WriteSultanStatus()
{
   if((int)(TimeGMT() - g_lastSultanExportTime) < 1) return;   // throttle ~1/sec
   g_lastSultanExportTime = TimeGMT();

   //--- Market Regime: D1/H1/M15 read fresh from MT5 (full history, no
   //--- warm-up) purely for display - NOT part of the H4/M30/M5 trading
   //--- cascade, which stays exactly as-is.
   datetime tD1, tH1, tM15, tM1;
   string d1Dir  = ReadCMP(g_hExportD1,  tD1);
   string h1Dir  = ReadCMP(g_hExportH1,  tH1);
   string m15Dir = ReadCMP(g_hExportM15, tM15);
   string m1Dir  = ReadCMP(g_hExportM1,  tM1);   // v37: passthrough for udp_listener.py's M1-leading-indicator commentary (was Pine-only before)

   int buyCount = 0, sellCount = 0, validCount = 0;
   if(g_masterDir      == "BUY") buyCount++; else if(g_masterDir      == "SELL") sellCount++;
   if(g_scalpMasterDir == "BUY") buyCount++; else if(g_scalpMasterDir == "SELL") sellCount++;
   if(g_scalpEntryDir  == "BUY") buyCount++; else if(g_scalpEntryDir  == "SELL") sellCount++;
   validCount = (g_masterDir != "WAIT" ? 1 : 0) + (g_scalpMasterDir != "WAIT" ? 1 : 0) + (g_scalpEntryDir != "WAIT" ? 1 : 0);
   // Alignment % = how much of H4/M30/M5 agree with the MAJORITY direction -
   // 100% = all 3 same (TRENDING), else SIDEWAYS. Own formula, not a replica
   // of any specific external reference.
   double alignmentPct = (validCount > 0) ? (MathMax(buyCount, sellCount) / 3.0 * 100.0) : 0.0;
   string regime  = (alignmentPct >= 99.9) ? "TRENDING" : "SIDEWAYS";
   string htfBias = (g_masterDir == "BUY") ? "BULLISH" : (g_masterDir == "SELL") ? "BEARISH" : "NEUTRAL";
   string m5Status = (g_scalpEntryDir == "WAIT") ? "WAIT" : (g_scalpEntryDir == g_masterDir) ? "WITH_TREND" : "COUNTER_TREND";

   //--- Bookmap Flow: 1-minute CVD delta history, sampled once per REAL
   //--- minute (wall-clock, not chart bars) into a small ring buffer.
   MqlDateTime dtNow;
   TimeToStruct(TimeGMT(), dtNow);
   int curMinuteBucket = dtNow.hour * 60 + dtNow.min;
   if(curMinuteBucket != g_lastCvdSampleMinute)
   {
      g_lastCvdSampleMinute = curMinuteBucket;
      for(int i = 0; i < CVD_HIST_LEN - 1; i++) g_cvdMinuteSamples[i] = g_cvdMinuteSamples[i + 1];
      g_cvdMinuteSamples[CVD_HIST_LEN - 1] = g_bookmapCvd;
      if(g_cvdSampleCount < CVD_HIST_LEN) g_cvdSampleCount++;
   }
   double delta1m = (g_cvdSampleCount >= 2) ? (g_cvdMinuteSamples[CVD_HIST_LEN - 1] - g_cvdMinuteSamples[CVD_HIST_LEN - 2]) : 0.0;
   string flowDominant = (g_bookmapVolRatioBuyPct >= 50.0) ? "BUY" : "SELL";

   //--- Liquidity: nearest wall + summary across all slots. "Ratio" here =
   //--- size / 10-lot baseline (same baseline WallWidth()/WallColor() use
   //--- for chart line scaling) - a strength multiplier, own interpretation.
   double offset = (g_bookmapPrice > 0) ? (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice) : 0.0;
   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double bidWallPx = (g_bookmapBidPx[0] > 0) ? g_bookmapBidPx[0] + offset : 0.0;
   double askWallPx = (g_bookmapAskPx[0] > 0) ? g_bookmapAskPx[0] + offset : 0.0;
   double bidWallSz = g_bookmapBidSz[0], askWallSz = g_bookmapAskSz[0];
   double distBid = (bidWallPx > 0) ? MathAbs(curPrice - bidWallPx) : 999999.0;
   double distAsk = (askWallPx > 0) ? MathAbs(curPrice - askWallPx) : 999999.0;
   string nearestWallSide = (distBid <= distAsk) ? "BID" : "ASK";
   double nearestWallDist = MathMin(distBid, distAsk);

   int bidWallCount = 0, askWallCount = 0;
   double bidTotalLot = 0.0, askTotalLot = 0.0;
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      if(g_bookmapBidPx[i] > 0) { bidWallCount++; bidTotalLot += g_bookmapBidSz[i]; }
      if(g_bookmapAskPx[i] > 0) { askWallCount++; askTotalLot += g_bookmapAskSz[i]; }
   }
   double wallImbalance = (bidTotalLot + askTotalLot > 0) ? (bidTotalLot - askTotalLot) / MathMax(bidTotalLot, askTotalLot) : 0.0;

   //--- Location: POC/VA position + distance, plus ATR(14 on H1)/24h range.
   double pocMt5 = (g_bookmapPocPrice > 0) ? g_bookmapPocPrice + offset : 0.0;
   double valMt5 = (g_bookmapVal > 0) ? g_bookmapVal + offset : 0.0;
   double vahMt5 = (g_bookmapVah > 0) ? g_bookmapVah + offset : 0.0;
   string position = "UNKNOWN";
   if(vahMt5 > valMt5 && valMt5 > 0)
      position = (curPrice > vahMt5) ? "ABOVE_VA" : (curPrice < valMt5) ? "BELOW_VA" : "INSIDE_VA";
   double distToPoc = (pocMt5 > 0) ? (curPrice - pocMt5) : 0.0;
   double vaWidth = (vahMt5 > valMt5) ? (vahMt5 - valMt5) : 0.0;
   double distToPocPct = (vaWidth > 0) ? (MathAbs(distToPoc) / vaWidth * 100.0) : 0.0;

   double atr14 = 0.0;
   double atrBuf[1];
   if(g_hATR != INVALID_HANDLE && CopyBuffer(g_hATR, 0, 0, 1, atrBuf) > 0) atr14 = atrBuf[0];

   double hi24 = -1.0, lo24 = 999999.0;
   for(int i = 0; i < 24; i++)
   {
      double h = iHigh(_Symbol, PERIOD_H1, i);
      double l = iLow(_Symbol, PERIOD_H1, i);
      if(h > hi24) hi24 = h;
      if(l < lo24 && l > 0) lo24 = l;
   }
   double range24h = (hi24 > 0) ? (hi24 - lo24) : 0.0;

   //--- Context Summary: plain-English synthesis of everything above.
   string liquidityCtx = (nearestWallSide == "BID") ? "BID_SUPPORT" : "ASK_RESISTANCE";
   string action = "WAIT_OBSERVE";
   if(regime == "TRENDING" && htfBias != "NEUTRAL" &&
      ((htfBias == "BULLISH" && flowDominant == "BUY") || (htfBias == "BEARISH" && flowDominant == "SELL")))
      action = (htfBias == "BULLISH") ? "FAVOR_BUY" : "FAVOR_SELL";

   //--- Build delta history JSON array (oldest first).
   string deltaHistJson = "[";
   int startIdx = CVD_HIST_LEN - g_cvdSampleCount;
   for(int i = startIdx; i < CVD_HIST_LEN; i++)
   {
      double d = (i == startIdx) ? 0.0 : (g_cvdMinuteSamples[i] - g_cvdMinuteSamples[i - 1]);
      deltaHistJson += StringFormat("%.1f", d);
      if(i < CVD_HIST_LEN - 1) deltaHistJson += ",";
   }
   deltaHistJson += "]";

   string json = "{";
   json += StringFormat("\"timestamp\":%.0f,", (double)TimeGMT());
   json += StringFormat("\"online\":%s,", g_bookmapOnline ? "true" : "false");
   json += StringFormat("\"symbol\":\"%s\",", _Symbol);
   json += StringFormat("\"price\":%.2f,", curPrice);
   json += StringFormat("\"balance\":%.2f,\"equity\":%.2f,",
                         AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY));
   json += StringFormat("\"ea_version\":\"%s\",", EA_VERSION);

   json += "\"regime\":{";
   json += StringFormat("\"h4\":\"%s\",\"m30\":\"%s\",\"m5\":\"%s\",", g_masterDir, g_scalpMasterDir, g_scalpEntryDir);
   json += StringFormat("\"d1\":\"%s\",\"h1\":\"%s\",\"m15\":\"%s\",\"m1\":\"%s\",", d1Dir, h1Dir, m15Dir, m1Dir);
   json += StringFormat("\"alignment_pct\":%.1f,\"regime\":\"%s\",\"htf_bias\":\"%s\",\"m5_status\":\"%s\"",
                         alignmentPct, regime, htfBias, m5Status);
   json += "},";

   json += "\"flow\":{";
   json += StringFormat("\"cvd\":%.1f,\"delta_1m\":%.1f,\"delta_history\":%s,", g_bookmapCvd, delta1m, deltaHistJson);
   json += StringFormat("\"vol_ratio_buy_pct\":%.1f,\"pulse_pct\":%.1f,\"absorption\":\"%s\",\"flow_dominant\":\"%s\"",
                         g_bookmapVolRatioBuyPct, g_bookmapPulsePct, g_bookmapAbsorption, flowDominant);
   json += "},";

   // v36: full ladder (not just nearest) - Dadang wants a proper vertical
   // wall ladder widget (red asks above price, green bids below, like a DOM)
   // in the web dashboard, not just a single "nearest wall" line. Exports
   // every non-zero wall slot (already offset-converted to MT5/XAUUSD scale)
   // - the frontend sorts/renders them, MQL5 just serializes what it has.
   string bidLadderJson = "[", askLadderJson = "[";
   bool bidFirst = true, askFirst = true;
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      if(g_bookmapBidPx[i] > 0)
      {
         if(!bidFirst) bidLadderJson += ",";
         bidLadderJson += StringFormat("[%.2f,%.1f]", g_bookmapBidPx[i] + offset, g_bookmapBidSz[i]);
         bidFirst = false;
      }
      if(g_bookmapAskPx[i] > 0)
      {
         if(!askFirst) askLadderJson += ",";
         askLadderJson += StringFormat("[%.2f,%.1f]", g_bookmapAskPx[i] + offset, g_bookmapAskSz[i]);
         askFirst = false;
      }
   }
   bidLadderJson += "]";
   askLadderJson += "]";

   json += "\"liquidity\":{";
   json += StringFormat("\"bid_wall_price\":%.2f,\"bid_wall_size\":%.1f,\"bid_wall_ratio\":%.1f,",
                         bidWallPx, bidWallSz, bidWallSz / 10.0);
   json += StringFormat("\"ask_wall_price\":%.2f,\"ask_wall_size\":%.1f,\"ask_wall_ratio\":%.1f,",
                         askWallPx, askWallSz, askWallSz / 10.0);
   json += StringFormat("\"nearest_wall_side\":\"%s\",\"nearest_wall_distance\":%.2f,", nearestWallSide, nearestWallDist);
   json += StringFormat("\"wall_imbalance\":%.2f,\"bid_wall_count\":%d,\"ask_wall_count\":%d,",
                         wallImbalance, bidWallCount, askWallCount);
   json += StringFormat("\"bid_wall_total_lot\":%.1f,\"ask_wall_total_lot\":%.1f,", bidTotalLot, askTotalLot);
   json += "\"bid_ladder\":" + bidLadderJson + ",\"ask_ladder\":" + askLadderJson;
   json += "},";

   // v42: macro correlation passthrough - lets the Sultan web dashboard show
   // the same dollar-vs-setup readout as the chart panel, from one source.
   // v43.2: USD fundamental now comes from MT5 itself (DXY, EURUSD fallback)
   // plus the economic calendar - the Bookmap 6E fields are kept but are only
   // populated if that path is ever re-enabled.
   string goldEffectJson = (g_usdBias == "WEAK") ? "GOLD NAIK" : (g_usdBias == "STRONG") ? "GOLD TURUN" : "-";
   json += StringFormat("\"macro\":{\"active\":%s,\"direction\":\"%s\",\"usd\":\"%s\",\"cvd\":%.1f,\"flow_confirms\":%s,\"verdict\":\"%s\"},",
                         g_macroActive ? "true" : "false", g_macroDirection, g_macroUsd,
                         g_macroCvd, g_macroFlowOk ? "true" : "false", g_macroVerdict);
   json += StringFormat("\"usd\":{\"symbol\":\"%s\",\"dir\":\"%s\",\"bias\":\"%s\",\"gold_effect\":\"%s\",\"next_event\":\"%s\",\"next_mins\":%d},",
                         g_usdSymbol, g_eurDir, g_usdBias, goldEffectJson,
                         g_usdNextEvent, g_usdNextMins);

   // v44: conviction score - display only, mirrors the chart panel block.
   json += StringFormat("\"conviction\":{\"dir\":\"%s\",\"mode\":\"%s\",\"score\":%d,\"max\":%d,\"grade\":\"%s\",\"chain_done\":\"%s\",\"chain_next\":\"%s\",\"chain_pending\":\"%s\",\"flow_score\":%d,\"flow_max\":%d,\"against\":[",
                         g_convDir, g_convMode, g_convScore, g_convMax, g_convGrade,
                         g_chainDone, g_chainNext, g_chainPending, g_flowScore, g_flowMax);
   if(g_convAgainst1 != "") json += "\"" + g_convAgainst1 + "\"";
   if(g_convAgainst2 != "") json += ",\"" + g_convAgainst2 + "\"";
   if(g_convAgainst3 != "") json += ",\"" + g_convAgainst3 + "\"";
   json += "]},";

   json += "\"location\":{";
   json += StringFormat("\"poc\":%.2f,\"val\":%.2f,\"vah\":%.2f,\"current_price\":%.2f,", pocMt5, valMt5, vahMt5, curPrice);
   json += StringFormat("\"position\":\"%s\",\"distance_to_poc\":%.2f,\"distance_to_poc_pct\":%.1f,",
                         position, distToPoc, distToPocPct);
   json += StringFormat("\"range_24h\":%.2f,\"atr14\":%.2f", range24h, atr14);
   json += "},";

   json += "\"context\":{";
   json += StringFormat("\"htf_bias\":\"%s\",\"flow\":\"%s\",\"liquidity\":\"%s\",\"location\":\"%s\",\"regime\":\"%s\",\"action\":\"%s\"",
                         htfBias, flowDominant, liquidityCtx, position, regime, action);
   json += "},";

   json += "\"data_status\":{";
   json += StringFormat("\"bookmap_online\":%s,\"bridge_latency_ms\":%.0f", g_bookmapOnline ? "true" : "false", g_bookmapAgeMs);
   json += "}";
   json += "}";

   int handle = FileOpen("sultan_status.json.tmp", FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE) return;
   FileWriteString(handle, json);
   FileClose(handle);
   // atomic-ish swap - avoid the web server ever reading a half-written file
   FileDelete("sultan_status.json", FILE_COMMON);
   FileMove("sultan_status.json.tmp", FILE_COMMON, "sultan_status.json", FILE_COMMON);
}

//--- v33: VAH/VAL lines - 2 dashed lines (lighter goldenrod than the solid
//--- POC line) bracketing the 70%-of-volume value area, same offset
//--- conversion + WALL_PREFIX cleanup convention as the wall/POC lines.
void UpdateValueAreaLines()
{
   string vahName = WALL_PREFIX + "VAH", vahTxt = WALL_PREFIX + "VAH_TXT";
   string valName = WALL_PREFIX + "VAL", valTxt = WALL_PREFIX + "VAL_TXT";
   if(!g_bookmapOnline || g_bookmapVah <= 0 || g_bookmapVal <= 0 || g_bookmapVah <= g_bookmapVal)
   {
      if(ObjectFind(0, vahName) >= 0) ObjectDelete(0, vahName);
      if(ObjectFind(0, vahTxt)  >= 0) ObjectDelete(0, vahTxt);
      if(ObjectFind(0, valName) >= 0) ObjectDelete(0, valName);
      if(ObjectFind(0, valTxt)  >= 0) ObjectDelete(0, valTxt);
      return;
   }
   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   // v35: own lanes (44/48 bars), past POC's (40) and the wall staircase
   // (8-35) - VAH/VAL sit close to POC by construction, so they especially
   // needed separation to avoid stacking text on top of POC's label.
   DrawValueAreaLine(vahName, vahTxt, g_bookmapVah + offset, "VAH", 44);
   DrawValueAreaLine(valName, valTxt, g_bookmapVal + offset, "VAL", 48);
}

void DrawValueAreaLine(string name, string textName, double mt5Price, string label, int barsAhead = 8)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASHDOT);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, C'170,140,60');   // dimmer than POC's solid clrGold
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT, StringFormat("%s @ %.2f", label, mt5Price));

   datetime labelTime = TimeCurrent() + PeriodSeconds(_Period) * barsAhead;
   if(ObjectFind(0, textName) < 0)
   {
      ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, mt5Price);
      ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_LEFT);
   }
   ObjectSetInteger(0, textName, OBJPROP_TIME, labelTime);
   ObjectSetDouble(0, textName, OBJPROP_PRICE, mt5Price);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, C'220,190,120');
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 11);
   ObjectSetString(0, textName, OBJPROP_TEXT, StringFormat(" %s", label));
}

//--- v33: Iceberg markers - IcebergEngine flags a price where far more
//--- volume has TRADED than its DISPLAYED resting size would suggest (a
//--- hidden refilling order). Informational only (no entry gating yet) -
//--- drawn in magenta to stay visually distinct from walls (green/red) and
//--- POC/VA (gold).
void UpdateIcebergLines()
{
   // v35: own lanes (52/56 bars), past POC (40) and VAH/VAL (44/48).
   DrawIcebergLine("BIDICE", g_bookmapBidIcePx, g_bookmapBidIceSz, g_bookmapBidIceRatio, "BID", 52);
   DrawIcebergLine("ASKICE", g_bookmapAskIcePx, g_bookmapAskIceSz, g_bookmapAskIceRatio, "ASK", 56);
}

void DrawIcebergLine(string key, double bookmapPrice, double size, double ratio, string sideLabel, int barsAhead = 8)
{
   string name = WALL_PREFIX + key, textName = WALL_PREFIX + key + "_TXT";
   if(!g_bookmapOnline || bookmapPrice <= 0 || size <= 0)
   {
      if(ObjectFind(0, name) >= 0)     ObjectDelete(0, name);
      if(ObjectFind(0, textName) >= 0) ObjectDelete(0, textName);
      return;
   }
   double offset   = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   double mt5Price = bookmapPrice + offset;

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrMagenta);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT,
      StringFormat("ICEBERG %s @ %.2f - displayed %.0f, ratio %.1fx", sideLabel, mt5Price, size, ratio));

   datetime labelTime = TimeCurrent() + PeriodSeconds(_Period) * barsAhead;
   if(ObjectFind(0, textName) < 0)
   {
      ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, mt5Price);
      ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_LEFT);
   }
   ObjectSetInteger(0, textName, OBJPROP_TIME, labelTime);
   ObjectSetDouble(0, textName, OBJPROP_PRICE, mt5Price);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, clrMagenta);
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 12);
   ObjectSetString(0, textName, OBJPROP_TEXT, StringFormat(" ICEBERG %s (%.1fx)", sideLabel, ratio));
}

//--- M30 momentum candle. Dadang: "M30 harus close di atas high candle
//--- sebelumnya" (BUY) / "close di bawah low candle sebelumnya" (SELL) -
//--- a genuinely STRONG candle (closes past the prior bar's extreme, not
//--- just past its open/midpoint), read directly from raw M30 OHLC (not
//--- the CMP indicator - this is a separate, stricter momentum check on
//--- top of CMP direction). Naturally "waits for the next M30 candle" with
//--- no extra state needed: shift 1/2 always reference the latest CLOSED
//--- bars, so the result only changes when a new M30 bar actually closes.
bool M30MomentumOk(string dir)
{
   if(!InpUseM30Momentum) return true;
   double prevHigh  = iHigh(_Symbol, InpScalpMasterTF, 2);
   double prevLow   = iLow(_Symbol, InpScalpMasterTF, 2);
   double lastClose = iClose(_Symbol, InpScalpMasterTF, 1);
   if(dir == "BUY")  return lastClose > prevHigh;
   if(dir == "SELL") return lastClose < prevLow;
   return false;
}

//--- Exit companion to M30MomentumOk(): Dadang: "ketika tidak close di atas
//--- high untuk buy dan close di bawah low candle sebelumnya, maka kita
//--- akan TP" - if M30 fails its OWN direction's strong-close test AND
//--- closes with a strong candle the OPPOSITE way, that's a decisive
//--- reversal signal - close the position now instead of waiting for the
//--- slower M15-flip cut-loss to eventually catch up.
void CheckM30MomentumExit()
{
   if(!InpUseM30Momentum) return;
   double prevHigh  = iHigh(_Symbol, InpScalpMasterTF, 2);
   double prevLow   = iLow(_Symbol, InpScalpMasterTF, 2);
   double lastClose = iClose(_Symbol, InpScalpMasterTF, 1);
   bool   m30StrongSell = (lastClose < prevLow);
   bool   m30StrongBuy  = (lastClose > prevHigh);
   if(!m30StrongSell && !m30StrongBuy) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      if((isBuy && m30StrongSell) || (!isBuy && m30StrongBuy))
      {
         if(trade.PositionClose(tk))
            Print("M30 MOMENTUM EXIT ticket=", tk);
      }
   }
}

//--- M5-tested-M30 filter. Dadang: "M30 buy, tunggu 1 candle merah di M5,
//--- abis close-nya tunggu CMP buy M5, baru kita buy" - a genuine test
//--- means an actual RED candle right before the bar that confirms BUY,
//--- not just "CMP state was SELL a moment ago". CORRECTED 2026-08-09:
//--- first version checked CMP-state history (g_scalpEntryPrevDir ==
//--- opposite), but that's nearly a TAUTOLOGY - CMP only has 2 live states
//--- (BUY/SELL), so "was opposite before this flip" is true almost every
//--- single time by construction (verified: 0 behavior change in headless
//--- test, v8 and v9 numbers came out byte-identical). Real candle COLOR
//--- is what actually varies - checks bar[2] (the bar right before the
//--- last CLOSED bar[1], which is the one confirming the current CMP dir).
bool M5TestedM30(string dir)
{
   if(!InpUseM5TestM30) return true;
   double o = iOpen(_Symbol, InpScalpEntryTF, 2);
   double c = iClose(_Symbol, InpScalpEntryTF, 2);
   if(dir == "BUY")  return c < o;   // candle right before the confirming bar was red
   if(dir == "SELL") return c > o;   // ... was green
   return false;
}

//--- Big-TF SNR avoidance, refined 2026-08-09 per Dadang's correction: NOT a
//--- blanket block. Being near a big-TF zone is only "bahaya" (dangerous)
//--- while the zone's own rejection-confirmation TF hasn't broken out yet in
//--- our direction - once it has, that's the classic base-drop-base / rally-
//--- base-rally pattern and IS a valid entry. Pairs (Dadang, verbatim +
//--- confirmed): Weekly->H4, Daily->H1. H4's own pair is M30 - but since
//--- dir passed in here is ALWAYS g_scalpMasterDir (M30's own live CMP, see
//--- OnTick()), that confirmation is already guaranteed by construction -
//--- no separate H4 check needed, H4-zone proximity alone never blocks.
bool NearBigSNR(string dir)
{
   if(!InpAvoidBigSNR) return false;
   double px  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double pip = PipSize();
   int bufIdx = (dir == "BUY") ? 6 : 5;   // resistance ahead for BUY, support ahead for SELL

   // Weekly zone -> confirm via H4's own CMP (g_masterDir, already tracked every tick)
   if(g_hWeekly != INVALID_HANDLE)
   {
      double level = ReadLiveLevel(g_hWeekly, bufIdx);
      if(level > 0 && MathAbs(level - px) / pip <= InpBigSNR_ZonePips && g_masterDir != dir)
         return true;   // near Weekly zone, H4 hasn't confirmed rejection yet - dangerous
   }

   // Daily zone -> confirm via H1's own CMP (dedicated handle, H1 not otherwise used)
   if(g_hDaily != INVALID_HANDLE)
   {
      double level = ReadLiveLevel(g_hDaily, bufIdx);
      if(level > 0 && MathAbs(level - px) / pip <= InpBigSNR_ZonePips)
      {
         datetime tH1;
         string h1Dir = (g_hH1 != INVALID_HANDLE) ? ReadCMP(g_hH1, tH1) : "WAIT";
         if(h1Dir != dir) return true;   // near Daily zone, H1 hasn't confirmed rejection yet
      }
   }

   return false;
}

//--- H1-must-confirm-SCALP gate. Dadang 2026-08-09 verbatim: "jangan cari
//--- sell jika H4 BO buy tapi H1 masih posisi BO buy, kita cari sell ketika
//--- H1 sudah CMP sell... selama Master gw tidak berubah dia akan tetap ke
//--- arah itu" - M30 flipping alone isn't enough evidence to fight H4; H1
//--- (one level up from M30, between M30 and H4) must ALSO have flipped
//--- before hunting the counter-trend direction. Only applies when dir
//--- opposes H4 - WITH-H4 trades need no such gate (nothing to fight).
bool H1ConfirmsScalp(string dir)
{
   if(!InpRequireH1ForScalp) return true;
   if(dir == g_masterDir) return true;         // trading WITH H4 - gate not relevant
   if(g_hH1 == INVALID_HANDLE) return true;    // handle unavailable - don't block
   datetime tH1;
   string h1Dir = ReadCMP(g_hH1, tH1);
   return h1Dir == dir;
}

int CountOpenPositions(string dirFilter = "")
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(dirFilter != "")
      {
         bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
         if(dirFilter == "BUY"  && !isBuy) continue;
         if(dirFilter == "SELL" &&  isBuy) continue;
      }
      n++;
   }
   return n;
}

//--- Sums floating P/L across all open positions matching dirFilter ("BUY"
//--- or "SELL"). Used to gate layering: Dadang 2026-08-09 "dilarang entri
//--- ketika masih minus, kita tambah entri hanya pas plus" - don't ADD a new
//--- layer on top of an already-open position in the same direction while
//--- that direction is still floating negative (anti-averaging-down safety
//--- rule, on top of the wider SL from the MAE-recovery analysis). The very
//--- FIRST entry in a direction is never blocked by this - only additional
//--- layers on top of an existing floating-loss position are.
double FloatingPLForDirection(string dirFilter)
{
   double total = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      if(dirFilter == "BUY"  && !isBuy) continue;
      if(dirFilter == "SELL" &&  isBuy) continue;
      total += PositionGetDouble(POSITION_PROFIT);
   }
   return total;
}

double CalcLot(double slPips)
{
   if(!InpUseRisk) return InpLot;
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmt   = balance * InpRiskPct / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(slPips <= 0 || tickValue <= 0 || tickSize <= 0) return InpLot;

   double slDistance  = slPips * PipSize();
   double valuePerLot = (slDistance / tickSize) * tickValue;
   double lot = (valuePerLot > 0) ? riskAmt / valuePerLot : InpLot;

   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0) lot = MathFloor(lot / step) * step;
   return MathMax(minLot, MathMin(maxLot, lot));
}

bool SpreadOk()
{
   if(InpMaxSpreadPips <= 0) return true;
   double spreadPips = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / PipSize();
   return spreadPips <= InpMaxSpreadPips;
}

string OppositeDir(string d)
{
   if(d == "BUY")  return "SELL";
   if(d == "SELL") return "BUY";
   return "WAIT";
}

//--- Resets the FIRE/STOP/RESUME cascade state - called whenever H4 (top
//--- regime) flips, so a stale firing-enabled flag from the previous H4
//--- regime can never carry over. M30/M5 direction tracking picks back up
//--- fresh from WAIT on the next tick's ReadCMP() calls.
void ResetCascadeState()
{
   g_m5FiringEnabled = false;
   g_lastM30BarTime  = 0;
   g_lastM5EventTime = 0;
   g_scalpMasterDir  = "WAIT";
   g_scalpEntryDir   = "WAIT";
}

//--- Entry TF flipping AGAINST Master = cut loss immediately, don't wait
//--- for SL/trailing. Re-entry happens naturally once Entry TF realigns
//--- with Master (handled by the normal TryOpen() call in OnTick()).
void CloseAllPositions(string reason)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      if(trade.PositionClose(tk))
         Print("CUT LOSS (", reason, ") ticket=", tk);
      else
         Print("CUT LOSS FAILED ticket=", tk, ": ", trade.ResultRetcodeDescription());
   }
}

void TryOpen(string dir, string tag, bool isScalp, datetime parentFlipTime = 0, datetime childFlipTime = 0)
{
   if(InpTradeDir == DIR_BUY_ONLY  && dir == "SELL") return;
   if(InpTradeDir == DIR_SELL_ONLY && dir == "BUY")  return;
   if(!SpreadOk()) return;
   if(InpMaxOpenPos > 0 && CountOpenPositions() >= InpMaxOpenPos) return;
   if(!InpAllowMultiple && CountOpenPositions(dir) > 0) return;

   // Anti-averaging-down: don't ADD a layer on top of an already-open
   // position in this direction while it's still floating negative. The
   // first entry (no existing position yet) is never blocked here.
   if(CountOpenPositions(dir) > 0 && FloatingPLForDirection(dir) < 0.0) return;

   bool   buy    = (dir == "BUY");
   double pip    = PipSize();
   double px     = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // SL: SCALP tier ALWAYS uses a fixed, tight SL (InpScalpSL_Pips) - NEVER
   // structural M30. Root cause found 2026-08-09: a SCALP position trades
   // OPPOSITE of the direction M30 just moved in (that's the cascade
   // condition), so M30's own res/sup on that opposite side is often stale/
   // far behind (M30 was busy making the move that triggered the cascade,
   // not forming a nearby reversal pattern) - this let SCALP losses run up
   // to -578 pips before the M15-flip cut-loss ever caught up. NORMAL tier
   // trades WITH Master's direction, where M30 agreeing gives a genuinely
   // nearby, relevant structural level - keeps its structural SL (payoff
   // 1.72, proven healthy, untouched by this fix).
   double sl = 0.0;
   if(isScalp)
   {
      if(InpScalpSL_Pips > 0)
         sl = buy ? px - InpScalpSL_Pips*pip : px + InpScalpSL_Pips*pip;
   }
   else
   {
      // Structural SL: place SL at M30's own live sup (BUY) / res (SELL) -
      // Dadang: "kita coba SL di area CMP M30" - a real market structure
      // level instead of an arbitrary pip distance. Falls back to the fixed
      // InpSL_Pips backstop if that level is missing or too close (noise risk).
      if(InpUseStructuralSL && g_hScalpMaster != INVALID_HANDLE)
      {
         double structLevel = buy ? ReadLiveLevel(g_hScalpMaster, 5) : ReadLiveLevel(g_hScalpMaster, 6);
         double structDist  = buy ? (px - structLevel) : (structLevel - px);
         if(structLevel > 0 && structDist >= InpStructuralSL_MinPips * pip)
            sl = structLevel;
      }
      if(sl == 0.0 && InpSL_Pips > 0)
         sl = buy ? px - InpSL_Pips*pip : px + InpSL_Pips*pip;
   }

   double tpPips = isScalp ? InpScalpTP_Pips : InpTP_Pips;   // SCALP gets its own short TP (see input group above)
   double tp     = (tpPips > 0) ? (buy ? px + tpPips*pip : px - tpPips*pip) : 0.0;
   double fallbackPips = isScalp ? InpScalpSL_Pips : InpSL_Pips;
   double slPipsActual = (sl > 0) ? MathAbs(px - sl) / pip : fallbackPips;
   double lot    = CalcLot(slPipsActual);

   // v23 Bookmap Absorption warning (live only - g_bookmapOnline is always
   // false during backtests, so this never changes backtest behavior).
   // "BUYER_ABSORBED" = buyers getting soaked up, bearish warning for a BUY.
   // "SELLER_ABSORBED" = sellers getting soaked up, bearish... i.e. bullish
   // warning against a SELL. Reduce lot, don't block - matches the exact
   // pattern already established in bookmap-bridge's own AbsorptionEngine.
   string absorbNote = "";
   if(InpUseBookmapAbsorptionWarning && g_bookmapOnline)
   {
      bool opposesEntry = (buy && g_bookmapAbsorption == "BUYER_ABSORBED") ||
                          (!buy && g_bookmapAbsorption == "SELLER_ABSORBED");
      if(opposesEntry)
      {
         double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         double reduced = lot * InpBookmapAbsorptionLotFactor;
         if(step > 0) reduced = MathFloor(reduced / step) * step;
         lot = MathMax(minLot, reduced);
         absorbNote = StringFormat(" | BOOKMAP WARNING: %s lawan arah, lot dikecilin ke %.2f", g_bookmapAbsorption, lot);
      }
   }

   // v30 POC overextension warning (live only) - Dadang: "garis poc" + wire
   // it into entry sizing. POC = harga dengan volume trade terbanyak sesi
   // ini (value area magnet) - kalau harga udah lari jauh dari POC SEARAH
   // entry yang mau dibuka, itu tanda entry telat/overextended (risiko balik
   // ke value area lebih besar). Warning + kecilin lot, BUKAN block - sama
   // pola persis kayak Absorption di atas, stackable (bisa kena dua-duanya).
   string pocNote = "";
   if(InpUsePocOverextendWarning && g_bookmapOnline && g_bookmapPocPrice > 0 && g_bookmapPrice > 0)
   {
      double pocMt5Price = g_bookmapPocPrice + (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice);
      double distFromPoc = buy ? (px - pocMt5Price) : (pocMt5Price - px);
      if(distFromPoc >= InpPocOverextendUsd)
      {
         double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         double reduced = lot * InpPocOverextendLotFactor;
         if(step > 0) reduced = MathFloor(reduced / step) * step;
         lot = MathMax(minLot, reduced);
         pocNote = StringFormat(" | POC WARNING: harga %.1f USD dari POC %.2f (overextended), lot dikecilin ke %.2f",
                                 distFromPoc, pocMt5Price, lot);
      }

      // v32 POC alignment warning - Dadang: "kalo harga di atas POC kita
      // gimana, kalo di bawah gimana" -> di atas POC = POC jadi support,
      // bias BUY; di bawah POC = POC jadi resistance, bias SELL. Kalau BUY
      // dibuka SEBELUM harga reclaim POC (masih di bawah) atau SELL dibuka
      // sebelum harga lepas POC (masih di atas), value area belum dukung -
      // "belum solid". Beda dari overextend (soal JARAK) - ini soal SISI,
      // berapapun jauhnya. Stackable sama 2 warning di atas.
      if(InpUsePocAlignWarning)
      {
         bool wrongSide = buy ? (px < pocMt5Price) : (px > pocMt5Price);
         if(wrongSide)
         {
            double minLot2 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
            double step2   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
            double reduced2 = lot * InpPocAlignLotFactor;
            if(step2 > 0) reduced2 = MathFloor(reduced2 / step2) * step2;
            lot = MathMax(minLot2, reduced2);
            pocNote += StringFormat(" | POC ALIGN WARNING: %s tapi harga masih %s POC %.2f (belum reclaim), lot dikecilin ke %.2f",
                                     dir, buy ? "DI BAWAH" : "DI ATAS", pocMt5Price, lot);
         }
      }
   }

   string comment = "DD-CR " + tag;
   // Time Law audit trail - Dadang: "lihat TV gw, CMP Master BO buy jam
   // 10:00, kita entri kalau M5 CMP buy terjadi di ATAS jam 10:00" - print
   // both timestamps side by side on every real entry so this can be
   // eyeballed directly against the TradingView reference chart.
   string timeLawNote = (parentFlipTime > 0 && childFlipTime > 0)
      ? StringFormat(" | Parent BO=%s Child BO=%s (child %s parent)",
                      TimeToString(parentFlipTime, TIME_DATE|TIME_MINUTES),
                      TimeToString(childFlipTime, TIME_DATE|TIME_MINUTES),
                      (childFlipTime > parentFlipTime) ? "AFTER" : "!! NOT AFTER !!")
      : "";
   if(trade.PositionOpen(_Symbol, buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, lot, px, sl, tp, comment))
      Print("ENTRY (", tag, ") ", dir, " lot=", lot, " @ ", px, " SL=", sl, " TP=", tp, timeLawNote, absorbNote, pocNote);
   else
      Print("ENTRY FAILED (", tag, ") ", dir, ": ", trade.ResultRetcodeDescription());
}

//--- Barrier-BE: uses Scalp Master TF's (M30 by default) own LIVE res/sup -
//--- NOT H4/Master. Dadang: "barriernya kasih M30 aja minimal biar gak
//--- terlalu mepet." Reason H4 alone was too aggressive: H4 forms new V/A
//--- shapes rarely, so its live res/sup often sits STALE - already broken
//--- by price long ago but not yet replaced by a fresh one (a new A-shape
//--- needs a fresh local top+reversal, which H4 rarely produces) - meaning
//--- the "touched barrier" check could stay permanently true right after
//--- entry, firing BE almost instantly. M30 refreshes far more often, so
//--- its level stays a genuine, still-ahead-of-price zone most of the time.
//--- Old local highs/lows price hasn't retested yet = "area pantul" (bounce
//--- zone). Dadang: "setiap sampai barrier pertama sebaiknya langsung set
//--- BE karena itu area pantul balik ke area BO TF entri; kalo TF entri
//--- tidak flip biasanya barrier akan jebol [dan lanjut untung]." So this
//--- doesn't cut the position - it just secures it at breakeven BEFORE a
//--- potential rejection, so if Entry TF later flips (triggering the
//--- normal cut-loss elsewhere), the "loss" is already risk-free. If Entry
//--- TF holds through the barrier instead, the position rides the eventual
//--- breakout with no downside taken. Direction-agnostic: BUY checks live
//--- res ahead, SELL checks live sup ahead - works for NORMAL and SCALP
//--- tier positions alike (barrier is relative to the position's own
//--- direction, not which tier opened it). Falls back to Master (H4) only
//--- if the Scalp tier isn't enabled (no M30 handle available).
void CheckBarrierBE()
{
   if(!InpUseBarrierBE) return;
   int barrierHandle = (g_hScalpMaster != INVALID_HANDLE) ? g_hScalpMaster : g_hMaster;
   if(barrierHandle == INVALID_HANDLE) return;
   double pip = PipSize();
   double liveRes = ReadLiveLevel(barrierHandle, 6);
   double liveSup = ReadLiveLevel(barrierHandle, 5);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      bool   isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double op    = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSL = PositionGetDouble(POSITION_SL);
      double curTP = PositionGetDouble(POSITION_TP);
      double curPx = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double profitPips = isBuy ? (curPx - op) / pip : (op - curPx) / pip;

      // Don't let barrier-BE fire the instant a position opens just because
      // it happened to be entered near an existing barrier - give the trade
      // some room first (Dadang: "terlalu cepat geser BE, gak sehat").
      if(profitPips < InpBarrierBE_MinProfitPips) continue;

      bool touchedBarrier = isBuy
         ? (liveRes > 0 && curPx >= liveRes)
         : (liveSup > 0 && curPx <= liveSup);
      if(!touchedBarrier) continue;

      double beSL = isBuy ? op + InpBarrierBE_LockPips*pip : op - InpBarrierBE_LockPips*pip;
      bool notYetAtBE = isBuy ? (curSL < op || curSL == 0) : (curSL > op || curSL == 0);
      if(notYetAtBE)
      {
         if(trade.PositionModify(tk, beSL, curTP))
            Print("BARRIER BE ticket=", tk, " SL->", beSL);
      }
   }
}

//--- SCALP-tagged positions (comment contains "SCALP") get their own,
//--- tighter BE/trailing config - see doctrine note at input declarations:
//--- data showed SCALP wins avg ~47pip but losses avg ~68pip (bad payoff),
//--- so it needs to lock gains/cut losses faster than the NORMAL tier.
void ManageTrailingAndBE()
{
   double pip = PipSize();

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      bool   isBuy  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      bool   isScalp = (StringFind(PositionGetString(POSITION_COMMENT), "SCALP") >= 0);
      double op     = PositionGetDouble(POSITION_PRICE_OPEN);
      double curPx  = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double profitPips = isBuy ? (curPx - op) / pip : (op - curPx) / pip;
      double curSL  = PositionGetDouble(POSITION_SL);
      double curTP  = PositionGetDouble(POSITION_TP);
      double newSL  = curSL;

      bool   useBE      = isScalp ? InpScalpUseBreakEven   : InpUseBreakEven;
      double beTrigger   = isScalp ? InpScalpBE_TriggerPips : InpBE_TriggerPips;
      double beLock      = isScalp ? InpScalpBE_LockPips    : InpBE_LockPips;
      bool   useTrail    = isScalp ? InpScalpUseTrailing    : InpUseTrailing;
      double trailStart  = isScalp ? InpScalpTrailStartPips : InpTrailStartPips;
      double trailStep   = isScalp ? InpScalpTrailStepPips  : InpTrailStepPips;

      if(!useBE && !useTrail) continue;

      if(useBE && profitPips >= beTrigger)
      {
         double beSL = isBuy ? op + beLock*pip : op - beLock*pip;
         bool notYetAtBE = isBuy ? (curSL < op || curSL == 0) : (curSL > op || curSL == 0);
         if(notYetAtBE) newSL = beSL;
      }
      if(useTrail && profitPips >= trailStart)
      {
         double trailSL = isBuy ? curPx - trailStep*pip : curPx + trailStep*pip;
         if(isBuy  && (trailSL > newSL || newSL == 0)) newSL = trailSL;
         if(!isBuy && (trailSL < newSL || newSL == 0)) newSL = trailSL;
      }
      if(newSL != curSL && newSL != 0)
         trade.PositionModify(tk, newSL, curTP);
   }
}

//--- exports one row per CLOSED position (entry+exit deal paired via
//--- DEAL_POSITION_ID) to Common\Files\ so it survives outside the
//--- tester's isolated sandbox and can be read/analyzed externally.
void ExportTradeHistory()
{
   if(!HistorySelect(0, TimeCurrent())) return;
   int total = HistoryDealsTotal();
   if(total <= 0) return;

   ulong posIds[];
   for(int i = 0; i < total; i++)
   {
      ulong dt = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(dt, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(dt, DEAL_SYMBOL) != _Symbol) continue;
      ulong pid = HistoryDealGetInteger(dt, DEAL_POSITION_ID);
      bool found = false;
      for(int j = 0; j < ArraySize(posIds); j++) if(posIds[j] == pid) { found = true; break; }
      if(!found) { ArrayResize(posIds, ArraySize(posIds) + 1); posIds[ArraySize(posIds) - 1] = pid; }
   }
   if(ArraySize(posIds) == 0) return;

   int handle = FileOpen("DD_CR_MultiTF_Report.csv", FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) { Print("Export CSV FAILED: ", GetLastError()); return; }
   FileWrite(handle, "position_id", "open_time", "close_time", "direction", "volume",
             "entry_price", "exit_price", "profit", "pips", "duration_min", "tier_tag");

   double pip = PipSize();
   int exported = 0;
   for(int p = 0; p < ArraySize(posIds); p++)
   {
      ulong pid = posIds[p];
      datetime openTime = 0, closeTime = 0;
      double entryPrice = 0, exitPrice = 0, profit = 0, volume = 0;
      string direction = "", tierTag = "";
      bool haveIn = false, haveOut = false;

      for(int i = 0; i < total; i++)
      {
         ulong dt = HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(dt, DEAL_POSITION_ID) != pid) continue;
         long entryFlag = HistoryDealGetInteger(dt, DEAL_ENTRY);
         if(entryFlag == DEAL_ENTRY_IN)
         {
            openTime   = (datetime)HistoryDealGetInteger(dt, DEAL_TIME);
            entryPrice = HistoryDealGetDouble(dt, DEAL_PRICE);
            volume     = HistoryDealGetDouble(dt, DEAL_VOLUME);
            direction  = (HistoryDealGetInteger(dt, DEAL_TYPE) == DEAL_TYPE_BUY) ? "BUY" : "SELL";
            tierTag    = HistoryDealGetString(dt, DEAL_COMMENT);   // "DD-CR H4>M15" or "DD-CR SCALP M30>M5"
            haveIn = true;
         }
         else if(entryFlag == DEAL_ENTRY_OUT || entryFlag == DEAL_ENTRY_OUT_BY)
         {
            closeTime  = (datetime)HistoryDealGetInteger(dt, DEAL_TIME);
            exitPrice  = HistoryDealGetDouble(dt, DEAL_PRICE);
            profit    += HistoryDealGetDouble(dt, DEAL_PROFIT) + HistoryDealGetDouble(dt, DEAL_SWAP) + HistoryDealGetDouble(dt, DEAL_COMMISSION);
            haveOut = true;
         }
      }
      if(!haveIn || !haveOut) continue;   // still open at end of test - skip

      double pips  = (direction == "BUY") ? (exitPrice - entryPrice) / pip : (entryPrice - exitPrice) / pip;
      int    durMn = (int)((closeTime - openTime) / 60);

      FileWrite(handle, (long)pid, TimeToString(openTime, TIME_DATE | TIME_MINUTES),
                TimeToString(closeTime, TIME_DATE | TIME_MINUTES), direction,
                DoubleToString(volume, 2), DoubleToString(entryPrice, 2), DoubleToString(exitPrice, 2),
                DoubleToString(profit, 2), DoubleToString(pips, 1), durMn, tierTag);
      exported++;
   }
   FileClose(handle);
   Print("Trade history exported: ", exported, " closed positions -> Common\\Files\\DD_CR_MultiTF_Report.csv");
}

double OnTester()
{
   ExportTradeHistory();
   return AccountInfoDouble(ACCOUNT_PROFIT);
}

void OnTick()
{
   ManageTrailingAndBE();
   CheckBarrierBE();
   CheckM30MomentumExit();
   ReadBookmapBridge();
   ReadMacroCorrelation();
   ReadUsdFundamental();
   ComputeConviction();   // display only - must run after all sources above are refreshed
   UpdatePanel();   // every tick - floating P/L, balance/equity, stats stay live
   WriteSultanStatus();   // v34 - throttled internally to ~1/sec

   // --- H4 (top regime) - polled every tick, cheap. A flip is a full reset:
   // close everything, wipe the M30/M5 cascade state, start fresh.
   datetime mChangeTime;
   string masterDir = ReadCMP(g_hMaster, mChangeTime);
   if(masterDir != g_masterDir)
   {
      if(masterDir != "WAIT" && g_masterDir != "WAIT")
         CloseAllPositions(StringFormat("H4 %s flip -> %s (regime reset)", g_masterDir, masterDir));
      g_masterDir = masterDir;
      g_masterChangeTime = mChangeTime;
      ResetCascadeState();
      Print("H4 FLIP -> ", g_masterDir, " @ ", TimeToString(mChangeTime));
   }
   if(g_masterDir == "WAIT") return;   // no H4 bias yet - don't trade

   // --- M30: the direction ACTUALLY traded (independent of whether it
   // currently agrees with H4 - see header doctrine comment). A genuine M30
   // CMP flip is the only real reversal trigger: cut any position trading
   // the old direction, require a fresh confirm before firing the new one.
   datetime m30ChangeTime;
   string m30Dir = ReadCMP(g_hScalpMaster, m30ChangeTime);
   if(m30Dir != "WAIT" && m30Dir != g_scalpMasterDir)
   {
      if(g_scalpMasterDir != "WAIT")
         CloseAllPositions(StringFormat("M30 flip %s -> %s (arah baru)", g_scalpMasterDir, m30Dir));
      g_m5FiringEnabled = false;
      Print("M30 FLIP -> ", m30Dir, " @ ", TimeToString(m30ChangeTime));
   }
   g_scalpMasterDir        = m30Dir;
   g_scalpMasterChangeTime = m30ChangeTime;
   if(g_scalpMasterDir == "WAIT") return;

   // v22 SIMPLIFICATION - Dadang 2026-08-10: "H4 BO buy close, tunggu M30 BO
   // buy close, M5 BO buy baru buy" + "VR CF ini hanya status, CMP buat TF
   // dia sendiri, lo harus tentukan mau trading di TF berapa." Drops the
   // counter-trend SCALP path entirely (v14-v21 all traded M30's direction
   // even when it opposed H4) - now M30 must ALSO equal H4, strict 3-way
   // alignment (H4=M30=M5), M5 chosen as the single entry TF. No more
   // "isScalp" tier - every entry is WITH H4.
   if(g_scalpMasterDir != g_masterDir) return;   // M30 belum align sama H4 - jangan trading dulu

   datetime m5ChangeTime;
   g_scalpEntryDir = ReadCMP(g_hScalpEntry, m5ChangeTime);

   // --- STOP: M5's own CMP flips against M30's current direction -> pause
   // new entries (Dadang: "kita stop ketika M5 flip"). Existing positions
   // are left alone here - SL/TP/BE/M30-momentum-exit above handle those.
   if(g_scalpEntryDir == OppositeDir(g_scalpMasterDir))
      g_m5FiringEnabled = false;

   // --- RESUME: checked ONLY at the open of a fresh M30 bar (Dadang:
   // "ketika open M30 dan BO searah master, M30 gas lagi lah entri"). If
   // M30 is still the same direction (didn't flip away) and M5 already
   // confirms that direction again, firing resumes.
   datetime m30BarTime = iTime(_Symbol, InpScalpMasterTF, 0);
   if(m30BarTime != g_lastM30BarTime)
   {
      g_lastM30BarTime = m30BarTime;
      if(g_scalpEntryDir == g_scalpMasterDir)
         g_m5FiringEnabled = true;
   }

   if(!g_m5FiringEnabled) return;
   if(g_scalpEntryDir != g_scalpMasterDir) return;   // paranoia - only ever fire while aligned

   // --- FIRE: every fresh M5 breakout EVENT searah M30 (buffer 7 - repeats
   // on EACH individual break past the latest pullback, not just the first
   // one). "kita entri sell setiap ada BO sell" - one entry per event, no
   // separate bar-gate needed since the event timestamp itself only changes
   // when a genuinely new break happens.
   datetime m5EventTime = ReadBreakoutEventTime(g_hScalpEntry);
   if(m5EventTime <= g_lastM5EventTime) return;
   g_lastM5EventTime = m5EventTime;   // consume this event now, pass/fail on filters below either way

   if(m5EventTime <= g_scalpMasterChangeTime) return;         // TIME LAW: after M30's own regime began
   if(!M1Ok(g_scalpMasterDir, m5EventTime))                return;
   if(!ADXOk(g_hADX_ScalpEntry))                            return;
   if(!RSIOk(g_hRSI_ScalpEntry, g_scalpMasterDir))          return;
   if(!M30MomentumOk(g_scalpMasterDir))                     return;
   if(!M5TestedM30(g_scalpMasterDir))                       return;
   if(NearBigSNR(g_scalpMasterDir))                         return;   // deket zone SNR W1/D1/H4 - "pasti balik arah"
   if(!H1ConfirmsScalp(g_scalpMasterDir))                   return;   // lawan H4 butuh H1 ikut confirm dulu
   if(!InpAllowScalpEntries)                                return;   // safety valve

   // isScalp (counter-trend vs H4) only picks which SL/TP/BE tier + tag is
   // used - the firing mechanism above is identical either way.
   bool isScalp = (g_scalpMasterDir != g_masterDir);
   string tag = isScalp
      ? StringFormat("SCALP %s>%s", EnumToString(InpScalpMasterTF), EnumToString(InpScalpEntryTF))
      : StringFormat("%s>%s>%s", EnumToString(InpMasterTF), EnumToString(InpScalpMasterTF), EnumToString(InpScalpEntryTF));
   TryOpen(g_scalpMasterDir, tag, isScalp, g_scalpMasterChangeTime, m5EventTime);
}
