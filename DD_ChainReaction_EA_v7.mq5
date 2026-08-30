//+------------------------------------------------------------------+
//|   CHAIN REACTION SYSTEM — EA v7 (MT5)  by DADANG WAHYUONO         |
//|   ENGINE STORYLINE + STATUS + BARRIER (doktrin asli Daily Deploy) |
//|                                                                  |
//|   Alur (diturunkan dari doktrin, tervalidasi sim):               |
//|   1. Eksekusi M30->M15(VR)->M5(CF) = entri.                      |
//|   2. STATUS entri vs H1/H4/Daily: ambil cuma SEARAH-DOMINAN      |
//|      (arah == H1 DAN == Daily; H4 bebas) = status CCC & CVC.     |
//|      → sim: PF 1.30, cuan 4/4 kuartal, tahan cost 8p.            |
//|   3. TP: BARRIER (BO lama = level CMP lama) ATAU fix-by-status.  |
//|      Barrier jebol → master BO baru → CF baru → RE-ENTRI.        |
//|   4. SL = extreme retracement, cap InpSLcapPips.                 |
//|   NO-REPAINT: bar M5 CLOSED. + panel status & P/L buat replay.   |
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "7.00"
#property strict
#include <Trade/Trade.mqh>
CTrade trade;

//============================ INPUT ================================
input group "=== STRUKTUR (eksekusi) ==="
input ENUM_TIMEFRAMES InpSetupTF = PERIOD_M30;  // Setup/arah eksekusi
input ENUM_TIMEFRAMES InpVrTF    = PERIOD_M15;  // VR
input ENUM_TIMEFRAMES InpTrigTF  = PERIOD_M5;   // Trigger CF = entri
input group "=== FILTER STATUS (storyline) ==="
input bool   InpReqH1  = true;   // Arah wajib SEARAH H1 (skip 'VR ke H1' = bahaya)
input bool   InpReqD1  = true;   // Arah wajib SEARAH Daily
input bool   InpReqH4  = false;  // Arah wajib SEARAH H4 (CCC only; false = CCC+CVC)
input group "=== TP / SL ==="
input bool   InpTPbarrier = true;  // TP = BARRIER (BO lama). false = fix-by-status
input double InpMinTPpips = 30;    // Barrier minimal sejauh ini (pip) — skip yg kedeketan
input double InpTPfar     = 12.0;  // TP fix status searah-semua (harga; 12=120pip)
input double InpTPmed     = 8.0;   // TP fix status H4-lawan (harga; 8=80pip)
input double InpSLcapPips = 50;    // SL cap (pip)
input double InpSLbufPips = 5;     // buffer SL (pip)
input group "=== RE-ENTRI ==="
input bool   InpReentry   = true;  // Masuk lagi tiap CF baru (barrier jebol = BO baru)
input int    InpMaxReentry= 4;     // Maks entri per siklus arah setup
input group "=== EXIT M1 (kunci profit) ==="
input bool   InpM1TP      = true;  // TP saat M1 BO LAWAN arah (setelah profit)
input double InpM1lockPips= 15;    // Min profit (pip) biar M1-exit aktif
input bool   InpM1Reentry = true;  // Masuk lagi saat M1 CF SEARAH di zona
input double InpZoneTolPips= 30;   // Toleransi zona re-entri M1 (pip)
input group "=== UMUM ==="
input double InpLot       = 0.02;
input int    InpCMPlook   = 2000;
input long   InpMagic     = 20260719;
input bool   InpShowPanel = true;

//============================ STATE ================================
string  aD, aH4, aH1, aSet, aVr, aTr;
double  lD, lH4, lH1, lSet, lVr, lTr;
datetime cD, cH4, cH1, cSet, cVr, cTr;

// mesin eksekusi (setup->VR->CF)
string   mDir="WAIT"; datetime mTime=0; bool vrSet=false; datetime vrTime=0;
double   favExt=0, retExt=0, lastCF_lvl=0; datetime lastCF=0; int reCount=0;
string   lastStatus="-";
// M1 management (kunci profit + re-entri)
string   aM1="WAIT"; double lM1=0; datetime cM1=0, lastBarM1=0;
double   cfZonePx=0; string cfDir="";
// MASTER DINAMIS: CMP semua TF (kecil->besar: M5,M15,M30,H1,H4,D1)
string   cmpA[6]; double lvlA[6]; datetime ctA[6]; string prevCmpA[6];
string   dynMasterTF="-"; int dynMasterIdx=-1;

