//+------------------------------------------------------------------+
//| DD_DumpCMP_EA.mq5                                                |
//|                                                                   |
//| Exports DD_CMP_Indicator's OWN buffers to CSV so the Python       |
//| research can be checked against the real detector instead of a    |
//| reimplementation of it.                                           |
//|                                                                   |
//| Dadang, 2026-08-15: "kalo lo gagal dengan semua penjelasan gw,    |
//| sepertinya lo tidak pakai breakout minor SNR yang ada di EA gw    |
//| deh." Twenty research runs found nothing while he trades the same |
//| idea profitably - and the symptom now points the same way: the    |
//| trap he describes as common (M5 already CF while M15 has quietly  |
//| flipped) shows up in only 3 of 121 reconstructed setups. If the   |
//| detector differs, all twenty runs measured a different object.    |
//|                                                                   |
//| Packaged as an EA rather than a Script purely so it appears in    |
//| the same Navigator list as the other EAs - Dadang could not find  |
//| it under Scripts. It does no trading whatsoever: it dumps on      |
//| attach, prints the result, and then sits idle. OnTick is empty.   |
//|                                                                   |
//| Buffers (see DD_CMP_Indicator.mq5):                              |
//|   2 = CmpBuffer               (+1 BUY / -1 SELL / 0 WAIT)        |
//|   3 = ChangeTimeBuffer        (when CMP last flipped)            |
//|   7 = BreakoutEventTimeBuffer (every fresh breakout event)       |
//|                                                                   |
//| Output: Common\Files\cmp_dump_<TF>.csv                           |
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "1.00"
#property strict

input string           InpSymbol = "XAUUSD";      // Simbol
input ENUM_TIMEFRAMES  InpTF     = PERIOD_M5;     // Timeframe
// 20k instead of 60k: at 60k the indicator dumped Mar 2024 -> Jan 2025,
// a window the MT5 PYTHON api can no longer fetch (copy_rates_range returns
// a single bar there), so the two could not be compared bar by bar at all.
// A shorter window lands inside the range both sides can still read.
input int              InpBars   = 20000;         // Jumlah bar

int OnInit()
{
   int h = iCustom(InpSymbol, InpTF, "DD_CMP_Indicator");
   if(h == INVALID_HANDLE)
   {
      Print("DUMP GAGAL: DD_CMP_Indicator tidak bisa di-load.");
      return(INIT_SUCCEEDED);
   }

   // the indicator needs time to walk a long history before its buffers fill
   int tries = 0;
   while(BarsCalculated(h) < InpBars && tries < 150) { Sleep(200); tries++; }
   int ready = BarsCalculated(h);
   int n = MathMin(InpBars, ready);
   Print("DUMP: BarsCalculated=", ready, "  dipakai=", n);
   if(n <= 0) { IndicatorRelease(h); return(INIT_SUCCEEDED); }

   double cmp[], chg[], ev[];
   datetime tm[];
   ArraySetAsSeries(cmp, false); ArraySetAsSeries(chg, false);
   ArraySetAsSeries(ev, false);  ArraySetAsSeries(tm, false);

   if(CopyBuffer(h, 2, 0, n, cmp) <= 0 ||
      CopyBuffer(h, 3, 0, n, chg) <= 0 ||
      CopyBuffer(h, 7, 0, n, ev)  <= 0 ||
      CopyTime(InpSymbol, InpTF, 0, n, tm) <= 0)
   {
      Print("DUMP GAGAL: CopyBuffer/CopyTime error ", GetLastError());
      IndicatorRelease(h);
      return(INIT_SUCCEEDED);
   }

   string fname = "cmp_dump_" + EnumToString(InpTF) + ".csv";
   int f = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(f == INVALID_HANDLE)
   {
      Print("DUMP GAGAL: tidak bisa buka ", fname, " err=", GetLastError());
      IndicatorRelease(h);
      return(INIT_SUCCEEDED);
   }

   FileWrite(f, "time", "cmp", "change_time", "breakout_event_time");
   int events = 0;
   for(int i = 0; i < n; i++)
   {
      FileWrite(f, (long)tm[i], (int)cmp[i], (long)chg[i], (long)ev[i]);
      if((long)ev[i] == (long)tm[i]) events++;
   }
   FileClose(f);
   IndicatorRelease(h);

   Print("=== DUMP SELESAI ===");
   Print("File   : Common\\Files\\", fname);
   Print("Bar    : ", n, "   breakout event: ", events);
   Print("Rentang: ", TimeToString(tm[0]), "  ->  ", TimeToString(tm[n - 1]));
   Print("Sekarang jalankan research/verify_detector.py");
   return(INIT_SUCCEEDED);
}

void OnTick() { }   // sengaja kosong - EA ini tidak trading sama sekali
