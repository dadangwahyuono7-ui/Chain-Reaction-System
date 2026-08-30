//+------------------------------------------------------------------+
//| DD_CMP_Indicator.mq5                                             |
//| CMP (Chain Reaction) minor-SNR body-close breakout detector.     |
//|                                                                   |
//| Ported from DD_CMP_Marker.v7.pine's f_cmp() - CMP DETECTION ONLY.|
//| Dadang: "ambil cara baca CMP aja atau cara minor breakout nya    |
//| bro... jangan copi semuanya karena cara entri yang baru ini udah |
//| beda dengan cara kita sebelum2 nya." No VR, no CF, no barrier,   |
//| no status filter, no TP/SL - just the raw CMP state machine.     |
//| The EA (DD_ChainReaction_MultiTF_EA.mq5) owns ALL entry logic.   |
//|                                                                   |
//| DOCTRINE (identical to cmp_engine.py's CMPDetector/TFState and   |
//| DD_CMP_Marker.v7.pine's f_cmp() - same 3 implementations, same   |
//| algorithm, cross-validated this session):                        |
//|   V-shape minor support:    prev bar BEARISH, curr bar BULLISH   |
//|                              -> sup = min(prev.open, prev.close) |
//|   A-shape minor resistance: prev bar BULLISH, curr bar BEARISH   |
//|                              -> res = max(prev.open, prev.close) |
//|   CMP starts WAIT. First close beyond res -> BUY. First close    |
//|   below sup -> SELL. Once BUY, ONLY a close below a (newer) sup  |
//|   can flip it SELL (and vice versa) - "VR = satu-satunya yang    |
//|   gagalkan CMP." Body-close only, never wicks.                   |
//|                                                                   |
//| NO-REPAINT: only evaluated on CONFIRMED (closed) bars - the      |
//| currently-forming bar always mirrors the last closed bar's CMP,  |
//| exactly like Pine's `barstate.isconfirmed` gate.                 |
//|                                                                   |
//| PERFORMANCE: incremental via prev_calculated - only new/reopened |
//| bars get processed each call (state carried in globals), NOT a  |
//| full history re-walk every tick. A full re-walk is O(n) per tick |
//| -> O(n^2) total, which made a 1-year M5 Strategy Tester run take |
//| over an hour; incremental is O(n) total, seconds instead.        |
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "1.30"
#property strict
#property indicator_chart_window
#property indicator_buffers 8
#property indicator_plots   2

#property indicator_label1  "CMP BUY"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  clrLime
#property indicator_width1  2

#property indicator_label2  "CMP SELL"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  clrRed
#property indicator_width2  2

// Buffers 0-1: visual arrow markers (only set on the bar CMP actually flips).
// Buffers 2-3: raw data for an EA to CopyBuffer() - CMP direction (1=BUY,
// -1=SELL, 0=WAIT) and the unix time (as double) the CMP last changed.
// Buffer 4: the EXACT price level that was broken to enter the CURRENT CMP
// regime (frozen until the next flip) - lets an EA check "has price come
// back to retest this breakout level and failed to flip CMP" before
// entering, instead of chasing blindly.
// Buffers 5-6: LIVE minor sup/res - keep updating on EVERY new V/A-shape,
// NOT frozen at the last flip like buffer 4. Dadang: "buat apa nunggu CMP
// flip bro, kan memang gak ada nunggu" - continuation entries deep into an
// established trend must retest the LATEST minor SNR level (the freshest
// pullback low/high), not the original breakout level from way back at the
// start of the move, which price may never come back down/up to touch
// again. Buffer 5 = live sup (retest zone for BUY), buffer 6 = live res
// (retest zone for SELL).
// Buffer 7: BreakoutEventTimeBuffer - Dadang 2026-08-09 (TEHINIX doctrine +
// "M5 membentuk M30" diagrams): ChangeTimeBuffer (buffer 3) only stamps the
// FIRST time the overall CMP regime flips - once BUY, it stays frozen even
// as price keeps breaking fresh minor-res levels on the way up. But per
// doctrine, EVERY individual break past the latest pullback (each fresh
// V/A-shape that then gets broken) is its OWN tradeable event - "kita entri
// sell setiap ada BO sell", not just the first one. This buffer stamps the
// time of the MOST RECENT such break, repeating every time a newly-formed
// pullback gets broken (whether that continues the current regime or flips
// it - a flip is itself also a break event, so this buffer updates on flips
// too, same times as ChangeTimeBuffer AND on every subsequent continuation
// break ChangeTimeBuffer misses).
// All 8 written in NATURAL (non-series, oldest-to-newest) index order to
// match prev_calculated's incremental convention - CopyBuffer() on the
// EA side still always returns index 0 = most recent bar regardless of
// this internal storage order, so nothing on the EA side needs to change.
double BuyArrowBuffer[];
double SellArrowBuffer[];
double CmpBuffer[];
double ChangeTimeBuffer[];
double BreakoutLevelBuffer[];
double LiveSupBuffer[];
double LiveResBuffer[];
double BreakoutEventTimeBuffer[];

// State carried across OnCalculate() calls - this is what makes the
// incremental walk possible (no need to re-derive sup/res/ar from scratch).
double   g_sup = 0.0, g_res = 0.0;
int      g_ar  = 0;              // 0=WAIT, 1=BUY, -1=SELL
datetime g_changeTime = 0;
double   g_breakoutLevel = 0.0;  // res/sup value that triggered the CURRENT g_ar regime
bool     g_resConsumed = true;   // has the CURRENT g_res level already been broken/used?
bool     g_supConsumed = true;   // has the CURRENT g_sup level already been broken/used?
datetime g_breakoutEventTime = 0;

