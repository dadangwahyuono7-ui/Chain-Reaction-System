//+------------------------------------------------------------------+
//| DD_ChainReaction_MultiTF_EA.mq5                                  |
//| Reads CMP from DD_CMP_Indicator.mq5 - EA itself NEVER computes    |
//| CMP (per Dadang's TASK ORDER: "EA tidak menghitung CMP. EA hanya |
//| membaca status CMP yang dihasilkan indikator MT5.")               |
//|                                                                   |
//| DOCTRINE (simple 2-TF Master/Entry pair, deliberately NOT the     |
//| v6.2/v7 Pine's VR->CF cascade - Dadang: "cara entri yang baru ini |
//| udah beda dengan cara kita sebelum2 nya"):                        |
//|   - Master TF sets the trading BIAS. EA only ever opens in the   |
//|     Master's current CMP direction.                               |
//|   - Entry TF triggers the actual open: whenever Entry TF's CMP    |
//|     matches Master's direction, open. When Entry TF flips AGAINST |
//|     Master, just STOP opening new positions (existing ones are    |
//|     managed by SL/TP/Trailing/BreakEven below, not force-closed). |
//|   - When Entry TF flips back to Master's direction, open again -  |
//|     repeatable as long as Master itself hasn't flipped.           |
//|                                                                    |
//| Supports any Master/Entry TF pair via input parameters (covers    |
//| H4->M30, H4->M15, H1->M15, H1->M5, M30->M15, M30->M5 and more).   |
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

enum ENUM_TRADE_DIRECTION
{
   DIR_BOTH      = 0,   // BUY & SELL
   DIR_BUY_ONLY  = 1,   // BUY only
   DIR_SELL_ONLY = 2    // SELL only
};

input group "=== TIMEFRAME PAIR (NORMAL) ==="
input ENUM_TIMEFRAMES     InpMasterTF     = PERIOD_H4;     // Master Timeframe (arah utama)
input ENUM_TIMEFRAMES     InpEntryTF      = PERIOD_M15;    // Entry Timeframe (trigger buka posisi)

input group "=== SCALP CASCADE (dynamic master) ==="
input bool                InpEnableScalp  = true;          // Aktifkan auto-scalp pas cascade kebentuk
input ENUM_TIMEFRAMES     InpScalpMasterTF= PERIOD_M30;     // Jadi 'master sementara' pas Entry TF + TF ini kompak lawan Master
input ENUM_TIMEFRAMES     InpScalpEntryTF = PERIOD_M5;      // Trigger entry buat scalp itu

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
input double              InpSL_Pips      = 200;            // Stop Loss (pips, 0 = tanpa SL) - dipakai KEDUA tier (backstop katastropik) - verified 2026-08-09 SL/TP/BE sweep
input double              InpTP_Pips      = 150;             // Take Profit NORMAL (pips, 0 = tanpa TP) - verified 2026-08-09 SL/TP/BE sweep

input group "=== TRAILING STOP / BREAK EVEN (NORMAL tier) ==="
input bool                InpUseTrailing  = true;           // Aktifkan trailing stop NORMAL
input double              InpTrailStartPips= 150;            // Trailing mulai aktif setelah profit sekian pip - verified 2026-08-09
input double              InpTrailStepPips = 70;             // Jarak trailing dari harga sekarang (pip) - verified 2026-08-09
input bool                InpUseBreakEven = true;           // Aktifkan break-even NORMAL
input double              InpBE_TriggerPips= 4;              // BE aktif setelah profit sekian pip - verified 2026-08-09: trigger SEDINI mungkin (4 pip) menang telak di WR (64.9%->72.0%) dibanding trigger lama 20pip
input double              InpBE_LockPips   = 2;              // SL dikunci sejauh ini dari entry (pip) pas BE - verified 2026-08-09

