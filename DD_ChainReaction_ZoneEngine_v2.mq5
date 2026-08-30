//+------------------------------------------------------------------+
//| DD_ChainReaction_ZoneEngine_v2.mq5                                |
//| Smart Supply & Demand Zone Engine - MT5 chart visualization (V2). |
//| Standalone EA - does NOT touch DD_ChainReaction_MultiTF_EA_v2.mq5 |
//| (the production EA). Reads zones_v2.csv, written every cycle by   |
//| bookmap-bridge-v2/bookmap_addon_v2.py's Bookmap-native addon, and  |
//| draws each Supply/Demand zone as a rectangle directly on the      |
//| chart - already MT5/XAUUSD price scale (converted Python-side).   |
//|                                                                    |
//| Dadang, 2026-08-26: "gw trading di MT5 bukan di Bookmap... bookmap |
//| akan gw minimise, gw fokus ke MT5 dan web kita aja" - this is the  |
//| first concrete piece of that: the zone engine's output shown      |
//| directly where he actually reads candles, no need to ever look at |
//| Bookmap itself once this is attached.                             |
//|                                                                    |
//| v1.06: two things Dadang flagged after v1.05 -                    |
//| (1) "panel blm muncul" - a CCanvas bitmap-label panel (ported from |
//| the production EA's own PnlRow() system) was tried at two corners  |
//| (RIGHT_LOWER, then LEFT_LOWER) and neither rendered on his         |
//| terminal for reasons not diagnosable without live access to his    |
//| MT5 instance. Reverted to plain OBJ_LABEL/OBJ_RECTANGLE_LABEL -    |
//| the SAME object types the v1.03 panel used and was CONFIRMED       |
//| visible in his own screenshot - just bigger and better organized,  |
//| trading peak visual polish for something that reliably shows up.   |
//| (2) "atur biar gak sesak" - the chart had turned into an unreadable|
//| stack of overlapping zone boxes. Two independent fixes: a real     |
//| (non-zero) InpMinScoreToShow default to drop pure noise, AND a     |
//| hard per-side draw cap (InpMaxZonesPerSide, nearest-to-price first)|
//| so the chart never fills up no matter how many zones pass the      |
//| score filter - the cap is the more robust of the two since it      |
//| bounds the worst case regardless of score distribution.            |
//+------------------------------------------------------------------+
#property copyright "Chain Reaction"
#property version   "1.06"
#property strict

input int    InpRefreshSeconds   = 1;     // How often to re-read zones_v2.csv
input int    InpMinScoreToShow   = 15;    // Hide zones scoring below this (filters pure noise)
input int    InpMaxZonesPerSide  = 4;     // Draw at most this many zones per side (nearest to price first) - keeps the chart readable
input bool   InpShowBrokenZones  = false; // BROKEN zones are usually gone within a cycle anyway - off by default to avoid clutter

#define SDZ_PREFIX "SDZ_"
#define PNL_PREFIX "SDZP_"

// Per-TF candle lean ("condong") - Dadang: "desain panel nya dan condong
// tiap candle timeframenya bro". Sourced from DD_CMP_Indicator via iCustom
// (same buffer convention as the production EA's own ReadCMP(): buffer 2,
// >0.5 = BUY, <-0.5 = SELL) rather than Bookmap's own tf_matrix, which is
// cold-start (no historical OHLC feed - checked live_status_v2.json and
// every TF read WARMUP with 1-3 bars). DD_CMP_Indicator has full MT5
// history and is correct immediately - matches Dadang's own stated
// priority this session: "gw trading di MT5 bukan di bookmap".
struct TFSlot { string label; ENUM_TIMEFRAMES tf; int handle; };
TFSlot g_tf[6] =
{
   {"D1",  PERIOD_D1,  INVALID_HANDLE},
   {"H4",  PERIOD_H4,  INVALID_HANDLE},
   {"H1",  PERIOD_H1,  INVALID_HANDLE},
   {"M30", PERIOD_M30, INVALID_HANDLE},
   {"M15", PERIOD_M15, INVALID_HANDLE},
   {"M5",  PERIOD_M5,  INVALID_HANDLE},
};

