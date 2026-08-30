//+------------------------------------------------------------------+
//|   CHAIN REACTION SYSTEM — EA v6.2 (MT5)                          |
//|   by DADANG WAHYUONO — cascade 3-TF (koreksi 2026-07-05)         |
//|                                                                  |
//|   STRUKTUR (contoh gambar Dadang): ARAH(D) -> VR(M) -> TRIG(E)   |
//|     default JUARA jujur = H4 > H1 > M30 (base PF 1.22 sim).      |
//|   1. ARAH  = CMP TF-D (controller, valid saat candle close).     |
//|   2. VR    = CMP TF-M LAWAN arah D (retracement) retest ZONA     |
//|              level D (SBR/RBS ±tol).                             |
//|   3. TRIG  = CMP TF-E balik SEARAH D di zona = ENTRI (searah D). |
//|   SL = puncak/dasar RETRACEMENT (STRUKTURAL, selalu sisi bener   |
//|        -> JUJUR, gak ada SL-kebalik yg dulu inflate PF).         |
//|   TP = ZONA IMPULS arah D (extreme sebelum retrace).             |
//|   NO-REPAINT: dibaca dari bar M5 CLOSED (shift>=1).              |
//|                                                                  |
//|   EXIT: base (TP/SL) ATAU partial 50%@X + BE (InpPartialPips).   |
//|   + PANEL P/L buat replay Strategy Tester.                       |
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "6.20"
#property strict

#include <Trade/Trade.mqh>
CTrade trade;

//============================ INPUT ================================
input group "=== STRUKTUR CASCADE (TF) ==="
input ENUM_TIMEFRAMES InpDirTF  = PERIOD_H1;   // ARAH (controller) | juara MT5: H1
input ENUM_TIMEFRAMES InpVrTF   = PERIOD_M30;  // VR (retracement ke zona) | juara: M30
input ENUM_TIMEFRAMES InpTrigTF = PERIOD_M15;  // TRIGGER (CF = entri) | juara: M15
input group "=== SINYAL ==="
input double  InpZonaTol      = 4.0;    // Zona retest level D (harga; 4.0 = 40 pip XAU)
input double  InpSLbuf        = 0.5;    // Buffer SL di atas/bawah extreme retrace (harga)
input double  InpMinRisk      = 0.3;    // Min jarak SL (harga)
input bool    InpReqDaily     = true;   // Wajib arah SEARAH Daily (=filter KUAT) | juara: true
input double  InpTPfrac       = 0.5;    // TP = frac x jarak zona | juara: 0.5 (WR 81% MT5)
input int     InpHourFrom     = 8;      // Filter sesi: jam server mulai | juara: 8
input int     InpHourTo      = 21;      // Filter sesi: jam server akhir | juara: 21
input group "=== EXIT ==="
input double  InpPartialPips  = 0;      // Partial 50% @ +X pip lalu BE (0 = BASE, TP/SL polos)
input double  InpBEpips       = 0;      // BE saja: SL->entry @ +X pip (0=off)
input group "=== UMUM ==="
input double  InpLot          = 0.02;   // Lot (>=0.02 kalau pakai partial)
input int     InpCMPlookback  = 2000;   // Bar dipindai per TF buat CMP
input long    InpMagic        = 20260705;
input bool    InpShowPanel    = true;   // Panel status + profit/loss

//============================ STATE CMP ============================
string   arah_D, arah_Dir, arah_Vr, arah_Trig, arah_H4;
double   lvl_Dir;
datetime ct_D, ct_Dir, ct_Vr, ct_Trig, ct_H4;

//==================== STATE MESIN (cascade D>M>E) ==================
string   d          = "WAIT";   // arah kerja = CMP TF-D
datetime dc_cur     = 0;
bool     vrSet      = false;     // VR (TF-M lawan D) sudah latch
datetime vrTime     = 0;
double   favExt     = 0.0;       // impuls arah D (calon TP zona)
double   retExt     = 0.0;       // puncak/dasar retracement (SL + cek zona)
double   tpZone     = 0.0;       // TP zona impuls (dibekukan saat VR)
datetime lastCF     = 0;

datetime lastBarM5  = 0;

// manajemen posisi (partial/BE)
ulong  mgPosTk    = 0;
bool   mgPartial  = false;
bool   mgBE       = false;