input group "=== SCALP TP / TRAILING / BE (tier terpisah) ==="
input double              InpScalpTP_Pips        = 25;       // TP SCALP (pips, 0 = tanpa TP) - dites: avg win SCALP cuma ~47pip, TP pendek kunci profit lebih sering
input bool                InpScalpUseBreakEven   = true;     // Aktifkan BE SCALP
input double              InpScalpBE_TriggerPips = 12;       // BE SCALP aktif setelah profit sekian pip
input double              InpScalpBE_LockPips    = 2;        // SL dikunci sejauh ini pas BE SCALP
input bool                InpScalpUseTrailing    = true;     // Aktifkan trailing SCALP
input double              InpScalpTrailStartPips = 15;       // Trailing SCALP mulai aktif setelah profit sekian pip
input double              InpScalpTrailStepPips  = 6;        // Jarak trailing SCALP

input group "=== RSI / ADX FILTER (eksperimen di luar doktrin CMP murni, default ON - verified 2026-08-09: WR64.9%/PF1.042 vs WR63.7%/PF0.979 tanpa filter) ==="
input bool                InpUseADX         = true;     // Filter momentum ADX (skip entry kalau ADX < InpADX_MinLevel)
input int                 InpADX_Period     = 14;       // Periode ADX
input double              InpADX_MinLevel   = 20;       // ADX minimum buat entry (di bawah ini = choppy/lemah)
input bool                InpUseRSI         = true;     // Filter overbought/oversold RSI
input int                 InpRSI_Period     = 14;       // Periode RSI
input double              InpRSI_Overbought = 70;       // Skip BUY kalau RSI >= ini
input double              InpRSI_Oversold   = 30;       // Skip SELL kalau RSI <= ini

input group "=== M1 CONFIRMATION (eksperimen, Dadang: M1 ngawal pembentukan M5) ==="
input bool                InpUseM1Confirm = false;    // Wajib M1 udah searah sebelum entry SCALP (M5)

input group "=== FILTER EKSEKUSI ==="
input double              InpMaxSpreadPips= 50;             // Spread filter (pips, 0 = tanpa filter)
input int                 InpSlippage     = 30;              // Slippage/deviation (points)
input double              InpRetestTolerancePips = 15;       // Toleransi jarak retest ke level breakout (pips)

input group "=== PANEL ==="
input bool                 InpShowPanel    = true;           // Tampilkan dashboard di chart
input string                InpPanelName    = "SULTAN SNIPER ENGINE"; // Judul panel
input string                InpOwnerName    = "Commander Dadang Wahyuono"; // Nama pemilik

enum ENUM_TRADE_MODE
{
   MODE_NORMAL = 0,   // trading Master/Entry pair (H4>M15 default), original bias direction
   MODE_SCALP  = 1     // cascade confirmed - trading ScalpMaster/ScalpEntry pair, OPPOSITE of Master
};

//======================================================================
string   g_masterDir        = "WAIT";
string   g_entryDir         = "WAIT";
string   g_scalpMasterDir   = "WAIT";
string   g_scalpEntryDir    = "WAIT";
datetime g_masterChangeTime = 0;
datetime g_lastEntryBarTime = 0;
datetime g_lastScalpEntryBarTime = 0;
int      g_hMaster = INVALID_HANDLE;
int      g_hEntry  = INVALID_HANDLE;
int      g_hScalpMaster = INVALID_HANDLE;
int      g_hScalpEntry  = INVALID_HANDLE;
ENUM_TRADE_MODE g_mode = MODE_NORMAL;

// RSI/ADX filter handles - only created when InpUseRSI/InpUseADX enabled.
// Separate handle per tier since NORMAL checks Entry TF (M15) and SCALP
// checks Scalp Entry TF (M5).
int      g_hRSI_Entry      = INVALID_HANDLE;
int      g_hADX_Entry      = INVALID_HANDLE;
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