// Nearest supply/demand found during the last UpdateZones() pass - fed to
// the panel so it doesn't need its own separate file read.
string g_nearSupplyMain = "-", g_nearSupplyDetail = "-";
string g_nearDemandMain = "-", g_nearDemandDetail = "-";
int    g_zoneCountSupply = 0, g_zoneCountDemand = 0;   // TOTAL non-broken zones known, not just the ones drawn

color DirColorZ(string d) { return (d == "BUY") ? clrLime : (d == "SELL" ? clrTomato : clrSilver); }

string StatusID(string status)
{
   if(status == "FRESH")    return "BARU";      // baru kebentuk, belum ada follow-up
   if(status == "ACTIVE")   return "AKTIF";     // udah dikonfirmasi, belum pernah di-retest
   if(status == "TESTED")   return "DIUJI";     // harga baru balik masuk sini sekali
   if(status == "WEAKENED") return "AUS";       // 2x+ retest, mulai lemah tapi belum jebol
   return status;                               // BROKEN dll (disembunyikan by default)
}

string StrengthID(double score) { return (score >= 60) ? "KUAT" : (score >= 30 ? "SEDANG" : "LEMAH"); }

//+------------------------------------------------------------------+
int OnInit()
{
   for(int i = 0; i < 6; i++)
   {
      g_tf[i].handle = iCustom(_Symbol, g_tf[i].tf, "DD_CMP_Indicator");
      if(g_tf[i].handle == INVALID_HANDLE)
         Print("[ZoneEngineV2] WARNING: gagal load DD_CMP_Indicator utk ", g_tf[i].label,
               " - baris condong TF ini bakal kosong (bukan fatal).");
   }

   EventSetTimer(MathMax(1, InpRefreshSeconds));
   CreatePanel();
   UpdateZones();
   UpdatePanel();
   Print("[ZoneEngineV2] Attached - reading zones_v2.csv every ", InpRefreshSeconds, "s");
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   for(int i = 0; i < 6; i++)
      if(g_tf[i].handle != INVALID_HANDLE) IndicatorRelease(g_tf[i].handle);
   ObjectsDeleteAll(0, SDZ_PREFIX);
   ObjectsDeleteAll(0, PNL_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
void OnTimer()
{
   UpdateZones();
   UpdatePanel();
}

//+------------------------------------------------------------------+
//| One zone box, colored/weighted by side + score + status. MQL5     |
//| chart objects have no real alpha channel, so "strength" is faked  |
//| by picking a dimmer vs. more saturated shade per score tier - a   |
//| BROKEN zone (if InpShowBrokenZones is on) always renders flat     |
//| gray regardless of score, since a broken zone's old score is      |
//| meaningless.                                                       |
//+------------------------------------------------------------------+
void DrawZone(int idx, string side, double lo, double hi, int wallCount, double totalLot,
              string status, int retestCount, int absorptionHits, double score)
{
   string key     = SDZ_PREFIX + side + "_" + IntegerToString(idx);
   string txtKey  = key + "_TXT";
   bool   isDemand = (side == "DEMAND");

   color clr;
   if(status == "BROKEN")
      clr = clrGray;
   else if(isDemand)
      clr = (score >= 60) ? C'0,200,120' : (score >= 30 ? C'0,140,85' : C'0,90,60');
   else
      clr = (score >= 60) ? C'220,60,60' : (score >= 30 ? C'170,50,50' : C'110,40,40');

   // WEAKENED gets a distinct dashed border - "this zone survived retests
   // but is aging/thinning out", visually different from a fresh ACTIVE box.
   ENUM_LINE_STYLE style = (status == "WEAKENED") ? STYLE_DASH : STYLE_SOLID;
   int width = (score >= 60) ? 3 : (score >= 30 ? 2 : 1);

   datetime t1 = TimeCurrent() - PeriodSeconds(_Period) * 60;
   datetime t2 = TimeCurrent() + PeriodSeconds(_Period) * 15;

   if(ObjectFind(0, key) < 0)
      ObjectCreate(0, key, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
   else
      ObjectMove(0, key, 0, t1, hi);
   ObjectSetInteger(0, key, OBJPROP_TIME, 1, t2);
   ObjectSetDouble(0, key, OBJPROP_PRICE, 1, lo);
   ObjectSetInteger(0, key, OBJPROP_FILL, true);
   ObjectSetInteger(0, key, OBJPROP_BACK, true);
   ObjectSetInteger(0, key, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, key, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, key, OBJPROP_STYLE, style);
   ObjectSetInteger(0, key, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, key, OBJPROP_COLOR, clr);

   string statusID   = StatusID(status);
   string strengthID = StrengthID(score);

   string label = StringFormat(" %s | %s %.0f | %s | %dw %.0fL | diuji%d serap%d",
                                side, strengthID, score, statusID, wallCount, totalLot, retestCount, absorptionHits);

   double midPrice   = (lo + hi) / 2.0;
   datetime labelTime = t1 + (datetime)((t2 - t1) * 0.35);
   if(ObjectFind(0, txtKey) < 0)
      ObjectCreate(0, txtKey, OBJ_TEXT, 0, labelTime, midPrice);
   else
      ObjectMove(0, txtKey, 0, labelTime, midPrice);
   ObjectSetInteger(0, txtKey, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, txtKey, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, txtKey, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetInteger(0, txtKey, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, txtKey, OBJPROP_FONTSIZE, 9);
   ObjectSetString(0, txtKey, OBJPROP_TEXT, label);
}

//+------------------------------------------------------------------+
//| zones_v2.csv: one line per zone, no header (variable row count) - |
//| side,lo,hi,wall_count,total_lot,status,retest_count,              |
//| absorption_hits,score - written by bookmap_addon_v2.py's          |
//| _write_zones_csv(). Missing/unreadable file just means the        |
//| Bookmap addon isn't running yet.                                   |
//|                                                                     |
//| v1.06: two passes now instead of draw-while-reading. Pass 1 reads  |
//| every row into parallel arrays (applying the broken/score filters  |
//| only). Pass 2 sorts each side's candidates by distance to current  |
//| price and draws only the nearest InpMaxZonesPerSide - the hard cap |
//| that actually solves "sesak" regardless of how many zones happen   |
//| to score above the threshold.                                      |
//+------------------------------------------------------------------+
void UpdateZones()
{
   int handle = FileOpen("zones_v2.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      ObjectsDeleteAll(0, SDZ_PREFIX);
      g_nearSupplyMain = "(bridge belum jalan)"; g_nearSupplyDetail = "-";
      g_nearDemandMain = "(bridge belum jalan)"; g_nearDemandDetail = "-";
      g_zoneCountSupply = 0; g_zoneCountDemand = 0;
      return;
   }

   string pSide[]; double pLo[], pHi[], pTotalLot[], pScore[];
   int    pWallCount[], pRetest[], pAbsorb[];
   string pStatus[];
   int n = 0;
   int countSupply = 0, countDemand = 0;

   while(!FileIsEnding(handle))
   {
      string side = FileReadString(handle);
      if(StringLen(side) == 0) break;   // trailing blank line at EOF

      double lo             = StringToDouble(FileReadString(handle));
      double hi             = StringToDouble(FileReadString(handle));
      int    wallCount      = (int)StringToInteger(FileReadString(handle));
      double totalLot       = StringToDouble(FileReadString(handle));
      string status         = FileReadString(handle);
      int    retestCount    = (int)StringToInteger(FileReadString(handle));
      int    absorptionHits = (int)StringToInteger(FileReadString(handle));
      double score          = StringToDouble(FileReadString(handle));

      if(status != "BROKEN") { if(side == "SUPPLY") countSupply++; else countDemand++; }
      if(status == "BROKEN" && !InpShowBrokenZones) continue;
      if(score < InpMinScoreToShow) continue;

      ArrayResize(pSide, n + 1);      pSide[n] = side;
      ArrayResize(pLo, n + 1);        pLo[n] = lo;
      ArrayResize(pHi, n + 1);        pHi[n] = hi;
      ArrayResize(pWallCount, n + 1); pWallCount[n] = wallCount;
      ArrayResize(pTotalLot, n + 1);  pTotalLot[n] = totalLot;
      ArrayResize(pStatus, n + 1);    pStatus[n] = status;
      ArrayResize(pRetest, n + 1);    pRetest[n] = retestCount;
      ArrayResize(pAbsorb, n + 1);    pAbsorb[n] = absorptionHits;
      ArrayResize(pScore, n + 1);     pScore[n] = score;
      n++;
   }
   FileClose(handle);

   ObjectsDeleteAll(0, SDZ_PREFIX);   // wipe last cycle, rebuild fresh from the selection below

   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double dist[]; ArrayResize(dist, n);
   for(int i = 0; i < n; i++)
      dist[i] = (pSide[i] == "SUPPLY") ? MathAbs(pLo[i] - price) : MathAbs(pHi[i] - price);

   string bestSupplyMain = "", bestSupplyDetail = "";
   string bestDemandMain = "", bestDemandDetail = "";
   int drawIdx = 0;

   string sides[2] = {"SUPPLY", "DEMAND"};
   for(int s = 0; s < 2; s++)
   {
      string wantSide = sides[s];
      int sideIdx[]; int sc = 0;
      for(int i = 0; i < n; i++)
         if(pSide[i] == wantSide) { ArrayResize(sideIdx, sc + 1); sideIdx[sc] = i; sc++; }

      // insertion sort by distance ascending - sc is always tiny (a handful
      // of zones per side), so this is plenty fast at a 1s refresh rate.
      for(int a = 1; a < sc; a++)
      {
         int key = sideIdx[a]; double keyDist = dist[key]; int b = a - 1;
         while(b >= 0 && dist[sideIdx[b]] > keyDist) { sideIdx[b + 1] = sideIdx[b]; b--; }
         sideIdx[b + 1] = key;
      }

      for(int a = 0; a < sc && a < InpMaxZonesPerSide; a++)
      {
         int i = sideIdx[a];
         DrawZone(drawIdx++, pSide[i], pLo[i], pHi[i], pWallCount[i], pTotalLot[i],
                  pStatus[i], pRetest[i], pAbsorb[i], pScore[i]);
      }

      if(sc > 0)
      {
         int i = sideIdx[0];
         string main   = (wantSide == "SUPPLY") ? StringFormat("%.2f  (+%.1f)", pLo[i], pLo[i] - price)
                                                 : StringFormat("%.2f  (-%.1f)", pHi[i], price - pHi[i]);
         string detail = StringFormat("%s %.0f | %s", StrengthID(pScore[i]), pScore[i], StatusID(pStatus[i]));
         if(wantSide == "SUPPLY") { bestSupplyMain = main; bestSupplyDetail = detail; }
         else                     { bestDemandMain = main; bestDemandDetail = detail; }
      }
   }

   ChartRedraw(0);

   g_nearSupplyMain   = (bestSupplyMain != "") ? bestSupplyMain : "tidak ada di atas harga";
   g_nearSupplyDetail = bestSupplyDetail;
   g_nearDemandMain   = (bestDemandMain != "") ? bestDemandMain : "tidak ada di bawah harga";
   g_nearDemandDetail = bestDemandDetail;
   g_zoneCountSupply  = countSupply;
   g_zoneCountDemand  = countDemand;
}

//+------------------------------------------------------------------+
//| Same buffer convention as the production EA's ReadCMP(): buffer 2, |
//| >0.5 = BUY, <-0.5 = SELL, else WAIT.                               |
//+------------------------------------------------------------------+
string ReadCMPDir(int handle)
{
   if(handle == INVALID_HANDLE) return "N/A";
   double buf[1];
   if(CopyBuffer(handle, 2, 0, 1, buf) <= 0) return "WAIT";
   if(buf[0] > 0.5)  return "BUY";
   if(buf[0] < -0.5) return "SELL";
   return "WAIT";
}

//+------------------------------------------------------------------+
//| v1.06: plain OBJ_LABEL/OBJ_RECTANGLE_LABEL panel - reverted from   |
//| the CCanvas version (v1.04/1.05), which never actually rendered on |
//| Dadang's terminal at either corner tried. This is the SAME object  |
//| system the earlier v1.03 panel used (confirmed visible in his own  |
//| screenshot) - bigger box, real section-divider bars instead of     |
//| ASCII dashes, and the 6 TFs laid out 2 columns x 3 rows (each its  |
//| own color) so nothing feels cramped.                               |
//+------------------------------------------------------------------+
// v1.06: summed every t+= in UpdatePanel() below for the real row count
// (title/sub/rule=64, condong header+3 rows=65, rule=20, 2x[header+main+
// detail]=71x2, rule=15, total row~14) = ~280px before margin - same "sum
// don't guess" lesson as the production panel's own PNL_H comment history.
#define PNL_W 300
#define PNL_H 300

void PnlLabel(string name, int xd, int yd, string text, color clr, int fontSize, string font = "Arial")
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_LOWER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetString(0, name, OBJPROP_FONT, font);
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, xd);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, yd);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
}

void PnlBar(string name, int xd, int yd, int w, int h, color clr)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_LOWER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, xd);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, yd);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
}