//============== CMP DETECTOR (mirror Pine f_get_data) ==============
void ComputeCMP(ENUM_TIMEFRAMES tf, int lookback, string &arah, double &lvl, datetime &ct)
{
   arah = "WAIT"; lvl = 0.0; ct = 0;
   double sup = 0.0, res = 0.0;
   int bars = Bars(_Symbol, tf);
   int start = MathMin(lookback, bars - 2);
   for(int i = start; i >= 1; i--)          // bar TUA -> BARU, hanya CLOSED
   {
      double o  = iOpen(_Symbol, tf, i),   c  = iClose(_Symbol, tf, i);
      double op = iOpen(_Symbol, tf, i+1), cp = iClose(_Symbol, tf, i+1);
      if(op > cp && c > o) sup = MathMin(op, cp);
      if(cp > op && o > c) res = MathMax(cp, op);
      string prev = arah;
      if(arah == "WAIT")
      {
         if(res > 0 && c > res) { arah = "BUY";  lvl = res; }
         else if(sup > 0 && c < sup) { arah = "SELL"; lvl = sup; }
      }
      else if(arah == "BUY")  { if(sup > 0 && c < sup) { arah = "SELL"; lvl = sup; } }
      else                    { if(res > 0 && c > res) { arah = "BUY";  lvl = res; } }
      if(arah != prev) ct = iTime(_Symbol, tf, i);
   }
}

void RefreshCMP()
{
   double dummy;
   ComputeCMP(InpDirTF,  InpCMPlookback, arah_Dir,  lvl_Dir, ct_Dir);
   ComputeCMP(InpVrTF,   InpCMPlookback, arah_Vr,   dummy,   ct_Vr);
   ComputeCMP(InpTrigTF, InpCMPlookback, arah_Trig, dummy,   ct_Trig);
   ComputeCMP(PERIOD_D1, InpCMPlookback, arah_D,    dummy,   ct_D);
   ComputeCMP(PERIOD_H4, InpCMPlookback, arah_H4,   dummy,   ct_H4);
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

void TryEnter(string dir, double sl, double tp)
{
   if(HasPosition()) return;
   bool buy = (dir == "BUY");
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(buy  && sl >= bid) return;          // validasi arah level (no SL-kebalik)
   if(!buy && sl <= ask) return;
   if(buy  && tp <= ask) return;
   if(!buy && tp >= bid) return;
   string cm = "CR " + dir;
   if(buy) trade.Buy(InpLot, _Symbol, 0.0, sl, tp, cm);
   else    trade.Sell(InpLot, _Symbol, 0.0, sl, tp, cm);
}

//============== MANAJEMEN: PARTIAL 50% + BE ========================
void ManagePosition()
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(tk != mgPosTk) { mgPosTk = tk; mgPartial = false; mgBE = false; }

      int    dir = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY) ? 1 : -1;
      double op  = PositionGetDouble(POSITION_PRICE_OPEN);
      double cur = PositionGetDouble(POSITION_PRICE_CURRENT);
      double vol = PositionGetDouble(POSITION_VOLUME);
      double sl  = PositionGetDouble(POSITION_SL);
      double tp  = PositionGetDouble(POSITION_TP);
      double pips = (dir==1 ? cur-op : op-cur) / 0.1;
      double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

      if(InpPartialPips > 0 && !mgPartial && pips >= InpPartialPips)
      {
         mgPartial = true;
         if(vol >= 2*vmin)
         {
            double half = MathFloor((vol/2.0)/vstep) * vstep;
            if(half >= vmin) trade.PositionClosePartial(tk, half);
         }
         bool slWorse = (dir==1) ? (sl < op) : (sl > op || sl == 0);
         if(slWorse) trade.PositionModify(tk, op, tp);
         continue;
      }
      if(InpPartialPips <= 0 && InpBEpips > 0 && !mgBE && pips >= InpBEpips)
      {
         mgBE = true;
         bool slWorse = (dir==1) ? (sl < op) : (sl > op || sl == 0);
         if(slWorse) trade.PositionModify(tk, op, tp);
      }
   }
}

//============== STATISTIK P/L (history, filter magic) =============
void GetStats(int &n, int &wins, double &gp, double &gl, double &net)
{
   n = 0; wins = 0; gp = 0.0; gl = 0.0; net = 0.0;
   HistorySelect(0, TimeCurrent());
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      if(HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      double p = HistoryDealGetDouble(tk, DEAL_PROFIT)
               + HistoryDealGetDouble(tk, DEAL_SWAP)
               + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      n++; net += p;
      if(p > 0) { wins++; gp += p; } else gl += -p;
   }
}