int OnInit()
{
   SetIndexBuffer(0, BuyArrowBuffer, INDICATOR_DATA);
   SetIndexBuffer(1, SellArrowBuffer, INDICATOR_DATA);
   SetIndexBuffer(2, CmpBuffer, INDICATOR_CALCULATIONS);
   SetIndexBuffer(3, ChangeTimeBuffer, INDICATOR_CALCULATIONS);
   SetIndexBuffer(4, BreakoutLevelBuffer, INDICATOR_CALCULATIONS);
   SetIndexBuffer(5, LiveSupBuffer, INDICATOR_CALCULATIONS);
   SetIndexBuffer(6, LiveResBuffer, INDICATOR_CALCULATIONS);
   SetIndexBuffer(7, BreakoutEventTimeBuffer, INDICATOR_CALCULATIONS);

   PlotIndexSetInteger(0, PLOT_ARROW, 233);   // up arrow
   PlotIndexSetInteger(1, PLOT_ARROW, 234);   // down arrow
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME, "DD CMP Engine");
   return(INIT_SUCCEEDED);
}

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

   // Arrays here are in the default NATURAL order (index 0 = oldest bar,
   // rates_total-1 = current/forming bar) - no ArraySetAsSeries, so we can
   // use prev_calculated directly per MQL5's standard incremental pattern.
   int start;
   if(prev_calculated <= 1)
   {
      start = 1;
      g_sup = 0.0; g_res = 0.0; g_ar = 0; g_changeTime = 0; g_breakoutLevel = 0.0;
      g_resConsumed = true; g_supConsumed = true; g_breakoutEventTime = 0;
   }
   else
   {
      // Redo from the second-to-last bar processed last call, in case the
      // final bar in that pass wasn't actually closed yet.
      start = prev_calculated - 2;
      if(start < 1) start = 1;
   }

   int lastClosed = rates_total - 2;   // never evaluate the forming bar itself
   for(int i = start; i <= lastClosed; i++)
   {
      int prev = i - 1;
      double o_prev = open[prev], c_prev = close[prev];
      double o_curr = open[i],    c_curr = close[i];

      // V-shape: prev bearish, curr bullish -> minor support
      if(o_prev > c_prev && c_curr > o_curr)
      {
         g_sup = MathMin(o_prev, c_prev);
         g_supConsumed = false;   // fresh pullback low - not yet broken
      }
      // A-shape: prev bullish, curr bearish -> minor resistance
      if(c_prev > o_prev && o_curr > c_curr)
      {
         g_res = MathMax(c_prev, o_prev);
         g_resConsumed = false;   // fresh pullback high - not yet broken
      }

      int prevAr = g_ar;
      if(g_ar == 0)
      {
         if(g_res > 0 && c_curr > g_res)      g_ar = 1;
         else if(g_sup > 0 && c_curr < g_sup) g_ar = -1;
      }
      else if(g_ar == 1)
      {
         if(g_sup > 0 && c_curr < g_sup) g_ar = -1;
      }
      else // g_ar == -1
      {
         if(g_res > 0 && c_curr > g_res) g_ar = 1;
      }
      if(g_ar != prevAr)
      {
         g_changeTime = time[i];
         // Freeze the exact level that caused THIS flip - res for a fresh
         // BUY, sup for a fresh SELL - stays constant until the next flip
         // even as sup/res themselves keep updating from newer V/A shapes.
         g_breakoutLevel = (g_ar == 1) ? g_res : g_sup;
      }

      // Fresh BREAKOUT EVENT (buffer 7, see comment at top) - fires every
      // time a not-yet-broken pullback level gets broken, whether that's
      // the first flip into a new regime OR the Nth continuation breakout
      // deep into an already-established one. Each one is its own event.
      if(!g_resConsumed && g_res > 0 && c_curr > g_res)
      {
         g_breakoutEventTime = time[i];
         g_resConsumed = true;
      }
      if(!g_supConsumed && g_sup > 0 && c_curr < g_sup)
      {
         g_breakoutEventTime = time[i];
         g_supConsumed = true;
      }

      CmpBuffer[i] = (double)g_ar;
      ChangeTimeBuffer[i] = (double)g_changeTime;
      BreakoutLevelBuffer[i] = g_breakoutLevel;
      LiveSupBuffer[i] = g_sup;
      LiveResBuffer[i] = g_res;
      BreakoutEventTimeBuffer[i] = (double)g_breakoutEventTime;
      BuyArrowBuffer[i]  = (g_ar != prevAr && g_ar == 1)  ? low[i]  - (high[i]-low[i])*0.5 - _Point*10 : EMPTY_VALUE;
      SellArrowBuffer[i] = (g_ar != prevAr && g_ar == -1) ? high[i] + (high[i]-low[i])*0.5 + _Point*10 : EMPTY_VALUE;
   }

   // The currently-forming bar (last index) never gets a new breakout
   // evaluation - it just mirrors the last CONFIRMED bar's CMP, exactly
   // like Pine's `barstate.isconfirmed` gate (no-repaint).
   int cur = rates_total - 1;
   if(cur > 0)
   {
      CmpBuffer[cur] = CmpBuffer[cur - 1];
      ChangeTimeBuffer[cur] = ChangeTimeBuffer[cur - 1];
      BreakoutLevelBuffer[cur] = BreakoutLevelBuffer[cur - 1];
      LiveSupBuffer[cur] = LiveSupBuffer[cur - 1];
      LiveResBuffer[cur] = LiveResBuffer[cur - 1];
      BreakoutEventTimeBuffer[cur] = BreakoutEventTimeBuffer[cur - 1];
   }
   BuyArrowBuffer[cur] = EMPTY_VALUE;
   SellArrowBuffer[cur] = EMPTY_VALUE;

   return(rates_total);
}