void CreatePanel()
{
   ObjectsDeleteAll(0, PNL_PREFIX);
   PnlBar(PNL_PREFIX + "BG", 8, 8, PNL_W, PNL_H, C'14,16,23');
   ObjectSetInteger(0, PNL_PREFIX + "BG", OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, PNL_PREFIX + "BG", OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, PNL_PREFIX + "BG", OBJPROP_COLOR, C'217,180,101');   // gold border
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
void UpdatePanel()
{
   // y measured from the BOTTOM of the panel box (CORNER_LEFT_LOWER) -
   // topOffset tracked top-down like a normal reading order and converted
   // at each call, which is far less error-prone than hand-picking a ys[]
   // array (exactly the mistake that under-sized the v1.03 panel).
   int boxBottom = 8, x0 = 22;
   int contentW = PNL_W - 28;
   #define YD(topOffset) (boxBottom + PNL_H - (topOffset))

   int t = 14;
   PnlLabel(PNL_PREFIX + "TITLE", x0, YD(t), "ZONE ENGINE V2", clrGold, 13); t += 20;
   PnlLabel(PNL_PREFIX + "SUB", x0, YD(t), "Smart Supply & Demand", clrSilver, 9); t += 18;
   PnlBar(PNL_PREFIX + "SEP1", x0, YD(t), contentW, 2, C'90,80,50'); t += 12;

   PnlLabel(PNL_PREFIX + "CONDONG_HDR", x0, YD(t), "Condong tiap candle:", clrWhite, 10); t += 17;
   // 2 columns x 3 rows - D1/H4/H1 left, M30/M15/M5 right
   for(int i = 0; i < 3; i++)
   {
      string dirL = ReadCMPDir(g_tf[i].handle);
      string dirR = ReadCMPDir(g_tf[i + 3].handle);
      PnlLabel(PNL_PREFIX + "TF" + IntegerToString(i) + "L", x0, YD(t),
                StringFormat("%-4s %s", g_tf[i].label, dirL), DirColorZ(dirL), 10, "Consolas");
      PnlLabel(PNL_PREFIX + "TF" + IntegerToString(i) + "R", x0 + contentW / 2, YD(t),
                StringFormat("%-4s %s", g_tf[i + 3].label, dirR), DirColorZ(dirR), 10, "Consolas");
      t += 16;
   }
   t += 6;
   PnlBar(PNL_PREFIX + "SEP2", x0, YD(t), contentW, 2, C'90,80,50'); t += 14;

   PnlLabel(PNL_PREFIX + "SUP_HDR", x0, YD(t), "SUPPLY terdekat", clrTomato, 10); t += 16;
   PnlLabel(PNL_PREFIX + "SUP_MAIN", x0 + 8, YD(t), g_nearSupplyMain, clrWhite, 11); t += 15;
   PnlLabel(PNL_PREFIX + "SUP_DET", x0 + 8, YD(t), g_nearSupplyDetail, clrTomato, 9); t += 20;

   PnlLabel(PNL_PREFIX + "DEM_HDR", x0, YD(t), "DEMAND terdekat", clrLimeGreen, 10); t += 16;
   PnlLabel(PNL_PREFIX + "DEM_MAIN", x0 + 8, YD(t), g_nearDemandMain, clrWhite, 11); t += 15;
   PnlLabel(PNL_PREFIX + "DEM_DET", x0 + 8, YD(t), g_nearDemandDetail, clrLimeGreen, 9); t += 20;

   PnlBar(PNL_PREFIX + "SEP3", x0, YD(t), contentW, 2, C'90,80,50'); t += 15;
   PnlLabel(PNL_PREFIX + "COUNT", x0, YD(t),
             StringFormat("Total Zona: %d SUPPLY, %d DEMAND", g_zoneCountSupply, g_zoneCountDemand), clrSilver, 9);

   ChartRedraw(0);
}
//+------------------------------------------------------------------+