// barrier = histori level CMP lama (H1 & setup TF)
double  barH1[]; double barSet[];

datetime lastBarTrig=0;

//============== CMP DETECTOR (Minor SNR body-break) ================
void ComputeCMP(ENUM_TIMEFRAMES tf,int lb,string &ar,double &lv,datetime &ct)
{
   ar="WAIT"; lv=0; ct=0; double sup=0,res=0;
   int bars=Bars(_Symbol,tf); int st=MathMin(lb,bars-2);
   for(int i=st;i>=1;i--)
   {
      double o=iOpen(_Symbol,tf,i),c=iClose(_Symbol,tf,i);
      double op=iOpen(_Symbol,tf,i+1),cp=iClose(_Symbol,tf,i+1);
      if(op>cp && c>o) sup=MathMin(op,cp);
      if(cp>op && o>c) res=MathMax(cp,op);
      string pv=ar;
      if(ar=="WAIT"){ if(res>0&&c>res){ar="BUY";lv=res;} else if(sup>0&&c<sup){ar="SELL";lv=sup;} }
      else if(ar=="BUY"){ if(sup>0&&c<sup){ar="SELL";lv=sup;} }
      else { if(res>0&&c>res){ar="BUY";lv=res;} }
      if(ar!=pv) ct=iTime(_Symbol,tf,i);
   }
}

void PushBarrier(double &arr[], double level)
{
   if(level<=0) return;
   int nsz=ArraySize(arr);
   if(nsz>0 && MathAbs(arr[nsz-1]-level)<_Point) return;  // sama, skip
   ArrayResize(arr,nsz+1); arr[nsz]=level;
   if(ArraySize(arr)>40){ for(int i=0;i<ArraySize(arr)-1;i++) arr[i]=arr[i+1]; ArrayResize(arr,ArraySize(arr)-1); }
}

double lastLvlH1=0, lastLvlSet=0;
void RefreshCMP()
{
   // CMP SEMUA TF (kecil->besar): M5,M15,M30,H1,H4,D1
   ENUM_TIMEFRAMES lad[6]={PERIOD_M5,PERIOD_M15,PERIOD_M30,PERIOD_H1,PERIOD_H4,PERIOD_D1};
   for(int i=0;i<6;i++) ComputeCMP(lad[i],InpCMPlook,cmpA[i],lvlA[i],ctA[i]);
   aH1=cmpA[3]; aH4=cmpA[4]; aD=cmpA[5];
   // barrier = level CMP lama (H1 idx3 & M30 idx2)
   if(lvlA[3]>0 && lvlA[3]!=lastLvlH1){ if(lastLvlH1>0) PushBarrier(barH1,lastLvlH1); lastLvlH1=lvlA[3]; }
   if(lvlA[2]>0 && lvlA[2]!=lastLvlSet){ if(lastLvlSet>0) PushBarrier(barSet,lastLvlSet); lastLvlSet=lvlA[2]; }
}

double NearestBarrier(double e,bool buy)
{
   double best=0; double mind=InpMinTPpips*0.1;
   for(int s=0;s<2;s++){
      int nb = (s==0)?ArraySize(barH1):ArraySize(barSet);
      for(int i=0;i<nb;i++){
         double lv=(s==0)?barH1[i]:barSet[i];
         if(buy && lv>=e+mind){ if(best==0||lv<best) best=lv; }
         if(!buy&& lv<=e-mind){ if(best==0||lv>best) best=lv; }
      }
   }
   return best;
}

//============== POSISI ============================================
bool HasPos(){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong t=PositionGetTicket(i);
   if(PositionSelectByTicket(t)&&PositionGetString(POSITION_SYMBOL)==_Symbol&&PositionGetInteger(POSITION_MAGIC)==InpMagic) return true;} return false; }

void GetStats(int &nn,int &w,double &net){ nn=0;w=0;net=0; HistorySelect(0,TimeCurrent());
   for(int i=0;i<HistoryDealsTotal();i++){ ulong tk=HistoryDealGetTicket(i); if(tk==0)continue;
      if(HistoryDealGetInteger(tk,DEAL_MAGIC)!=InpMagic)continue; if(HistoryDealGetString(tk,DEAL_SYMBOL)!=_Symbol)continue;
      if(HistoryDealGetInteger(tk,DEAL_ENTRY)!=DEAL_ENTRY_OUT)continue;
      double p=HistoryDealGetDouble(tk,DEAL_PROFIT)+HistoryDealGetDouble(tk,DEAL_SWAP)+HistoryDealGetDouble(tk,DEAL_COMMISSION);
      nn++; net+=p; if(p>0) w++; } }