//============== PANEL (chart objects) =============================
#define PFX "DDCR_"
void PLbl(string name, int x, int y, string txt, color c, int fs=9, string font="Consolas")
{
   string id = PFX + name;
   if(ObjectFind(0, id) < 0)
   {
      ObjectCreate(0, id, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, id, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, id, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, id, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, id, OBJPROP_HIDDEN, true);
   }
   ObjectSetString(0, id, OBJPROP_TEXT, txt);
   ObjectSetString(0, id, OBJPROP_FONT, font);
   ObjectSetInteger(0, id, OBJPROP_FONTSIZE, fs);
   ObjectSetInteger(0, id, OBJPROP_COLOR, c);
}
void PBox(string name, int x, int y, int w, int h, color bg, color border)
{
   string id = PFX + name;
   if(ObjectFind(0, id) < 0)
   {
      ObjectCreate(0, id, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, id, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, id, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, id, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, id, OBJPROP_XSIZE, w);
      ObjectSetInteger(0, id, OBJPROP_YSIZE, h);
      ObjectSetInteger(0, id, OBJPROP_BGCOLOR, bg);
      ObjectSetInteger(0, id, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, id, OBJPROP_COLOR, border);
      ObjectSetInteger(0, id, OBJPROP_BACK, false);
      ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, id, OBJPROP_HIDDEN, true);
   }
}
string TFtxt(ENUM_TIMEFRAMES tf) { return StringSubstr(EnumToString(tf), 7); }

void ShowPanel()
{
   if(!InpShowPanel) return;
   color GOLD=C'224,179,58', DGOLD=C'201,162,39', GRN=C'0,230,118', RED=C'255,69,58';
   color GRAY=C'139,146,160', TEAL=C'0,199,190', AMBER=C'245,165,36';
   PBox("bg", 8, 20, 350, 300, C'10,10,20', DGOLD);
   int x=18, y=28, dy=18;
   PLbl("t0", x, y, "DADANG WAHYUONO - CHAIN REACTION v6.2", GOLD, 10, "Arial Black"); y+=dy+4;
   string casc = TFtxt(InpDirTF)+" > "+TFtxt(InpVrTF)+" > "+TFtxt(InpTrigTF);
   PLbl("t1", x, y, "Cascade: "+casc+"   (exit "+(InpPartialPips>0?"PARTIAL":"BASE")+")", GRAY, 9); y+=dy;
   PLbl("t2", x, y, "CMP  D:"+arah_D+"  ARAH("+TFtxt(InpDirTF)+"):"+arah_Dir, GRAY, 9); y+=dy;
   PLbl("t3", x, y, "     VR("+TFtxt(InpVrTF)+"):"+arah_Vr+"  TRIG("+TFtxt(InpTrigTF)+"):"+arah_Trig, GRAY, 9); y+=dy;
   bool zoneLive = vrSet && lvl_Dir>0 &&
                   (d=="SELL" ? retExt >= lvl_Dir-InpZonaTol : retExt <= lvl_Dir+InpZonaTol);
   string stat = d=="WAIT" ? "tunggu CMP "+TFtxt(InpDirTF) :
                 !vrSet ? "(1) tunggu VR "+TFtxt(InpVrTF)+" lawan "+d :
                 zoneLive ? "(2) VR+ZONA OK - tunggu TRIG "+TFtxt(InpTrigTF)+" !" :
                 "(2) VR OK - tunggu retest zona";
   PLbl("t4", x, y, "MESIN: "+stat, zoneLive?GOLD:GRAY, 9); y+=dy+4;

   double fl=0; int pdir=0; double pOpen=0, pLots=0, flPips=0;
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong tk=PositionGetTicket(i);
      if(PositionSelectByTicket(tk))
         if(PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==InpMagic)
         {
            fl += PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
            pdir=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)?1:-1;
            pOpen=PositionGetDouble(POSITION_PRICE_OPEN); pLots+=PositionGetDouble(POSITION_VOLUME);
            double cur=PositionGetDouble(POSITION_PRICE_CURRENT);
            flPips=(pdir==1?cur-pOpen:pOpen-cur)/0.1;
         }
   }
   PLbl("h1", x, y, "-------- POSISI --------", DGOLD, 9); y+=dy;
   if(pdir==0) PLbl("p1", x, y, "(tidak ada posisi)", GRAY, 9);
   else PLbl("p1", x, y, StringFormat("%s %.2f @ %.2f  P/L %+.2f$ (%+.1fp)",
        pdir==1?"BUY":"SELL", pLots, pOpen, fl, flPips), fl>=0?GRN:RED, 9);
   y+=dy+4;

   int n,wins; double gp,gl,net; GetStats(n,wins,gp,gl,net);
   double wr = n>0?100.0*wins/n:0, pf = gl>0?gp/gl:(gp>0?99.9:0);
   PLbl("h2", x, y, "-------- HASIL ---------", DGOLD, 9); y+=dy;
   PLbl("r1", x, y, StringFormat("Trades %d  Win %d  Lose %d", n, wins, n-wins), GRAY, 9); y+=dy;
   PLbl("r2", x, y, StringFormat("WR %.1f%%   PF %.2f", wr, pf), wr>=60?GRN:(wr>=45?AMBER:RED), 10, "Arial Black"); y+=dy;
   PLbl("r3", x, y, StringFormat("PROFIT %+.2f$  (float %+.2f$)", net, fl), (net+fl)>=0?GRN:RED, 11, "Arial Black"); y+=dy;
   PLbl("r4", x, y, StringFormat("Balance %.2f  Equity %.2f",
        AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY)), TEAL, 9); y+=dy;
   PLbl("r5", x, y, "TP=zona impuls  SL=extreme retrace (jujur)", GRAY, 8);
}

