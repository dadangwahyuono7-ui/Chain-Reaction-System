//+------------------------------------------------------------------+
//| DD_ChainResearch_EA.mq5                                          |
//|                                                                   |
//| RESEARCH EA - Strategy Tester only. Separate file, separate magic |
//| number, separate object prefix. It does NOT read, write or share  |
//| anything with DD_ChainReaction_MultiTF_EA - Dadang: "lo edit atau |
//| kopi EA gw agar tidak merusaknya, lo buat file baru."             |
//|                                                                   |
//| WHY THIS EXISTS                                                   |
//| The Python studies are simulations, not backtests. They allow     |
//| unlimited overlapping positions, model no slippage, and have no   |
//| equity curve - so their numbers cannot be trusted as trading      |
//| results. The Strategy Tester models one position at a time, real  |
//| spread, and real fills. That is the only place a win rate means   |
//| anything.                                                         |
//|                                                                   |
//| r4.0, 2026-08-16 - CORE REWRITE around the CONTI + M30-MOMENTUM-  |
//| EXIT combo, the only mechanism this session validated across      |
//| MULTIPLE independent backtests (cascade_align_sweep.py PF 1.90,   |
//| full_cascade_sweep.py conti-mode PF 1.6, conti_momentum_exit_     |
//| sweep.py PF 3.71 n=375/208 days, beating a strict 8-seed random-   |
//| direction control on EVERY parameter combo tried) - see            |
//| research/CORE_DOCTRINE.md ss8c/8d for the full writeup.            |
//|                                                                   |
//| ENTRY (CONTI, Dadang's exact spec 2026-08-16): "jika H4 BO buy     |
//| close dan M30 BO buy kita akan cari buy di M5. Jika M5 sell kita   |
//| stop entri sampai M5 BO buy lagi dengan catatan ketika M5 buy      |
//| terjadi M30 masih CMP buy. Kalau M30 sell, stop sampai M30 buy     |
//| lagi dengan catatan H4 masih buy. Kita akan ulang terus."          |
//| -> H4.dir == M30.dir == a FRESH M5 breakout in that same           |
//| direction, checked live every tick (freshBreak only fires once     |
//| per new break, so "stop until M5/M30 realign" falls out for free   |
//| from using the event array, no extra state machine needed).        |
//|                                                                   |
//| EXIT (M30-momentum, Dadang's exact spec 2026-08-16): "TP kita:     |
//| ketika M30 tidak bisa buat breakout baru atau tidak bisa break     |
//| resis terdekat dia." Not a fixed price target - close the moment   |
//| M30's own CMP reverses, OR price approaches M30's live res/sup     |
//| and gets rejected there (retreats without M30 actually breaking    |
//| through). A structural SL stays underneath as a hard risk stop -   |
//| tested WITHOUT it (2026-08-16): PF dropped 3.71->3.13 and the      |
//| worst single trade ballooned to -132 USD unprotected - keeping     |
//| the cap is strictly better, not a trade-off.                       |
//|                                                                   |
//| TESTED AND REJECTED (kept out on purpose, not overlooked):         |
//|  - Breakeven/trailing SL once MFE reaches a threshold: PF WORSE    |
//|    in every combo tried (1.29-2.91 vs 3.71) - it cuts winners      |
//|    short before their M30-confirmed exit without protecting the    |
//|    worst losers (which never reach the trigger anyway).            |
//|  - Barrier-VR (counter-trend entry when M30 flips against H4 at    |
//|    an H4 zone): PF 0.84 average, didn't validate standalone.       |
//|  - Full Time Law cascade down to M1: only 35 days of M1 history    |
//|    available via the API - too short a sample, only 1/12 combos    |
//|    beat control, and even that one's control PF was suspiciously   |
//|    high too (the M30-momentum EXIT alone already explains most of  |
//|    the edge, independent of the M1-precise entry timing).          |
//|  - D1/H4 zone-touch + pullback (the OLD r3.7 mechanism this        |
//|    replaces): PF 1.68 standalone (research/snr_sweep.py) - real,   |
//|    but far weaker than CONTI + M30-momentum-exit.                  |
//|                                                                   |
//| WHAT'S CARRIED OVER FROM r3.7 UNCHANGED                            |
//|  - Minor SNR on the LINE CHART: close only, three-close pivot,    |
//|    break requires a full pip, BREAKOUT FORMATION LAW retest.       |
//|  - CMP ALWAYS EXISTS, WarmupCmp() replays history at OnInit.       |
//|  - TIME LAW: freshBreak only fires once per genuinely new break.   |
//|  - Panel chrome (CCanvas gold card) and the ENTIRE Bookmap bridge  |
//|    block (CVD, Pulse/Absorb, POC, Value Area, Iceberg) - NOT       |
//|    touched in this rewrite. Dadang, 2026-08-16: "jangan sentuh     |
//|    area Bookmap panelnya karena nanti masih akan gw kombinasi      |
//|    dengan data Bookmap kan CVD Market Puls DOM dll."                |
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <Canvas\Canvas.mqh>
CTrade trade;

#define RESEARCH_VERSION "r4.7"   // r4.0 CONTI+momentum-exit rewrite -> r4.1 panel/spam fix -> r4.2 jarak zona -> r4.3 SNR near-price+ladder -> r4.4 zone anchor -> r4.5 zone anchor (broken-required) -> r4.6 chart color/label rework -> r4.7 retest gate dihapus
#define DASH_PREFIX "DD_RISET_DASH_"
#define SNR_PREFIX  "DD_RISET_SNR_"
#define BM_HIST_DIR "bookmap_history\\"
#define BM_HIST_GLOB "bookmap_history_v2_*.csv"
#define WALL_SLOTS_PER_SIDE 10   // must match udp_listener.py's write_mt5_bridge_file() - only used to skip the right number of CSV fields, walls themselves aren't drawn here

input group "=== STRUKTUR (H4 > M30 > M5, CONTI cascade) ==="
input ENUM_TIMEFRAMES InpEntryTF   = PERIOD_M5;    // TF eksekusi - fresh breakout di sini = trigger entri
input ENUM_TIMEFRAMES InpParentTF  = PERIOD_M30;   // Harus align sama master saat M5 breakout terjadi
input ENUM_TIMEFRAMES InpMasterTF  = PERIOD_H4;    // Arah utama - CONTI cuma jalan searah H4

input group "=== JARAK MINIMUM DARI ZONA LAWAN (tervalidasi 2026-08-16) ==="
// Dadang, screenshot 2026-08-16: "di atasnya pas ada garis tapi malah
// entri BUY bro, lo harus kasih jarak dari garis, masaka entri buy di
// resistance." Benar - CONTI murni cek arah CMP, sebelumnya sama sekali
// gak ngecek ada tembok resistance/support (H4/M30, yang BELUM jebol) di
// depan mata pas mau entri. research/conti_momentum_exit_sweep.py (analisa
// lanjutan): filter ini MONOTON naik terus PF-nya makin jauh jaraknya -
// 0 pip PF3.71 -> 20p PF3.74 -> 50p PF4.13 -> 100p PF4.96 (n turun dari
// 375 ke 253, tapi WR & PF dua-duanya naik terus, lolos kontrol di semua
// titik). Default 50 pip - cukup jauh buat efeknya kerasa, gak motong
// jumlah trade separah 100p.
input double InpMinZoneDistUsd = 5.0;   // BUY diblok kalau resistance H4/M30 yang belum jebol ada dalam jarak ini; SELL sama tapi ke suport

input group "=== ZONE ANCHOR (tervalidasi 2026-08-16, PF naik 3.71 -> 5.33) ==="
// Dadang, screenshot 2026-08-16: "jika arah M30 buy, lo hanya akan buy
// ketika ada garis suport, bukan sell di resisi, karena resisi buat TP."
// CONTI polos nembak di M5 breakout MANAPUN selama H4=M30 align, gak
// peduli lagi di ruang kosong atau di zona. Sekarang WAJIB "berlabuh" -
// searah BUY: harga lagi deket suport H4/M30 (mantul) ATAU deket/baru
// nembus resis H4/M30 (breakout lanjutan) - simetris buat SELL. Kalau
// gak ada zona H4/M30 manapun di dekat harga, sinyal dilewatin.
// research/conti_momentum_exit_sweep.py (lanjutan): MONOTON - toleransi
// 30 pip PF5.33, 50 pip PF4.69, 80 pip PF4.08, 120 pip PF3.89, semua
// lolos kontrol jauh (kontrol maks cuma 2.16-2.84). Default 50 pip -
// makin ketat (angka lebih kecil) makin tinggi PF-nya kalau mau dites.
input bool   InpRequireZoneAnchor = true;
input double InpZoneAnchorTolUsd  = 5.0;

input group "=== M30-MOMENTUM EXIT (tervalidasi 2026-08-16, PF 3.71 n=375/208 hari) ==="
// Dadang: "TP kita: ketika M30 tidak bisa buat breakout baru atau tidak
// bisa break resis terdekat dia." Ganti TOTAL mekanisme TP lama (target
// garis D1/H4/H1 statis) - sekarang murni dinamis, dipantau tiap tick
// selagi posisi terbuka lewat ManageMomentumExit(). Menang TELAK lawan TP
// statis di SEMUA kombinasi parameter yang diuji (PF rata-rata 3.35 vs
// 1.50, research/conti_momentum_exit_sweep.py).
input double InpNearTolUsd    = 1.0;   // jarak dianggap "sudah mendekati" resis/suport M30 terdekat
input double InpRetreatTolUsd = 2.0;   // mundur sejauh ini dari titik terdekat tadi TANPA M30 tembus = ditolak, exit
// Ide Dadang, dites 2026-08-16: SL dihapus total, cuma tunggu M30 flip
// close. HASIL: PF malah TURUN (3.13 vs 3.71) dan worst single trade
// meledak jadi -132 USD tanpa proteksi. Structural SL yang ada di bawah
// (grup RISIKO, InpMaxSLUsd) menang di PF DAN lebih aman - bukan
// trade-off, dua-duanya menang. JANGAN dihapus.

input group "=== CHOP FILTER (opsional, tervalidasi tapi OFF by default) ==="
// research/conti_momentum_exit_sweep.py analisis lanjutan, 2026-08-16:
// skip entri kalau market lagi choppy (banyak flip CMP M30 belakangan).
// Monoton: makin ketat filternya, makin tinggi PF-nya, tapi makin jarang
// entri. chop<=8 (3 hari, PF 4.14) tervalidasi lawan kontrol; belum
// sekuat validasi CONTI+momentum-exit sendiri (baru 1 threshold dicoba
// bukan grid penuh) - makanya default OFF, bukan karena gak kepake.
input bool   InpUseChopFilter   = false;
input int    InpChopWindowDays  = 3;    // jendela hitung mundur buat hitung skor chop
input int    InpChopMaxFlips    = 8;    // skip entri kalau flip M30 dalam jendela ini > angka ini

