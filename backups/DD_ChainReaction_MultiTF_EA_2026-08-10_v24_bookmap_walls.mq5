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
CTrade trade;

// Version tag - bump this MANUALLY every time the code changes, shown on
// panel + startup Print so Dadang can visually confirm a freshly compiled
// .ex5 actually loaded (vs a stale cached one MT5 didn't reload properly).
// Simple v1/v2/v3... - easier to eyeball than a compile timestamp.
#define EA_VERSION "v24"

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

input group "=== PANEL ==="
input bool                 InpShowPanel    = true;           // Tampilkan dashboard di chart
input string                InpPanelName    = "SULTAN SNIPER ENGINE"; // Judul panel
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
double   g_bookmapBid1Px = 0, g_bookmapBid1Sz = 0, g_bookmapBid2Px = 0, g_bookmapBid2Sz = 0;
double   g_bookmapAsk1Px = 0, g_bookmapAsk1Sz = 0, g_bookmapAsk2Px = 0, g_bookmapAsk2Sz = 0;

#define DASH_PREFIX "DD_DASH_"
#define WALL_PREFIX "DD_WALL_"

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

   if(InpShowPanel) CreatePanel();
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
   ObjectsDeleteAll(0, DASH_PREFIX);
   ObjectsDeleteAll(0, WALL_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| On-chart live panel - built from real EA state, no placeholders. |
//+------------------------------------------------------------------+
color DirColor(string d) { return (d == "BUY") ? clrLime : (d == "SELL" ? clrTomato : clrSilver); }

void PanelLabel(string key, int x, int y, int size, color clr, string font = "Consolas")
{
   string name = DASH_PREFIX + key;
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, size);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetString(0, name, OBJPROP_FONT, font);
}

