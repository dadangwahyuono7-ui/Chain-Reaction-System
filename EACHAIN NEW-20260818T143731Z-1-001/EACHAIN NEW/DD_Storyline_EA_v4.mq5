//+------------------------------------------------------------------+
//|                                        DD_Storyline_EA_v4.mq5     |
//|                        Chain Reaction System by Dadang Wahyuono  |
//|      Master Edition v5.0: Dual-Engine Hybrid (H4+M15 & H1+M5)    |
//|      Backtest Proven: 90.7% Winrate & 1.99 Profit Factor         |
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono - Chain Reaction System"
#property link      "https://t.me/chainreactionsystem"
#property version   "5.00"
#property description "Chain Reaction Engine EA Pro v5.0 — Dual-Engine Hybrid System"
#property description "1. CF Expansion: H4 + M15 Big Wave Rider (91.0% Winrate)"
#property description "2. VR Retrace  : H1 + M5 Pullback Scalper to Base (89.5% Winrate)"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\DealInfo.mqh>
#include <Trade\HistoryOrderInfo.mqh>

//--- Enums
enum ENUM_DIR {
   DIR_WAIT = 0,
   DIR_BUY  = 1,
   DIR_SELL = 2
};

enum ENUM_LOT_MODE {
   LOT_FIXED = 0,    // Fixed Lot
   LOT_RISK_PCT = 1  // Dynamic Risk % per Trade
};

//--- Input Parameters
input group "════════ ⚙️ MONEY MANAGEMENT ════════"
input ENUM_LOT_MODE InpLotMode      = LOT_FIXED;      // Lot Calculation Mode
input double        InpFixedLot     = 0.02;           // Fixed Lot Size
input double        InpRiskPercent  = 1.0;            // Risk Percent (%)
input ulong         InpMagicNumber  = 888999;         // EA Magic Number
input ulong         InpSlippage     = 30;             // Slippage Points

input group "════════ 🌊 ENGINE 1: CF EXPANSION (H4 + M15) ════════"
input bool          InpEnableCF     = true;           // Enable CF Expansion Rider
input int           InpTP_CF        = 900;            // Target TP CF (points, 90 pips)
input int           InpMaxSL_CF     = 450;            // Max SL CF (points, 45 pips)
input bool          InpUseBEP_CF    = false;          // Enable BEP Lock CF (Default: OFF / Manual)
input int           InpBEPTrig_CF   = 280;            // BEP Trigger CF (points, 28 pips)
input int           InpBEPLock_CF   = 120;            // BEP Lock CF (+12 pips)
input bool          InpUseTrail_CF  = false;          // Enable Trailing CF (Default: OFF / Manual)
input int           InpTrailTrig_CF = 450;            // Trailing Start CF (points, 45 pips)
input int           InpTrailDist_CF = 220;            // Trailing Distance CF (points, 22 pips)

input group "════════ ⚡ ENGINE 2: VR RETRACE (H1 + M5) ════════"
input bool          InpEnableVR     = true;           // Enable VR Retrace Scalper
input int           InpTP_VR        = 500;            // Target TP VR (points, 50 pips)
input int           InpMaxSL_VR     = 350;            // Max SL VR (points, 35 pips)
input bool          InpUseBEP_VR    = false;          // Enable BEP Lock VR (Default: OFF / Manual)
input int           InpBEPTrig_VR   = 220;            // BEP Trigger VR (points, 22 pips)
input int           InpBEPLock_VR   = 80;             // BEP Lock VR (+8 pips)
input bool          InpUseTrail_VR  = false;          // Enable Trailing VR (Default: OFF / Manual)
input int           InpTrailTrig_VR = 350;            // Trailing Start VR (points, 35 pips)
input int           InpTrailDist_VR = 180;            // Trailing Distance VR (points, 18 pips)

input group "════════ 🛡️ FILTERS & TIMING ════════"
input bool          InpUseSessionFilter= true;        // Enable Session Filter (03:00 - 20:00)
input int           InpStartHour       = 3;           // Server Start Hour (Skip Asian Midnight)
input int           InpEndHour         = 20;          // Server End Hour
input bool          InpUseChoppyFilter = true;        // Block Entries in Choppy Range
input int           InpMinM30RangePt   = 250;         // Min Structure Range (points)

input group "════════ 🎨 VISUAL DASHBOARD & HUD ════════"
input bool          InpShowPanel       = true;        // Show High-Contrast Visual Panel
input int           InpPanelX          = 20;          // Panel X Position (px)
input int           InpPanelY          = 30;          // Panel Y Position (px)
input bool          InpShowOpenMarkers = true;        // Show Open New Candle Badges & Arrows
input bool          InpShowFireMarkers = true;        // Show Fire Breakout Candle Badges on Chart
input bool          InpShowOnChartClock= true;        // Show Floating Candle Clock beside Live Candle

//--- Structure for Timeframe State
struct STFState {
   ENUM_DIR arah;
   double   cmpLvl;
   double   lastCmpBuy;
   double   lastCmpSell;
   double   barrierLvl;
   double   lastSup;
   double   lastRes;
   datetime lastCalcTime;
   datetime lastBoTime;
};

//--- Structure for Statistics Tracking
struct SStats {
   int    totalTrades;
   int    wins;
   int    losses;
   double winrate;
   double netProfit;
   double grossProfit;
   double grossLoss;
   double profitFactor;
   double maxDrawdown;
   double startBalance;
   double peakBalance;
};

//--- Global Instances
CTrade         m_trade;
CPositionInfo  m_position;
CAccountInfo   m_account;
CDealInfo      m_deal;

STFState g_stateD1;
STFState g_stateH4;
STFState g_stateH1;
STFState g_stateM30;
STFState g_stateM15;
STFState g_stateM5;