#define DASH_PREFIX "DD_DASH_"

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

   g_hMaster = iCustom(_Symbol, InpMasterTF, "DD_CMP_Indicator");
   g_hEntry  = iCustom(_Symbol, InpEntryTF,  "DD_CMP_Indicator");
   if(g_hMaster == INVALID_HANDLE || g_hEntry == INVALID_HANDLE)
   {
      Print("ERROR: gagal load DD_CMP_Indicator - pastikan DD_CMP_Indicator.ex5 ada di folder Indicators.");
      return(INIT_FAILED);
   }
   if(InpEnableScalp)
   {
      g_hScalpMaster = iCustom(_Symbol, InpScalpMasterTF, "DD_CMP_Indicator");
      g_hScalpEntry  = iCustom(_Symbol, InpScalpEntryTF,  "DD_CMP_Indicator");
      if(g_hScalpMaster == INVALID_HANDLE || g_hScalpEntry == INVALID_HANDLE)
      {
         Print("ERROR: gagal load DD_CMP_Indicator buat scalp TF.");
         return(INIT_FAILED);
      }
   }
   if(InpUseRSI)
   {
      g_hRSI_Entry = iRSI(_Symbol, InpEntryTF, InpRSI_Period, PRICE_CLOSE);
      if(InpEnableScalp) g_hRSI_ScalpEntry = iRSI(_Symbol, InpScalpEntryTF, InpRSI_Period, PRICE_CLOSE);
   }
   if(InpUseADX)
   {
      g_hADX_Entry = iADX(_Symbol, InpEntryTF, InpADX_Period);
      if(InpEnableScalp) g_hADX_ScalpEntry = iADX(_Symbol, InpScalpEntryTF, InpADX_Period);
   }
   if(InpUseM1Confirm)
   {
      g_hM1 = iCustom(_Symbol, PERIOD_M1, "DD_CMP_Indicator");
      if(g_hM1 == INVALID_HANDLE)
         Print("WARNING: gagal load DD_CMP_Indicator buat M1 confirmation - filter M1 di-skip (bukan fatal).");
   }

   if(InpShowPanel) CreatePanel();
   Print("DD Chain Reaction Multi-TF EA aktif: Master=", EnumToString(InpMasterTF),
         " -> Entry=", EnumToString(InpEntryTF),
         InpEnableScalp ? StringFormat("  |  Scalp cascade: %s>%s", EnumToString(InpScalpMasterTF), EnumToString(InpScalpEntryTF)) : "",
         InpUseADX ? "  |  ADX filter ON" : "",
         InpUseRSI ? "  |  RSI filter ON" : "");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(g_hMaster != INVALID_HANDLE) IndicatorRelease(g_hMaster);
   if(g_hEntry  != INVALID_HANDLE) IndicatorRelease(g_hEntry);
   if(g_hScalpMaster != INVALID_HANDLE) IndicatorRelease(g_hScalpMaster);
   if(g_hScalpEntry  != INVALID_HANDLE) IndicatorRelease(g_hScalpEntry);
   if(g_hRSI_Entry      != INVALID_HANDLE) IndicatorRelease(g_hRSI_Entry);
   if(g_hADX_Entry      != INVALID_HANDLE) IndicatorRelease(g_hADX_Entry);
   if(g_hRSI_ScalpEntry != INVALID_HANDLE) IndicatorRelease(g_hRSI_ScalpEntry);
   if(g_hADX_ScalpEntry != INVALID_HANDLE) IndicatorRelease(g_hADX_ScalpEntry);
   if(g_hM1             != INVALID_HANDLE) IndicatorRelease(g_hM1);
   ObjectsDeleteAll(0, DASH_PREFIX);
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
   int px = 12, py = 18, w = 250, h = 268;
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
   PanelLabel("OWNER",  px, y, 8,  clrSilver);     y += 20;
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
   PanelLabel("EQUITY", px, y, 9,  clrWhite);

   ObjectSetString(0, DASH_PREFIX + "TITLE", OBJPROP_TEXT, InpPanelName);
   ObjectSetString(0, DASH_PREFIX + "OWNER", OBJPROP_TEXT, InpOwnerName);
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

   ObjectSetString(0, DASH_PREFIX + "MODE", OBJPROP_TEXT,
                    (g_mode == MODE_SCALP) ? "*** SCALP MODE ***" : "Mode: NORMAL");
   ObjectSetInteger(0, DASH_PREFIX + "MODE", OBJPROP_COLOR, (g_mode == MODE_SCALP) ? clrOrange : clrYellow);

   ObjectSetString(0, DASH_PREFIX + "PAIR", OBJPROP_TEXT,
                    StringFormat("%s > %s", EnumToString(InpMasterTF), EnumToString(InpEntryTF)));

   ObjectSetString(0, DASH_PREFIX + "MASTER", OBJPROP_TEXT, "Master:  " + g_masterDir);
   ObjectSetInteger(0, DASH_PREFIX + "MASTER", OBJPROP_COLOR, DirColor(g_masterDir));

   ObjectSetString(0, DASH_PREFIX + "ENTRY", OBJPROP_TEXT, "Entry TF: " + g_entryDir);
   ObjectSetInteger(0, DASH_PREFIX + "ENTRY", OBJPROP_COLOR, DirColor(g_entryDir));

   if(InpEnableScalp)
   {
      ObjectSetString(0, DASH_PREFIX + "SCALPM", OBJPROP_TEXT,
                       StringFormat("Scalp M (%s): %s", EnumToString(InpScalpMasterTF), g_scalpMasterDir));
      ObjectSetInteger(0, DASH_PREFIX + "SCALPM", OBJPROP_COLOR, DirColor(g_scalpMasterDir));

      ObjectSetString(0, DASH_PREFIX + "SCALPE", OBJPROP_TEXT,
                       StringFormat("Scalp E (%s): %s", EnumToString(InpScalpEntryTF), g_scalpEntryDir));
      ObjectSetInteger(0, DASH_PREFIX + "SCALPE", OBJPROP_COLOR, DirColor(g_scalpEntryDir));
   }
   else
   {
      ObjectSetString(0, DASH_PREFIX + "SCALPM", OBJPROP_TEXT, "Scalp cascade: OFF");
      ObjectSetInteger(0, DASH_PREFIX + "SCALPM", OBJPROP_COLOR, clrGray);
      ObjectSetString(0, DASH_PREFIX + "SCALPE", OBJPROP_TEXT, "");
   }

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