input group "=== CHAIN STRENGTH (M15 - opsional, informational by default) ==="
input bool             InpCheckChainStrength = true;    // Tampilin status M15 di panel
input ENUM_TIMEFRAMES  InpChainCheckTF       = PERIOD_M15;
input bool             InpRequireStrongChain = false;   // WAJIB kuat (M15 gak lawan) sebelum entri - off = cuma info

input group "=== MINOR SNR (LINE CHART) ==="
// Dadang, 2026-08-16 (spek formal persis): Close1>Close2 AND Close3>Close2
// -> Resistance=Close2; BROKEN = Close > Resistance + 1 pip (simetris buat
// Support). Line chart doang, Close doang - Open/High/Low/Wick semua
// diabaikan. "TIDAK ADA WAJIB RETES 2 CANDLE. VR dan CF itu hanya STATUS,
// VR bukan wajib. Kalo tidak ada VR berarti CONTI, kalo ada VR berarti
// retracement." - jadi TIDAK ADA input retest lagi di sini, breakout
// selalu murni close-only, sesuai spek di atas.
input double InpBreakPips  = 1.0;                  // CMP break = +/- N pip

input group "=== GARIS SNR DI CHART (visual - H4 & M30, yang benar-benar dipakai logic) ==="
input bool InpDrawSnrLines = true;
// Dadang, 2026-08-16, contoh chart: nunjukin TANGGA (ladder) - 3 RESIS +
// 3 SUPORT sekaligus kelihatan, bukan cuma 1 garis "paling deket" doang.
input int  InpMaxZonesPerTF = 3;                   // simpen N pivot terbaru per tipe per TF
// Dadang, 2026-08-16: "biar gak spam lo bisa tampilkan jika sudah
// mendekati price nya." Pivot baru kebentuk tiap beberapa candle M30/H4 -
// gambar SEMUANYA langsung = spam. Sekarang garis baru muncul begitu
// harga udah dalam jarak ini darinya (kapanpun itu terjadi), bukan pas
// pivot-nya kebentuk.
input double InpSnrShowDistUsd = 10.0;              // tampilkan garis begitu harga dalam jarak ini (USD)

input group "=== RISIKO (bagian yang hilang di studi Python) ==="
input double InpLot          = 0.01;
input bool   InpAdaptiveSL   = true;   // SL dari struktur valid terdekat di TF eksekusi
input int    InpStructLookback = 30;   // bar ke belakang buat cari struktur
input double InpMinSLUsd     = 2.0;    // SL minimum (USD) biar gak ketembak noise - ~20 pip
input double InpMaxSLUsd     = 12.0;   // SL maksimum (USD) - REJECT kalau lebih (bukan clamp), tervalidasi menang PF dan tail-risk lawan versi tanpa cap
// r4.0: TP statis (InpTPRatio) DIHAPUS - exit sekarang murni
// ManageMomentumExit() di atas. InpUseTrailing default DIMATIKAN: versi
// breakeven-move yang mirip (geser SL begitu profit sekian) dites
// 2026-08-16 dan PF-nya lebih jelek di semua kombinasi (motong pemenang
// sebelum sempat ke exit M30 yang lebih besar). Kode dibiarkan ada buat
// yang mau eksperimen, tapi jangan nyalain tanpa alasan kuat - datanya
// udah bilang ini kalah lawan "biarin murni M30 yang nentuin."
input bool   InpUseTrailing  = false;
input double InpTrailStartUsd = 3.0;
input double InpTrailStepUsd  = 2.0;

input group "=== PANEL ==="
input bool   InpShowPanel      = true;
input string InpPanelName      = "CHAIN REACTION - RISET";
input string InpOwnerName      = "Dadang Wahyuono";

input group "=== BOOKMAP BRIDGE (live/replay, sama seperti produksi) ==="
input bool   InpShowBookmapPanel = true;    // Tampilin CVD/Pulse/POC/VA/Iceberg Bookmap di panel
input double InpBookmapStaleSec  = 30.0;    // Anggap data basi kalau beda lebih dari ini (detik)

input group "=== LAIN-LAIN ==="
input ulong  InpMagic = 990011;        // magic TERPISAH dari EA produksi
input int    InpSlippage = 30;

//--- CMP state per timeframe. Direction ALWAYS holds a value once seeded -
//--- there is no NONE and no WAIT, only the status around it changes.
struct CmpState
{
   string   dir;          // "BUY" / "SELL"
   datetime since;        // when this direction was established
   double   sup, res;     // live minor SNR levels
   bool     supUsed, resUsed;
   datetime lastBar;
   // when the CURRENT res/sup pivot itself formed - used to key its chart
   // line so it only ever gets drawn once, and to detect a genuinely NEW
   // pivot (2026-08-16 "biar gak spam" rework, see UpdateSnrLinesNearPrice).
   datetime resFormedAt, supFormedAt;
   // SNR METHOD (Arum, 10-chapter transcript, 2026-08-16 "GAS BRO"): every
   // fresh break gets its own KEY LEVEL. Reset to false at the top of
   // every UpdateCmp() call - true only on the exact tick a NEW break
   // fires. Still needed in r4.0: CONTI's M5 trigger IS "freshBreak".
   bool     freshBreak;
   string   breakDir;
   double   breakLevel;
};

CmpState g_entry, g_parent, g_master;   // M5 / M30 / H4 - the whole CONTI + momentum-exit system runs off these three
CmpState g_chainCheck;                  // M15 - informational "no gap in chain" strength check, doesn't gate

datetime g_lastEntryBar = 0;

// M30-MOMENTUM EXIT state. Single flag is enough - HasPosition() below
// guarantees only ONE position from this EA is ever open at a time, same
// assumption research/conti_momentum_exit_sweep.py's backtest made.
bool g_approached = false;

double PipSize() { return SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10.0; }
string TfName(ENUM_TIMEFRAMES tf) { return StringSubstr(EnumToString(tf), 7); }

//--- Dadang: "bisa buatkan indikator hitung mundur candle di tiap TF kah
//--- bro." Time left until the CURRENT (forming) bar on that TF closes.
string CountdownStr(ENUM_TIMEFRAMES tf)
{
   datetime barOpen  = iTime(_Symbol, tf, 0);
   datetime barClose = barOpen + PeriodSeconds(tf);
   long remain = (long)barClose - (long)TimeCurrent();
   if(remain < 0) remain = 0;
   int hh = (int)(remain / 3600);
   int mm = (int)((remain % 3600) / 60);
   int ss = (int)(remain % 60);
   if(hh > 0) return StringFormat("%02d:%02d:%02d", hh, mm, ss);
   return StringFormat("%02d:%02d", mm, ss);
}

//+------------------------------------------------------------------+
//| GARIS SNR DI CHART - satu objek per pivot, TAPI dengan rolling cap|
//| di InpMaxZonesPerTF per tipe per TF (bukan cuma di seed awal).    |
//| r4.0 ganti dari D1+H4 ke H4+M30 - M30 pivot JAUH lebih sering     |
//| daripada D1/H4, jadi versi lama ("tiap pivot dapat garis permanen,|
//| gak pernah dihapus") numpuk jadi spam dalam hitungan jam. Dadang, |
//| 2026-08-16: "garis SNR jadi spam banget bro." Sekarang begitu     |
//| garis baru ke-N+1 muncul, garis PALING LAMA di bucket yang sama   |
//| (zoneTag+R/S) dihapus - selalu cuma nyimpen InpMaxZonesPerTF garis|
//| TERBARU, sama seperti seed awal sudah lakukan, cuma sekarang live |
//| update-nya juga taat aturan yang sama, bukan cuma sekali di OnInit|
//+------------------------------------------------------------------+
string g_h4LinesR[], g_h4LinesS[], g_m30LinesR[], g_m30LinesS[];

//--- Rolling history of the last InpMaxZonesPerTF DISTINCT pivots per
//--- type per TF - g_master.res/g_parent.res on their own only ever hold
//--- the SINGLE latest pivot (overwritten each time a new one forms), so
//--- showing a "tangga" (ladder) of several past levels at once (Dadang's
//--- example chart, 2026-08-16) needs its own history, pushed to from
//--- OnTick every time UpdateCmp() reports a genuinely new pivot.
double   g_h4ResPx[],  g_h4SupPx[],  g_m30ResPx[],  g_m30SupPx[];
datetime g_h4ResTm[],  g_h4SupTm[],  g_m30ResTm[],  g_m30SupTm[];

void PushPivotHistory(double &pxArr[], datetime &tmArr[], double px, datetime tm)
{
   if(tm == 0) return;
   int n = ArraySize(tmArr);
   if(n > 0 && tmArr[n - 1] == tm) return;   // same pivot as last time, nothing new
   ArrayResize(pxArr, n + 1); ArrayResize(tmArr, n + 1);
   pxArr[n] = px; tmArr[n] = tm;
   while(ArraySize(tmArr) > InpMaxZonesPerTF)
   {
      for(int i = 0; i < ArraySize(tmArr) - 1; i++) { pxArr[i] = pxArr[i + 1]; tmArr[i] = tmArr[i + 1]; }
      ArrayResize(pxArr, ArraySize(pxArr) - 1); ArrayResize(tmArr, ArraySize(tmArr) - 1);
   }
}

//--- Dadang's example chart, 2026-08-16 ("ni contoh nya"): RESIS always
//--- green, SUPORT always gold/yellow - color encodes ZONE TYPE, not which
//--- TF it came from (H4 vs M30 are told apart by line width instead, see
//--- DrawZoneLine below).
color ZoneLineColor(bool isRes) { return isRes ? C'46,204,113' : C'241,196,15'; }

void TrackAndCap(string &tracker[], string name)
{
   for(int i = 0; i < ArraySize(tracker); i++) if(tracker[i] == name) return;   // already tracked (re-seed), skip
   int n = ArraySize(tracker);
   ArrayResize(tracker, n + 1);
   tracker[n] = name;
   while(ArraySize(tracker) > InpMaxZonesPerTF)
   {
      ObjectDelete(0, tracker[0]);
      ObjectDelete(0, tracker[0] + "_TXT");
      for(int i = 0; i < ArraySize(tracker) - 1; i++) tracker[i] = tracker[i + 1];
      ArrayResize(tracker, ArraySize(tracker) - 1);
   }
}

