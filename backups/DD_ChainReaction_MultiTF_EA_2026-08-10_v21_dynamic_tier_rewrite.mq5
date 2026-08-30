//+------------------------------------------------------------------+
//| DD_ChainReaction_MultiTF_EA.mq5                                  |
//| Reads CMP from DD_CMP_Indicator.mq5 - EA itself NEVER computes    |
//| CMP (per Dadang's TASK ORDER: "EA tidak menghitung CMP. EA hanya |
//| membaca status CMP yang dihasilkan indikator MT5.")               |
//|                                                                   |
//| DOCTRINE v21 (2026-08-10) - REWRITE per Dadang: "coba pakai ilmu  |
//| real gw", pointing to D:\bunga\dayli deploy-20260614T073129Z-3-003|
//| (Bunker's original Daily Deploy source - see full synthesis in    |
//| memory project_mt5_cmp_ea_tuning.md). This REPLACES v14-v20's     |
//| fixed H4->M30->M5 cascade, which is exactly the "trader skema"    |
//| mistake the source material explicitly warns against:              |
//| "Makin banyak backtest pun tak guna kalau skema... BO-VRCF,       |
//| BO-VRCF ah tak ada iminiasi betul."                                |
//|                                                                    |
//| CORE RULE - VR confirmation TF is DYNAMIC, never fixed:            |
//| "Saya cakap timeframe yang buat BO berlawanan. Jadi dekat situ    |
//| semua timeframe boleh guna... Kalau saya cakap kena tunggu M15    |
//| sahaja, nanti dia akan jadi lebih skema."                          |
//|                                                                    |
//| IMPLEMENTATION (MVP subset of the full doctrine - see memory for   |
//| deferred parts: barrier-queue TP, low/high-risk mode toggle,      |
//| M15/M1 tiers):                                                     |
//|   - BIAS: Weekly CMP only, fixed gate, separate from the cascade. |
//|     Only trade in bias direction, ever.                            |
//|   - 4 PARALLEL TIERS run simultaneously (not one fixed cascade):  |
//|     D1->H4, H4->H1, H1->M30, M30->M5. Each runs its own            |
//|     fire/stop/resume state machine (same proven mechanism as       |
//|     v14-v20's single M30->M5 pair, now replicated per tier).       |
//|     Whichever tier's child TF produces a fresh CF first (searah    |
//|     bias) fires - THIS is the "TF konfirmasi dinamis" behavior:    |
//|     no single TF is hardcoded as THE trigger.                      |
//|   - SL/TP scaled per tier (bigger tier = wider) - approximates the |
//|     barrier-queue TP concept without full barrier tracking yet.    |
//|   - Position sizing: risk-dollar-first (InpUseRisk), matching      |
//|     Bunker's explicit method: "saya nak riskkan 100 dolar untuk    |
//|     trade tu, jadi saya kira lotsize dan SL dari situ" - NOT fixed |
//|     lot + fixed pip SL.                                            |
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

#define EA_VERSION "v21"

enum ENUM_TRADE_DIRECTION
{
   DIR_BOTH      = 0,   // BUY & SELL
   DIR_BUY_ONLY  = 1,   // BUY only
   DIR_SELL_ONLY = 2    // SELL only
};

input group "=== BIAS (Weekly only, fixed gate - 'Bias ini kita akan tengok di Time Frame Weekly sahaja') ==="
input bool                InpUseBias      = true;    // Wajib arah Weekly CMP sebelum trading (matiin cuma buat testing/debug)

input group "=== TIER CASCADE DINAMIS (D1>H4, H4>H1, H1>M30, M30>M5 - SEMUA jalan paralel) ==="
input bool                InpEnableTier0_D1H4  = true;   // Tier 0: Daily -> H4 (paling lebar/jarang)
input bool                InpEnableTier1_H4H1  = true;   // Tier 1: H4 -> H1
input bool                InpEnableTier2_H1M30 = true;   // Tier 2: H1 -> M30
input bool                InpEnableTier3_M30M5 = true;   // Tier 3: M30 -> M5 (paling ketat/sering)