//============== ENTRY ==============================================
void TryEnter(string dir,double sl)
{
   if(HasPos()) return;
   bool buy=(dir=="BUY");
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double px=buy?ask:bid;
   double tp;
   if(InpTPbarrier){ tp=NearestBarrier(px,buy); if(tp<=0) tp=buy?px+InpTPmed:px-InpTPmed; }
   else { bool cccc=(aH4==dir); double d=cccc?InpTPfar:InpTPmed; tp=buy?px+d:px-d; }
   if(buy && sl>=bid) return; if(!buy && sl<=ask) return;
   if(buy && tp<=ask) return; if(!buy && tp>=bid) return;
   if(trade.PositionOpen(_Symbol, buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL, InpLot, px, sl, tp, "CR7 "+lastStatus))
   { cfZonePx=px; cfDir=dir; }   // simpan ZONA CF buat re-entri M1
}

double PosFloatPips(int &dir){ dir=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong t=PositionGetTicket(i);
      if(PositionSelectByTicket(t)&&PositionGetString(POSITION_SYMBOL)==_Symbol&&PositionGetInteger(POSITION_MAGIC)==InpMagic){
         dir=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)?1:-1;
         double op=PositionGetDouble(POSITION_PRICE_OPEN),cu=PositionGetDouble(POSITION_PRICE_CURRENT);
         return (dir==1?cu-op:op-cu)/0.1; } }
   return 0; }

void CloseAllPos(){ for(int i=PositionsTotal()-1;i>=0;i--){ ulong t=PositionGetTicket(i);
   if(PositionSelectByTicket(t)&&PositionGetString(POSITION_SYMBOL)==_Symbol&&PositionGetInteger(POSITION_MAGIC)==InpMagic) trade.PositionClose(t);} }

// TP saat M1 BO LAWAN arah (setelah profit) = kunci profit
void ManageM1()
{
   if(!InpM1TP || !HasPos()) return;
   int dir; double fp=PosFloatPips(dir);
   if(dir==0 || fp<InpM1lockPips) return;
   if(dir==1 && aM1=="SELL") CloseAllPos();   // buy, M1 flip sell -> TP
   if(dir==-1&& aM1=="BUY")  CloseAllPos();   // sell, M1 flip buy -> TP
}

// Re-entri saat M1 CF SEARAH lagi di ZONA CF
void TryM1Reentry()
{
   if(!InpM1Reentry || HasPos() || mDir=="WAIT") return;
   if(cfDir!=mDir) return;                     // arah setup harus masih sama
   if(reCount>=InpMaxReentry) return;
   if(aM1!=mDir) return;                        // M1 harus CF (searah setup)
   double px=(mDir=="BUY")?SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(cfZonePx>0 && MathAbs(px-cfZonePx)>InpZoneTolPips*0.1) return;   // harus dekat zona CF
   bool ok=(!InpReqH1||aH1==mDir)&&(!InpReqD1||aD==mDir)&&(!InpReqH4||aH4==mDir);
   if(!ok) return;
   double sl=(mDir=="SELL")? (retExt>0?retExt:px+InpSLcapPips*0.1)+InpSLbufPips*0.1
                           : (retExt>0?retExt:px-InpSLcapPips*0.1)-InpSLbufPips*0.1;
   if(mDir=="SELL" && sl-px>InpSLcapPips*0.1) sl=px+InpSLcapPips*0.1;
   if(mDir=="BUY"  && px-sl>InpSLcapPips*0.1) sl=px-InpSLcapPips*0.1;
   if(MathAbs(px-sl)>=3*0.1){ TryEnter(mDir,sl); reCount++; }
}

//============== PANEL =============================================
#define PFX "CR7_"
void PL(string nm,int x,int y,string tx,color c,int fs=9){ string id=PFX+nm;
   if(ObjectFind(0,id)<0){ ObjectCreate(0,id,OBJ_LABEL,0,0,0); ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);
      ObjectSetInteger(0,id,OBJPROP_XDISTANCE,x); ObjectSetInteger(0,id,OBJPROP_YDISTANCE,y);
      ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);}
   ObjectSetString(0,id,OBJPROP_TEXT,tx); ObjectSetString(0,id,OBJPROP_FONT,"Consolas");
   ObjectSetInteger(0,id,OBJPROP_FONTSIZE,fs); ObjectSetInteger(0,id,OBJPROP_COLOR,c); }