//============== INIT / DEINIT / TICK ===============================
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   return(INIT_SUCCEEDED);
}
void OnDeinit(const int reason) { ObjectsDeleteAll(0, PFX); Comment(""); }

void OnTick()
{
   ManagePosition();
   ShowPanel();

   datetime tM5 = iTime(_Symbol, PERIOD_M5, 0);
   if(tM5 == lastBarM5) return;
   lastBarM5 = tM5;

   RefreshCMP();
   double h1 = iHigh(_Symbol, PERIOD_M5, 1);
   double l1 = iLow(_Symbol, PERIOD_M5, 1);
   double c1 = iClose(_Symbol, PERIOD_M5, 1);

   // ── MESIN CASCADE D>M>E (mirror sim run_general.gen) ──
   if(arah_Dir == "WAIT") { d = "WAIT"; vrSet = false; return; }
   if(arah_Dir != d || ct_Dir != dc_cur)
   {
      d = arah_Dir; dc_cur = ct_Dir;
      vrSet = false; vrTime = 0; lastCF = 0;
      favExt = (d=="SELL") ? l1 : h1; retExt = 0; tpZone = 0;
   }
   string opp = (d=="BUY") ? "SELL" : "BUY";

   if(!vrSet)
   {
      favExt = (d=="SELL") ? MathMin(favExt, l1) : MathMax(favExt, h1);   // impuls arah D
      if(arah_Vr == opp && ct_Vr > MathMax(dc_cur, lastCF))
      {
         vrSet = true; vrTime = ct_Vr; tpZone = favExt;
         retExt = (d=="SELL") ? h1 : l1;
      }
      return;
   }

   retExt = (d=="SELL") ? MathMax(retExt, h1) : MathMin(retExt, l1);      // extreme retrace

   if(arah_Trig == d && ct_Trig > vrTime)
   {
      bool inzone = lvl_Dir>0 && (d=="SELL" ? retExt >= lvl_Dir-InpZonaTol
                                            : retExt <= lvl_Dir+InpZonaTol);
      double e  = c1;
      double sl = (d=="SELL") ? retExt + InpSLbuf : retExt - InpSLbuf;    // STRUKTURAL
      double tp = e + InpTPfrac * (tpZone - e);   // TP-frac: 0.5/0.7 = target lebih dekat = WR naik
      bool risk_ok = MathAbs(e - sl) >= InpMinRisk;
      bool tp_ok   = (tpZone>0) && ((d=="SELL") ? (tp<e) : (tp>e));
      bool dOk     = !InpReqDaily || arah_D == d;
      MqlDateTime st; TimeToStruct(iTime(_Symbol, PERIOD_M5, 1), st);
      bool hourOk  = (st.hour >= InpHourFrom && st.hour <= InpHourTo);
      lastCF = ct_Trig; vrSet = false;
      if(inzone && risk_ok && tp_ok && dOk && hourOk)
         TryEnter(d, sl, tp);
      favExt = e;
   }
}
//+------------------------------------------------------------------+