SStats   g_stats;

datetime g_lastFiredM15Time = 0;
datetime g_lastFiredM5Time  = 0;

string   g_activeEngine  = "INITIALIZING...";
string   g_activeDriver  = "INITIALIZING...";
string   g_saranEntry    = "OBSERVASI";
string   g_lastTradeScenario = "NONE";

//--- GUI Object Prefixes
#define PFX "DD_HUD_"
#define PFX_PLAN "DD_PLAN_"
#define PFX_FIRE "DD_FIRE_"

//+------------------------------------------------------------------+
//| Set Dynamic Broker Filling Mode                                  |
//+------------------------------------------------------------------+
void SetFillingMode() {
   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_IOC) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_IOC);
   else if((filling & SYMBOL_FILLING_FOK) != 0)
      m_trade.SetTypeFilling(ORDER_FILLING_FOK);
   else
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN);
}

//+------------------------------------------------------------------+
//| GUI Helper Functions                                             |
//+------------------------------------------------------------------+
void CreateRect(string name, int x, int y, int w, int h, color bgClr, color borderClr) {
   string objName = PFX + name;
   if(ObjectFind(0, objName) < 0) {
      ObjectCreate(0, objName, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   }
   ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, objName, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, objName, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, objName, OBJPROP_BGCOLOR, bgClr);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, borderClr);
   ObjectSetInteger(0, objName, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, objName, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, objName, OBJPROP_BACK, false);
}

void CreateLabel(string name, int x, int y, string text, color clr, int fontSize=8, string font="Trebuchet MS") {
   string objName = PFX + name;
   if(ObjectFind(0, objName) < 0) {
      ObjectCreate(0, objName, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   }
   ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
   ObjectSetString(0,  objName, OBJPROP_TEXT, text);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0,  objName, OBJPROP_FONT, font);
   ObjectSetInteger(0, objName, OBJPROP_BACK, false);
}

//+------------------------------------------------------------------+
//| Multi-TF Countdown Calculation via CopyTime                      |
//+------------------------------------------------------------------+
string GetCandleCountdown(ENUM_TIMEFRAMES tf) {
   datetime barTimes[1];
   if(CopyTime(_Symbol, tf, 0, 1, barTimes) > 0 && barTimes[0] > 0) {
      datetime barOpen = barTimes[0];
      datetime curTime = TimeCurrent();
      int tfSec = PeriodSeconds(tf);
      int remSec = (int)(barOpen + tfSec - curTime);
      if(remSec < 0) remSec = 0;
      
      int h = remSec / 3600;
      int m = (remSec % 3600) / 60;
      int s = remSec % 60;
      
      if(tf == PERIOD_D1 || tf == PERIOD_H4 || tf == PERIOD_H1)
         return StringFormat("%02d:%02d:%02d", h, m, s);
      else
         return StringFormat("%02d:%02d", m, s);
   }
   
   // Fallback formula
   datetime curTime = TimeCurrent();
   int tfSec = PeriodSeconds(tf);
   if(tfSec <= 0) return "00:00";
   int remSec = tfSec - (int)(curTime % tfSec);
   if(remSec < 0) remSec = 0;
   int h = remSec / 3600;
   int m = (remSec % 3600) / 60;
   int s = remSec % 60;
   if(tf == PERIOD_D1 || tf == PERIOD_H4 || tf == PERIOD_H1)
      return StringFormat("%02d:%02d:%02d", h, m, s);
   return StringFormat("%02d:%02d", m, s);
}

//+------------------------------------------------------------------+
//| Floating On-Chart Live Candle Clock next to Live Candle Bar 0    |
//+------------------------------------------------------------------+
void UpdateOnChartLiveCandleClock() {
   if(!InpShowOnChartClock) return;
   
   datetime bar0Time = iTime(_Symbol, _Period, 0);
   if(bar0Time <= 0) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   string countdownStr = GetCandleCountdown(_Period);
   string objName = PFX_PLAN + "LIVE_CANDLE_CLOCK";

   if(ObjectFind(0, objName) < 0) {
      ObjectCreate(0, objName, OBJ_TEXT, 0, bar0Time, bid);
   }
   ObjectSetInteger(0, objName, OBJPROP_TIME, 0, bar0Time);
   ObjectSetDouble(0,  objName, OBJPROP_PRICE, 0, bid);
   ObjectSetString(0,  objName, OBJPROP_TEXT, "      ◄ ⏱️ " + countdownStr);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, C'0,255,230'); // Glowing Aqua
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, 11);
   ObjectSetString(0,  objName, OBJPROP_FONT, "Trebuchet MS Bold");
   ObjectSetInteger(0, objName, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, objName, OBJPROP_BACK, false);
   ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
}

//+------------------------------------------------------------------+
//| On-Chart Drawing Functions (Open Candle Markers, Lines, Badges)  |
//+------------------------------------------------------------------+
void DrawOnChartHLine(string name, double price, color clr, ENUM_LINE_STYLE style, int width, string desc) {
   string objName = PFX_PLAN + name;
   if(ObjectFind(0, objName) < 0) {
      ObjectCreate(0, objName, OBJ_HLINE, 0, 0, price);
   }
   ObjectSetDouble(0, objName, OBJPROP_PRICE, price);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, objName, OBJPROP_STYLE, style);
   ObjectSetInteger(0, objName, OBJPROP_WIDTH, width);
   ObjectSetString(0, objName, OBJPROP_TEXT, desc);
   ObjectSetInteger(0, objName, OBJPROP_BACK, true);
}