//--- Line + a price/RESIS-SUPORT text label (matches Dadang's example
//--- chart) anchored a few bars into the future so it doesn't sit on top
//--- of candles, same pattern as the wall labels in the production EA.
void DrawZoneLine(string zoneTag, bool isRes, string key, double price, ENUM_TIMEFRAMES tf)
{
   if(!InpDrawSnrLines || price <= 0.0) return;
   string name = SNR_PREFIX + key;
   color clr = ZoneLineColor(isRes);
   bool isNew = (ObjectFind(0, name) < 0);
   if(isNew)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, (tf == InpMasterTF) ? 2 : 1);   // H4 tebal, M30 tipis
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);

      string txtName = name + "_TXT";
      datetime labelTime = TimeCurrent() + PeriodSeconds(InpEntryTF) * 8;
      ObjectCreate(0, txtName, OBJ_TEXT, 0, labelTime, price);
      ObjectSetString(0, txtName, OBJPROP_TEXT, " " + (isRes ? "RESIS " : "SUPORT ") + TfName(tf) + " " + DoubleToString(price, 2));
      ObjectSetInteger(0, txtName, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 9);
      ObjectSetInteger(0, txtName, OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(0, txtName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, txtName, OBJPROP_HIDDEN, true);
   }
   // MQL5 won't take a reference-array parameter from a ternary expression
   // ("g_h4LinesR : g_h4LinesS" isn't an lvalue) - four explicit branches.
   if(zoneTag == "H4" && isRes)        TrackAndCap(g_h4LinesR, name);
   else if(zoneTag == "H4" && !isRes)  TrackAndCap(g_h4LinesS, name);
   else if(zoneTag == "M30" && isRes)  TrackAndCap(g_m30LinesR, name);
   else if(zoneTag == "M30" && !isRes) TrackAndCap(g_m30LinesS, name);
}

//--- Dadang, 2026-08-16: "biar gak spam lo bisa tampilkan jika sudah
//--- mendekati price nya." A line no longer draws the instant its pivot
//--- forms (every few M30 bars - "garis SNR jadi spam banget") - it draws
//--- the first time price comes within InpSnrShowDistUsd of it, whenever
//--- that happens to be. Keyed by resFormedAt/supFormedAt so it still only
//--- ever draws ONCE per genuine pivot no matter how many ticks pass
//--- before/after price gets close.
void ShowZoneLineIfNear(string zoneTag, bool isRes, double level, datetime formedAt, double price, ENUM_TIMEFRAMES tf)
{
   if(level <= 0.0 || formedAt == 0) return;
   if(MathAbs(price - level) > InpSnrShowDistUsd) return;
   string key = zoneTag + (isRes ? "_R_" : "_S_") + (string)formedAt;
   DrawZoneLine(zoneTag, isRes, key, level, tf);
}

void ShowHistNearPrice(string zoneTag, bool isRes, double &pxArr[], datetime &tmArr[], double price, ENUM_TIMEFRAMES tf)
{
   for(int i = 0; i < ArraySize(tmArr); i++)
      ShowZoneLineIfNear(zoneTag, isRes, pxArr[i], tmArr[i], price, tf);
}

void UpdateSnrLinesNearPrice()
{
   // record any genuinely new pivot into the ladder history first
   PushPivotHistory(g_h4ResPx,  g_h4ResTm,  g_master.res, g_master.resFormedAt);
   PushPivotHistory(g_h4SupPx,  g_h4SupTm,  g_master.sup, g_master.supFormedAt);
   PushPivotHistory(g_m30ResPx, g_m30ResTm, g_parent.res, g_parent.resFormedAt);
   PushPivotHistory(g_m30SupPx, g_m30SupTm, g_parent.sup, g_parent.supFormedAt);

   if(!InpDrawSnrLines) return;
   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   ShowHistNearPrice("H4",  true,  g_h4ResPx,  g_h4ResTm,  price, InpMasterTF);
   ShowHistNearPrice("H4",  false, g_h4SupPx,  g_h4SupTm,  price, InpMasterTF);
   ShowHistNearPrice("M30", true,  g_m30ResPx, g_m30ResTm, price, InpParentTF);
   ShowHistNearPrice("M30", false, g_m30SupPx, g_m30SupTm, price, InpParentTF);
}

//+------------------------------------------------------------------+
//| Minor SNR, line chart, CLOSE ONLY.                               |
//| Pivot: Close2 above both neighbours = resistance, below = support.|
//| Break: close a full pip past the level, and (optionally) only     |
//| after the retest sequence required by the BREAKOUT FORMATION LAW. |
//+------------------------------------------------------------------+
void UpdateCmp(CmpState &st, ENUM_TIMEFRAMES tf)
{
   st.freshBreak = false;   // only true for the exact tick a NEW break fires below
   datetime bt = iTime(_Symbol, tf, 0);
   if(bt == st.lastBar) return;          // one evaluation per closed bar
   st.lastBar = bt;

   // shift 1 = last CLOSED bar; never look at the forming bar
   double c1 = iClose(_Symbol, tf, 4);
   double c2 = iClose(_Symbol, tf, 3);
   double c3 = iClose(_Symbol, tf, 2);
   double now   = iClose(_Symbol, tf, 1);
   if(c1 <= 0 || now <= 0) return;

   // Pivot updates the LEVEL immediately (still needed live for CONTI/exit/
   // zone-distance logic) but drawing itself is deferred to
   // UpdateSnrLinesNearPrice() - see note above ("biar gak spam").
   if(c2 > c1 && c2 > c3)
   {
      st.res = c2; st.resUsed = false; st.resFormedAt = iTime(_Symbol, tf, 3);   // pivot high
   }
   if(c2 < c1 && c2 < c3)
   {
      st.sup = c2; st.supUsed = false; st.supFormedAt = iTime(_Symbol, tf, 3);   // pivot low
   }

   double margin = InpBreakPips * PipSize();

   // Dadang, 2026-08-16 (exact formal spec): "TIDAK ADA WAJIB RETES 2
   // CANDLE. VR dan CF itu hanya STATUS, VR bukan wajib. Kalo tidak ada VR
   // berarti CONTI, kalo ada VR berarti retracement." BROKEN is purely
   // Close > Resistance + 1 pip (or < Support - 1 pip) - no 2-candle
   // retest sequence gates it. A prior 2-candle "BREAKOUT FORMATION LAW"
   // requirement here was wrong - removed, not just defaulted off, so a
   // stale .set file can never silently reintroduce it.
   //
   // SNR METHOD ch2 / Daily Deploy "CF bisa berkali-kali": `dir` updates on
   // EVERY fresh break, not just the first one after a flip - each one
   // re-stamps freshBreak/breakDir/breakLevel for OnTick's CONTI check.
   if(st.res > 0 && !st.resUsed && now > st.res + margin)
   {
      st.dir = "BUY"; st.since = iTime(_Symbol, tf, 1);
      st.freshBreak = true; st.breakDir = "BUY"; st.breakLevel = st.res;
      st.resUsed = true;
   }
   else if(st.sup > 0 && !st.supUsed && now < st.sup - margin)
   {
      st.dir = "SELL"; st.since = iTime(_Symbol, tf, 1);
      st.freshBreak = true; st.breakDir = "SELL"; st.breakLevel = st.sup;
      st.supUsed = true;
   }
}

//+------------------------------------------------------------------+
//| WARMUP - Dadang: "gak baca CMP breakout, gw kosong ini." UpdateCmp|
//| only ever SET .dir on a fresh breakout AFTER attach - it never    |
//| looked backward, so a symbol/TF whose last real breakout was long |
//| before attach just sat at "" (empty) until the next one, direct   |
//| violation of "CMP ALWAYS EXISTS" (CLAUDE.md). This replays the    |
//| exact same state machine over available history ONCE at OnInit so |
//| .dir is already correct on the very first tick.                  |
//+------------------------------------------------------------------+
void WarmupCmp(CmpState &st, ENUM_TIMEFRAMES tf)
{
   int bars = iBars(_Symbol, tf);
   int n = MathMin(bars - 5, 3000);
   if(n < 5) return;
   double margin = InpBreakPips * PipSize();

   for(int s = n; s >= 1; s--)
   {
      double c1  = iClose(_Symbol, tf, s + 3);
      double c2  = iClose(_Symbol, tf, s + 2);
      double c3  = iClose(_Symbol, tf, s + 1);
      double now = iClose(_Symbol, tf, s);
      if(c1 <= 0 || now <= 0) continue;

      if(c2 > c1 && c2 > c3) { st.res = c2; st.resUsed = false; st.resFormedAt = iTime(_Symbol, tf, s + 2); }
      if(c2 < c1 && c2 < c3) { st.sup = c2; st.supUsed = false; st.supFormedAt = iTime(_Symbol, tf, s + 2); }

      // No retest gate - matches UpdateCmp() live path, see note there
      // ("TIDAK ADA WAJIB RETES 2 CANDLE").
      if(st.res > 0 && !st.resUsed && now > st.res + margin)
      {
         st.dir = "BUY"; st.since = iTime(_Symbol, tf, s);
         st.breakDir = "BUY"; st.breakLevel = st.res;
         st.resUsed = true;
      }
      else if(st.sup > 0 && !st.supUsed && now < st.sup - margin)
      {
         st.dir = "SELL"; st.since = iTime(_Symbol, tf, s);
         st.breakDir = "SELL"; st.breakLevel = st.sup;
         st.supUsed = true;
      }
   }
   st.lastBar = iTime(_Symbol, tf, 0);   // matches what live UpdateCmp would have left behind
}

bool HasPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == (long)InpMagic) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| ADAPTIVE SL - nearest valid structure on the execution timeframe. |
//| Floor at InpMinSLUsd (noise guard), REJECT (not clamp) if wider   |
//| than InpMaxSLUsd - dites 2026-08-16 lawan versi tanpa cap sama    |
//| sekali (PF turun, worst trade -132 USD) - cap ini menang, wajib   |
//| dipertahankan.                                                   |
//+------------------------------------------------------------------+
double StructuralSL(bool isBuy, double entry)
{
   double best = 0.0;
   for(int i = 1; i <= InpStructLookback; i++)
   {
      double lo = iLow(_Symbol, InpEntryTF, i);
      double hi = iHigh(_Symbol, InpEntryTF, i);
      if(isBuy)  { if(best == 0.0 || lo < best) best = lo; }
      else       { if(best == 0.0 || hi > best) best = hi; }
   }
   if(best <= 0.0) return 0.0;
   double dist = isBuy ? (entry - best) : (best - entry);
   if(dist < InpMinSLUsd) dist = InpMinSLUsd;
   return isBuy ? entry - dist : entry + dist;
}