//--- reads buffer 4 (frozen breakout level of the CURRENT CMP regime)
double ReadBreakoutLevel(int handle)
{
   double buf[1];
   if(CopyBuffer(handle, 4, 0, 1, buf) <= 0) return 0.0;
   return buf[0];
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

//--- Overbought/oversold filter (eksperimen, off by default): skip BUY if
//--- RSI already overbought, skip SELL if RSI already oversold - "nunggu
//--- candle over retes dulu" per Dadang. Always true if InpUseRSI is off.
bool RSIOk(int handle, string dir)
{
   if(!InpUseRSI || handle == INVALID_HANDLE) return true;
   double buf[1];
   if(CopyBuffer(handle, 0, 1, 1, buf) <= 0) return true;   // last closed bar
   double rsi = buf[0];
   if(dir == "BUY"  && rsi >= InpRSI_Overbought) return false;
   if(dir == "SELL" && rsi <= InpRSI_Oversold)   return false;
   return true;
}

//--- M1 confirmation (eksperimen, off by default): wajib M1's CMP udah
//--- searah SEBELUM entry SCALP (M5) dibuka - "M1 ngawal pembentukan M5".
//--- Always true kalau InpUseM1Confirm off atau handle-nya gagal load.
bool M1Ok(string dir)
{
   if(!InpUseM1Confirm || g_hM1 == INVALID_HANDLE) return true;
   datetime tM1;
   string m1Dir = ReadCMP(g_hM1, tM1);
   return m1Dir == dir;
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

void TryOpen(string dir, string tag, bool isScalp)
{
   if(InpTradeDir == DIR_BUY_ONLY  && dir == "SELL") return;
   if(InpTradeDir == DIR_SELL_ONLY && dir == "BUY")  return;
   if(!SpreadOk()) return;
   if(InpMaxOpenPos > 0 && CountOpenPositions() >= InpMaxOpenPos) return;
   if(!InpAllowMultiple && CountOpenPositions(dir) > 0) return;

   bool   buy    = (dir == "BUY");
   double pip    = PipSize();
   double px     = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl     = (InpSL_Pips > 0) ? (buy ? px - InpSL_Pips*pip : px + InpSL_Pips*pip) : 0.0;
   double tpPips = isScalp ? InpScalpTP_Pips : InpTP_Pips;   // SCALP gets its own short TP (see input group above)
   double tp     = (tpPips > 0) ? (buy ? px + tpPips*pip : px - tpPips*pip) : 0.0;
   double lot    = CalcLot(InpSL_Pips);

   string comment = "DD-CR " + tag;
   if(trade.PositionOpen(_Symbol, buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, lot, px, sl, tp, comment))
      Print("ENTRY (", tag, ") ", dir, " lot=", lot, " @ ", px, " SL=", sl, " TP=", tp);
   else
      Print("ENTRY FAILED (", tag, ") ", dir, ": ", trade.ResultRetcodeDescription());
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

//--- Zone-precision entry filter: require the pullback candle to actually
//--- come back and RETEST the exact breakout level that put CMP into this
//--- direction (within InpRetestTolerancePips), AND still close on the
//--- correct side of it (proof the level held, wasn't able to flip). Dadang:
//--- "entrinya dibuat di area breakout, buat memastikan area cmp nya sudah
//--- diuji dan tidak sanggup flip." Stricter than a plain opposite-colored
//--- candle - filters out entries where price never came back near the
//--- actual level (imprecise zone) even if the candle color matched.
bool RetestedBreakout(ENUM_TIMEFRAMES tf, string dir, double breakoutLevel)
{
   if(breakoutLevel <= 0) return false;   // no recorded breakout level yet

   double o  = iOpen(_Symbol, tf, 1);
   double c  = iClose(_Symbol, tf, 1);
   double lo = iLow(_Symbol, tf, 1);
   double hi = iHigh(_Symbol, tf, 1);
   double tolerance = InpRetestTolerancePips * PipSize();

   if(dir == "BUY")
   {
      bool pulledBack  = (c < o);                             // still a down candle first
      bool touchedZone = (lo <= breakoutLevel + tolerance);    // low came close enough to the breakout level
      bool held        = (c >= breakoutLevel);                 // close didn't actually fall back below it
      return pulledBack && touchedZone && held;
   }
   else // SELL
   {
      bool pulledBack  = (c > o);
      bool touchedZone = (hi >= breakoutLevel - tolerance);
      bool held        = (c <= breakoutLevel);
      return pulledBack && touchedZone && held;
   }
}

void OnTick()
{
   ManageTrailingAndBE();
   UpdatePanel();   // every tick - floating P/L, balance/equity, stats stay live

   // --- Top Master (structural bias) - polled every tick, cheap. A flip here
   // is a full regime reset: close everything, drop back to NORMAL mode, and
   // let the state machine below re-decide from scratch on the new bias.
   datetime mChangeTime;
   string masterDir = ReadCMP(g_hMaster, mChangeTime);
   if(masterDir != g_masterDir)
   {
      if(masterDir != "WAIT" && g_masterDir != "WAIT")
         CloseAllPositions(StringFormat("Master %s flip -> %s (regime reset)", EnumToString(InpMasterTF), masterDir));
      g_masterDir = masterDir;
      g_masterChangeTime = mChangeTime;
      g_mode = MODE_NORMAL;
      Print("MASTER FLIP -> ", g_masterDir, " @ ", TimeToString(mChangeTime));
   }
   if(g_masterDir == "WAIT") return;   // no master bias yet - don't trade

   datetime eChangeTime;
   g_entryDir = ReadCMP(g_hEntry, eChangeTime);
   if(InpEnableScalp)
   {
      datetime tsm, tse;
      g_scalpMasterDir = ReadCMP(g_hScalpMaster, tsm);
      g_scalpEntryDir  = ReadCMP(g_hScalpEntry, tse);
   }

   if(g_mode == MODE_NORMAL)
   {
      if(g_entryDir == OppositeDir(g_masterDir))
      {
         // Entry TF opposes Master - cut any NORMAL position now, don't wait.
         CloseAllPositions(StringFormat("Entry TF %s lawan Master %s", g_entryDir, g_masterDir));

         // Cascade check: if the scalp-tier Master ALSO already opposes the
         // top Master (not just Entry TF alone), this isn't noise anymore -
         // switch into SCALP mode and trade the opposite direction, betting
         // the top Master itself may pull back within the next few bars
         // (candle-formation doctrine: child-TF breakout tends to drag the
         // parent TF's candle color with it).
         if(InpEnableScalp && g_scalpMasterDir == OppositeDir(g_masterDir))
         {
            g_mode = MODE_SCALP;
            Print("CASCADE CONFIRMED (", EnumToString(InpScalpMasterTF), " ", g_scalpMasterDir,
                  ") -> switching to SCALP mode");
         }
         return;
      }

      if(g_entryDir != g_masterDir) return;   // entry TF still WAIT - pause new entries

      // Only re-evaluate NORMAL entries once per Entry-TF bar close.
      datetime entryBarTime = iTime(_Symbol, InpEntryTF, 0);
      if(entryBarTime == g_lastEntryBarTime) return;
      g_lastEntryBarTime = entryBarTime;

      // Zone-precision confirmation: don't chase - only enter after price
      // has come back and retested the Entry TF's own breakout level and
      // held (didn't flip). Stops buying straight into an extended rally's
      // peak (or selling into a dump's bottom) far from the actual level.
      double normalBreakout = ReadBreakoutLevel(g_hEntry);
      if(!RetestedBreakout(InpEntryTF, g_masterDir, normalBreakout)) return;

      // Eksperimen (off by default): ADX momentum + RSI overbought/oversold.
      if(!ADXOk(g_hADX_Entry)) return;
      if(!RSIOk(g_hRSI_Entry, g_masterDir)) return;

      TryOpen(g_masterDir, StringFormat("%s>%s", EnumToString(InpMasterTF), EnumToString(InpEntryTF)), false);
   }
   else // MODE_SCALP - trade the OPPOSITE direction of the top Master
   {
      string scalpDir = OppositeDir(g_masterDir);

      // Cut-loss reference is ALWAYS Entry TF (M15) - the same TF that
      // triggered the cascade in the first place - never M5. M5 is only the
      // scalp's ENTRY trigger; using it for exits too would whipsaw on its
      // own noise. If M15 flips back to agree with Master, the cascade that
      // justified this scalp is over: cut loss and drop back to NORMAL.
      if(g_entryDir == g_masterDir)
      {
         CloseAllPositions(StringFormat("Entry TF (%s) %s balik searah Master %s - cascade kelar",
                                         EnumToString(InpEntryTF), g_entryDir, g_masterDir));
         g_mode = MODE_NORMAL;
         return;
      }

      // Secondary safety net: if the scalp-tier Master (M30) itself already
      // realigned with H4 - even though M15 technically hasn't yet - the
      // cascade's own basis is gone, bail too.
      if(g_scalpMasterDir == g_masterDir)
      {
         CloseAllPositions(StringFormat("Scalp Master %s balik searah Master %s - batal cascade",
                                         EnumToString(InpScalpMasterTF), g_masterDir));
         g_mode = MODE_NORMAL;
         return;
      }

      // M5 (scalp Entry TF) only gates NEW scalp entries, never forces an
      // exit on an already-open scalp position.
      if(g_scalpEntryDir != scalpDir) return;   // scalp entry still WAIT/against - pause new entries only

      datetime scalpBarTime = iTime(_Symbol, InpScalpEntryTF, 0);
      if(scalpBarTime == g_lastScalpEntryBarTime) return;
      g_lastScalpEntryBarTime = scalpBarTime;

      double scalpBreakout = ReadBreakoutLevel(g_hScalpEntry);
      if(!RetestedBreakout(InpScalpEntryTF, scalpDir, scalpBreakout)) return;

      // Eksperimen (off by default): ADX momentum + RSI overbought/oversold + M1 confirmation.
      if(!ADXOk(g_hADX_ScalpEntry)) return;
      if(!RSIOk(g_hRSI_ScalpEntry, scalpDir)) return;
      if(!M1Ok(scalpDir)) return;

      TryOpen(scalpDir, StringFormat("SCALP %s>%s", EnumToString(InpScalpMasterTF), EnumToString(InpScalpEntryTF)), true);
   }
}