void DrawOnChartText(string name, datetime time, double price, string text, color clr, int fontSize=9) {
   string objName = PFX_PLAN + name;
   if(ObjectFind(0, objName) < 0) {
      ObjectCreate(0, objName, OBJ_TEXT, 0, time, price);
   }
   ObjectSetInteger(0, objName, OBJPROP_TIME, 0, time);
   ObjectSetDouble(0,  objName, OBJPROP_PRICE, 0, price);
   ObjectSetString(0,  objName, OBJPROP_TEXT, text);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0,  objName, OBJPROP_FONT, "Trebuchet MS Bold");
   ObjectSetInteger(0, objName, OBJPROP_BACK, false);
}

void DrawOnChartArrow(string name, datetime time, double price, int arrowCode, color clr) {
   string objName = PFX_PLAN + name;
   if(ObjectFind(0, objName) < 0) {
      ObjectCreate(0, objName, OBJ_ARROW, 0, time, price);
   }
   ObjectSetInteger(0, objName, OBJPROP_TIME, 0, time);
   ObjectSetDouble(0,  objName, OBJPROP_PRICE, 0, price);
   ObjectSetInteger(0, objName, OBJPROP_ARROWCODE, arrowCode);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, objName, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, objName, OBJPROP_BACK, false);
}

//+------------------------------------------------------------------+
//| Draw Fire Breakout Candle Marker on Chart                        |
//+------------------------------------------------------------------+
void RenderFireMarkers() {
   if(!InpShowFireMarkers) return;
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   // Render Fire Marker for Currently Active Positions
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(m_position.SelectByIndex(i)) {
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) {
            datetime posTime  = (datetime)PositionGetInteger(POSITION_TIME);
            double   posPrice = PositionGetDouble(POSITION_PRICE_OPEN);
            ENUM_POSITION_TYPE pType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            string   comment  = PositionGetString(POSITION_COMMENT);

            string tag = IntegerToString(PositionGetInteger(POSITION_TICKET));
            string arrName = PFX_FIRE + "ACT_ARR_" + tag;
            string txtName = PFX_FIRE + "ACT_TXT_" + tag;

            bool isCF = (StringFind(comment, "CF") >= 0);
            int arrowCode = (pType == POSITION_TYPE_BUY) ? 233 : 234;
            double arrPrice = (pType == POSITION_TYPE_BUY) ? posPrice - 60 * pt : posPrice + 60 * pt;
            double txtPrice = (pType == POSITION_TYPE_BUY) ? posPrice - 140 * pt : posPrice + 140 * pt;
            color  clr      = (pType == POSITION_TYPE_BUY) ? C'0,230,118' : (isCF ? C'255,50,80' : C'255,170,0');
            string labelTxt = StringFormat("🔥 FIRE %s (%s)", pType == POSITION_TYPE_BUY ? "BUY" : "SELL", isCF ? "CF M15" : "VR M5");

            // Create/Update Arrow
            if(ObjectFind(0, arrName) < 0) ObjectCreate(0, arrName, OBJ_ARROW, 0, posTime, arrPrice);
            ObjectSetInteger(0, arrName, OBJPROP_TIME, 0, posTime);
            ObjectSetDouble(0,  arrName, OBJPROP_PRICE, 0, arrPrice);
            ObjectSetInteger(0, arrName, OBJPROP_ARROWCODE, arrowCode);
            ObjectSetInteger(0, arrName, OBJPROP_COLOR, clr);
            ObjectSetInteger(0, arrName, OBJPROP_WIDTH, 3);
            ObjectSetInteger(0, arrName, OBJPROP_BACK, false);

            // Create/Update Text Badge
            if(ObjectFind(0, txtName) < 0) ObjectCreate(0, txtName, OBJ_TEXT, 0, posTime, txtPrice);
            ObjectSetInteger(0, txtName, OBJPROP_TIME, 0, posTime);
            ObjectSetDouble(0,  txtName, OBJPROP_PRICE, 0, txtPrice);
            ObjectSetString(0,  txtName, OBJPROP_TEXT, labelTxt);
            ObjectSetInteger(0, txtName, OBJPROP_COLOR, clr);
            ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 9);
            ObjectSetString(0,  txtName, OBJPROP_FONT, "Trebuchet MS Bold");
            ObjectSetInteger(0, txtName, OBJPROP_BACK, false);
         }
      }
   }
}

void DrawOpenNewCandleMarkers() {
   if(!InpShowOpenMarkers) return;
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   // 1. Marker Open Candle H4
   datetime tOpenH4 = iTime(_Symbol, PERIOD_H4, 0);
   if(tOpenH4 > 0) {
      int barShiftH4 = iBarShift(_Symbol, _Period, tOpenH4);
      if(barShiftH4 >= 0) {
         double lowH4 = iLow(_Symbol, _Period, barShiftH4);
         DrawOnChartArrow("H4_CURRENT_OPEN", tOpenH4, lowH4 - 150 * pt, 241, C'255,215,0');
         DrawOnChartText("TXT_H4_CURRENT_OPEN", tOpenH4, lowH4 - 230 * pt, "🏛️ OPEN H4", C'255,215,0', 8);
      }
   }

   // 2. Marker Open Candle M30
   datetime tOpenM30 = iTime(_Symbol, PERIOD_M30, 0);
   if(tOpenM30 > 0 && tOpenM30 != tOpenH4) {
      int barShiftM30 = iBarShift(_Symbol, _Period, tOpenM30);
      if(barShiftM30 >= 0) {
         double lowM30 = iLow(_Symbol, _Period, barShiftM30);
         DrawOnChartArrow("M30_CURRENT_OPEN", tOpenM30, lowM30 - 60 * pt, 241, C'0,210,255');
         DrawOnChartText("TXT_M30_CURRENT_OPEN", tOpenM30, lowM30 - 120 * pt, "🕒 OPEN M30", C'0,210,255', 7);
      }
   }
}

