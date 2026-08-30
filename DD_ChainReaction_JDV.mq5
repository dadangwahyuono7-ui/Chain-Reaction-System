//+------------------------------------------------------------------+
//|        DD — CHAIN REACTION SYSTEM · JDV (EA MT5)                  |
//|        by DADANG WAHYUONO — port dari Pine DD-CMP v6             |
//|                                                                  |
//|  Setup: M5 CF -> M15 (master) + CONTROLLER H4 searah.            |
//|  Entri = CF (breakout) M5 balik arah M15 setelah VR.             |
//|  TP    = SNR lama terdekat (left barrier) · SL = SL AMAN struktur|
//|  Cut   = CF flip valid (M5 CMP balik arah) — opsional.           |
//|  Deteksi CMP = Minor SNR body-break, PERSIS Pine f_get_data.     |
//|  Pakai bar CLOSED (shift>=1) → NO-REPAINT, valid buat Strategy   |
//|  Tester (replay/backtest).                                       |
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//============================ INPUT ================================
input double  InpLot           = 0.01;   // Lot
input int     InpTPlevel       = 1;      // Target TP (1=SNR terdekat, 2, 3)
input double  InpSLbufferPts   = 50;     // Buffer SL aman (points)
input int     InpPivStrength   = 3;      // Kekuatan pivot SNR lama (left barrier)
input bool    InpCutOnFlip     = true;   // Cut loss saat M5 CF flip (close balik arah)
input bool    InpReqDailyAlign = false;  // Wajib H4 SEARAH Daily (lebih ketat)
input int     InpCMPlookback   = 1500;   // Bar dipindai per TF buat init CMP
input int     InpPivLookback   = 400;    // Bar dipindai cari pivot SNR
input long    InpMagic         = 20260629;
input bool    InpShowPanel     = true;   // Tampilkan panel status

//============================ STATE ================================
string  arah_D, arah_H4, arah_H1, arah_M30, arah_M15, arah_M5, arah_M1;
double  lvl_D, lvl_H4, lvl_H1, lvl_M30, lvl_M15, lvl_M5, lvl_M1;
datetime ct_D, ct_H4, ct_H1, ct_M30, ct_M15, ct_M5, ct_M1;

// phase machine M15 (master setup) — vr dari M5
string  prevArah_M15 = "WAIT";
bool    vrSeen_M15   = false;
int     phase_M15    = 0;
int     cfCnt_M15    = 0;

datetime lastBarM5 = 0;

//============== CMP DETECTOR (mirror Pine f_get_data) ==============
void ComputeCMP(ENUM_TIMEFRAMES tf, int lookback, string &arah, double &lvl, datetime &ct)
{
   arah = "WAIT"; lvl = 0.0; ct = 0;
   double sup = 0.0, res = 0.0;
   int bars = Bars(_Symbol, tf);
   int start = MathMin(lookback, bars - 2);
   // iterasi bar TUA -> BARU, hanya bar CLOSED (shift >= 1)
   for(int i = start; i >= 1; i--)
   {
      double o  = iOpen(_Symbol, tf, i),   c  = iClose(_Symbol, tf, i);
      double op = iOpen(_Symbol, tf, i+1), cp = iClose(_Symbol, tf, i+1);
      // Minor SNR (body): prev bearish + curr bullish -> support ; prev bullish + curr bearish -> resist
      if(op > cp && c > o) sup = MathMin(op, cp);
      if(cp > op && o > c) res = MathMax(cp, op);
      string prev = arah;
      if(arah == "WAIT")
      {
         if(res > 0 && c > res) { arah = "BUY";  lvl = res; }
         else if(sup > 0 && c < sup) { arah = "SELL"; lvl = sup; }
      }
      else if(arah == "BUY")
      {
         if(sup > 0 && c < sup) { arah = "SELL"; lvl = sup; }
      }
      else // SELL
      {
         if(res > 0 && c > res) { arah = "BUY"; lvl = res; }
      }
      if(arah != prev) ct = iTime(_Symbol, tf, i);
   }
}