input group "=== LOT / RISK MANAGEMENT (risk-dollar-first, sesuai 'ilmu real' Bunker) ==="
input bool                InpUseRisk      = true;          // Risk % dari balance -> turunin lot dari situ (BUKAN fixed lot). Bunker: "saya nak riskkan 100 dolar, kira lotsize dari situ"
input double              InpLot          = 0.01;           // Lot fixed (dipakai kalau InpUseRisk=false)
input double              InpRiskPct      = 1.0;            // Risk % balance per trade (kalau InpUseRisk=true)

input group "=== POSISI ==="
input long                InpMagic        = 20260807;       // Magic number
input int                 InpMaxOpenPos   = 0;              // Maximum posisi terbuka bersamaan (0 = unlimited)
input bool                InpAllowMultiple= true;           // Boleh entry baru walau udah ada posisi searah (layering)
input ENUM_TRADE_DIRECTION InpTradeDir    = DIR_BOTH;       // Filter arah trading
input bool                InpBlockAddWhileLosing = true;    // Dadang 2026-08-09: "dilarang entri ketika masih minus, tambah entri hanya pas plus" - anti-averaging-down

input group "=== SL/TP PER TIER (pip, di-scale: tier gede = lebar) ==="
input double              InpTier0SL_Pips = 600;    // SL Tier 0 (D1>H4) - fallback kalau risk-sizing off
input double              InpTier0TP_Pips = 1000;   // TP Tier 0
input double              InpTier1SL_Pips = 250;    // SL Tier 1 (H4>H1)
input double              InpTier1TP_Pips = 400;    // TP Tier 1
input double              InpTier2SL_Pips = 100;    // SL Tier 2 (H1>M30)
input double              InpTier2TP_Pips = 180;    // TP Tier 2
input double              InpTier3SL_Pips = 40;     // SL Tier 3 (M30>M5)
input double              InpTier3TP_Pips = 90;     // TP Tier 3

input group "=== TRAILING STOP / BREAK EVEN (per tier, tier gede = lebih lebar) ==="
input bool                InpUseTrailing     = true;
input bool                InpUseBreakEven    = true;
input double              InpBE_LockPips     = 2;      // SL dikunci sejauh ini dari entry pas BE (semua tier)
input double              InpTier0BE_TriggerPips    = 200;  input double InpTier0TrailStartPips = 200; input double InpTier0TrailStepPips = 100;
input double              InpTier1BE_TriggerPips    = 80;   input double InpTier1TrailStartPips = 80;  input double InpTier1TrailStepPips = 40;
input double              InpTier2BE_TriggerPips    = 30;   input double InpTier2TrailStartPips = 30;  input double InpTier2TrailStepPips = 15;
input double              InpTier3BE_TriggerPips    = 15;   input double InpTier3TrailStartPips = 15;  input double InpTier3TrailStepPips = 8;

input group "=== FILTER EKSEKUSI ==="
input double              InpMaxSpreadPips= 50;             // Spread filter (pips, 0 = tanpa filter)
input int                 InpSlippage     = 30;              // Slippage/deviation (points)

input group "=== BOOKMAP BRIDGE (live-only, informational) ==="
input bool                InpShowBookmapPanel = true;
input double              InpBookmapStaleSec  = 5.0;

input group "=== PANEL ==="
input bool                 InpShowPanel    = true;
input string                InpPanelName    = "SULTAN SNIPER ENGINE";
input string                InpOwnerName    = "Commander Dadang Wahyuono";

//======================================================================
// TF ladder - one indicator handle per unique TF, tiers reference these
// by index so H4/H1/M30 (each used as both a parent AND a child by
// adjacent tiers) only get ONE handle/CMP-read each per tick.
enum { TF_W1=0, TF_D1=1, TF_H4=2, TF_H1=3, TF_M30=4, TF_M5=5, TF_COUNT=6 };
ENUM_TIMEFRAMES g_tfEnum[TF_COUNT] = {PERIOD_W1, PERIOD_D1, PERIOD_H4, PERIOD_H1, PERIOD_M30, PERIOD_M5};
string          g_tfName[TF_COUNT] = {"W1","D1","H4","H1","M30","M5"};
int             g_hTF[TF_COUNT];
string          g_tfDir[TF_COUNT];
datetime        g_tfChangeTime[TF_COUNT];