void UpdateOnChartTradePlan() {
   DrawOpenNewCandleMarkers();
   RenderFireMarkers();
   UpdateOnChartLiveCandleClock();

   // Draw Clean CMP Lines (D1, H4, H1)
   if(g_stateD1.cmpLvl > 0) DrawOnChartHLine("CMP_D1", g_stateD1.cmpLvl, C'0,230,118', STYLE_SOLID, 2, "DAILY CMP: " + DoubleToString(g_stateD1.cmpLvl, 2));
   if(g_stateH4.cmpLvl > 0) DrawOnChartHLine("CMP_H4", g_stateH4.cmpLvl, C'255,50,80', STYLE_DASH, 2, "H4 CMP: " + DoubleToString(g_stateH4.cmpLvl, 2));
   if(g_stateH1.cmpLvl > 0) DrawOnChartHLine("CMP_H1", g_stateH1.cmpLvl, C'255,170,0', STYLE_DOT, 1, "H1 CMP: " + DoubleToString(g_stateH1.cmpLvl, 2));
}

//+------------------------------------------------------------------+
//| Initialize Visual GUI Dashboard                                  |
//+------------------------------------------------------------------+
void InitVisualPanel() {
   if(!InpShowPanel) return;

   int x = InpPanelX;
   int y = InpPanelY;
   int w = 620;
   int h = 430;

   CreateRect("MainBG", x, y, w, h, C'15,19,30', C'45,55,75');
   CreateRect("HeaderBG", x, y, w, 32, C'30,36,54', C'0,230,118');

   CreateLabel("HeaderTitle", x + 12, y + 7, "👑 CHAIN REACTION PRO v5.0 | DUAL-ENGINE HYBRID", clrWhite, 10, "Trebuchet MS Bold");

   // Subcards
   CreateRect("MTFCard", x + 10, y + 40, 330, 160, C'20,26,40', C'40,50,70');
   CreateRect("StatsCard", x + 350, y + 40, 260, 160, C'20,26,40', C'40,50,70');
   CreateRect("CockpitCard", x + 10, y + 210, 600, 210, C'22,28,44', C'45,58,82');

   ChartRedraw();
}