void PBox(){ string id=PFX+"bg"; if(ObjectFind(0,id)<0){ ObjectCreate(0,id,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);ObjectSetInteger(0,id,OBJPROP_XDISTANCE,8);ObjectSetInteger(0,id,OBJPROP_YDISTANCE,20);
   ObjectSetInteger(0,id,OBJPROP_XSIZE,340);ObjectSetInteger(0,id,OBJPROP_YSIZE,278);ObjectSetInteger(0,id,OBJPROP_BGCOLOR,(color)C'10,10,20');
   ObjectSetInteger(0,id,OBJPROP_BORDER_TYPE,BORDER_FLAT);ObjectSetInteger(0,id,OBJPROP_COLOR,(color)C'201,162,39');ObjectSetInteger(0,id,OBJPROP_BACK,false);
   ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);} }

void ShowPanel()
{
   if(!InpShowPanel) return;
   color GOLD=(color)C'224,179,58',GRN=(color)C'0,230,118',RED=(color)C'255,69,58',GRAY=(color)C'139,146,160';
   PBox(); int x=18,y=28,dy=18;
   PL("t0",x,y,"DADANG WAHYUONO - CHAIN REACTION v7",GOLD,10); y+=dy+3;
   PL("t1",x,y,"D:"+cmpA[5]+"  H4:"+cmpA[4]+"  H1:"+cmpA[3],GRAY,9); y+=dy;
   PL("t2",x,y,"M30:"+cmpA[2]+" M15:"+cmpA[1]+" M5:"+cmpA[0]+"  M1:"+aM1,GRAY,9); y+=dy;
   // status entri terakhir + master dinamis
   bool ok=(mDir!="WAIT")&&(!InpReqH1||cmpA[3]==mDir)&&(!InpReqD1||cmpA[5]==mDir)&&(!InpReqH4||cmpA[4]==mDir);
   PL("t3",x,y,"MASTER "+dynMasterTF+"  arah="+mDir+"  status="+lastStatus,ok?GOLD:GRAY,10); y+=dy;
   PL("t4",x,y,"CMP gagal hanya oleh TF sendiri · master flip otomatis",GRAY,8); y+=dy;
   PL("t5",x,y,"barrier H1:"+IntegerToString(ArraySize(barH1))+" setup:"+IntegerToString(ArraySize(barSet))+"  reentri:"+IntegerToString(reCount),GRAY,8); y+=dy+3;
   // posisi
   double fl=0,flp=0; int pd=0; double po=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong t=PositionGetTicket(i);
      if(PositionSelectByTicket(t)&&PositionGetString(POSITION_SYMBOL)==_Symbol&&PositionGetInteger(POSITION_MAGIC)==InpMagic){
         fl+=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP); pd=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)?1:-1;
         po=PositionGetDouble(POSITION_PRICE_OPEN); double cu=PositionGetDouble(POSITION_PRICE_CURRENT); flp=(pd==1?cu-po:po-cu)/0.1; } }
   PL("h1",x,y,"------- POSISI -------",(color)C'201,162,39',9); y+=dy;
   if(pd==0) PL("p1",x,y,"(tidak ada)",GRAY,9); else PL("p1",x,y,StringFormat("%s @ %.2f  %+.2f$ (%+.1fp)",pd==1?"BUY":"SELL",po,fl,flp),fl>=0?GRN:RED,9);
   y+=dy+3;
   int nn,w; double net; GetStats(nn,w,net); double wr=nn>0?100.0*w/nn:0, pf=0;
   PL("h2",x,y,"------- HASIL -------",(color)C'201,162,39',9); y+=dy;
   PL("r1",x,y,StringFormat("Trades %d  Win %d  WR %.1f%%",nn,w,wr),wr>=45?GRN:RED,10); y+=dy;
   PL("r2",x,y,StringFormat("PROFIT %+.2f$ (float %+.2f$)",net,fl),(net+fl)>=0?GRN:RED,11); y+=dy;
   PL("r3",x,y,StringFormat("Balance %.2f Equity %.2f",AccountInfoDouble(ACCOUNT_BALANCE),AccountInfoDouble(ACCOUNT_EQUITY)),(color)C'0,199,190',9); y+=dy;
   PL("r4",x,y,"TP="+(InpTPbarrier?"BARRIER":"fix")+"  M1:"+aM1+(InpM1TP?" [lock-profit ON]":""),GRAY,8);
   PL("r5",x,y,"reentri "+(InpReentry?"ON":"off")+" | M1-reentri "+(InpM1Reentry?"ON":"off")+" | SLcap "+DoubleToString(InpSLcapPips,0)+"p",GRAY,8);
}