#define NUM_TIERS 4
int      g_tierParentIdx[NUM_TIERS] = {TF_D1, TF_H4, TF_H1, TF_M30};
int      g_tierChildIdx[NUM_TIERS]  = {TF_H4, TF_H1, TF_M30, TF_M5};
string   g_tierTag[NUM_TIERS]       = {"D1>H4","H4>H1","H1>M30","M30>M5"};
bool     g_tierFiringEnabled[NUM_TIERS];
datetime g_tierLastParentBarTime[NUM_TIERS];
datetime g_tierLastEventTime[NUM_TIERS];

string   g_biasDir = "WAIT";

int      g_lastDealsTotal  = -1;
int      g_statTrades = 0, g_statWins = 0, g_statLosses = 0;
double   g_statTotalProfit = 0.0;

bool     g_bookmapOnline    = false;
double   g_bookmapCvd       = 0.0;
double   g_bookmapPulsePct  = 0.0;
string   g_bookmapAbsorption = "NONE";

#define DASH_PREFIX "DD_DASH_"

//--- pip size. XAUUSD 2-digit quote: 1 pip = 10 points = $0.10.
double PipSize()
{
   return (_Digits == 3 || _Digits == 5 || _Digits == 2) ? _Point * 10.0 : _Point;
}

double TierSL(int t) { if(t==0) return InpTier0SL_Pips; if(t==1) return InpTier1SL_Pips; if(t==2) return InpTier2SL_Pips; return InpTier3SL_Pips; }
double TierTP(int t) { if(t==0) return InpTier0TP_Pips; if(t==1) return InpTier1TP_Pips; if(t==2) return InpTier2TP_Pips; return InpTier3TP_Pips; }
double TierBETrigger(int t)   { if(t==0) return InpTier0BE_TriggerPips;    if(t==1) return InpTier1BE_TriggerPips;    if(t==2) return InpTier2BE_TriggerPips;    return InpTier3BE_TriggerPips; }
double TierTrailStart(int t)  { if(t==0) return InpTier0TrailStartPips;    if(t==1) return InpTier1TrailStartPips;    if(t==2) return InpTier2TrailStartPips;    return InpTier3TrailStartPips; }
double TierTrailStep(int t)   { if(t==0) return InpTier0TrailStepPips;     if(t==1) return InpTier1TrailStepPips;     if(t==2) return InpTier2TrailStepPips;     return InpTier3TrailStepPips; }
bool   TierEnabled(int t)     { if(t==0) return InpEnableTier0_D1H4; if(t==1) return InpEnableTier1_H4H1; if(t==2) return InpEnableTier2_H1M30; return InpEnableTier3_M30M5; }

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);

   for(int i = 0; i < TF_COUNT; i++)
   {
      g_hTF[i] = iCustom(_Symbol, g_tfEnum[i], "DD_CMP_Indicator");
      if(g_hTF[i] == INVALID_HANDLE)
      {
         Print("ERROR: gagal load DD_CMP_Indicator buat ", g_tfName[i], " - pastikan DD_CMP_Indicator.ex5 ada di folder Indicators.");
         return(INIT_FAILED);
      }
   }

   if(InpShowPanel) CreatePanel();
   Print("DD Chain Reaction Multi-TF EA [", EA_VERSION, "] aktif: Bias=Weekly, tier dinamis D1>H4>H1>M30>M5");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   for(int i = 0; i < TF_COUNT; i++)
      if(g_hTF[i] != INVALID_HANDLE) IndicatorRelease(g_hTF[i]);
   ObjectsDeleteAll(0, DASH_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| On-chart live panel                                              |
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
   int px = 12, py = 18, w = 260, h = 380;
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
   PanelLabel("BIAS",   px, y, 10, clrYellow);     y += 20;
   PanelLabel("TIER0",  px, y, 9,  clrSilver);     y += 16;
   PanelLabel("TIER1",  px, y, 9,  clrSilver);     y += 16;
   PanelLabel("TIER2",  px, y, 9,  clrSilver);     y += 16;
   PanelLabel("TIER3",  px, y, 9,  clrSilver);     y += 20;
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

   ObjectSetString(0, DASH_PREFIX + "BIAS", OBJPROP_TEXT, "Bias (W1): " + g_biasDir);
   ObjectSetInteger(0, DASH_PREFIX + "BIAS", OBJPROP_COLOR, DirColor(g_biasDir));

   string tierKeys[NUM_TIERS] = {"TIER0","TIER1","TIER2","TIER3"};
   for(int t = 0; t < NUM_TIERS; t++)
   {
      string fireStr = g_tierFiringEnabled[t] ? "ON" : "off";
      string txt = StringFormat("%s: %s->%s [%s]", g_tierTag[t],
                                 g_tfDir[g_tierParentIdx[t]], g_tfDir[g_tierChildIdx[t]], fireStr);
      ObjectSetString(0, DASH_PREFIX + tierKeys[t], OBJPROP_TEXT, txt);
      ObjectSetInteger(0, DASH_PREFIX + tierKeys[t], OBJPROP_COLOR, g_tierFiringEnabled[t] ? clrLime : clrGray);
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

//--- reads buffer 7 (BreakoutEventTimeBuffer) - time of the MOST RECENT
//--- individual breakout past the latest pullback, repeating on EVERY such
//--- break (not just the first regime-flip like buffer 3/ChangeTimeBuffer).
datetime ReadBreakoutEventTime(int handle)
{
   double buf[1];
   if(CopyBuffer(handle, 7, 0, 1, buf) <= 0) return 0;
   return (datetime)buf[0];
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

//--- Sums floating P/L across all open positions matching dirFilter. Used to
//--- gate layering: Dadang 2026-08-09 "dilarang entri ketika masih minus,
//--- kita tambah entri hanya pas plus" - anti-averaging-down.
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

//--- Risk-dollar-first lot sizing (Bunker's actual method, per 2026-08-10
//--- transcript synthesis): "saya ada 500 dolar, saya nak riskkan 100 dolar
//--- untuk trade tu, jadi saya kira lotsize dan SL dari situ" - decide $ risk
//--- FIRST, derive lot from that + the SL distance, not the reverse.
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

//--- Resets the fire/stop/resume state for ALL tiers - called on Bias flip
//--- (Weekly), since every tier's live regime is void once the top gate changes.
void ResetAllTiers()
{
   for(int t = 0; t < NUM_TIERS; t++)
   {
      g_tierFiringEnabled[t] = false;
      g_tierLastParentBarTime[t] = 0;
      g_tierLastEventTime[t] = 0;
   }
}

void TryOpen(string dir, int tier, datetime parentFlipTime, datetime childFlipTime)
{
   if(InpTradeDir == DIR_BUY_ONLY  && dir == "SELL") return;
   if(InpTradeDir == DIR_SELL_ONLY && dir == "BUY")  return;
   if(!SpreadOk()) return;
   if(InpMaxOpenPos > 0 && CountOpenPositions() >= InpMaxOpenPos) return;
   if(!InpAllowMultiple && CountOpenPositions(dir) > 0) return;
   if(InpBlockAddWhileLosing && CountOpenPositions(dir) > 0 && FloatingPLForDirection(dir) < 0.0) return;

   bool   buy    = (dir == "BUY");
   double pip    = PipSize();
   double px     = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   double slPips = TierSL(tier);
   double tpPips = TierTP(tier);
   double sl = (slPips > 0) ? (buy ? px - slPips*pip : px + slPips*pip) : 0.0;
   double tp = (tpPips > 0) ? (buy ? px + tpPips*pip : px - tpPips*pip) : 0.0;
   double lot = CalcLot(slPips);

   string comment = "DD-CR " + g_tierTag[tier];
   string timeLawNote = (parentFlipTime > 0 && childFlipTime > 0)
      ? StringFormat(" | Parent BO=%s Child BO=%s (child %s parent)",
                      TimeToString(parentFlipTime, TIME_DATE|TIME_MINUTES),
                      TimeToString(childFlipTime, TIME_DATE|TIME_MINUTES),
                      (childFlipTime > parentFlipTime) ? "AFTER" : "!! NOT AFTER !!")
      : "";
   if(trade.PositionOpen(_Symbol, buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, lot, px, sl, tp, comment))
      Print("ENTRY (", g_tierTag[tier], ") ", dir, " lot=", lot, " @ ", px, " SL=", sl, " TP=", tp, timeLawNote);
   else
      Print("ENTRY FAILED (", g_tierTag[tier], ") ", dir, ": ", trade.ResultRetcodeDescription());
}

//--- Identifies which tier a position belongs to from its comment tag, so
//--- trailing/BE can apply the right tier's parameters to each position.
int TierFromComment(string comment)
{
   for(int t = 0; t < NUM_TIERS; t++)
      if(StringFind(comment, g_tierTag[t]) >= 0) return t;
   return 3;   // fallback: tightest tier's params (safest default)
}

void ManageTrailingAndBE()
{
   double pip = PipSize();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      int t = TierFromComment(PositionGetString(POSITION_COMMENT));
      bool   isBuy  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      double op     = PositionGetDouble(POSITION_PRICE_OPEN);
      double curPx  = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double profitPips = isBuy ? (curPx - op) / pip : (op - curPx) / pip;
      double curSL  = PositionGetDouble(POSITION_SL);
      double curTP  = PositionGetDouble(POSITION_TP);
      double newSL  = curSL;

      if(InpUseBreakEven && profitPips >= TierBETrigger(t))
      {
         double beSL = isBuy ? op + InpBE_LockPips*pip : op - InpBE_LockPips*pip;
         bool notYetAtBE = isBuy ? (curSL < op || curSL == 0) : (curSL > op || curSL == 0);
         if(notYetAtBE) newSL = beSL;
      }
      if(InpUseTrailing && profitPips >= TierTrailStart(t))
      {
         double trailSL = isBuy ? curPx - TierTrailStep(t)*pip : curPx + TierTrailStep(t)*pip;
         if(isBuy  && (trailSL > newSL || newSL == 0)) newSL = trailSL;
         if(!isBuy && (trailSL < newSL || newSL == 0)) newSL = trailSL;
      }
      if(newSL != curSL && newSL != 0)
         trade.PositionModify(tk, newSL, curTP);
   }
}

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
            tierTag    = HistoryDealGetString(dt, DEAL_COMMENT);
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
      if(!haveIn || !haveOut) continue;

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

//--- Bookmap live-bridge reader - informational only, LIVE ONLY (naturally
//--- reports OFFLINE during backtests since the file's real wall-clock
//--- timestamp never matches simulated historical time).
void ReadBookmapBridge()
{
   g_bookmapOnline = false;
   if(!InpShowBookmapPanel) return;
   int handle = FileOpen("bookmap_live_signal.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return;
   for(int i = 0; i < 5 && !FileIsEnding(handle); i++) FileReadString(handle);
   if(FileIsEnding(handle)) { FileClose(handle); return; }
   double ts = StringToDouble(FileReadString(handle));
   FileReadString(handle);
   double cvd     = StringToDouble(FileReadString(handle));
   double pulse   = StringToDouble(FileReadString(handle));
   string absorb  = FileReadString(handle);
   FileClose(handle);
   double ageSec = (double)TimeGMT() - ts;
   if(ageSec < 0 || ageSec > InpBookmapStaleSec) return;
   g_bookmapOnline     = true;
   g_bookmapCvd        = cvd;
   g_bookmapPulsePct   = pulse;
   g_bookmapAbsorption = absorb;
}

//--- Runs the fire/stop/resume state machine for ONE tier (same proven
//--- mechanism as v14-v20's single M30->M5 pair, now generic per tier).
//--- Returns true on the exact tick this tier should fire an entry.
bool UpdateTier(int t, string &outDir)
{
   int pIdx = g_tierParentIdx[t];
   int cIdx = g_tierChildIdx[t];
   string parentDir = g_tfDir[pIdx];
   string childDir  = g_tfDir[cIdx];
   outDir = parentDir;

   if(parentDir == "WAIT" || parentDir != g_biasDir)
   {
      g_tierFiringEnabled[t] = false;
      return false;
   }

   // STOP: child flips against parent
   if(childDir == OppositeDir(parentDir))
      g_tierFiringEnabled[t] = false;

   // RESUME: checked only at a fresh parent-bar open
   datetime parentBarTime = iTime(_Symbol, g_tfEnum[pIdx], 0);
   if(parentBarTime != g_tierLastParentBarTime[t])
   {
      g_tierLastParentBarTime[t] = parentBarTime;
      if(childDir == parentDir) g_tierFiringEnabled[t] = true;
   }

   if(!g_tierFiringEnabled[t]) return false;
   if(childDir != parentDir) return false;

   // FIRE: every fresh breakout EVENT on the child TF (buffer 7)
   datetime eventTime = ReadBreakoutEventTime(g_hTF[cIdx]);
   if(eventTime <= g_tierLastEventTime[t]) return false;
   g_tierLastEventTime[t] = eventTime;   // consume regardless of Time Law check below

   if(eventTime <= g_tfChangeTime[pIdx]) return false;   // TIME LAW: after parent's own regime began

   return true;
}

void OnTick()
{
   ManageTrailingAndBE();
   ReadBookmapBridge();
   UpdatePanel();

   // Update all 6 TFs' CMP state once per tick
   for(int i = 0; i < TF_COUNT; i++)
      g_tfDir[i] = ReadCMP(g_hTF[i], g_tfChangeTime[i]);

   // BIAS gate - Weekly only, fixed, separate from the dynamic cascade.
   // "Bias ini kita akan tengok di Time Frame Weekly sahaja."
   string newBias = InpUseBias ? g_tfDir[TF_W1] : "BUY_SELL_IGNORED";
   if(InpUseBias)
   {
      if(newBias != g_biasDir)
      {
         if(newBias != "WAIT" && g_biasDir != "WAIT")
            CloseAllPositions(StringFormat("Bias (W1) flip %s -> %s", g_biasDir, newBias));
         g_biasDir = newBias;
         ResetAllTiers();
         Print("BIAS FLIP -> ", g_biasDir);
      }
      if(g_biasDir == "WAIT") return;
   }
   else
   {
      g_biasDir = "BOTH";   // bias disabled - tiers just need parentDir consistency with itself, handled below
   }

   // Run all 4 tiers in parallel - whichever fires first this tick, fires.
   // This IS the "TF konfirmasi dinamis" behavior: no single TF is hardcoded
   // as the entry trigger, each tier watches its own adjacent parent/child
   // pair independently and any of them can produce a valid entry.
   for(int t = 0; t < NUM_TIERS; t++)
   {
      if(!TierEnabled(t)) continue;

      // When InpUseBias is off, treat each tier's own parent CMP as its
      // local "bias" (debug/comparison mode only - not the real doctrine).
      string effectiveBias = InpUseBias ? g_biasDir : g_tfDir[g_tierParentIdx[t]];
      string savedBias = g_biasDir;
      if(!InpUseBias) g_biasDir = effectiveBias;

      string dir;
      bool fired = UpdateTier(t, dir);

      if(!InpUseBias) g_biasDir = savedBias;

      if(fired)
         TryOpen(dir, t, g_tfChangeTime[g_tierParentIdx[t]], g_tierLastEventTime[t]);
   }
}