void RefreshAllCMP()
{
   ComputeCMP(PERIOD_D1,  InpCMPlookback, arah_D,   lvl_D,   ct_D);
   ComputeCMP(PERIOD_H4,  InpCMPlookback, arah_H4,  lvl_H4,  ct_H4);
   ComputeCMP(PERIOD_H1,  InpCMPlookback, arah_H1,  lvl_H1,  ct_H1);
   ComputeCMP(PERIOD_M30, InpCMPlookback, arah_M30, lvl_M30, ct_M30);
   ComputeCMP(PERIOD_M15, InpCMPlookback, arah_M15, lvl_M15, ct_M15);
   ComputeCMP(PERIOD_M5,  InpCMPlookback, arah_M5,  lvl_M5,  ct_M5);
   ComputeCMP(PERIOD_M1,  InpCMPlookback, arah_M1,  lvl_M1,  ct_M1);
}

//============== PHASE M15 (mirror Pine) -> SIGNAL ==================
// return: 0=none, 1=BUY signal, -1=SELL signal (fresh CF fire + H4 controller)
int UpdatePhaseM15_Signal()
{
   int sig = 0;
   if(arah_M15 != prevArah_M15)
   {
      prevArah_M15 = arah_M15;
      vrSeen_M15   = false;
      cfCnt_M15    = 0;
      phase_M15    = (arah_M15 == "WAIT") ? 0 : 1;
   }
   if(arah_M15 != "WAIT")
   {
      if(!vrSeen_M15 && arah_M5 != "WAIT" && arah_M5 != arah_M15 && ct_M5 > ct_M15)
         vrSeen_M15 = true;
      // derivePhase (M15 tanpa cf_high): WAIT?0 : !vr?1 : (arah_vr==self?4 : 2)
      int np;
      if(!vrSeen_M15) np = 1;
      else if(arah_M5 == arah_M15) np = 4;   // M5 balik searah M15 = CF
      else np = 2;
      bool cfFired = (phase_M15 <= 2 && np >= 3);
      if(cfFired) cfCnt_M15++;
      phase_M15 = np;
      if(cfFired)
      {
         bool h4ok    = (arah_H4 == arah_M15 && arah_H4 != "WAIT");
         bool dailyok = (!InpReqDailyAlign || arah_D == arah_M15);
         if(h4ok && dailyok)
            sig = (arah_M15 == "BUY") ? 1 : -1;
      }
   }
   return sig;
}

//============== PIVOT SNR LAMA (left barrier) ======================
// kumpulkan pivot high/low di chart TF, isi array level di atas/bawah price
void CollectPivots(double price, bool buy, double &tp1, double &tp2, double &tp3, double &slAman)
{
   tp1 = 0; tp2 = 0; tp3 = 0; slAman = 0;
   double above[]; double below[];
   ArrayResize(above, 0); ArrayResize(below, 0);
   int str = InpPivStrength;
   int bars = Bars(_Symbol, _Period);
   int lb = MathMin(InpPivLookback, bars - str - 2);
   for(int i = str + 1; i <= lb; i++)
   {
      bool ph = true, pl = true;
      double hi = iHigh(_Symbol, _Period, i);
      double lo = iLow(_Symbol, _Period, i);
      for(int k = 1; k <= str; k++)
      {
         if(hi <= iHigh(_Symbol, _Period, i+k) || hi <= iHigh(_Symbol, _Period, i-k)) ph = false;
         if(lo >= iLow(_Symbol, _Period, i+k)  || lo >= iLow(_Symbol, _Period, i-k))  pl = false;
      }
      if(ph && hi > price) { int n=ArraySize(above); ArrayResize(above,n+1); above[n]=hi; }
      if(pl && lo < price) { int n=ArraySize(below); ArrayResize(below,n+1); below[n]=lo; }
   }
   ArraySort(above);                       // ascending (terdekat di atas dulu)
   // below: ascending; nearest-below = terbesar = elemen terakhir
   ArraySort(below);
   double buf = InpSLbufferPts * _Point;
   if(buy)
   {
      if(ArraySize(above) > 0) tp1 = above[0];
      if(ArraySize(above) > 1) tp2 = above[1];
      if(ArraySize(above) > 2) tp3 = above[2];
      if(ArraySize(below) > 0) slAman = below[ArraySize(below)-1] - buf;
   }
   else
   {
      int n = ArraySize(below);
      if(n > 0) tp1 = below[n-1];           // terdekat di bawah
      if(n > 1) tp2 = below[n-2];
      if(n > 2) tp3 = below[n-3];
      if(ArraySize(above) > 0) slAman = above[0] + buf;  // resist terdekat di atas
   }
}