//============== INIT/DEINIT/TICK ==================================
int OnInit(){ trade.SetExpertMagicNumber(InpMagic); trade.SetDeviationInPoints(30);
   ArrayResize(barH1,0); ArrayResize(barSet,0);
   EventSetTimer(1);            // panel refresh tiap detik (biar muncul walau market tutup)
   RefreshCMP(); ShowPanel();   // langsung tampil pas attach
   return(INIT_SUCCEEDED); }
void OnDeinit(const int r){ EventKillTimer(); ObjectsDeleteAll(0,PFX); ChartRedraw(); }
void OnTimer(){ ShowPanel(); ChartRedraw(); }   // panel jalan tanpa tick (weekend/replay pause)

void OnTick()
{
   ShowPanel();
   // ── GATE M1: refresh CMP M1 tiap bar M1 + re-entri M1; kunci-profit tiap tick ──
   datetime tM1=iTime(_Symbol,PERIOD_M1,0);
   if(tM1!=lastBarM1){ lastBarM1=tM1; ComputeCMP(PERIOD_M1,600,aM1,lM1,cM1); TryM1Reentry(); }
   ManageM1();   // per tick: TP secepatnya pas M1 lawan + udah profit

   datetime tt=iTime(_Symbol,InpTrigTF,0);
   if(tt==lastBarTrig) return; lastBarTrig=tt;
   RefreshCMP();
   double pip=0.1;

   // ════ ENGINE MASTER DINAMIS ════
   // CMP cuma bisa gagal oleh TF-nya SENDIRI. ENTRI = anak TERKECIL (M5..H1) yang
   // CMP-nya FLIP bar ini DAN searah parent + grandparent (2 tingkat di atas).
   // Arah = arah anak itu (= master flip otomatis pas cascade dalam).
   string names[6]={"M5","M15","M30","H1","H4","D1"};
   int entIdx=-1; string entDir="";
   for(int i=0;i<4;i++)
   {
      string D=cmpA[i];
      if(D=="WAIT" || prevCmpA[i]=="" ) continue;
      if(D!=prevCmpA[i] && cmpA[i+1]==D && cmpA[i+2]==D){ entIdx=i; entDir=D; break; }
   }
   for(int i=0;i<6;i++) prevCmpA[i]=cmpA[i];   // simpan buat deteksi flip berikutnya
   if(entIdx<0) return;

   dynMasterIdx=entIdx+1; dynMasterTF=names[dynMasterIdx];
   if(entDir!=mDir){ mDir=entDir; reCount=0; }      // arah master ganti → reset re-entri
   bool ok=(!InpReqH1||cmpA[3]==entDir)&&(!InpReqH4||cmpA[4]==entDir)&&(!InpReqD1||cmpA[5]==entDir);
   lastStatus=dynMasterTF+" "+(cmpA[3]==entDir?"C":"V")+(cmpA[4]==entDir?"C":"V")+(cmpA[5]==entDir?"C":"V");

   double e=iClose(_Symbol,PERIOD_M5,1);
   // SL = extreme LAWAN (VR) window M5, cap
   double sl;
   if(entDir=="BUY"){ double mn=e; for(int k=1;k<=24;k++) mn=MathMin(mn,iLow(_Symbol,PERIOD_M5,k)); sl=mn-InpSLbufPips*pip; }
   else             { double mx=e; for(int k=1;k<=24;k++) mx=MathMax(mx,iHigh(_Symbol,PERIOD_M5,k)); sl=mx+InpSLbufPips*pip; }
   if(entDir=="BUY"  && e-sl>InpSLcapPips*pip) sl=e-InpSLcapPips*pip;
   if(entDir=="SELL" && sl-e>InpSLcapPips*pip) sl=e+InpSLcapPips*pip;
   retExt=sl;
   bool riskOk=MathAbs(e-sl)>=3*pip;
   bool allow=!HasPos() && (InpReentry ? reCount<InpMaxReentry : reCount==0);
   if(ok && riskOk && allow){ TryEnter(entDir,sl); reCount++; }
}
//+------------------------------------------------------------------+