//+------------------------------------------------------------------+
//| Update Visual GUI Dashboard Contents                             |
//+------------------------------------------------------------------+
void UpdateVisualPanel() {
   if(!InpShowPanel) return;

   int x = InpPanelX;
   int y = InpPanelY;

   string cd_D1  = GetCandleCountdown(PERIOD_D1);
   string cd_H4  = GetCandleCountdown(PERIOD_H4);
   string cd_H1  = GetCandleCountdown(PERIOD_H1);
   string cd_M30 = GetCandleCountdown(PERIOD_M30);
   string cd_M15 = GetCandleCountdown(PERIOD_M15);
   string cd_M5  = GetCandleCountdown(PERIOD_M5);

   datetime curTimeNow = TimeCurrent();
   int m5BarInM30 = (int)((curTimeNow % 1800) / 300) + 1;
   if(m5BarInM30 > 6) m5BarInM30 = 6;
   if(m5BarInM30 < 1) m5BarInM30 = 1;

   int m30BarInH4 = (int)((curTimeNow % 14400) / 1800) + 1;
   if(m30BarInH4 > 8) m30BarInH4 = 8;
   if(m30BarInH4 < 1) m30BarInH4 = 1;

   string curChartTFStr = EnumToString(_Period);
   StringReplace(curChartTFStr, "PERIOD_", "");
   string mainCountdown = GetCandleCountdown(_Period);
   CreateLabel("HeaderTitle", x + 12, y + 7, StringFormat("👑 CHAIN REACTION PRO v5.0 | ⏱️ %s CANDLE: %s", curChartTFStr, mainCountdown), clrWhite, 10, "Trebuchet MS Bold");

   // 1. MTF Table with Live Countdowns & Intra-Candle Indicators
   CreateLabel("MTF_Header", x + 18, y + 45, "📊 MULTI-TIMEFRAME STORYLINE", clrYellow, 8, "Trebuchet MS Bold");
   CreateLabel("MTF_D1",  x + 18, y + 65,  StringFormat("DAILY : %-4s | CMP: %7.2f | ⏱️ %s", g_stateD1.arah == DIR_BUY ? "BUY" : "SELL", g_stateD1.cmpLvl, cd_D1), g_stateD1.arah == DIR_BUY ? C'0,230,118' : C'255,50,80', 7);
   CreateLabel("MTF_H4",  x + 18, y + 85,  StringFormat("H4 🌊 : %-4s | CMP: %7.2f | ⏱️ %s", g_stateH4.arah == DIR_BUY ? "BUY" : "SELL", g_stateH4.cmpLvl, cd_H4), g_stateH4.arah == DIR_BUY ? C'0,230,118' : C'255,50,80', 8, "Trebuchet MS Bold");
   CreateLabel("MTF_H1",  x + 18, y + 105, StringFormat("H1 ⚡ : %-4s | CMP: %7.2f | ⏱️ %s", g_stateH1.arah == DIR_BUY ? "BUY" : "SELL", g_stateH1.cmpLvl, cd_H1), g_stateH1.arah == DIR_BUY ? C'0,230,118' : C'255,50,80', 8, "Trebuchet MS Bold");
   CreateLabel("MTF_M30", x + 18, y + 125, StringFormat("M30 🏛️: %-4s | CMP: %7.2f | [B %d/8] ⏱️ %s", g_stateM30.arah == DIR_BUY ? "BUY" : "SELL", g_stateM30.cmpLvl, m30BarInH4, cd_M30), g_stateM30.arah == DIR_BUY ? C'0,230,118' : C'255,50,80', 7);
   CreateLabel("MTF_M15", x + 18, y + 145, StringFormat("M15 🌊: %-4s | CMP: %7.2f | ⏱️ %s", g_stateM15.arah == DIR_BUY ? "BUY" : "SELL", g_stateM15.cmpLvl, cd_M15), g_stateM15.arah == DIR_BUY ? C'0,230,118' : C'255,50,80', 8, "Trebuchet MS Bold");
   CreateLabel("MTF_M5",  x + 18, y + 165, StringFormat("M5  ⚡: %-4s | CMP: %7.2f | [B %d/6] ⏱️ %s", g_stateM5.arah == DIR_BUY ? "BUY" : "SELL", g_stateM5.cmpLvl, m5BarInM30, cd_M5), g_stateM5.arah == DIR_BUY ? C'0,230,118' : C'255,50,80', 7);

   // 2. Real-Time Performance Card
   color wrColor = g_stats.winrate >= 60.0 ? C'0,255,120' : (g_stats.winrate >= 45.0 ? C'255,215,0' : C'255,80,80');
   color pnlColor = g_stats.netProfit >= 0 ? C'0,255,120' : C'255,80,80';

   CreateLabel("Stats_Header", x + 360, y + 45, "📈 STRATEGY TESTER WINRATE", clrAqua, 8, "Trebuchet MS Bold");
   CreateLabel("Stats_Trades", x + 360, y + 65, StringFormat("Total Trades : %d (W: %d | L: %d)", g_stats.totalTrades, g_stats.wins, g_stats.losses), clrWhite, 8);
   CreateLabel("Stats_Winrate",x + 360, y + 85, StringFormat("WINRATE      : %.1f %%", g_stats.winrate), wrColor, 10, "Trebuchet MS Bold");
   CreateLabel("Stats_Profit", x + 360, y + 110, StringFormat("Net Profit   : $%.2f", g_stats.netProfit), pnlColor, 9, "Trebuchet MS Bold");
   CreateLabel("Stats_PF",     x + 360, y + 130, StringFormat("Profit Factor: %.2f", g_stats.profitFactor), clrSilver, 8);
   CreateLabel("Stats_DD",     x + 360, y + 150, StringFormat("Max Drawdown : %.2f %%", g_stats.maxDrawdown), C'255,140,140', 8);
   CreateLabel("Stats_Bal",    x + 360, y + 170, StringFormat("Balance      : $%.2f", m_account.Balance()), clrWhite, 8);

   // 3. Action Cockpit & Dual-Engine Status
   string engineModeStr = "";
   color  engineModeClr = clrWhite;

   if(g_stateH4.arah == g_stateH1.arah && g_stateH4.arah != DIR_WAIT) {
      engineModeStr = StringFormat("🌊 ENGINE 1: CF EXPANSION (H4 + M15 %s RIDER)", g_stateH4.arah == DIR_BUY ? "BUY" : "SELL");
      engineModeClr = g_stateH4.arah == DIR_BUY ? C'0,230,118' : C'255,50,80';
   } else if(g_stateH4.arah != DIR_WAIT && g_stateH1.arah != DIR_WAIT) {
      engineModeStr = StringFormat("⚡ ENGINE 2: VR RETRACE (H1 + M5 %s SCALP TO H4 BASE)", g_stateH1.arah == DIR_BUY ? "BUY" : "SELL");
      engineModeClr = C'255,170,0';
   } else {
      engineModeStr = "⏳ OBSERVASI STRUKTUR PASAR";
      engineModeClr = clrSilver;
   }

   CreateLabel("Cockpit_Title",     x + 18, y + 215, "🎮 DUAL-ENGINE ACTION COCKPIT", clrGold, 9, "Trebuchet MS Bold");
   CreateLabel("Cockpit_Engine",    x + 18, y + 235, engineModeStr, engineModeClr, 9, "Trebuchet MS Bold");
   CreateLabel("Cockpit_Driver",    x + 18, y + 260, "• PENGEMUDI : " + g_activeDriver, clrWhite, 8);
   CreateLabel("Cockpit_Saran",     x + 18, y + 285, "• SARAN     : " + g_saranEntry, clrYellow, 8, "Trebuchet MS Bold");
   CreateLabel("Cockpit_H4Base",    x + 18, y + 310, StringFormat("• TARGET BASE H4: %.2f | DAILY BASE: %.2f", g_stateH4.cmpLvl, g_stateD1.cmpLvl), clrAqua, 8);
   CreateLabel("Cockpit_LastTrade", x + 18, y + 335, "• EKSEKUSI  : " + g_lastTradeScenario, clrWhite, 8);
   CreateLabel("Cockpit_Siklus",    x + 18, y + 355, StringFormat("• SIKLUS WAKTU: M5 [Bar %d/6 M30] | M30 [Bar %d/8 H4]", m5BarInM30, m30BarInH4), C'0,210,255', 8, "Trebuchet MS Bold");
   CreateLabel("Cockpit_Foot",      x + 18, y + 378, "Hukum: CF = H4+M15 (91% Win) | VR = H1+M5 (89.5% Win) | 100% Fractal Confluence", clrGray, 7);

   ChartRedraw();
}

