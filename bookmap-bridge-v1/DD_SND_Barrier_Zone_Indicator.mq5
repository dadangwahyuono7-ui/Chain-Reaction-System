//+------------------------------------------------------------------+
//| DD_SND_Barrier_Zone_Indicator.mq5                                |
//| Multi-TF S&D Barrier Zone & Bookmap Real Wall Validator (V1.00)  |
//| Copyright 2026, Commander Dadang Wahyuono                        |
//|                                                                  |
//| Maps S&D structural zones (DBD, RBR, SBR, RBS, A/V-Shapes)       |
//| across D1, H4, H1, M30 and validates with real Bookmap Walls!    |
//+------------------------------------------------------------------+
#property copyright "Commander Dadang Wahyuono"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

#property indicator_label1  "SND Fractal High"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrRed
#property indicator_width1  2

#property indicator_label2  "SND Fractal Low"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrLime
#property indicator_width2  2

//--- Inputs
input group "=== PILIHAN TIMEFRAME S&D ==="
input bool   InpShowD1           = true;    // Tampilkan Zona D1 (Root Makro, Skor 95)
input bool   InpShowH4           = true;    // Tampilkan Zona H4 (Master Trend, Skor 85)
input bool   InpShowH1           = true;    // Tampilkan Zona H1 (Taktikal, Skor 70)
input bool   InpShowM30          = true;    // Tampilkan Zona M30 (Scalp Master, Skor 55)

input group "=== PENGATURAN ZONA ==="
input int    InpMaxZonesPerSide  = 5;       // Maksimal Zona per Sisi (S1..S5 & D1..D5)
input double InpMinZoneGapUsd    = 1.50;    // Jarak Minimal Antar Kotak (Anti-Tumpang Tindih)
input bool   InpMatchBookmap     = true;    // Validasi Tembok Likuiditas Asli Bookmap
input bool   InpShowLabels       = true;    // Tampilkan Label Teks Info di Kotak
input int    InpBoxExtendBars    = 25;      // Panjang Kotak ke Kanan (Bars)

input group "=== WARNA TEMA CYBERPUNK ==="
input color  InpSupplyColor      = C'255,51,75';   // Warna Garis Supply (Merah Neon)
input color  InpSupplyBgColor    = C'50,12,18';    // Warna Isi Kotak Supply
input color  InpDemandColor      = C'0,230,118';   // Warna Garis Demand (Hijau Neon)
input color  InpDemandBgColor    = C'10,40,22';    // Warna Isi Kotak Demand

#define OBJ_PREFIX "DD_SND_"
#define MAX_QUEUE  40

struct BarrierItem
{
   string dir;       // BUY / SELL
   double level;     // Level harga
   double lo;
   double hi;
   double score;     // 95=D1, 85=H4, 70=H1, 55=M30
   string tf;        // D1 / H4 / H1 / M30
   int    retest;
   double bmWallLot;
};

// Indicator plot buffers
double ArrowHighBuffer[];
double ArrowLowBuffer[];

// Indicator handles
int g_hD1 = INVALID_HANDLE;
int g_hH4 = INVALID_HANDLE;
int g_hH1 = INVALID_HANDLE;
int g_hM30 = INVALID_HANDLE;