void ManageTrailing()
{
   if(!InpUseTrailing) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;

      long type = PositionGetInteger(POSITION_TYPE);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      if(type == POSITION_TYPE_BUY)
      {
         double profit = bid - open;
         if(profit >= InpTrailStartUsd)
         {
            double newSl = bid - InpTrailStepUsd;
            if(newSl > sl) trade.PositionModify(tk, newSl, tp);
         }
      }
      else
      {
         double profit = open - ask;
         if(profit >= InpTrailStartUsd)
         {
            double newSl = ask + InpTrailStepUsd;
            if(sl == 0.0 || newSl < sl) trade.PositionModify(tk, newSl, tp);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| M30-MOMENTUM EXIT - Dadang, 2026-08-16: "TP kita: ketika M30      |
//| tidak bisa buat breakout baru atau tidak bisa break resis         |
//| terdekat dia." Two ways out, checked every tick while in position:|
//|  1. M30 CMP itself reverses against the trade -> M30 clearly      |
//|     "tidak bisa lanjut" - close immediately.                      |
//|  2. Price approaches M30's live res/sup (within InpNearTolUsd):   |
//|     if M30 actually breaks through it (resUsed/supUsed flips      |
//|     True) that's genuine continuation - keep holding, watch the   |
//|     NEXT M30 zone the same way. If instead price retreats more    |
//|     than InpRetreatTolUsd from that approach WITHOUT ever         |
//|     breaking through - M30 got rejected at its own nearest zone   |
//|     - close there.                                                |
//| research/conti_momentum_exit_sweep.py: beats a fixed-ratio TP on  |
//| EVERY parameter combo tried (avg PF 3.35 vs 1.50).                |
//+------------------------------------------------------------------+
void ManageMomentumExit()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;

      long type = PositionGetInteger(POSITION_TYPE);
      bool isBuy = (type == POSITION_TYPE_BUY);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double price = isBuy ? bid : ask;

      bool doClose = false;
      if(isBuy)
      {
         if(g_parent.dir == "SELL") doClose = true;   // M30 reversed
         else
         {
            double dist = g_parent.res - price;
            if(g_parent.res > 0.0 && dist <= InpNearTolUsd) g_approached = true;
            if(g_parent.resUsed) g_approached = false;   // M30 broke through - genuine continuation
            else if(g_approached && g_parent.res > 0.0 && dist > InpRetreatTolUsd) doClose = true;   // rejected
         }
      }
      else
      {
         if(g_parent.dir == "BUY") doClose = true;
         else
         {
            double dist = price - g_parent.sup;
            if(g_parent.sup > 0.0 && dist <= InpNearTolUsd) g_approached = true;
            if(g_parent.supUsed) g_approached = false;
            else if(g_approached && g_parent.sup > 0.0 && dist > InpRetreatTolUsd) doClose = true;
         }
      }

      if(doClose)
      {
         trade.PositionClose(tk);
         g_approached = false;
      }
   }
}

//--- Dadang, screenshot 2026-08-16: "di atasnya pas ada garis tapi malah
//--- entri BUY bro, lo harus kasih jarak dari garis, masaka entri buy di
//--- resistance." Blocks a CONTI signal if an UNBROKEN opposing H4 or M30
//--- zone sits within InpMinZoneDistUsd ahead of price - BUY blocked by a
//--- near, not-yet-broken resistance above; SELL blocked by a near support
//--- below. Validated monotonic: PF climbs from 3.71 (off) to 4.96 at 100
//--- pip (research/conti_momentum_exit_sweep.py follow-up sweep).
bool ZoneBlocksEntry(string dir)
{
   if(InpMinZoneDistUsd <= 0.0) return false;
   double price = (dir == "BUY") ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(dir == "BUY")
   {
      if(g_master.res > 0.0 && !g_master.resUsed && g_master.res > price && (g_master.res - price) < InpMinZoneDistUsd) return true;
      if(g_parent.res > 0.0 && !g_parent.resUsed && g_parent.res > price && (g_parent.res - price) < InpMinZoneDistUsd) return true;
   }
   else
   {
      if(g_master.sup > 0.0 && !g_master.supUsed && g_master.sup < price && (price - g_master.sup) < InpMinZoneDistUsd) return true;
      if(g_parent.sup > 0.0 && !g_parent.supUsed && g_parent.sup < price && (price - g_parent.sup) < InpMinZoneDistUsd) return true;
   }
   return false;
}

//--- Dadang, screenshot 2026-08-16: "jika arah M30 buy, lo hanya akan buy
//--- ketika ada garis suport, bukan sell di resisi, karena resisi buat
//--- TP." A CONTI signal only counts if price is currently "berlabuh" at
//--- a zone matching the trade direction - near an H4/M30 SUPPORT (bounce)
//--- for BUY, or near an H4/M30 RESISTANCE (breakout continuation through
//--- it) for BUY too - never in open space with no zone nearby. Symmetric
//--- for SELL. Validated: PF climbs from 3.71 (off) to 5.33 at 30 pip
//--- tolerance (research/conti_momentum_exit_sweep.py follow-up).
//--- Dadang, screenshot 2026-08-16 (chop-then-clean-break example): "ketika
//--- resis lo jebol BODI setelah chopi dia naik langsung - jadi tidak
//--- boleh entri sembarangan karena TF kecil itu hanya noise." Two very
//--- different situations both sit "near a zone": price bouncing off an
//--- UNBROKEN level (real signal, no candle-close needed from that TF
//--- yet), vs M5 wobbling right around a level that TF hasn't actually
//--- closed through yet (noise during a chop - resUsed/supUsed still
//--- false). So: for a BUY, near an unbroken SUPPORT counts (bounce), but
//--- near a RESISTANCE only counts once THAT TF's own candle has already
//--- closed through it (resUsed==true - a real breakout, not M5 noise
//--- pre-empting it). Symmetric for SELL. Validated: PF higher at every
//--- tolerance vs the plain-proximity version (research/
//--- conti_momentum_exit_sweep.py follow-up - e.g. 30 pip tol: 5.33 -> 6.30).
bool IsZoneAnchored(string dir)
{
   if(!InpRequireZoneAnchor) return true;
   double price = (dir == "BUY") ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double t = InpZoneAnchorTolUsd;
   if(dir == "BUY")
   {
      bool nearUnbrokenSup = (g_master.sup > 0.0 && !g_master.supUsed && MathAbs(price - g_master.sup) <= t) ||
                             (g_parent.sup > 0.0 && !g_parent.supUsed && MathAbs(price - g_parent.sup) <= t);
      bool nearBrokenRes   = (g_master.res > 0.0 && g_master.resUsed && MathAbs(price - g_master.res) <= t) ||
                             (g_parent.res > 0.0 && g_parent.resUsed && MathAbs(price - g_parent.res) <= t);
      return nearUnbrokenSup || nearBrokenRes;
   }
   else
   {
      bool nearUnbrokenRes = (g_master.res > 0.0 && !g_master.resUsed && MathAbs(price - g_master.res) <= t) ||
                             (g_parent.res > 0.0 && !g_parent.resUsed && MathAbs(price - g_parent.res) <= t);
      bool nearBrokenSup   = (g_master.sup > 0.0 && g_master.supUsed && MathAbs(price - g_master.sup) <= t) ||
                             (g_parent.sup > 0.0 && g_parent.supUsed && MathAbs(price - g_parent.sup) <= t);
      return nearUnbrokenRes || nearBrokenSup;
   }
}

//--- M30 flip count within the last InpChopWindowDays - Dadang's
//--- hypothesis 2026-08-16 "harusnya tehnik ini cuma gagal di sideways
//--- atau choppy" tested true directionally (trending PF 4.14 vs choppy
//--- PF 3.21, research/CORE_DOCTRINE.md ss8c) - this filter skips entries
//--- when the recent M30 CMP has been flipping a lot.
int ChopScore()
{
   int flips = 0;
   string lastDir = "";
   datetime cutoff = TimeCurrent() - (datetime)(InpChopWindowDays * 86400);
   int bars = iBars(_Symbol, InpParentTF);
   int n = MathMin(bars - 5, 2000);
   double margin = InpBreakPips * PipSize();
   // lightweight re-derivation of M30's own pivot/breakout state, walked
   // fresh from n->1 EVERY call - must be plain locals, not static, or the
   // pivot state would leak between separate ChopScore() calls instead of
   // starting clean each time.
   double dbgRes = 0, dbgSup = 0; bool dbgResUsed = true, dbgSupUsed = true;
   for(int s = n; s >= 1; s--)
   {
      datetime bt = iTime(_Symbol, InpParentTF, s);
      double c1 = iClose(_Symbol, InpParentTF, s + 3);
      double c2 = iClose(_Symbol, InpParentTF, s + 2);
      double c3 = iClose(_Symbol, InpParentTF, s + 1);
      double now = iClose(_Symbol, InpParentTF, s);
      if(c1 <= 0 || now <= 0) continue;
      if(c2 > c1 && c2 > c3) { dbgRes = c2; dbgResUsed = false; }
      if(c2 < c1 && c2 < c3) { dbgSup = c2; dbgSupUsed = false; }
      string d = "";
      if(dbgRes > 0 && !dbgResUsed && now > dbgRes + margin) { d = "BUY"; dbgResUsed = true; }
      else if(dbgSup > 0 && !dbgSupUsed && now < dbgSup - margin) { d = "SELL"; dbgSupUsed = true; }
      if(bt < cutoff) continue;   // pivot state must still walk through bars before cutoff, only counting is windowed
      if(d != "" && lastDir != "" && d != lastDir) flips++;
      if(d != "") lastDir = d;
   }
   return flips;
}

//+------------------------------------------------------------------+
//| BOOKMAP BRIDGE - ported from DD_ChainReaction_MultiTF_EA_UPGRADE  |
//| (read-only reference, never modified). Live path reads the CSV    |
//| udp_listener.py overwrites every cycle; Tester/Optimization path  |
//| replays the recorded bookmap_history_v2_*.csv archive instead,    |
//| since a live file's wall-clock timestamp never matches simulated  |
//| time. Wall-ladder fields are read-and-discarded (positional CSV,  |
//| must consume them to reach the rest of the row) but not stored -  |
//| this EA doesn't draw wall lines, only the panel numbers.          |
//|                                                                   |
//| NOT TOUCHED IN r4.0 - Dadang, 2026-08-16: "jangan sentuh area     |
//| Bookmap panelnya karena nanti masih akan gw kombinasi dengan data |
//| Bookmap kan CVD Market Puls DOM dll."                              |
//+------------------------------------------------------------------+
bool     g_bookmapOnline    = false;
double   g_bookmapPrice     = 0.0;   // Bookmap's OWN instrument price (GCZ6), for POC/VA offset conversion
double   g_bookmapCvd       = 0.0;
double   g_bookmapPulsePct  = 0.0;
string   g_bookmapAbsorption = "NONE";
double   g_bookmapPocPrice       = 0.0;
double   g_bookmapPocVolume      = 0.0;
double   g_bookmapVolRatioBuyPct = 50.0;
double   g_bookmapVal = 0.0, g_bookmapVah = 0.0;
double   g_bookmapBidIcePx = 0.0, g_bookmapBidIceRatio = 0.0;
double   g_bookmapAskIcePx = 0.0, g_bookmapAskIceRatio = 0.0;

bool     g_bmHistLoaded = false;
int      g_bmHistCount  = 0;
datetime g_bmHistTime[];
double   g_bmHistBmPrice[];
double   g_bmHistCvd[];
double   g_bmHistPulse[];
string   g_bmHistAbsorb[];
double   g_bmHistPocPrice[];
double   g_bmHistPocVolume[];
double   g_bmHistVal[];
double   g_bmHistVah[];

void LoadOneBookmapHistoryFile(string relPath)
{
   int handle = FileOpen(relPath, FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return;

   for(int i = 0; i < 24 && !FileIsEnding(handle); i++) FileReadString(handle);   // skip header row

   while(!FileIsEnding(handle))
   {
      double ts = StringToDouble(FileReadString(handle));
      if(FileIsEnding(handle)) break;
      FileReadString(handle);                              // time_wib - skip
      double price   = StringToDouble(FileReadString(handle));
      double cvd     = StringToDouble(FileReadString(handle));
      double pulse   = StringToDouble(FileReadString(handle));
      string absorb  = FileReadString(handle);
      FileReadString(handle);                              // h4_cmp - skip
      double poc     = StringToDouble(FileReadString(handle));
      double pocVol  = StringToDouble(FileReadString(handle));
      for(int i = 0; i < 3 && !FileIsEnding(handle); i++) FileReadString(handle);   // vol_ratio,buy_vol,sell_vol
      double val     = StringToDouble(FileReadString(handle));
      double vah     = StringToDouble(FileReadString(handle));
      for(int i = 0; i < 9 && !FileIsEnding(handle); i++) FileReadString(handle);   // best_bid_px..ask_ice_sz
      if(!FileIsEnding(handle)) FileReadString(handle);     // ask_ice_ratio

      if(ts <= 0) continue;

      int idx = g_bmHistCount;
      ArrayResize(g_bmHistTime,     idx + 1, 50000);
      ArrayResize(g_bmHistBmPrice,  idx + 1, 50000);
      ArrayResize(g_bmHistCvd,      idx + 1, 50000);
      ArrayResize(g_bmHistPulse,    idx + 1, 50000);
      ArrayResize(g_bmHistAbsorb,   idx + 1, 50000);
      ArrayResize(g_bmHistPocPrice, idx + 1, 50000);
      ArrayResize(g_bmHistPocVolume,idx + 1, 50000);
      ArrayResize(g_bmHistVal,      idx + 1, 50000);
      ArrayResize(g_bmHistVah,      idx + 1, 50000);

      g_bmHistTime[idx]      = (datetime)ts;
      g_bmHistBmPrice[idx]   = price;
      g_bmHistCvd[idx]       = cvd;
      g_bmHistPulse[idx]     = pulse;
      g_bmHistAbsorb[idx]    = absorb;
      g_bmHistPocPrice[idx]  = poc;
      g_bmHistPocVolume[idx] = pocVol;
      g_bmHistVal[idx]       = val;
      g_bmHistVah[idx]       = vah;
      g_bmHistCount++;
   }
   FileClose(handle);
}

void LoadBookmapHistory()
{
   g_bmHistCount  = 0;
   g_bmHistLoaded = false;
   ArrayResize(g_bmHistTime, 0);
   ArrayResize(g_bmHistBmPrice, 0);
   ArrayResize(g_bmHistCvd, 0);
   ArrayResize(g_bmHistPulse, 0);
   ArrayResize(g_bmHistAbsorb, 0);
   ArrayResize(g_bmHistPocPrice, 0);
   ArrayResize(g_bmHistPocVolume, 0);
   ArrayResize(g_bmHistVal, 0);
   ArrayResize(g_bmHistVah, 0);

   string fname;
   long search = FileFindFirst(BM_HIST_DIR + BM_HIST_GLOB, fname, FILE_COMMON);
   if(search == INVALID_HANDLE)
   {
      Print("RisetBookmapReplay: gak ada file di Common\\Files\\", BM_HIST_DIR,
            " - panel Bookmap bakal OFFLINE selama backtest ini.");
      return;
   }
   int fileCount = 0;
   do
   {
      LoadOneBookmapHistoryFile(BM_HIST_DIR + fname);
      fileCount++;
   }
   while(FileFindNext(search, fname));
   FileFindClose(search);

   g_bmHistLoaded = (g_bmHistCount > 0);
   Print("RisetBookmapReplay: ", g_bmHistCount, " baris dari ", fileCount, " file - rentang ",
         (g_bmHistCount > 0 ? TimeToString(g_bmHistTime[0], TIME_DATE|TIME_MINUTES) : "-"),
         " s/d ",
         (g_bmHistCount > 0 ? TimeToString(g_bmHistTime[g_bmHistCount-1], TIME_DATE|TIME_MINUTES) : "-"));
}

int FindBookmapHistoryIndex(datetime t)
{
   if(g_bmHistCount == 0 || t < g_bmHistTime[0]) return -1;
   int lo = 0, hi = g_bmHistCount - 1;
   while(lo < hi)
   {
      int mid = (lo + hi + 1) / 2;
      if(g_bmHistTime[mid] <= t) lo = mid; else hi = mid - 1;
   }
   return lo;
}

void ReadBookmapHistoryReplay()
{
   g_bookmapOnline = false;
   if(!g_bmHistLoaded) return;

   int idx = FindBookmapHistoryIndex(TimeCurrent());
   if(idx < 0) return;

   double ageSec = (double)TimeCurrent() - (double)g_bmHistTime[idx];
   if(ageSec > InpBookmapStaleSec * 4.0) return;

   g_bookmapOnline     = true;
   g_bookmapPrice      = g_bmHistBmPrice[idx];
   g_bookmapCvd        = g_bmHistCvd[idx];
   g_bookmapPulsePct   = g_bmHistPulse[idx];
   g_bookmapAbsorption = g_bmHistAbsorb[idx];
   g_bookmapPocPrice   = g_bmHistPocPrice[idx];
   g_bookmapPocVolume  = g_bmHistPocVolume[idx];
   g_bookmapVal        = g_bmHistVal[idx];
   g_bookmapVah        = g_bmHistVah[idx];
   // history archive doesn't carry iceberg - stays at 0/"none" during replay
   g_bookmapBidIcePx = 0.0; g_bookmapBidIceRatio = 0.0;
   g_bookmapAskIcePx = 0.0; g_bookmapAskIceRatio = 0.0;
}

void ReadBookmapBridge()
{
   g_bookmapOnline = false;
   if(!InpShowBookmapPanel) return;

   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
   {
      ReadBookmapHistoryReplay();
      return;
   }

   int handle = FileOpen("bookmap_live_signal.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return;   // bridge never ran, or udp_listener.py isn't up

   int totalFields = 18 + WALL_SLOTS_PER_SIDE * 2 * 2;
   for(int i = 0; i < totalFields && !FileIsEnding(handle); i++) FileReadString(handle);   // skip header row
   if(FileIsEnding(handle)) { FileClose(handle); return; }

   double ts    = StringToDouble(FileReadString(handle));
   double price = StringToDouble(FileReadString(handle));
   double cvd     = StringToDouble(FileReadString(handle));
   double pulse   = StringToDouble(FileReadString(handle));
   string absorb  = FileReadString(handle);
   double pocPrice   = StringToDouble(FileReadString(handle));
   double pocVolume  = StringToDouble(FileReadString(handle));
   double volRatio   = StringToDouble(FileReadString(handle));
   FileReadString(handle);                              // buy_vol_session - skip
   FileReadString(handle);                              // sell_vol_session - skip
   double val        = StringToDouble(FileReadString(handle));
   double vah         = StringToDouble(FileReadString(handle));
   double bidIcePx    = StringToDouble(FileReadString(handle));
   FileReadString(handle);                              // bid_ice_sz - skip
   double bidIceRatio = StringToDouble(FileReadString(handle));
   double askIcePx    = StringToDouble(FileReadString(handle));
   FileReadString(handle);                              // ask_ice_sz - skip
   double askIceRatio = StringToDouble(FileReadString(handle));
   // wall ladder - read and discard, this panel doesn't draw wall lines
   for(int i = 0; i < WALL_SLOTS_PER_SIDE * 2 * 2 && !FileIsEnding(handle); i++) FileReadString(handle);
   FileClose(handle);

   double ageSec = (double)TimeGMT() - ts;
   if(MathAbs(ageSec) > InpBookmapStaleSec) return;   // stale/offline

   g_bookmapOnline     = true;
   g_bookmapPrice      = price;
   g_bookmapCvd        = cvd;
   g_bookmapPulsePct   = pulse;
   g_bookmapAbsorption = absorb;
   g_bookmapPocPrice       = pocPrice;
   g_bookmapPocVolume      = pocVolume;
   g_bookmapVolRatioBuyPct = volRatio;
   g_bookmapVal            = val;
   g_bookmapVah            = vah;
   g_bookmapBidIcePx       = bidIcePx;
   g_bookmapBidIceRatio    = bidIceRatio;
   g_bookmapAskIcePx       = askIcePx;
   g_bookmapAskIceRatio    = askIceRatio;
}

//+------------------------------------------------------------------+
//| PANEL - CCanvas, ported style from DD_ChainReaction_MultiTF_EA_   |
//| UPGRADE.mq5 (gold/dark rounded card, PnlTxt/Row/Rule helpers).    |
//| Content stays this EA's own: CMP per TF (with timestamps), CONTI  |
//| status, M30-momentum exit watch, position, win rate - plus the    |
//| Bookmap block (untouched, see note above ManageMomentumExit).     |
//+------------------------------------------------------------------+
color DirColor(string d) { return (d == "BUY") ? clrLime : (d == "SELL" ? clrTomato : clrSilver); }

CCanvas g_panelCanvas;
uint    g_lastPanelDrawMs = 0;

#define PNL_FONT "Arial"
#define PNL_WEIGHT_NORMAL 400
#define PNL_WEIGHT_BOLD   700

color PNL_GOLD    = C'217,180,101';
color PNL_EMERALD = C'52,211,153';
color PNL_ROSE    = C'251,113,133';
color PNL_SILVER  = C'139,149,167';
color PNL_LABEL   = C'255,255,255';
color PNL_WHITE   = C'255,255,255';
color PNL_BG      = C'14,16,23';
color PNL_RULE    = C'52,45,30';
color PNL_SHADOW  = C'0,0,0';

int PNL_PX = 12, PNL_PY = 18, PNL_W = 300, PNL_H = 860;
int PNL_MARGIN = 14, PNL_RADIUS = 10, PNL_BORDER = 2;
int PNL_VALUE_COL = 140;

color PnlLerp(uchar r1, uchar g1, uchar b1, uchar r2, uchar g2, uchar b2, double t)
{
   t = MathMax(0.0, MathMin(1.0, t));
   uchar r = (uchar)MathRound(r1 + (r2 - r1) * t);
   uchar g = (uchar)MathRound(g1 + (g2 - g1) * t);
   uchar b = (uchar)MathRound(b1 + (b2 - b1) * t);
   return (color)((uchar)r + ((uchar)g << 8) + ((uchar)b << 16));
}

void PnlFillRoundedRect(int x1, int y1, int x2, int y2, int r, uint argb)
{
   g_panelCanvas.FillRectangle(x1 + r, y1, x2 - r, y2, argb);
   g_panelCanvas.FillRectangle(x1, y1 + r, x2, y2 - r, argb);
   g_panelCanvas.FillCircle(x1 + r, y1 + r, r, argb);
   g_panelCanvas.FillCircle(x2 - r, y1 + r, r, argb);
   g_panelCanvas.FillCircle(x1 + r, y2 - r, r, argb);
   g_panelCanvas.FillCircle(x2 - r, y2 - r, r, argb);
}

void PnlTxt(int x, int y, string s, color clr, int size = 11, uint anchor = TA_LEFT | TA_TOP)
{
   g_panelCanvas.FontSet(PNL_FONT, size, PNL_WEIGHT_NORMAL);
   g_panelCanvas.TextOut(x, y, s, ColorToARGB(clr, 255), anchor);
}

void PnlTxtB(int x, int y, string s, color clr, int size = 14, uint anchor = TA_LEFT | TA_TOP)
{
   g_panelCanvas.FontSet(PNL_FONT, size, PNL_WEIGHT_BOLD);
   uint argbOutline = ColorToARGB(C'0,0,0', 255);
   uint argbFill    = ColorToARGB(clr, 255);
   for(int dx = -2; dx <= 2; dx++)
      for(int dy = -2; dy <= 2; dy++)
         if(dx != 0 || dy != 0)
            g_panelCanvas.TextOut(x + dx, y + dy, s, argbOutline, anchor);
   g_panelCanvas.TextOut(x, y, s, argbFill, anchor);
}

void PnlRule(int x, int y, int w) { g_panelCanvas.FillRectangle(x, y, x + w, y + 1, ColorToARGB(PNL_RULE, 255)); }

void PnlRow(int x, int y, int colW, string label, string value, color valueClr)
{
   PnlTxtB(x, y, label, PNL_LABEL, 11);
   PnlTxtB(x + PNL_VALUE_COL, y - 1, value, valueClr, 13);
}

void PnlAccentRow(int x, int y, int colW, string label, string value, color valueClr, color accentClr)
{
   g_panelCanvas.FillRectangle(x - 9, y, x - 6, y + 14, ColorToARGB(accentClr, 255));
   PnlRow(x, y, colW, label, value, valueClr);
}

void PnlStatusDot(int x, int y, color clr) { g_panelCanvas.FillCircle(x, y, 3, ColorToARGB(clr, 255)); }

void CreatePanel()
{
   ObjectsDeleteAll(0, DASH_PREFIX);
   int bmpW = PNL_W + PNL_MARGIN * 2, bmpH = PNL_H + PNL_MARGIN * 2;
   g_panelCanvas.CreateBitmapLabel(DASH_PREFIX + "CANVAS", 15, 15, bmpW, bmpH, COLOR_FORMAT_ARGB_NORMALIZE);
   ObjectSetInteger(0, DASH_PREFIX + "CANVAS", OBJPROP_CORNER, CORNER_LEFT_UPPER);
}

int    g_lastDealsTotal  = -1;
int    g_statTrades = 0, g_statWins = 0, g_statLosses = 0;
double g_statTotalProfit = 0.0;

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
   if(!MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION))
   {
      uint nowMs = GetTickCount();
      if(nowMs - g_lastPanelDrawMs < 200) return;
      g_lastPanelDrawMs = nowMs;
   }

   int ox = PNL_MARGIN, oy = PNL_MARGIN;
   g_panelCanvas.Erase(0);

   for(int s = 6; s >= 1; s--)
      PnlFillRoundedRect(ox + s, oy + s, ox + PNL_W + s, oy + PNL_H + s, PNL_RADIUS,
                          ColorToARGB(PNL_SHADOW, (uchar)(7 * (7 - s))));

   PnlFillRoundedRect(ox, oy, ox + PNL_W, oy + PNL_H, PNL_RADIUS, ColorToARGB(PNL_GOLD, 255));
   PnlFillRoundedRect(ox + PNL_BORDER, oy + PNL_BORDER, ox + PNL_W - PNL_BORDER, oy + PNL_H - PNL_BORDER,
                       PNL_RADIUS - PNL_BORDER, ColorToARGB(PNL_BG, 255));

   g_panelCanvas.FillRectangle(ox + PNL_RADIUS, oy, ox + PNL_W - PNL_RADIUS, oy + 4, ColorToARGB(PNL_GOLD, 255));
   for(int i = 0; i < 6; i++)
      g_panelCanvas.FillRectangle(ox + PNL_RADIUS, oy + 4 + i, ox + PNL_W - PNL_RADIUS, oy + 5 + i,
                                   ColorToARGB(PNL_GOLD, (uchar)(90 - i * 14)));

   int x0 = ox + 14, y = oy + 12, contentW = PNL_W - 28;

   PnlTxtB(x0, y, InpPanelName, PNL_GOLD, 14); y += 19;
   PnlTxtB(x0, y, "[ " + RESEARCH_VERSION + " ]  " + InpOwnerName, PNL_LABEL, 10); y += 15;
   PnlTxtB(x0, y, "RISET - bukan produksi (magic " + (string)InpMagic + ")", PNL_EMERALD, 10); y += 17;
   PnlRule(x0, y, contentW); y += 10;

   // CONTI status - Dadang 2026-08-16: "jika H4 BO buy dan M30 BO buy kita
   // cari buy di M5." True the instant H4 and M30 CMP agree; the M5 fresh
   // breakout that actually triggers an order is separate (see ENTRY row).
   bool haveDir = (g_master.dir != "" && g_parent.dir != "");
   bool contiOn = haveDir && (g_master.dir == g_parent.dir);
   string modeTxt = !haveDir ? "Mode: WAIT" : (contiOn ? "Mode: CONTI AKTIF (H4=M30)" : "*** M30 VR - TUNGGU REALIGN ***");
   color modeClr  = !haveDir ? PNL_LABEL : (contiOn ? PNL_EMERALD : PNL_ROSE);
   PnlStatusDot(x0 + 3, y + 6, modeClr);
   PnlTxtB(x0 + 13, y, modeTxt, modeClr, 12); y += 19;
   PnlTxtB(x0, y, StringFormat("%s  >  %s  >  %s", TfName(InpMasterTF), TfName(InpParentTF), TfName(InpEntryTF)), PNL_WHITE, 11); y += 17;
   PnlRule(x0, y, contentW); y += 8;

   // COUNTDOWN - Dadang: "buatkan indikator hitung mundur candle di tiap
   // TF." Waktu tersisa sampai candle YANG SEDANG JALAN di TF itu ditutup.
   PnlTxtB(x0, y, "COUNTDOWN CANDLE", PNL_GOLD, 10); y += 15;
   ENUM_TIMEFRAMES cdTf[3] = {InpMasterTF, InpParentTF, InpEntryTF};
   for(int cI = 0; cI < 3; cI++)
   {
      PnlRow(x0, y, contentW, TfName(cdTf[cI]), CountdownStr(cdTf[cI]), PNL_WHITE); y += 15;
   }
   PnlRule(x0, y, contentW); y += 8;

   PnlRow(x0, y, contentW, "MASTER (" + TfName(InpMasterTF) + ")", g_master.dir == "" ? "..." : g_master.dir, DirColor(g_master.dir)); y += 14;
   PnlTxt(x0 + 4, y, "sejak " + (g_master.since == 0 ? "-" : TimeToString(g_master.since, TIME_DATE | TIME_MINUTES)), PNL_SILVER, 9); y += 15;

   PnlRow(x0, y, contentW, "PARENT (" + TfName(InpParentTF) + ")", g_parent.dir == "" ? "..." : g_parent.dir, DirColor(g_parent.dir)); y += 14;
   PnlTxt(x0 + 4, y, "sejak " + (g_parent.since == 0 ? "-" : TimeToString(g_parent.since, TIME_DATE | TIME_MINUTES)), PNL_SILVER, 9); y += 15;

   PnlRow(x0, y, contentW, "ENTRY (" + TfName(InpEntryTF) + ")", g_entry.dir == "" ? "..." : g_entry.dir, DirColor(g_entry.dir)); y += 14;
   PnlTxt(x0 + 4, y, "sejak " + (g_entry.since == 0 ? "-" : TimeToString(g_entry.since, TIME_DATE | TIME_MINUTES))
          + (g_entry.freshBreak ? "  [FRESH BREAK]" : ""),
          g_entry.freshBreak ? PNL_GOLD : PNL_SILVER, 9); y += 18;
   PnlRule(x0, y, contentW); y += 8;

   // M30-MOMENTUM EXIT WATCH - live view of what ManageMomentumExit() is
   // actually tracking right now, only meaningful while a position is open.
   bool inPos = HasPosition();
   if(inPos)
   {
      long ptype = -1; double pOpen = 0, pSl = 0, pPnl = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong tk = PositionGetTicket(i);
         if(!PositionSelectByTicket(tk)) continue;
         if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
         if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
         ptype = PositionGetInteger(POSITION_TYPE);
         pOpen = PositionGetDouble(POSITION_PRICE_OPEN);
         pSl   = PositionGetDouble(POSITION_SL);
         pPnl  = PositionGetDouble(POSITION_PROFIT);
         break;
      }
      bool posBuy = (ptype == POSITION_TYPE_BUY);
      double zoneLv = posBuy ? g_parent.res : g_parent.sup;
      double curPx  = posBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double distToZone = zoneLv > 0 ? MathAbs(zoneLv - curPx) : -1.0;
      // short status word in the value column (PnlRow's value font is too
      // big/short-columned for a sentence - Dadang, 2026-08-16: "area ini
      // keluar dari kotak panel"), full detail on the smaller sub-line
      // below, same split pattern as MASTER/PARENT/ENTRY's "sejak" line.
      PnlRow(x0, y, contentW, "M30 EXIT WATCH", g_approached ? "MENDEKAT" : "MENUNGGU",
             g_approached ? PNL_GOLD : PNL_LABEL); y += 14;
      PnlTxt(x0 + 4, y, distToZone >= 0 ? DoubleToString(distToZone, 2) + " ke " + (posBuy ? "resis" : "suport") + " M30 terdekat" : "belum ada zona M30",
             PNL_SILVER, 9); y += 15;
   }
   else
   {
      PnlRow(x0, y, contentW, "M30 EXIT WATCH", "-", PNL_LABEL); y += 18;
   }

   if(InpUseChopFilter)
   {
      int chop = ChopScore();
      bool chopBlocked = (chop > InpChopMaxFlips);
      PnlRow(x0, y, contentW, "Chop Filter", StringFormat("%d flip %s", chop, chopBlocked ? "[SKIP]" : "[OK]"),
             chopBlocked ? PNL_ROSE : PNL_EMERALD); y += 14;
      PnlTxt(x0 + 4, y, StringFormat("maks %d flip / %d hari", InpChopMaxFlips, InpChopWindowDays), PNL_SILVER, 9); y += 15;
   }

   // JARAK ZONA - Dadang, 2026-08-16: "kasih jarak dari garis, masaka
   // entri buy di resistance." Shows live whether the NEXT signal (if H4=
   // M30 already aligned) would currently be blocked by a too-close
   // unbroken opposing zone.
   if(InpMinZoneDistUsd > 0.0 && g_master.dir != "" && g_master.dir == g_parent.dir)
   {
      bool zoneBlocked = ZoneBlocksEntry(g_master.dir);
      PnlRow(x0, y, contentW, "Jarak Zona", zoneBlocked ? "TERLALU DEKAT" : "AMAN",
             zoneBlocked ? PNL_ROSE : PNL_EMERALD); y += 14;
      PnlTxt(x0 + 4, y, StringFormat("min %.2f dari resis/suport belum jebol", InpMinZoneDistUsd), PNL_SILVER, 9); y += 15;

      bool anchored = IsZoneAnchored(g_master.dir);
      PnlRow(x0, y, contentW, "Zone Anchor", anchored ? "BERLABUH" : "RUANG KOSONG",
             anchored ? PNL_EMERALD : PNL_ROSE); y += 14;
      PnlTxt(x0 + 4, y, StringFormat("dalam %.2f dari resis/suport H4/M30", InpZoneAnchorTolUsd), PNL_SILVER, 9); y += 15;
   }
   PnlRule(x0, y, contentW); y += 10;

   if(InpCheckChainStrength)
   {
      bool strong = (g_chainCheck.dir == "" || g_parent.dir == "" || g_chainCheck.dir == g_parent.dir);
      PnlRow(x0, y, contentW, "CHECK (" + TfName(InpChainCheckTF) + ")",
             g_chainCheck.dir == "" ? "..." : g_chainCheck.dir, DirColor(g_chainCheck.dir)); y += 14;
      PnlTxt(x0 + 4, y, strong ? "KUAT (utuh)" : "LEMAH (bolong - masih nguji parent)",
             strong ? PNL_EMERALD : PNL_ROSE, 9); y += 15;
   }
   PnlRule(x0, y, contentW); y += 10;

   RecalcStatsIfNeeded();
   double winRate = (g_statTrades > 0) ? ((double)g_statWins / (double)g_statTrades * 100.0) : 0.0;
   color winRateClr = (winRate >= 50.0 || g_statTrades == 0) ? PNL_EMERALD : PNL_ROSE;
   PnlRow(x0, y, contentW, "Win Rate", StringFormat("%.1f%%  (%dW / %dL)", winRate, g_statWins, g_statLosses), winRateClr); y += 16;
   PnlRow(x0, y, contentW, "Closed Profit", StringFormat("%+.2f  (%d trades)", g_statTotalProfit, g_statTrades),
          g_statTotalProfit >= 0 ? PNL_EMERALD : PNL_ROSE); y += 18;
   PnlRule(x0, y, contentW); y += 10;

   // short status word in the value column + detail on its own sub-line -
   // Dadang, 2026-08-16: "area posisi masih keluar dari kotak panel" (the
   // old one-line "BUY @ 2650.32  SL 2645.00  P/L +12.34" string is far
   // too wide for PNL_VALUE_COL at this font size).
   string posShort = "-"; string posDetail = ""; color posClr = PNL_LABEL;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      long type   = PositionGetInteger(POSITION_TYPE);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double pnl  = PositionGetDouble(POSITION_PROFIT);
      posShort  = (type == POSITION_TYPE_BUY ? "BUY" : "SELL");
      posDetail = StringFormat("@ %.2f  SL %.2f  P/L %+.2f", open, sl, pnl);
      posClr = (pnl >= 0) ? PNL_EMERALD : PNL_ROSE;
      break;
   }
   PnlRow(x0, y, contentW, "Posisi", posShort, posClr); y += 14;
   if(posDetail != "") { PnlTxt(x0 + 4, y, posDetail, posClr, 9); y += 15; }
   PnlRow(x0, y, contentW, "Bal / Equity", StringFormat("%.2f / %.2f", AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY)), PNL_WHITE); y += 18;
   PnlRule(x0, y, contentW); y += 12;

   //--- BOOKMAP BLOCK - NOT TOUCHED (Dadang, 2026-08-16: "jangan sentuh
   //--- area Bookmap panelnya karena nanti masih akan gw kombinasi dengan
   //--- data Bookmap kan CVD Market Puls DOM dll") -----------------------
   if(InpShowBookmapPanel)
   {
      if(g_bookmapOnline)
      {
         PnlStatusDot(x0 + 3, y + 5, PNL_GOLD);
         PnlTxtB(x0 + 13, y, "BOOKMAP  ·  LIVE", PNL_GOLD, 11); y += 18;
         PnlRow(x0, y, contentW, "CVD", StringFormat("%+.1f", g_bookmapCvd), g_bookmapCvd >= 0 ? PNL_EMERALD : PNL_ROSE); y += 16;

         color pulseClr = (g_bookmapAbsorption != "NONE") ? C'251,191,36' : PNL_LABEL;
         PnlRow(x0, y, contentW, "Pulse / Absorb", StringFormat("%.1f%%  %s", g_bookmapPulsePct, g_bookmapAbsorption), pulseClr); y += 18;

         double pricePct = MathMax(-100.0, MathMin(100.0, (g_bookmapPulsePct - 50.0) * 2.0));
         int gx = x0 + contentW / 2, gy = y + 50, gr = 48;
         for(double a = 180.0; a <= 360.0; a += 1.5)
         {
            double rad = a * M_PI / 180.0;
            int px2 = gx + (int)MathRound(gr * MathCos(rad));
            int py2 = gy + (int)MathRound(gr * MathSin(rad));
            double t = (a - 180.0) / 180.0;
            color c = (t < 0.5)
                        ? PnlLerp(150, 45, 60,  70, 70, 78,  t / 0.5)
                        : PnlLerp(70, 70, 78,  40, 140, 100, (t - 0.5) / 0.5);
            g_panelCanvas.FillCircle(px2, py2, 4, ColorToARGB(c, 235));
         }
         double needleAngle = 180.0 + ((pricePct + 100.0) / 200.0) * 180.0;
         double nrad = needleAngle * M_PI / 180.0;
         int tipx = gx + (int)MathRound(40 * MathCos(nrad));
         int tipy = gy + (int)MathRound(40 * MathSin(nrad));
         double ndx = tipx - gx, ndy = tipy - gy, nlen = MathSqrt(ndx * ndx + ndy * ndy);
         double nx = -ndy / nlen, ny = ndx / nlen;
         uint needleClr = ColorToARGB(PNL_WHITE, 255);
         g_panelCanvas.Line(gx, gy, tipx, tipy, needleClr);
         g_panelCanvas.Line((int)(gx + nx), (int)(gy + ny), (int)(tipx + nx), (int)(tipy + ny), needleClr);
         g_panelCanvas.Line((int)(gx - nx), (int)(gy - ny), (int)(tipx - nx), (int)(tipy - ny), needleClr);
         g_panelCanvas.FillCircle(gx, gy, 4, needleClr);

         color pressClr = (pricePct > 15.0) ? PNL_EMERALD : (pricePct < -15.0) ? PNL_ROSE : PNL_LABEL;
         PnlTxtB(x0, gy + gr + 10, "Price down", PNL_LABEL, 9);
         PnlTxtB(x0 + contentW - 56, gy + gr + 10, "Price up", PNL_LABEL, 9);
         PnlTxtB(gx - 24, gy + gr + 6, StringFormat("%+.0f%%", pricePct), pressClr, 15);
         y = gy + gr + 30;
         PnlRule(x0, y, contentW); y += 10;

         PnlRow(x0, y, contentW, "Vol Ratio", StringFormat("%.0f%% BUY / %.0f%% SELL", g_bookmapVolRatioBuyPct, 100.0 - g_bookmapVolRatioBuyPct),
                g_bookmapVolRatioBuyPct >= 50.0 ? PNL_EMERALD : PNL_ROSE); y += 16;

         double bmOffset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
         string pocTxt = g_bookmapPocPrice > 0 ? StringFormat("%.2f (%.0f vol)", g_bookmapPocPrice + bmOffset, g_bookmapPocVolume) : "-";
         PnlRow(x0, y, contentW, "POC", pocTxt, PNL_GOLD); y += 16;

         string vaTxt = (g_bookmapVah > g_bookmapVal && g_bookmapVal > 0)
                          ? StringFormat("%.2f - %.2f", g_bookmapVal + bmOffset, g_bookmapVah + bmOffset) : "-";
         PnlRow(x0, y, contentW, "Value Area", vaTxt, PNL_GOLD); y += 16;

         string iceTxt; color iceClr;
         if(g_bookmapBidIcePx > 0 && g_bookmapBidIceRatio >= g_bookmapAskIceRatio)
         {
            iceTxt = StringFormat("BID @ %.2f (%.1fx)", g_bookmapBidIcePx + bmOffset, g_bookmapBidIceRatio);
            iceClr = clrMagenta;
         }
         else if(g_bookmapAskIcePx > 0)
         {
            iceTxt = StringFormat("ASK @ %.2f (%.1fx)", g_bookmapAskIcePx + bmOffset, g_bookmapAskIceRatio);
            iceClr = clrMagenta;
         }
         else { iceTxt = "none"; iceClr = PNL_LABEL; }
         PnlRow(x0, y, contentW, "Iceberg", iceTxt, iceClr); y += 18;
      }
      else
      {
         PnlStatusDot(x0 + 3, y + 5, clrGray);
         PnlTxtB(x0 + 13, y, "BOOKMAP: OFFLINE", clrGray, 11); y += 18;
         PnlTxtB(x0, y, "(gak jalan / di luar rentang rekaman)", clrGray, 9);
      }
   }
   //--- END BOOKMAP BLOCK ------------------------------------------------

   int footerY = oy + PNL_H - 34;
   PnlRule(x0, footerY, contentW);
   PnlTxtB(x0, footerY + 8, "Chain Reaction System - riset", PNL_SILVER, 9);
   PnlTxtB(x0, footerY + 20, InpOwnerName, PNL_SILVER, 9);

   g_panelCanvas.Update(true);
   ChartRedraw(0);
}

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   // NOTE: ZeroMemory() on a struct holding a `string` field leaves that
   // string in a corrupted, non-"" state that later prints as "(null)"
   // instead of comparing equal to "" - MQL5 strings are reference-counted
   // objects, not raw bytes. Every CmpState needs .dir set explicitly.
   CmpState blank;
   blank.dir = ""; blank.since = 0; blank.sup = 0; blank.res = 0;
   blank.supUsed = true; blank.resUsed = true; blank.lastBar = 0;
   blank.resFormedAt = 0; blank.supFormedAt = 0;
   blank.freshBreak = false; blank.breakDir = ""; blank.breakLevel = 0;
   g_entry = blank; g_parent = blank; g_master = blank;
   g_chainCheck = blank;
   g_approached = false;
   ArrayFree(g_h4LinesR); ArrayFree(g_h4LinesS); ArrayFree(g_m30LinesR); ArrayFree(g_m30LinesS);
   ArrayFree(g_h4ResPx); ArrayFree(g_h4SupPx); ArrayFree(g_m30ResPx); ArrayFree(g_m30SupPx);
   ArrayFree(g_h4ResTm); ArrayFree(g_h4SupTm); ArrayFree(g_m30ResTm); ArrayFree(g_m30SupTm);

   // WARMUP: replay history so CMP is correct from tick 1, not "..." until
   // the next live breakout happens to occur (Dadang: "gak baca CMP
   // breakout, gw kosong ini").
   WarmupCmp(g_entry,      InpEntryTF);
   WarmupCmp(g_parent,     InpParentTF);
   WarmupCmp(g_master,     InpMasterTF);
   WarmupCmp(g_chainCheck, InpChainCheckTF);

   // Gambar zona H4/M30 kalau harga KEBETULAN udah deket pas EA nyala -
   // biasanya nunggu tick pertama di OnTick(), ini cuma jaga-jaga awal.
   UpdateSnrLinesNearPrice();

   CreatePanel();
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      LoadBookmapHistory();

   Print("DD_ChainResearch_EA [", RESEARCH_VERSION, "] - RISET, bukan produksi. Magic ", InpMagic,
         "  |  MASTER=", g_master.dir, " PARENT=", g_parent.dir, " ENTRY=", g_entry.dir);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   g_panelCanvas.Destroy();
   ObjectsDeleteAll(0, DASH_PREFIX);
   ObjectsDeleteAll(0, SNR_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Dadang, 2026-08-16: "lo buat aja jadi csv hasil backtest, jadi     |
//| ketika selesai gw besok tinggal bilang lo liat hasil replay        |
//| semalem." Fires automatically once a Strategy Tester pass finishes |
//| - writes every closed trade (this EA's magic/symbol only) to a     |
//| CSV in Common\Files\ (same shared folder the Bookmap bridge uses)  |
//| so it can be read directly afterward without any manual export.    |
//| Fixed filename, overwritten each run - always the LATEST pass.     |
//+------------------------------------------------------------------+
double OnTester()
{
   int handle = FileOpen("DD_ChainResearch_last_test_report.csv",
                          FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return 0.0;

   FileWrite(handle, "close_time", "dir", "volume", "open_time", "open_price",
             "close_price", "profit", "reason");

   if(HistorySelect(0, TimeCurrent()))
   {
      int total = HistoryDealsTotal();

      // First pass: cache each position's OPEN (DEAL_ENTRY_IN) info by position id.
      ulong    posId[]; double posOpenPx[]; datetime posOpenTm[]; long posType[];
      for(int i = 0; i < total; i++)
      {
         ulong dt = HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(dt, DEAL_MAGIC) != (long)InpMagic) continue;
         if(HistoryDealGetString(dt, DEAL_SYMBOL) != _Symbol) continue;
         if(HistoryDealGetInteger(dt, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;

         int n = ArraySize(posId);
         ArrayResize(posId, n + 1); ArrayResize(posOpenPx, n + 1);
         ArrayResize(posOpenTm, n + 1); ArrayResize(posType, n + 1);
         posId[n]     = HistoryDealGetInteger(dt, DEAL_POSITION_ID);
         posOpenPx[n] = HistoryDealGetDouble(dt, DEAL_PRICE);
         posOpenTm[n] = (datetime)HistoryDealGetInteger(dt, DEAL_TIME);
         posType[n]   = HistoryDealGetInteger(dt, DEAL_TYPE);
      }

      // Second pass: one row per CLOSE (DEAL_ENTRY_OUT/OUT_BY), matched back
      // to its position's open info above.
      for(int i = 0; i < total; i++)
      {
         ulong dt = HistoryDealGetTicket(i);
         if(HistoryDealGetInteger(dt, DEAL_MAGIC) != (long)InpMagic) continue;
         if(HistoryDealGetString(dt, DEAL_SYMBOL) != _Symbol) continue;
         long entryFlag = HistoryDealGetInteger(dt, DEAL_ENTRY);
         if(entryFlag != DEAL_ENTRY_OUT && entryFlag != DEAL_ENTRY_OUT_BY) continue;

         ulong pid = HistoryDealGetInteger(dt, DEAL_POSITION_ID);
         double openPx = 0.0; datetime openTm = 0; long otype = -1;
         for(int k = 0; k < ArraySize(posId); k++)
            if(posId[k] == pid) { openPx = posOpenPx[k]; openTm = posOpenTm[k]; otype = posType[k]; break; }

         datetime closeTm = (datetime)HistoryDealGetInteger(dt, DEAL_TIME);
         double closePx   = HistoryDealGetDouble(dt, DEAL_PRICE);
         double profit    = HistoryDealGetDouble(dt, DEAL_PROFIT) + HistoryDealGetDouble(dt, DEAL_SWAP)
                             + HistoryDealGetDouble(dt, DEAL_COMMISSION);
         double vol       = HistoryDealGetDouble(dt, DEAL_VOLUME);
         string dir       = (otype == DEAL_TYPE_BUY) ? "BUY" : "SELL";

         long reasonCode = HistoryDealGetInteger(dt, DEAL_REASON);
         string reason = "OTHER";
         if(reasonCode == DEAL_REASON_SL) reason = "SL";
         else if(reasonCode == DEAL_REASON_TP) reason = "TP";
         else if(reasonCode == DEAL_REASON_EXPERT) reason = "EXPERT";   // ManageMomentumExit() close
         else if(reasonCode == DEAL_REASON_SO) reason = "STOPOUT";

         FileWrite(handle,
                    TimeToString(closeTm, TIME_DATE | TIME_SECONDS), dir, DoubleToString(vol, 2),
                    TimeToString(openTm, TIME_DATE | TIME_SECONDS), DoubleToString(openPx, 2),
                    DoubleToString(closePx, 2), DoubleToString(profit, 2), reason);
      }
   }

   FileClose(handle);
   return 0.0;
}

void OnTick()
{
   UpdateCmp(g_entry,  InpEntryTF);
   UpdateCmp(g_parent, InpParentTF);
   UpdateCmp(g_master, InpMasterTF);
   if(InpCheckChainStrength) UpdateCmp(g_chainCheck, InpChainCheckTF);
   UpdateSnrLinesNearPrice();   // draws H4/M30 lines only once price is close - "biar gak spam"

   ManageMomentumExit();   // r4.0: replaces the old fixed TP entirely - checked every tick, own position or none
   ManageTrailing();       // off by default in r4.0, see RISIKO group comment
   ReadBookmapBridge();
   UpdatePanel();

   if(HasPosition()) return;                       // one position at a time

   // CONTI ENTRY - Dadang, 2026-08-16 (exact spec): "jika H4 BO buy close
   // dan M30 BO buy kita akan cari buy di M5. Jika M5 sell kita stop entri
   // sampai M5 BO buy lagi dengan catatan ketika M5 buy terjadi M30 masih
   // CMP buy. Dan jika M30 sell maka kita stop sampai ada M30 jadi buy
   // lagi dengan catatan H4 masih buy. Kita akan ulang terus."
   // g_entry.freshBreak is a FRESH-EVENT flag (only true on the exact bar
   // a new M5 break fires) - "stop entri sampai M5 BO buy lagi" and "stop
   // sampai M30 balik" both fall out for free from checking this live
   // every tick against the CURRENT g_master/g_parent state, no separate
   // state machine needed (research/cascade_align_sweep.py, PF 1.90
   // standalone; combined with ManageMomentumExit() above, PF 3.71).
   string signalDir = "";
   if(g_master.dir == "BUY"  && g_parent.dir == "BUY"  && g_entry.freshBreak && g_entry.breakDir == "BUY")  signalDir = "BUY";
   if(g_master.dir == "SELL" && g_parent.dir == "SELL" && g_entry.freshBreak && g_entry.breakDir == "SELL") signalDir = "SELL";
   if(signalDir == "") return;

   if(ZoneBlocksEntry(signalDir)) return;   // tembok resistance/support (H4/M30 belum jebol) kedeketan - skip
   if(!IsZoneAnchored(signalDir)) return;   // harus berlabuh di suport (BUY) / resis (SELL) H4/M30 - bukan di ruang kosong

   if(InpUseChopFilter && ChopScore() > InpChopMaxFlips) return;   // market lagi choppy, skip

   if(InpRequireStrongChain && g_chainCheck.dir != "" && g_chainCheck.dir != signalDir) return;

   datetime bar = iTime(_Symbol, InpEntryTF, 0);
   if(bar == g_lastEntryBar) return;               // one decision per bar
   ExecuteEntry(signalDir, bar);
}

//+------------------------------------------------------------------+
//| Places the order the instant CONTI fires. TP intentionally left at|
//| 0 (no fixed target) - exit is entirely ManageMomentumExit()'s job |
//| now. Only SL is a hard order-level stop.                          |
//+------------------------------------------------------------------+
void ExecuteEntry(string dir, datetime bar)
{
   bool isBuy = (dir == "BUY");
   double price = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                        : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = InpAdaptiveSL ? StructuralSL(isBuy, price)
                             : (isBuy ? price - InpMinSLUsd : price + InpMinSLUsd);
   if(sl <= 0.0) return;
   double slDist = MathAbs(price - sl);

   // Structural SL cap - REJECT (not clamp) if the structure calls for
   // something wider than InpMaxSLUsd. Tested wider/removed entirely
   // 2026-08-16: this cap wins on PF AND on tail risk, keep it.
   if(slDist > InpMaxSLUsd) return;

   g_approached = false;   // fresh position - M30-momentum exit watch starts clean
   bool ok = isBuy ? trade.Buy(InpLot, _Symbol, 0.0, sl, 0.0, "CONTI_" + RESEARCH_VERSION)
                   : trade.Sell(InpLot, _Symbol, 0.0, sl, 0.0, "CONTI_" + RESEARCH_VERSION);
   if(ok) g_lastEntryBar = bar;
}