//============== POSISI ============================================
bool HasPosition()
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(PositionSelectByTicket(tk))
         if(PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==InpMagic)
            return true;
   }
   return false;
}

int PositionDir() // 1 buy, -1 sell, 0 none
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(PositionSelectByTicket(tk))
         if(PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==InpMagic)
            return (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? 1 : -1;
   }
   return 0;
}

void CloseAll()
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(PositionSelectByTicket(tk))
         if(PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==InpMagic)
            trade.PositionClose(tk);
   }
}

//============== PANEL =============================================
void ShowPanel(int sig)
{
   if(!InpShowPanel) return;
   string regime = (arah_H4=="WAIT"||arah_D=="WAIT") ? "-" : (arah_H4==arah_D ? "H4 SEARAH Daily (KUAT)" : "H4 VR ke Daily (CHOPPY)");
   string setup  = (phase_M15>=3 && arah_H4==arah_M15 && arah_H4!="WAIT") ? ("SETUP "+arah_M15+" SIAP") :
                   (phase_M15==2 ? "VR OK - tunggu CF M15" : phase_M15==1 ? "tunggu VR (M5)" : "tunggu setup");
   string s = "DADANG WAHYUONO - CHAIN REACTION SYSTEM (JDV)\n";
   s += "------------------------------------------\n";
   s += "Daily=" + arah_D + "  H4(CTRL)=" + arah_H4 + "  H1=" + arah_H1 + "\n";
   s += "M30=" + arah_M30 + "  M15*=" + arah_M15 + "  M5=" + arah_M5 + "\n";
   s += "REGIME : " + regime + "\n";
   s += "SETUP  : M5 CF->M15 +H4  | " + setup + "\n";
   s += "PHASE M15: " + IntegerToString(phase_M15) + "  (CF#" + IntegerToString(cfCnt_M15) + ")\n";
   Comment(s);
}

//============== INIT / TICK =======================================
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { Comment(""); }

void OnTick()
{
   // gate: proses sekali per bar M5 CLOSED (no-repaint)
   datetime tM5 = iTime(_Symbol, PERIOD_M5, 0);
   if(tM5 == lastBarM5) { return; }
   lastBarM5 = tM5;

   RefreshAllCMP();
   int sig = UpdatePhaseM15_Signal();
   ShowPanel(sig);

   int pdir = PositionDir();

   // ── Cut on CF flip (M5 CMP balik lawan arah posisi) ──
   if(InpCutOnFlip && pdir != 0)
   {
      if(pdir == 1 && arah_M5 == "SELL") CloseAll();
      if(pdir == -1 && arah_M5 == "BUY") CloseAll();
      pdir = PositionDir();
   }

   if(sig == 0) return;
   if(HasPosition()) return;   // 1 posisi/waktu

   bool buy = (sig == 1);
   double price = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double tp1, tp2, tp3, slAman;
   CollectPivots(price, buy, tp1, tp2, tp3, slAman);

   // pilih TP sesuai input (fallback ke terdekat yang ada)
   double tp = tp1;
   if(InpTPlevel == 2 && tp2 > 0) tp = tp2;
   if(InpTPlevel == 3 && tp3 > 0) tp = tp3;
   if(tp <= 0) tp = buy ? price + 200*_Point : price - 200*_Point; // fallback
   if(slAman <= 0) slAman = buy ? price - 200*_Point : price + 200*_Point;

   // validasi arah level
   if(buy && (tp <= price || slAman >= price)) return;
   if(!buy && (tp >= price || slAman <= price)) return;

   if(buy) trade.Buy(InpLot, _Symbol, 0.0, slAman, tp, "JDV BUY");
   else    trade.Sell(InpLot, _Symbol, 0.0, slAman, tp, "JDV SELL");
}
//+------------------------------------------------------------------+