void CreatePanel()
{
   int px = 12, py = 18, w = 250, h = 322;
   string bg = DASH_PREFIX + "BG";
   ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, bg, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, px - 8);
   ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, py - 10);
   ObjectSetInteger(0, bg, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, bg, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, bg, OBJPROP_BGCOLOR, C'12,14,20');
   ObjectSetInteger(0, bg, OBJPROP_COLOR, clrGoldenrod);
   ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, bg, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, bg, OBJPROP_BACK, false);
   ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, bg, OBJPROP_HIDDEN, true);

   string goldbar = DASH_PREFIX + "TOPBAR";
   ObjectCreate(0, goldbar, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, goldbar, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, goldbar, OBJPROP_XDISTANCE, px - 8);
   ObjectSetInteger(0, goldbar, OBJPROP_YDISTANCE, py - 10);
   ObjectSetInteger(0, goldbar, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, goldbar, OBJPROP_YSIZE, 4);
   ObjectSetInteger(0, goldbar, OBJPROP_BGCOLOR, clrGoldenrod);
   ObjectSetInteger(0, goldbar, OBJPROP_COLOR, clrGoldenrod);
   ObjectSetInteger(0, goldbar, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, goldbar, OBJPROP_BACK, false);
   ObjectSetInteger(0, goldbar, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, goldbar, OBJPROP_HIDDEN, true);

   int y = py;
   PanelLabel("TITLE",  px, y, 11, clrGoldenrod); y += 18;
   PanelLabel("OWNER",  px, y, 8,  clrSilver);     y += 16;
   PanelLabel("BUILD",  px, y, 8,  clrAqua);       y += 20;
   PanelLabel("MODE",   px, y, 10, clrYellow);     y += 18;
   PanelLabel("PAIR",   px, y, 9,  clrWhite);      y += 18;
   PanelLabel("MASTER", px, y, 9,  clrSilver);     y += 16;
   PanelLabel("ENTRY",  px, y, 9,  clrSilver);     y += 18;
   PanelLabel("SCALPM", px, y, 9,  clrSilver);     y += 16;
   PanelLabel("SCALPE", px, y, 9,  clrSilver);     y += 20;
   PanelLabel("POS",    px, y, 9,  clrWhite);      y += 18;
   PanelLabel("TRADES", px, y, 9,  clrWhite);      y += 16;
   PanelLabel("WINRATE",px, y, 9,  clrWhite);      y += 16;
   PanelLabel("PROFIT", px, y, 9,  clrWhite);      y += 18;
   PanelLabel("EQUITY", px, y, 9,  clrWhite);      y += 20;
   PanelLabel("BMHDR",  px, y, 8,  clrGoldenrod);  y += 16;
   PanelLabel("BMCVD",  px, y, 9,  clrSilver);     y += 16;
   PanelLabel("BMPULSE",px, y, 9,  clrSilver);

   ObjectSetString(0, DASH_PREFIX + "TITLE", OBJPROP_TEXT, InpPanelName + "  [" + EA_VERSION + "]");
   ObjectSetString(0, DASH_PREFIX + "OWNER", OBJPROP_TEXT, InpOwnerName);
   ObjectSetString(0, DASH_PREFIX + "BUILD", OBJPROP_TEXT, "Version: " + EA_VERSION);
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
   RecalcStatsIfNeeded();

   double floatingPL = 0.0;
   int openCount = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      floatingPL += PositionGetDouble(POSITION_PROFIT);
      openCount++;
   }

   double winRate = (g_statTrades > 0) ? (100.0 * g_statWins / g_statTrades) : 0.0;

   bool withH4 = (g_scalpMasterDir == g_masterDir);
   ObjectSetString(0, DASH_PREFIX + "MODE", OBJPROP_TEXT,
                    g_scalpMasterDir == "WAIT" ? "Mode: WAIT" : (withH4 ? "Mode: WITH H4" : "*** MODE: AGAINST H4 ***"));
   ObjectSetInteger(0, DASH_PREFIX + "MODE", OBJPROP_COLOR, withH4 ? clrYellow : clrOrange);

   ObjectSetString(0, DASH_PREFIX + "PAIR", OBJPROP_TEXT,
                    StringFormat("%s > %s > %s", EnumToString(InpMasterTF), EnumToString(InpScalpMasterTF), EnumToString(InpScalpEntryTF)));

   ObjectSetString(0, DASH_PREFIX + "MASTER", OBJPROP_TEXT, "H4:  " + g_masterDir);
   ObjectSetInteger(0, DASH_PREFIX + "MASTER", OBJPROP_COLOR, DirColor(g_masterDir));

   ObjectSetString(0, DASH_PREFIX + "ENTRY", OBJPROP_TEXT, "Firing: " + (g_m5FiringEnabled ? "ON" : "PAUSED"));
   ObjectSetInteger(0, DASH_PREFIX + "ENTRY", OBJPROP_COLOR, g_m5FiringEnabled ? clrLime : clrGray);

   ObjectSetString(0, DASH_PREFIX + "SCALPM", OBJPROP_TEXT,
                    StringFormat("M30 (%s): %s", EnumToString(InpScalpMasterTF), g_scalpMasterDir));
   ObjectSetInteger(0, DASH_PREFIX + "SCALPM", OBJPROP_COLOR, DirColor(g_scalpMasterDir));

   ObjectSetString(0, DASH_PREFIX + "SCALPE", OBJPROP_TEXT,
                    StringFormat("M5 (%s): %s", EnumToString(InpScalpEntryTF), g_scalpEntryDir));
   ObjectSetInteger(0, DASH_PREFIX + "SCALPE", OBJPROP_COLOR, DirColor(g_scalpEntryDir));

   ObjectSetString(0, DASH_PREFIX + "POS", OBJPROP_TEXT,
                    StringFormat("Open: %d   Float P/L: %.2f", openCount, floatingPL));
   ObjectSetInteger(0, DASH_PREFIX + "POS", OBJPROP_COLOR, (floatingPL >= 0) ? clrLime : clrTomato);

   ObjectSetString(0, DASH_PREFIX + "TRADES", OBJPROP_TEXT,
                    StringFormat("Closed: %d  (W:%d / L:%d)", g_statTrades, g_statWins, g_statLosses));

   ObjectSetString(0, DASH_PREFIX + "WINRATE", OBJPROP_TEXT, StringFormat("Win Rate: %.1f%%", winRate));
   ObjectSetInteger(0, DASH_PREFIX + "WINRATE", OBJPROP_COLOR, (winRate >= 50.0) ? clrLime : clrOrange);

   ObjectSetString(0, DASH_PREFIX + "PROFIT", OBJPROP_TEXT, StringFormat("Total Profit: %.2f", g_statTotalProfit));
   ObjectSetInteger(0, DASH_PREFIX + "PROFIT", OBJPROP_COLOR, (g_statTotalProfit >= 0) ? clrLime : clrTomato);

   ObjectSetString(0, DASH_PREFIX + "EQUITY", OBJPROP_TEXT,
                    StringFormat("Bal: %.2f   Eq: %.2f", AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY)));

   if(InpShowBookmapPanel)
   {
      if(g_bookmapOnline)
      {
         ObjectSetString(0, DASH_PREFIX + "BMHDR", OBJPROP_TEXT, "-- BOOKMAP (live) --");
         ObjectSetInteger(0, DASH_PREFIX + "BMHDR", OBJPROP_COLOR, clrGoldenrod);

         ObjectSetString(0, DASH_PREFIX + "BMCVD", OBJPROP_TEXT, StringFormat("CVD: %+.1f", g_bookmapCvd));
         ObjectSetInteger(0, DASH_PREFIX + "BMCVD", OBJPROP_COLOR, (g_bookmapCvd >= 0) ? clrLime : clrTomato);

         color pulseClr = clrSilver;
         if(g_bookmapAbsorption != "NONE") pulseClr = clrOrange;
         ObjectSetString(0, DASH_PREFIX + "BMPULSE", OBJPROP_TEXT,
                          StringFormat("Pulse: %.1f%%  Absorb: %s", g_bookmapPulsePct, g_bookmapAbsorption));
         ObjectSetInteger(0, DASH_PREFIX + "BMPULSE", OBJPROP_COLOR, pulseClr);
      }
      else
      {
         ObjectSetString(0, DASH_PREFIX + "BMHDR", OBJPROP_TEXT, "-- BOOKMAP: OFFLINE --");
         ObjectSetInteger(0, DASH_PREFIX + "BMHDR", OBJPROP_COLOR, clrGray);
         ObjectSetString(0, DASH_PREFIX + "BMCVD", OBJPROP_TEXT, "(gak jalan / backtest)");
         ObjectSetInteger(0, DASH_PREFIX + "BMCVD", OBJPROP_COLOR, clrGray);
         ObjectSetString(0, DASH_PREFIX + "BMPULSE", OBJPROP_TEXT, "");
      }
   }

   ChartRedraw(0);
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
//--- MT5/Python instance is running. LIVE ONLY - during Strategy Tester
//--- backtests the file's real wall-clock timestamp will never match the
//--- simulated historical time, so this naturally (and correctly) reports
//--- OFFLINE/stale the whole backtest - that's expected, not a bug.
//--- Informational only for now, does not gate any entry/exit decision.
void ReadBookmapBridge()
{
   g_bookmapOnline = false;
   if(!InpShowBookmapPanel)
   {
      ObjectsDeleteAll(0, WALL_PREFIX);
      return;
   }

   int handle = FileOpen("bookmap_live_signal.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) { ObjectsDeleteAll(0, WALL_PREFIX); return; }   // bridge never ran, or udp_listener.py isn't up

   for(int i = 0; i < 13 && !FileIsEnding(handle); i++) FileReadString(handle);   // skip header row (13 fields, v24)
   if(FileIsEnding(handle)) { FileClose(handle); ObjectsDeleteAll(0, WALL_PREFIX); return; }

   double ts    = StringToDouble(FileReadString(handle));
   double price = StringToDouble(FileReadString(handle));   // Bookmap's OWN instrument price (GCZ6, not XAUUSD)
   double cvd     = StringToDouble(FileReadString(handle));
   double pulse   = StringToDouble(FileReadString(handle));
   string absorb  = FileReadString(handle);
   double bid1Px = StringToDouble(FileReadString(handle)), bid1Sz = StringToDouble(FileReadString(handle));
   double bid2Px = StringToDouble(FileReadString(handle)), bid2Sz = StringToDouble(FileReadString(handle));
   double ask1Px = StringToDouble(FileReadString(handle)), ask1Sz = StringToDouble(FileReadString(handle));
   double ask2Px = StringToDouble(FileReadString(handle)), ask2Sz = StringToDouble(FileReadString(handle));
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

   g_bookmapOnline     = true;
   g_bookmapPrice      = price;
   g_bookmapCvd        = cvd;
   g_bookmapPulsePct   = pulse;
   g_bookmapAbsorption = absorb;
   g_bookmapBid1Px = bid1Px; g_bookmapBid1Sz = bid1Sz;
   g_bookmapBid2Px = bid2Px; g_bookmapBid2Sz = bid2Sz;
   g_bookmapAsk1Px = ask1Px; g_bookmapAsk1Sz = ask1Sz;
   g_bookmapAsk2Px = ask2Px; g_bookmapAsk2Sz = ask2Sz;
   UpdateWallLines();
}

//--- Draws (or updates) one Bookmap wall as a horizontal line on the MT5
//--- chart. bookmapPrice comes straight from Bookmap's own instrument (e.g.
//--- GCZ6 futures) - offset converts it to XAUUSD-equivalent. Deletes the
//--- object if this wall slot is empty (price<=0, sent that way by the
//--- Python side when fewer than 2 walls exist on that side).
void DrawWallLine(string key, double bookmapPrice, double size, double offset, color clr, string sideLabel)
{
   string name = WALL_PREFIX + key;
   if(bookmapPrice <= 0 || size <= 0)
   {
      if(ObjectFind(0, name) >= 0) ObjectDelete(0, name);
      return;
   }
   double mt5Price = bookmapPrice + offset;
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT,
      StringFormat("%s %.0f lot @ %.2f (bookmap %.2f)", sideLabel, size, mt5Price, bookmapPrice));
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

   DrawWallLine("BID1", g_bookmapBid1Px, g_bookmapBid1Sz, offset, clrLime,     "BID WALL 1");
   DrawWallLine("BID2", g_bookmapBid2Px, g_bookmapBid2Sz, offset, C'0,140,0',  "BID WALL 2");
   DrawWallLine("ASK1", g_bookmapAsk1Px, g_bookmapAsk1Sz, offset, clrRed,      "ASK WALL 1");
   DrawWallLine("ASK2", g_bookmapAsk2Px, g_bookmapAsk2Sz, offset, C'150,0,0',  "ASK WALL 2");
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
      Print("ENTRY (", tag, ") ", dir, " lot=", lot, " @ ", px, " SL=", sl, " TP=", tp, timeLawNote, absorbNote);
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
   UpdatePanel();   // every tick - floating P/L, balance/equity, stats stay live

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