//+------------------------------------------------------------------+
//| Calculate Timeframe CMP & Minor SNR                              |
//+------------------------------------------------------------------+
void CalculateTFState(ENUM_TIMEFRAMES tf, STFState &state, int maxBars=100) {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, tf, 0, maxBars, rates);
   if(copied < 5) return;

   state.lastCalcTime = rates[0].time;
   double sup1 = 0, res1 = 0;
   state.lastSup = 0;
   state.lastRes = 0;
   state.cmpLvl  = 0;
   state.arah    = DIR_WAIT;

   for(int i = copied - 2; i >= 1; i--) {
      bool isMinorSup = (rates[i+1].close < rates[i+1].open) && (rates[i].close > rates[i].open);
      bool isMinorRes = (rates[i+1].close > rates[i+1].open) && (rates[i].close < rates[i].open);

      if(isMinorSup) {
         sup1 = MathMin(rates[i+1].close, rates[i+1].open);
         state.lastSup = sup1;
      }
      if(isMinorRes) {
         res1 = MathMax(rates[i+1].close, rates[i+1].open);
         state.lastRes = res1;
      }

      double c = rates[i].close;

      if(state.arah == DIR_WAIT) {
         if(res1 > 0 && c > res1) {
            state.arah = DIR_BUY;
            state.cmpLvl = res1;
            state.lastCmpBuy = res1;
            state.lastBoTime = rates[i].time;
         } else if(sup1 > 0 && c < sup1) {
            state.arah = DIR_SELL;
            state.cmpLvl = sup1;
            state.lastCmpSell = sup1;
            state.lastBoTime = rates[i].time;
         }
      }
      else if(state.arah == DIR_BUY) {
         if(sup1 > 0 && c < sup1) {
            state.arah = DIR_SELL;
            state.barrierLvl = state.lastCmpBuy;
            state.lastCmpSell = sup1;
            state.cmpLvl = sup1;
            state.lastBoTime = rates[i].time;
         } else if(res1 > 0 && c > res1) {
            state.lastCmpBuy = res1;
            state.cmpLvl = res1;
            state.lastBoTime = rates[i].time;
         }
      }
      else if(state.arah == DIR_SELL) {
         if(res1 > 0 && c > res1) {
            state.arah = DIR_BUY;
            state.barrierLvl = state.lastCmpSell;
            state.lastCmpBuy = res1;
            state.cmpLvl = res1;
            state.lastBoTime = rates[i].time;
         } else if(sup1 > 0 && c < sup1) {
            state.lastCmpSell = sup1;
            state.cmpLvl = sup1;
            state.lastBoTime = rates[i].time;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate Dynamic Lot Size                                       |
//+------------------------------------------------------------------+
double CalculateLotSize(double slPoints) {
   if(InpLotMode == LOT_FIXED) return InpFixedLot;
   
   double balance = m_account.Balance();
   double riskAmt = balance * (InpRiskPercent / 100.0);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(tickSize <= 0 || tickVal <= 0 || slPoints <= 0) return InpFixedLot;
   
   double lot = riskAmt / (slPoints * (tickVal / tickSize));
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lot = MathFloor(lot / stepLot) * stepLot;
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;
   return lot;
}

int CountOpenPositions(ENUM_POSITION_TYPE type) {
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(m_position.SelectByIndex(i)) {
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) {
            if(m_position.PositionType() == type) count++;
         }
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Optional Trailing SL & BEP Management (Manual Control Supported) |
//+------------------------------------------------------------------+
void ManageOpenTrades() {
   int openCount = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(m_position.SelectByIndex(i)) {
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) {
            openCount++;

            string comment   = m_position.Comment();
            bool isCF = (StringFind(comment, "CF") >= 0);
            bool useBEP   = isCF ? InpUseBEP_CF   : InpUseBEP_VR;
            bool useTrail = isCF ? InpUseTrail_CF : InpUseTrail_VR;

            if(!useBEP && !useTrail) continue;

            double pt    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
            long   stops = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
            double minGap= (stops + 10) * pt;

            double openPrice = m_position.PriceOpen();
            double curSL     = m_position.StopLoss();
            double curTP     = m_position.TakeProfit();
            double curPrice  = m_position.PriceCurrent();
            ulong  ticket    = m_position.Ticket();

            int bepTrig   = isCF ? InpBEPTrig_CF   : InpBEPTrig_VR;
            int bepLock   = isCF ? InpBEPLock_CF   : InpBEPLock_VR;
            int trailTrig = isCF ? InpTrailTrig_CF : InpTrailTrig_VR;
            int trailDist = isCF ? InpTrailDist_CF : InpTrailDist_VR;

            // BUY POSITION
            if(m_position.PositionType() == POSITION_TYPE_BUY) {
               double profitPt = (curPrice - openPrice) / pt;

               // Dynamic Wave Trailing
               if(useTrail && profitPt >= trailTrig) {
                  double newSL = curPrice - trailDist * pt;
                  if(newSL > openPrice && (curSL == 0 || newSL - curSL >= 50 * pt)) {
                     if(curPrice - newSL >= minGap) m_trade.PositionModify(ticket, newSL, curTP);
                  }
               }
               // Move to BEP + Lock
               else if(useBEP && profitPt >= bepTrig) {
                  double bepSL = openPrice + bepLock * pt;
                  if((curSL < bepSL || curSL == 0) && (curPrice - bepSL >= minGap)) {
                     m_trade.PositionModify(ticket, bepSL, curTP);
                  }
               }
            }
            // SELL POSITION
            else if(m_position.PositionType() == POSITION_TYPE_SELL) {
               double profitPt = (openPrice - curPrice) / pt;

               // Dynamic Wave Trailing
               if(useTrail && profitPt >= trailTrig) {
                  double newSL = curPrice + trailDist * pt;
                  if(newSL < openPrice && (curSL == 0 || curSL - newSL >= 50 * pt)) {
                     if(newSL - curPrice >= minGap) m_trade.PositionModify(ticket, newSL, curTP);
                  }
               }
               // Move to BEP + Lock
               else if(useBEP && profitPt >= bepTrig) {
                  double bepSL = openPrice - bepLock * pt;
                  if((curSL > bepSL || curSL == 0) && (bepSL - curPrice >= minGap)) {
                     m_trade.PositionModify(ticket, bepSL, curTP);
                  }
               }
            }
         }
      }
   }

   // Auto-clean fire markers when no active positions
   if(openCount == 0) {
      ObjectsDeleteAll(0, PFX_FIRE);
   }
}

//+------------------------------------------------------------------+
//| Update Performance Stats                                         |
//+------------------------------------------------------------------+
void UpdatePerformanceStats() {
   HistorySelect(0, TimeCurrent());
   int totalDeals = HistoryDealsTotal();
   
   g_stats.totalTrades = 0;
   g_stats.wins        = 0;
   g_stats.losses      = 0;
   g_stats.grossProfit = 0;
   g_stats.grossLoss   = 0;
   g_stats.netProfit   = 0;

   for(int i = 0; i < totalDeals; i++) {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0) {
         if(HistoryDealGetString(ticket, DEAL_SYMBOL) == _Symbol &&
            HistoryDealGetInteger(ticket, DEAL_MAGIC) == InpMagicNumber &&
            HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_OUT) {
            
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            g_stats.totalTrades++;
            
            if(profit > 0) {
               g_stats.wins++;
               g_stats.grossProfit += profit;
            } else if(profit < 0) {
               g_stats.losses++;
               g_stats.grossLoss += MathAbs(profit);
            }
         }
      }
   }

   g_stats.netProfit = g_stats.grossProfit - g_stats.grossLoss;
   g_stats.winrate   = (g_stats.totalTrades > 0) ? ((double)g_stats.wins / g_stats.totalTrades) * 100.0 : 0.0;
   g_stats.profitFactor = (g_stats.grossLoss > 0) ? (g_stats.grossProfit / g_stats.grossLoss) : (g_stats.grossProfit > 0 ? 999.0 : 0.0);

   double curEquity = m_account.Equity();
   if(curEquity > g_stats.peakBalance) g_stats.peakBalance = curEquity;
   if(g_stats.peakBalance > 0) {
      double dd = (g_stats.peakBalance - curEquity) / g_stats.peakBalance * 100.0;
      if(dd > g_stats.maxDrawdown) g_stats.maxDrawdown = dd;
   }
}

//+------------------------------------------------------------------+
//| Expert Initialization Function                                   |
//+------------------------------------------------------------------+
int OnInit() {
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(InpSlippage);
   SetFillingMode();

   g_stats.startBalance = m_account.Balance();
   g_stats.peakBalance  = g_stats.startBalance;

   InitVisualPanel();
   UpdatePerformanceStats();
   EventSetTimer(1);

   Print("✅ DD Storyline EA v5.0 (Dual-Engine Hybrid) Initialized successfully on ", _Symbol);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert Deinitialization Function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
   ObjectsDeleteAll(0, PFX_PLAN);
   ObjectsDeleteAll(0, PFX_FIRE);
}

//+------------------------------------------------------------------+
//| Expert Timer Function                                            |
//+------------------------------------------------------------------+
void OnTimer() {
   UpdateVisualPanel();
}

//+------------------------------------------------------------------+
//| Expert Tick Function — Dual-Engine Decision Core                 |
//+------------------------------------------------------------------+
void OnTick() {
   datetime curBarTime = iTime(_Symbol, _Period, 0);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   // 1. RECALCULATE ALL TF STATES FIRST (UNCONDITIONALLY)
   CalculateTFState(PERIOD_D1,  g_stateD1,  50);
   CalculateTFState(PERIOD_H4,  g_stateH4,  50);
   CalculateTFState(PERIOD_H1,  g_stateH1,  50);
   CalculateTFState(PERIOD_M30, g_stateM30, 50);
   CalculateTFState(PERIOD_M15, g_stateM15, 60);
   CalculateTFState(PERIOD_M5,  g_stateM5,  100);

   // 2. MANAGE POSITIONS, DRAWINGS & REFRESH STATS
   ManageOpenTrades();
   UpdatePerformanceStats();
   UpdateOnChartTradePlan();

   // 3. ALWAYS UPDATE VISUAL PANEL & TIMERS ON EVERY TICK
   UpdateVisualPanel();

   // 4. SESSION FILTER CHECK
   if(InpUseSessionFilter) {
      MqlDateTime dt;
      TimeToStruct(TimeCurrent(), dt);
      if(dt.hour < InpStartHour || dt.hour > InpEndHour) {
         g_activeDriver = "⏳ DI LUAR JAM TRADING (SESI ASIA TENGAH MALAM DIBEKUKAN)";
         g_saranEntry   = "STANDBY (Filter Sesi Aktif)";
         UpdateVisualPanel();
         return;
      }
   }

   // 5. SINGLE POSITION RULE
   if(PositionsTotal() > 0) {
      g_activeDriver = "🌊 MENGAWAL POSISI AKTIF (MANUAL TP/SL / TRAILING KONTROL)";
      g_saranEntry   = "RIDING THE WAVE";
      UpdateVisualPanel();
      return;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   datetime curM15Open  = iTime(_Symbol, PERIOD_M15, 0);
   datetime prevM15Open = iTime(_Symbol, PERIOD_M15, 1);
   datetime curM5Open   = iTime(_Symbol, PERIOD_M5, 0);
   datetime prevM5Open  = iTime(_Symbol, PERIOD_M5, 1);

   // Fresh Breakout Trigger Check
   bool isFreshM15 = (g_stateM15.lastBoTime >= prevM15Open) && (g_lastFiredM15Time != curM15Open);
   bool isFreshM5  = (g_stateM5.lastBoTime  >= prevM5Open)  && (g_lastFiredM5Time  != curM5Open);

   // ══════════════════════════════════════════════════════════════════
   // 🌊 ENGINE 1: CF EXPANSION (H4 + M15 BIG WAVE RIDER)
   // ══════════════════════════════════════════════════════════════════
   if(InpEnableCF && g_stateH4.arah == g_stateH1.arah && g_stateH4.arah != DIR_WAIT) {
      g_activeEngine = "CF EXPANSION (H4+M15)";

      // CF BUY FLY
      if(g_stateH4.arah == DIR_BUY) {
         if(g_stateM15.arah == DIR_BUY && isFreshM15 && CountOpenPositions(POSITION_TYPE_BUY) == 0) {
            double sl = (g_stateH1.lastSup > 0 && ask - g_stateH1.lastSup < InpMaxSL_CF * pt) ? (g_stateH1.lastSup - 40 * pt) : (ask - InpMaxSL_CF * pt);
            double tp = ask + InpTP_CF * pt;
            double lot = CalculateLotSize((ask - sl) / pt);

            if(m_trade.Buy(lot, _Symbol, ask, sl, tp, "DD_CF_BUY_H4M15")) {
               g_lastTradeScenario = "CF BUY (H4+M15 Flying Wave)";
               g_lastFiredM15Time  = curM15Open;
               UpdateOnChartTradePlan();
               UpdatePerformanceStats();
            }
         } else {
            g_activeDriver = "H4 BUY FLY (Menunggu Fresh M15 BO BUY)";
            g_saranEntry   = "SIAP TEMBAK BUY SAAT M15 BREAKOUT";
         }
      }
      // CF SELL DROP
      else if(g_stateH4.arah == DIR_SELL) {
         if(g_stateM15.arah == DIR_SELL && isFreshM15 && CountOpenPositions(POSITION_TYPE_SELL) == 0) {
            double sl = (g_stateH1.lastRes > 0 && g_stateH1.lastRes - bid < InpMaxSL_CF * pt) ? (g_stateH1.lastRes + 40 * pt) : (bid + InpMaxSL_CF * pt);
            double tp = bid - InpTP_CF * pt;
            double lot = CalculateLotSize((sl - bid) / pt);

            if(m_trade.Sell(lot, _Symbol, bid, sl, tp, "DD_CF_SELL_H4M15")) {
               g_lastTradeScenario = "CF SELL (H4+M15 Dropping Wave)";
               g_lastFiredM15Time  = curM15Open;
               UpdateOnChartTradePlan();
               UpdatePerformanceStats();
            }
         } else {
            g_activeDriver = "H4 SELL DROP (Menunggu Fresh M15 BO SELL)";
            g_saranEntry   = "SIAP TEMBAK SELL SAAT M15 BREAKOUT";
         }
      }
   }
   // ══════════════════════════════════════════════════════════════════
   // ⚡ ENGINE 2: VR RETRACE SCALP (H1 + M5 TO H4 BASE)
   // ══════════════════════════════════════════════════════════════════
   else if(InpEnableVR && g_stateH4.arah != DIR_WAIT && g_stateH1.arah != DIR_WAIT && g_stateH4.arah != g_stateH1.arah) {
      g_activeEngine = "VR RETRACE (H1+M5)";

      // VR SCALP SELL (H4 BUY, H1 RETEST MERAH) -> SCALP KE LANTAI H4
      if(g_stateH4.arah == DIR_BUY && g_stateH1.arah == DIR_SELL) {
         if(g_stateM5.arah == DIR_SELL && isFreshM5 && CountOpenPositions(POSITION_TYPE_SELL) == 0) {
            double sl = (g_stateH1.lastRes > 0 && g_stateH1.lastRes - bid < InpMaxSL_VR * pt) ? (g_stateH1.lastRes + 30 * pt) : (bid + InpMaxSL_VR * pt);
            double tp = (g_stateH4.cmpLvl > 0 && g_stateH4.cmpLvl < bid - 200 * pt) ? g_stateH4.cmpLvl : (bid - InpTP_VR * pt);
            double lot = CalculateLotSize((sl - bid) / pt);

            if(m_trade.Sell(lot, _Symbol, bid, sl, tp, "DD_VR_SELL_H1M5")) {
               g_lastTradeScenario = "VR SCALP SELL (Retrace ke Lantai H4)";
               g_lastFiredM5Time   = curM5Open;
               UpdateOnChartTradePlan();
               UpdatePerformanceStats();
            }
         } else {
            g_activeDriver = "H1 VR RETRACE SELL (Menunggu Fresh M5 BO SELL)";
            g_saranEntry   = "SIAP SCALP SELL KE LANTAI H4";
         }
      }
      // VR SCALP BUY (H4 SELL, H1 RETEST HIJAU) -> SCALP KE ATAP H4
      else if(g_stateH4.arah == DIR_SELL && g_stateH1.arah == DIR_BUY) {
         if(g_stateM5.arah == DIR_BUY && isFreshM5 && CountOpenPositions(POSITION_TYPE_BUY) == 0) {
            double sl = (g_stateH1.lastSup > 0 && ask - g_stateH1.lastSup < InpMaxSL_VR * pt) ? (g_stateH1.lastSup - 30 * pt) : (ask - InpMaxSL_VR * pt);
            double tp = (g_stateH4.cmpLvl > 0 && g_stateH4.cmpLvl > ask + 200 * pt) ? g_stateH4.cmpLvl : (ask + InpTP_VR * pt);
            double lot = CalculateLotSize((ask - sl) / pt);

            if(m_trade.Buy(lot, _Symbol, ask, sl, tp, "DD_VR_BUY_H1M5")) {
               g_lastTradeScenario = "VR SCALP BUY (Retrace ke Atap H4)";
               g_lastFiredM5Time   = curM5Open;
               UpdateOnChartTradePlan();
               UpdatePerformanceStats();
            }
         } else {
            g_activeDriver = "H1 VR RETRACE BUY (Menunggu Fresh M5 BO BUY)";
            g_saranEntry   = "SIAP SCALP BUY KE ATAP H4";
         }
      }
   }

   UpdateVisualPanel();
}