// Bookmap Bridge Cache
bool   g_bmOnline = false;
double g_bmPrice = 0.0;
double g_bmBidPx[10], g_bmBidSz[10];
double g_bmAskPx[10], g_bmAskSz[10];

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
{
   SetIndexBuffer(0, ArrowHighBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, ArrowLowBuffer, INDICATOR_DATA);

   PlotIndexSetInteger(0, PLOT_ARROW, 234); // Down arrow
   PlotIndexSetInteger(1, PLOT_ARROW, 233); // Up arrow
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   // Load CMP Indicator handles for all 4 TFs
   g_hD1  = iCustom(_Symbol, PERIOD_D1,  "DD_CMP_Indicator");
   g_hH4  = iCustom(_Symbol, PERIOD_H4,  "DD_CMP_Indicator");
   g_hH1  = iCustom(_Symbol, PERIOD_H1,  "DD_CMP_Indicator");
   g_hM30 = iCustom(_Symbol, PERIOD_M30, "DD_CMP_Indicator");

   EventSetTimer(1);
   IndicatorSetString(INDICATOR_SHORTNAME, "DD S&D Barrier Zone Master");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                       |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectsDeleteAll(0, OBJ_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Read Bookmap live wall depth from common file                     |
//+------------------------------------------------------------------+
void ReadBookmapLiveSignal()
{
   if(!InpMatchBookmap) { g_bmOnline = false; return; }
   int handle = FileOpen("bookmap_live_signal.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) { g_bmOnline = false; return; }

   double price = StringToDouble(FileReadString(handle));
   if(price <= 0) { FileClose(handle); g_bmOnline = false; return; }

   // Skip unneeded fields to reach depth arrays
   for(int i = 0; i < 18; i++) FileReadString(handle);

   for(int i = 0; i < 10; i++) g_bmBidPx[i] = StringToDouble(FileReadString(handle));
   for(int i = 0; i < 10; i++) g_bmBidSz[i] = StringToDouble(FileReadString(handle));
   for(int i = 0; i < 10; i++) g_bmAskPx[i] = StringToDouble(FileReadString(handle));
   for(int i = 0; i < 10; i++) g_bmAskSz[i] = StringToDouble(FileReadString(handle));

   g_bmPrice = price;
   g_bmOnline = true;
   FileClose(handle);
}

double GetBookmapWallInZone(bool isDemand, double lo, double hi)
{
   if(!g_bmOnline || g_bmPrice <= 0) return 0.0;
   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bmPrice;
   double totalLot = 0.0;

   if(isDemand)
   {
      for(int i = 0; i < 10; i++)
      {
         if(g_bmBidPx[i] > 0 && g_bmBidSz[i] > 0)
         {
            double mt5Px = g_bmBidPx[i] + offset;
            if(mt5Px >= (lo - 1.0) && mt5Px <= (hi + 1.0)) totalLot += g_bmBidSz[i];
         }
      }
      if(totalLot == 0.0 && g_bmBidSz[0] > 0)
      {
         double bestBid = g_bmBidPx[0] + offset;
         if(bestBid >= lo - 2.0 && bestBid <= hi + 2.0) totalLot = g_bmBidSz[0];
      }
   }
   else
   {
      for(int i = 0; i < 10; i++)
      {
         if(g_bmAskPx[i] > 0 && g_bmAskSz[i] > 0)
         {
            double mt5Px = g_bmAskPx[i] + offset;
            if(mt5Px >= (lo - 1.0) && mt5Px <= (hi + 1.0)) totalLot += g_bmAskSz[i];
         }
      }
      if(totalLot == 0.0 && g_bmAskSz[0] > 0)
      {
         double bestAsk = g_bmAskPx[0] + offset;
         if(bestAsk >= lo - 2.0 && bestAsk <= hi + 2.0) totalLot = g_bmAskSz[0];
      }
   }
   return totalLot;
}

//+------------------------------------------------------------------+
//| Extract S&D structural levels from CMP indicator handle          |
//+------------------------------------------------------------------+
void ExtractTFZones(int handle, ENUM_TIMEFRAMES tf, string tfName, double score, double tol, BarrierItem &outList[])
{
   if(handle == INVALID_HANDLE || BarsCalculated(handle) < 5) return;
   int n = 2000;
   double ctBuf[], dirBuf[], lvlBuf[], supBuf[], resBuf[];
   if(CopyBuffer(handle, 3, 0, n, ctBuf) <= 0) return;
   if(CopyBuffer(handle, 2, 0, n, dirBuf) <= 0) return;
   if(CopyBuffer(handle, 4, 0, n, lvlBuf) <= 0) return;
   CopyBuffer(handle, 5, 0, n, supBuf);
   CopyBuffer(handle, 6, 0, n, resBuf);

   int have = MathMin(MathMin(ArraySize(ctBuf), ArraySize(dirBuf)), ArraySize(lvlBuf));
   if(have < 2) return;

   BarrierItem found[];
   double prevRes = 0.0, prevSup = 0.0;
   double prevCt = ctBuf[have - 1];

   for(int i = have - 2; i >= 0 && ArraySize(found) < MAX_QUEUE; i--)
   {
      // 1. A-shape Minor Resistance (Supply)
      if(ArraySize(resBuf) > i && resBuf[i] > 0 && resBuf[i] != prevRes)
      {
         int fn = ArraySize(found);
         if(fn < MAX_QUEUE)
         {
            ArrayResize(found, fn + 1);
            found[fn].dir = "SELL";
            found[fn].level = resBuf[i];
            found[fn].lo = resBuf[i] - tol;
            found[fn].hi = resBuf[i] + tol;
            found[fn].score = score;
            found[fn].tf = tfName;
            found[fn].retest = 0;
         }
         prevRes = resBuf[i];
      }
      // 2. V-shape Minor Support (Demand)
      if(ArraySize(supBuf) > i && supBuf[i] > 0 && supBuf[i] != prevSup)
      {
         int fn = ArraySize(found);
         if(fn < MAX_QUEUE)
         {
            ArrayResize(found, fn + 1);
            found[fn].dir = "BUY";
            found[fn].level = supBuf[i];
            found[fn].lo = supBuf[i] - tol;
            found[fn].hi = supBuf[i] + tol;
            found[fn].score = score;
            found[fn].tf = tfName;
            found[fn].retest = 0;
         }
         prevSup = supBuf[i];
      }
   }

   // Apply SBR / RBS conversion based on current bar close
   double c = iClose(_Symbol, tf, 1);
   for(int i = 0; i < ArraySize(found); i++)
   {
      bool broken = (found[i].dir == "BUY") ? (c < found[i].level - tol) : (c > found[i].level + tol);
      if(broken)
      {
         found[i].dir = (found[i].dir == "BUY") ? "SELL" : "BUY";
      }

      int curSz = ArraySize(outList);
      ArrayResize(outList, curSz + 1);
      outList[curSz] = found[i];
   }
}

//+------------------------------------------------------------------+
//| Draw S&D Boxes on the MT5 Chart                                  |
//+------------------------------------------------------------------+
void RenderSNDBoxes()
{
   ReadBookmapLiveSignal();

   BarrierItem allItems[];
   if(InpShowD1)  ExtractTFZones(g_hD1,  PERIOD_D1,  "D1",  95.0, 2.0, allItems);
   if(InpShowH4)  ExtractTFZones(g_hH4,  PERIOD_H4,  "H4",  85.0, 2.0, allItems);
   if(InpShowH1)  ExtractTFZones(g_hH1,  PERIOD_H1,  "H1",  70.0, 1.5, allItems);
   if(InpShowM30) ExtractTFZones(g_hM30, PERIOD_M30, "M30", 55.0, 1.0, allItems);

   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Partition into Supply (above price) and Demand (below price)
   BarrierItem rawSupply[], rawDemand[];
   for(int i = 0; i < ArraySize(allItems); i++)
   {
      if(allItems[i].lo >= curPrice + 0.20)
      {
         int s = ArraySize(rawSupply);
         ArrayResize(rawSupply, s + 1);
         rawSupply[s] = allItems[i];
      }
      else if(allItems[i].hi <= curPrice - 0.20)
      {
         int d = ArraySize(rawDemand);
         ArrayResize(rawDemand, d + 1);
         rawDemand[d] = allItems[i];
      }
   }

   // Sort Supply ascending (lowest first: S1, S2...)
   for(int a = 1; a < ArraySize(rawSupply); a++)
   {
      BarrierItem k = rawSupply[a];
      int b = a - 1;
      while(b >= 0 && rawSupply[b].lo > k.lo) { rawSupply[b+1] = rawSupply[b]; b--; }
      rawSupply[b+1] = k;
   }

   // Sort Demand descending (highest first: D1, D2...)
   for(int a = 1; a < ArraySize(rawDemand); a++)
   {
      BarrierItem k = rawDemand[a];
      int b = a - 1;
      while(b >= 0 && rawDemand[b].hi < k.hi) { rawDemand[b+1] = rawDemand[b]; b--; }
      rawDemand[b+1] = k;
   }

   // Filter anti-overlapping with InpMinZoneGapUsd
   BarrierItem finalSupply[], finalDemand[];
   for(int i = 0; i < ArraySize(rawSupply) && ArraySize(finalSupply) < InpMaxZonesPerSide; i++)
   {
      int fs = ArraySize(finalSupply);
      if(fs > 0 && rawSupply[i].lo < finalSupply[fs-1].hi + InpMinZoneGapUsd) continue;
      ArrayResize(finalSupply, fs + 1);
      finalSupply[fs] = rawSupply[i];
      finalSupply[fs].bmWallLot = GetBookmapWallInZone(false, rawSupply[i].lo, rawSupply[i].hi);
   }

   for(int i = 0; i < ArraySize(rawDemand) && ArraySize(finalDemand) < InpMaxZonesPerSide; i++)
   {
      int fd = ArraySize(finalDemand);
      if(fd > 0 && rawDemand[i].hi > finalDemand[fd-1].lo - InpMinZoneGapUsd) continue;
      ArrayResize(finalDemand, fd + 1);
      finalDemand[fd] = rawDemand[i];
      finalDemand[fd].bmWallLot = GetBookmapWallInZone(true, rawDemand[i].lo, rawDemand[i].hi);
   }

   datetime t1 = iTime(_Symbol, _Period, 0) - PeriodSeconds(_Period) * 80;
   datetime t2 = iTime(_Symbol, _Period, 0) + PeriodSeconds(_Period) * InpBoxExtendBars;

   // 1. Draw Supply Boxes (S1..SN)
   for(int i = 0; i < InpMaxZonesPerSide; i++)
   {
      string boxName = OBJ_PREFIX + "SUPPLY_BOX_" + IntegerToString(i+1);
      string txtName = OBJ_PREFIX + "SUPPLY_TXT_" + IntegerToString(i+1);

      if(i < ArraySize(finalSupply))
      {
         BarrierItem item = finalSupply[i];
         if(ObjectFind(0, boxName) < 0)
         {
            ObjectCreate(0, boxName, OBJ_RECTANGLE, 0, t1, item.hi, t2, item.lo);
            ObjectSetInteger(0, boxName, OBJPROP_COLOR, InpSupplyColor);
            ObjectSetInteger(0, boxName, OBJPROP_BGCOLOR, InpSupplyBgColor);
            ObjectSetInteger(0, boxName, OBJPROP_FILL, true);
            ObjectSetInteger(0, boxName, OBJPROP_BACK, true);
            ObjectSetInteger(0, boxName, OBJPROP_WIDTH, i == 0 ? 2 : 1);
         }
         else
         {
            ObjectMove(0, boxName, 0, t1, item.hi);
            ObjectMove(0, boxName, 1, t2, item.lo);
         }

         if(InpShowLabels)
         {
            string wallStr = (item.bmWallLot > 0) ? StringFormat(" • Ask Wall: %.0fL", item.bmWallLot) : "";
            string labelText = StringFormat("🔴 S%d [%s] (%.2f - %.2f)%s", i+1, item.tf, item.lo, item.hi, wallStr);

            if(ObjectFind(0, txtName) < 0)
            {
               ObjectCreate(0, txtName, OBJ_TEXT, 0, t1, item.hi);
               ObjectSetInteger(0, txtName, OBJPROP_COLOR, InpSupplyColor);
               ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 9);
               ObjectSetString(0, txtName, OBJPROP_FONT, "JetBrains Mono");
            }
            ObjectMove(0, txtName, 0, t1, item.hi);
            ObjectSetString(0, txtName, OBJPROP_TEXT, labelText);
         }
      }
      else
      {
         ObjectDelete(0, boxName);
         ObjectDelete(0, txtName);
      }
   }

   // 2. Draw Demand Boxes (D1..DN)
   for(int i = 0; i < InpMaxZonesPerSide; i++)
   {
      string boxName = OBJ_PREFIX + "DEMAND_BOX_" + IntegerToString(i+1);
      string txtName = OBJ_PREFIX + "DEMAND_TXT_" + IntegerToString(i+1);

      if(i < ArraySize(finalDemand))
      {
         BarrierItem item = finalDemand[i];
         if(ObjectFind(0, boxName) < 0)
         {
            ObjectCreate(0, boxName, OBJ_RECTANGLE, 0, t1, item.hi, t2, item.lo);
            ObjectSetInteger(0, boxName, OBJPROP_COLOR, InpDemandColor);
            ObjectSetInteger(0, boxName, OBJPROP_BGCOLOR, InpDemandBgColor);
            ObjectSetInteger(0, boxName, OBJPROP_FILL, true);
            ObjectSetInteger(0, boxName, OBJPROP_BACK, true);
            ObjectSetInteger(0, boxName, OBJPROP_WIDTH, i == 0 ? 2 : 1);
         }
         else
         {
            ObjectMove(0, boxName, 0, t1, item.hi);
            ObjectMove(0, boxName, 1, t2, item.lo);
         }

         if(InpShowLabels)
         {
            string wallStr = (item.bmWallLot > 0) ? StringFormat(" • Bid Wall: %.0fL", item.bmWallLot) : "";
            string labelText = StringFormat("🟢 D%d [%s] (%.2f - %.2f)%s", i+1, item.tf, item.lo, item.hi, wallStr);

            if(ObjectFind(0, txtName) < 0)
            {
               ObjectCreate(0, txtName, OBJ_TEXT, 0, t1, item.lo);
               ObjectSetInteger(0, txtName, OBJPROP_COLOR, InpDemandColor);
               ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 9);
               ObjectSetString(0, txtName, OBJPROP_FONT, "JetBrains Mono");
            }
            ObjectMove(0, txtName, 0, t1, item.lo);
            ObjectSetString(0, txtName, OBJPROP_TEXT, labelText);
         }
      }
      else
      {
         ObjectDelete(0, boxName);
         ObjectDelete(0, txtName);
      }
   }

   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   if(rates_total < 3) return(0);

   // Populate arrows for fractal swing highs and lows
   int start = (prev_calculated <= 1) ? 1 : prev_calculated - 2;
   int lastClosed = rates_total - 2;

   for(int i = start; i <= lastClosed; i++)
   {
      int prev = i - 1;
      // A-shape: Bullish followed by Bearish -> Fractal High (Supply origin)
      if(close[prev] > open[prev] && open[i] > close[i])
      {
         ArrowHighBuffer[i] = high[i] + (high[i] - low[i]) * 0.4 + _Point * 10;
      }
      else
      {
         ArrowHighBuffer[i] = EMPTY_VALUE;
      }

      // V-shape: Bearish followed by Bullish -> Fractal Low (Demand origin)
      if(open[prev] > close[prev] && close[i] > open[i])
      {
         ArrowLowBuffer[i] = low[i] - (high[i] - low[i]) * 0.4 - _Point * 10;
      }
      else
      {
         ArrowLowBuffer[i] = EMPTY_VALUE;
      }
   }

   int cur = rates_total - 1;
   ArrowHighBuffer[cur] = EMPTY_VALUE;
   ArrowLowBuffer[cur] = EMPTY_VALUE;

   RenderSNDBoxes();
   return(rates_total);
}

//+------------------------------------------------------------------+
//| Timer event handler                                              |
//+------------------------------------------------------------------+
void OnTimer()
{
   RenderSNDBoxes();
}
//+------------------------------------------------------------------+
