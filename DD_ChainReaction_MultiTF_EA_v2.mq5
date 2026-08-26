//+------------------------------------------------------------------+
//| DD_ChainReaction_MultiTF_EA_v2.mq5                                |
//| Forked from DD_ChainReaction_MultiTF_EA_UPGRADE.mq5 (v51-H1CUTSAFE|
//| stable production core) 2026-08-17 per Dadang: "kita buat ea baru|
//| pakai core yang ini ... karena chain research bl stabil" - the    |
//| UPGRADE file itself stays UNTOUCHED as the safe rollback; all new |
//| development continues here.                                       |
//| Reads CMP from DD_CMP_Indicator.mq5 - EA itself NEVER computes    |
//| CMP (per Dadang's TASK ORDER: "EA tidak menghitung CMP. EA hanya |
//| membaca status CMP yang dihasilkan indikator MT5.")               |
//|                                                                   |
//| DOCTRINE (H4->M30->M5 cascade, Dadang's own rule dictated verbatim|
//| 2026-08-09 after re-reading D:\bunga\TEHINIX BERIKUTNYA in full   |
//| + 3 hand-drawn diagrams - NO M15/H1 anywhere, M15 confirmed to be |
//| leftover test scaffolding, not doctrine: "M15 itu hanya uji gate  |
//| gw sebenarnya teknik gw kan H4 M30 M5"):                          |
//|   - H4 (Master) sets the outer regime. A flip is a full reset -   |
//|     close everything, start the M30/M5 cascade fresh.             |
//|   - M30's OWN live CMP is the direction actually being traded -   |
//|     "kita akan cari sell jika M30 sell" - independent of whether  |
//|     M30 currently agrees or disagrees with H4 (that agreement/    |
//|     disagreement only affects which SL/TP/BE tier + tag is used,  |
//|     see isScalp in TryOpen calls below).                          |
//|   - FIRE: every fresh M5 BREAKOUT EVENT (DD_CMP_Indicator buffer  |
//|     7, BreakoutEventTimeBuffer - updates on EVERY individual      |
//|     break past the latest pullback, not just the first state      |
//|     flip) that matches M30's current direction = one entry each.  |
//|     "kita entri sell setiap ada BO sell" - repeats/layers as long |
//|     as fresh M5 breakouts keep coming in that direction.          |
//|   - STOP (pause, not reverse): the instant M5's own CMP flips     |
//|     AGAINST M30's direction - "kita stop ketika M5 flip".         |
//|   - RESUME: checked ONLY at the open of a fresh M30 bar - if M30  |
//|     is still the same direction (hasn't flipped away) AND M5      |
//|     already confirms that direction again, firing resumes -       |
//|     "setelah flip dan close candle M30 masih sama belum flip,     |
//|     ketika open M30 dan BO searah master, M30 gas lagi lah entri".|
//|   - REVERSAL: M30's own CMP genuinely flipping to the opposite    |
//|     direction - cuts any position trading the old direction and   |
//|     starts tracking the new one fresh (re-arm required before any |
//|     new entry, same STOP/RESUME rules apply to the new direction).|
//+------------------------------------------------------------------+
#property copyright "Dadang Wahyuono"
#property version   "1.00"
#property strict
#include <Trade/Trade.mqh>
#include <Canvas\Canvas.mqh>
CTrade trade;

// Version tag - bump this MANUALLY every time the code changes, shown on
// panel + startup Print so Dadang can visually confirm a freshly compiled
// .ex5 actually loaded (vs a stale cached one MT5 didn't reload properly).
// Simple v1/v2/v3... - easier to eyeball than a compile timestamp.
#define EA_VERSION "v53.26-LABELFIX"

// v52.11: MT5 terminal-wide GlobalVariable (survives EA reload/reattach AND
// terminal restart, expires only after 4 weeks unused) - Dadang caught this
// live: found 4 stacked BOOKMAP-TRIG positions after today's rapid-fire
// reload cycle (~10 reloads/hour while iterating). Root cause:
// g_lastBookmapTriggerTime was a plain global, reset to 0 on every OnInit(),
// so the 15-minute cooldown effectively restarted every reload instead of
// surviving it. Named per-magic so it can never collide with anything else
// sharing this terminal's global variable namespace.
#define GV_BOOKMAP_TRIGGER_TIME "DD_CR_v2_BookmapTriggerTime"
#define GV_VARETEST_TRIGGER_TIME "DD_CR_v2_VaRetestTriggerTime"   // v52.42: same reload-survival reasoning as above
#define GV_VARETEST_TICKET "DD_CR_v2_VaRetestTicket"   // v52.44: persist the open position's ticket too - without this, an EA reload mid-trade silently STOPS the SL-trailing Dadang explicitly asked for ("sl kita ikut geser"), even though the position itself stays open on the broker side
#define GV_FUSION_TICKET "DD_CR_v2_FusionH1H4Ticket"   // v52.45: persist Fusion H1/H4's open position ticket across reload, same reasoning as VARETEST above - without this a reload mid-trade would silently stop watching for the H4-flip structural exit
#define GV_MOMENTUM_TICKET "DD_CR_v2_MomentumTicket"   // v52.71: same reload-survival reasoning as VARETEST/FUSION above

// v43: symbol used as the USD fundamental proxy. Declared up here because
// #define is a sequential preprocessor directive - OnInit() references it
// long before the panel code where the rest of the USD block lives.
#define USD_SYMBOL "EURUSD"

enum ENUM_TRADE_DIRECTION
{
   DIR_BOTH      = 0,   // BUY & SELL
   DIR_BUY_ONLY  = 1,   // BUY only
   DIR_SELL_ONLY = 2    // SELL only
};

input group "=== TIMEFRAME PAIR (H4 -> M30 -> M5, no M15/H1 per doktrin) ==="
input ENUM_TIMEFRAMES     InpMasterTF     = PERIOD_H4;     // H4 Master - regime bias, flip = full reset
input ENUM_TIMEFRAMES     InpScalpMasterTF= PERIOD_M30;     // M30 - arah yang BENERAN ditrading (live, independen dari H4)
input ENUM_TIMEFRAMES     InpScalpEntryTF = PERIOD_M5;      // M5 - trigger entry, fire tiap fresh breakout event

input group "=== ENTRI ==="
input bool                InpAllowScalpEntries = true;     // Safety valve - false = infrastruktur jalan tapi gak ada posisi beneran dibuka

input group "=== LOT / RISK MANAGEMENT ==="
input bool                InpUseRisk      = false;         // Pakai risk % dari balance (bukan lot fixed)
input double              InpLot          = 0.01;           // Lot fixed (dipakai kalau InpUseRisk=false)
input double              InpRiskPct      = 1.0;            // Risk % balance per trade (kalau InpUseRisk=true)

input group "=== POSISI ==="
input long                InpMagic        = 20260817;       // Magic number - beda dari UPGRADE (20260807) biar posisi gak ketuker kalau dua2nya sempet jalan
input int                 InpMaxOpenPos   = 0;              // Maximum posisi terbuka bersamaan (0 = unlimited) - verified 2026-08-09: aturan Dadang "setiap M5/M15 BO searah Master, entri" = layering, bukan one-shot
input bool                InpAllowMultiple= true;           // Boleh entry baru walau udah ada posisi searah - WAJIB true buat layering (default lama false = cuma 1 layer, melanggar aturan)
input ENUM_TRADE_DIRECTION InpTradeDir    = DIR_BOTH;       // Filter arah trading

input group "=== STOP LOSS / TAKE PROFIT (NORMAL tier) ==="
input double              InpSL_Pips      = 200;            // Stop Loss FALLBACK (pips, 0 = tanpa SL) - dipakai kalau structural SL gak valid/off
input double              InpTP_Pips      = 200;             // Take Profit NORMAL (pips, 0 = tanpa TP) - verified 2026-08-09 SL/TP/BE sweep
input bool                InpUseStructuralSL = true;         // SL di area CMP M30 (bukan pip tetap) - Dadang: "kita coba SL di area CMP M30"
input double              InpStructuralSL_MinPips = 30;      // Minimal jarak SL struktural M30 - kalau lebih deket dari ini, fallback ke InpSL_Pips

input group "=== TRAILING STOP / BREAK EVEN (WITH-H4 tier - Dadang 2026-08-09: 'yang searah H4 harus lebar' - trend-following, jangan dikunci cepet kayak SCALP) ==="
input bool                InpUseTrailing  = false;           // Aktifkan trailing stop WITH-H4
input double              InpTrailStartPips= 300;            // Trailing mulai aktif setelah profit sekian pip - v15 sempet dipersempit ke 40 samain SCALP, TERBUKTI SALAH (profit tier ini anjlok $73->$10) - dibalikin lebar
input double              InpTrailStepPips = 100;             // Jarak trailing dari harga sekarang (pip) - dibalikin lebar sama alasan di atas
input bool                InpUseBreakEven = false;           // Aktifkan break-even WITH-H4
input double              InpBE_TriggerPips= 100;             // BE aktif setelah profit sekian pip - dibalikin lebar (v15's 15pip cocok buat SCALP doang, motong trend WITH-H4 yang harusnya lari jauh)
input double              InpBE_LockPips   = 2;              // SL dikunci sejauh ini dari entry (pip) pas BE - verified 2026-08-09

input group "=== SCALP TP / SL / TRAILING / BE (tier terpisah, counter-trend R:R) ==="
input double              InpScalpSL_Pips        = 90;       // SL SCALP FIXED (pips) - retuned 2026-08-09: MAE analysis nunjukin trade yang AKHIRNYA MENANG bisa minus dulu sampe ~61pip (90th percentile) sebelum recover - SL 20pip lama motong 90% calon winner sebelum sempet balik
input double              InpScalpTP_Pips        = 150;      // TP SCALP (pips) - dilebarin 2026-08-09, proteksi sekarang dari BE-lock dini + trailing, bukan dari rasio SL:TP ketat kayak dulu
input bool                InpScalpUseBreakEven   = false;     // Aktifkan BE SCALP
input double              InpScalpBE_TriggerPips = 15;       // BE SCALP aktif setelah profit sekian pip - retuned 2026-08-09, sama alasan kayak NORMAL tier di atas
input double              InpScalpBE_LockPips    = 2;        // SL dikunci sejauh ini pas BE SCALP
input bool                InpScalpUseTrailing    = false;     // Aktifkan trailing SCALP - WAJIB ON, verified headless: payoff anjlok 1.52->0.71 kalau dimatiin (TP55 kasih ruang trailing kerja beneran, beda dari TP25 lama)
input double              InpScalpTrailStartPips = 40;       // Trailing SCALP mulai aktif setelah profit sekian pip - retuned 2026-08-09
input double              InpScalpTrailStepPips  = 20;       // Jarak trailing SCALP - retuned 2026-08-09

input group "=== M1 CONFIRMATION (eksperimen, Dadang: M1 ngawal pembentukan M5) ==="
input bool                InpUseM1Confirm = false;    // Wajib M1 udah searah sebelum entry SCALP (M5)

input group "=== M30 MOMENTUM CANDLE (Dadang: M30 close harus lewatin high/low candle sebelumnya) ==="
input bool                InpUseM30Momentum = false;   // Wajib M30 close di atas high (BUY) / bawah low (SELL) candle sebelumnya buat entry; posisi ke-exit kalau M30 malah close kuat ke arah lawan

input group "=== M5 TEST M30 (Dadang: M30 buy, tapi M5 sell dulu nguji, baru M5 balik buy, baru kita buy) ==="
input bool                InpUseM5TestM30 = false;   // Wajib M5 sempet SELL (lawan arah entry) dulu SEBELUM balik ke arah entry - bukti M30 udah "diuji" dan tetep kuat, bukan langsung searah dari awal

input group "=== HINDARI SNR TF BESAR (Dadang 2026-08-09: 'hindari entri di area SNR TF besar Weekly Daily H4, area itu pasti balik arah') ==="
input bool                InpAvoidBigSNR      = false;   // Skip entry kalau harga lagi deket zone SNR Weekly/Daily/H4 yang bakal ngelawan arah entry
input double              InpBigSNR_ZonePips  = 100;    // Lebar zone "deket" (pips) - dicek dari live sup (buat SELL) / res (buat BUY) di W1, D1, H4

input group "=== H1 GATE BUAT SCALP (eksperimen, default OFF - Dadang 2026-08-09: 'balikin ke M30 karena kalo H1 kita telat' - verified headless + out-of-sample: H1 gate bikin entry lebih lambat & profit sedikit lebih kecil di 2 periode data, gak ada bukti manfaat konsisten) ==="
input bool                InpRequireH1ForScalp = false;  // Wajib H1 CMP JUGA udah searah sebelum berani SCALP (lawan H4) - gak berlaku pas searah H4. Infrastruktur tetep ada buat eksperimen lanjut kalau perlu.

input group "=== BARRIER BE (Dadang: barrier lama = area pantul, begitu nyentuh langsung BE) ==="
input bool                InpUseBarrierBE     = true;   // Aktifkan barrier-BE (Master TF punya live res/sup lama)
input double              InpBarrierBE_LockPips = 0;    // SL dikunci sejauh ini dari entry pas kena barrier (0 = true breakeven)
input double              InpBarrierBE_MinProfitPips = 50;   // Minimal profit dulu sebelum barrier-BE boleh aktif - Dadang: "BE setelah lari minimal 50 pip"

input group "=== FILTER EKSEKUSI ==="
input double              InpMaxSpreadPips= 0;             // Spread filter (pips, 0 = tanpa filter)
input int                 InpSlippage     = 30;              // Slippage/deviation (points)

// v52.47: BARRIER VETO - Dadang 2026-08-19, live walkthrough + formalisasi
// (lihat memory doctrine_barrier_chochmss): "EA tidak boleh SELL meski ada
// CF SELL, meski CMP H4/H1/M30 SELL, ketika di area CMP OLD BUY-nya H4/H1/M30
// - minimal nunggu H4 jebol SELL kalau barrier itu H4."
// CMP LAMA = BARRIER: level TF (H4/H1/M30) itu SENDIRI sebelum flip terkini
// -nya. Kode LAMA (ReadLiveLevel buffer 4) cuma nyimpen level flip TERKINI;
// EA sekarang juga nyimpen level flip SEBELUMNYA (g_h4/h1/m30 OldBarrier*)
// supaya "zona lama" itu masih diinget WALAU TF-nya udah sempet flip lagi.
// Barrier dianggap jebol HANYA kalau candle TF itu SENDIRI (bukan tick
// live) udah CLOSE di sisi yang benar - "kalo mau turun, H4 HARUS close di
// bawah harga barrier CMP buy lama" (Dadang, sama sesi). Sampai jebol,
// entry LAWAN arah barrier itu di-VETO TOTAL (bukan warning/kecilin lot
// kayak Absorption/POC - ini block beneran, karena "jangan maksa SELL yang
// cuma bolak-balik sebelum valid CMP SELL baru hasil jebol barrier").
// Berlaku UNIVERSAL ke SEMUA jenis entry (Chain/DD/VARetest/Bookmap/Fusion)
// via TryOpen() - bukan cuma satu sinyal doang.
input group "=== BARRIER VETO (v52.47, 'CMP lama' H4/H1/M30 - block sampai bener2 jebol) ==="
input bool                InpUseBarrierVeto      = true;   // Block entry lawan barrier H4/H1/M30 sampai TF itu sendiri CLOSE tembus
input double              InpBarrierVetoZoneUsd  = 3.0;    // Toleransi "masih di area barrier" (USD) - harga dianggap masih ketahan kalau sejauh ini dari level barrier di sisi yang salah

input group "=== SWEEP REVERSAL VETO (v52.72, real loss - jangan entry lanjut arah lama pas sweep udah confirmed reversal) ==="
input bool                InpUseSweepReversalVeto = true;   // Selama Wall Sweep REVERSAL_CONFIRMED masih aktif (g_sweepRecActive), cuma boleh entry ke arah reversal-nya - lepas otomatis begitu levelnya genuinely kejebol

input group "=== BOOKMAP BRIDGE (live-only, Dadang: 'biar kita tau juga potensinya') ==="
input bool                InpShowBookmapPanel = true;    // Tampilin CVD/Pulse/Absorption Bookmap di panel
input double              InpBookmapStaleSec  = 30.0;    // Anggap data basi/Bookmap gak jalan kalau beda lebih dari ini (detik, dua arah - v24 dilebarin dari 5.0)
input bool                InpUseBookmapAbsorptionWarning = true;   // v23 2026-08-10: Absorption lawan arah -> kecilin lot (BUKAN block), sama persis pola bookmap-bridge: "BUY WARNING, buyer mulai ter-absorb, kurangi lot". LIVE ONLY - gak ngaruh ke backtest sama sekali (g_bookmapOnline selalu false offline)
input double              InpBookmapAbsorptionLotFactor  = 0.5;    // Lot dikali segini kalau absorption lawan arah entry
input bool                InpUsePocOverextendWarning = true;    // v30 2026-08-10: harga udah lari jauh dari POC (value area session) searah entry -> kecilin lot (BUKAN block), sama pola kayak Absorption. LIVE ONLY
input double              InpPocOverextendUsd        = 20.0;    // Jarak (USD) dari POC ke arah entry yang dianggap "overextended"
input double              InpPocOverextendLotFactor  = 0.5;     // Lot dikali segini kalau overextended dari POC
input bool                InpUsePocAlignWarning = true;    // v32 2026-08-10: harga di sisi SALAH POC relatif ke arah entry (BUY tapi harga < POC / SELL tapi harga > POC = belum "reclaim" value area) -> kecilin lot. Beda dari overextend (jarak) - ini soal SISI, berapapun jaraknya
input double              InpPocAlignLotFactor  = 0.5;     // Lot dikali segini kalau harga di sisi salah POC
input bool                InpUseLiquiditySupportWarning = true;   // v52.1 2026-08-17: gak ada wall ATAU iceberg di sisi ENTRY (bid buat BUY/ask buat SELL) deket harga -> kecilin lot. Dadang: "ngegate entri gak apa2 bro karena masih demo... tapi dia harus tetap entri atau cut lose sesuai data yang ada" - WARNING sama pola kayak Absorption/POC di atas, BUKAN block - entry & cut-loss tetap selalu jalan
input double              InpWallMinAgeSec = 30.0;   // v52.14 2026-08-17: "browsing sebagai ahli" - praktik profesional: wall yang baru muncul bisa "bait" (mancing lalu ditarik), wall yang udah lama bertahan lebih dipercaya. Wall di slot terdekat harus udah ada minimal sekian detik baru dianggap support/resistance ASLI oleh HasLiquiditySupport(). Iceberg TIDAK kena syarat ini (refill aktif udah bukti sendiri, beda dari wall statis)
input double              InpWallMinSizeLot = 30.0;   // v52.19 2026-08-17: Dadang - "gw mau semua wall kelihatan... yang kuat wall besar" - beda dari wall_threshold_size=10 di Python (itu floor VISIBILITAS, semua wall >=10 lot tetep digambar/ditampilin). Ini floor KEPUTUSAN - wall harus >= sekian lot baru dianggap cukup kuat buat HasLiquiditySupport() (mempengaruhi lot boost + trigger bookmap mandiri)
input double              InpWallSearchRangeUsd = 15.0;   // v52.20 2026-08-17: Dadang - "harus baca super jauh agar tau wall dimana... bukan hanya di sekitaran harga yang live" - HasLiquiditySupport() sekarang nyisir SEMUA 10 slot wall per sisi (dulu cuma slot[0]/wall terdeket), radius pencarian sekian USD dari harga (dulu ~$3-5 doang, sekarang jauh lebih lebar) - kira-kira 1x ATR14 XAUUSD
input double              InpWallZoneClusterUsd = 3.0;   // v52.31 2026-08-17: Dadang - "kotaknya boleh aja tapi garis2 wall tadi kalo bisa tetap ada... dalam kotakan itu lo beri tulisan total wall nya aja" - walls within this $ gap of each other ALSO get a dim box overlay with a live wall-count label, ON TOP OF (not instead of) their individual lines. DISPLAY-ONLY - HasLiquiditySupport() unaffected, still reads the individual per-wall array with its own InpWallSearchRangeUsd radius. v52.33: this is now the box's MAX TOTAL WIDTH (first wall to last), not a per-step gap - see ClusterAndDrawWallZones()
input bool                InpLocationRegimeAware = true;   // v52.15 2026-08-17: "browsing sebagai ahli" - praktik volume-profile: SIDEWAYS = fade harga yang extended dari POC (lama), TRENDING = close di luar VAH/VAL itu justru continuation, bukan alasan diblok. BookmapLocationOk() sekarang cek regime + searah H4 dulu sebelum ngeblok - matikan buat balik ke behavior lama (selalu blok kalau extended)
input double              InpLiquiditySupportLotFactor = 0.5;     // Lot dikali segini kalau gak ada liquidity support deket harga
input bool                InpUseLiquidityBoost = true;    // v52.2 2026-08-17: Bookmap KUAT mendukung (>=2 dari CVD arah/Absorption-favor/Liquidity Support, ATAU iceberg sendirian di sisi entry) -> lot dinaikin, diterapkan SETELAH semua warning di atas. Dadang: "EA tidak boleh takut entri apa lagi jika bookmap data mendukung karena satu-satunya data real kita hanya bookmap"
input double              InpLiquidityBoostLotFactor = 1.5;    // Lot dikali segini kalau bookmap kuat mendukung (dibatasi SYMBOL_VOLUME_MAX)
input double              InpPocSidewaysZoneUsd = 3.0;     // Jarak (USD) dari POC yang dianggap "di POC" (bukan jelas di atas/bawah) - dipake buat panel BIAS BUY/SELL/SIDEWAYS
input double              InpPocMigrateUsd = 1.0;          // v52.41: POC harus geser minimal segini USD (skala Bookmap/GCZ6) searah trend dalam InpPocMigrateLookbackMin menit biar Regime dianggap TRENDING (bukan cuma CMP align doang) - Dadang: "poc ini ternyata bisa langsung pindah ke atas atau ke bawah ini artinya apa"
input int                 InpPocMigrateLookbackMin = 10;   // v52.41: jendela waktu (menit) buat ngukur pergerakan POC di IsPocMigrating()
input double              InpReloadMinLot    = 80.0;   // v52.84: wall (near-live slot) harus minimal segini lot baru dicatat sebagai Reload Level candidate kalau dia jebol - dari bootcamp Pavlovic: level yang PERNAH nunjukin minat kuat tapi kalah, terus BELAKANGAN jebol -> retest = ekspektasi "reload" (sisi yang dulu kalah masuk lagi, akselerasi)
input double              InpReloadRetestUsd = 1.0;    // Jarak (USD, skala XAUUSD) dari Reload Level yang masih dianggap "retest" level itu
input int                 InpReloadWindowMin = 90;     // Reload Level dianggap basi (dibuang dari memori) kalau gak diretest dalam sekian menit sejak dicatat

input group "=== BOOKMAP-TRIGGERED ENTRY (Dadang 2026-08-17: 'kita ngikutin bookmap aja karena tehnikal gw kan hanya baca candle' - bookmap boleh jadi pemicu entry SENDIRI, gak wajib nunggu CMP H4/M30/M5 align) ==="
input bool                InpUseBookmapTrigger = true;    // Aktifkan entry independen dari sinyal bookmap kuat (di luar cascade CMP biasa)
input int                 InpBookmapTriggerCooldownMin = 15;   // Jarak minimum antar entry bookmap-trigger (menit) - kondisi bookmap kuat bisa bertahan lama, ini nyegah numpuk entry tiap tick

// v52.42: VA RETEST entry - Dadang: "kita hanya entri ketika BREAK VAL ATAU
// VAH DAN pullback ke area val atau hal atau poc" + "sl kita nanti di bawah
// vah atau val dan kalo mereka geser sl kita juga ikut geser" + "ea harus
// entri sesuai yang kita diskusikan toh kita pakai demo di mt5 kita bro buat
// uji" - classic breakout-then-retest, wired to REAL entries per his
// explicit informed choice (demo account, not backtested first - his call,
// flagged clearly beforehand). Default OFF - explicit opt-in required.
input bool                 InpUseVaRetestTrigger     = true;    // Entry BREAKOUT VAH/VAL + pullback retest ke level itu - v52.43: Dadang "lo on aja bro" - ON eksplisit atas permintaan dia sendiri di demo
input double                InpVaRetestToleranceUsd   = 2.0;     // Seberapa deket harga harus balik ke VAH/VAL biar dianggap "retest" (skala harga MT5)
input double                InpVaRetestSlBufferUsd    = 3.0;     // SL ditaruh sejauh ini di seberang sisi JAUH value area (BUY: di bawah VAL, SELL: di atas VAH - v52.54) - IKUT GESER selama posisi masih kebuka, ngikutin VAH/VAL terbaru
input double                InpVaRetestSlTrailStepUsd = 0.5;     // SL cuma di-update kalau geser levelnya minimal segini (biar gak spam PositionModify tiap tick)
input int                   InpVaRetestCooldownMin    = 30;      // Jarak minimum antar entry VA-retest (menit)
input int                 InpBookmapConfirmSec = 180;   // v52.10 (10s, awal) -> v52.12 (180s = 3 menit) - Dadang: "ini masih berubah ubah gimana ya... kita trading kan bukan detikan bro". Arah bookmap (BUY/SELL) harus konsisten SELAMA sekian detik dulu sebelum dianggap valid - selaras cara main lo yang per-candle (M5 ke atas), bukan per-tick
input double              InpBookmapCvdSmoothMin = 5.0;   // v52.13 2026-08-17: Dadang - "lo harus ambil rata2 misal 30 menit atau 5 menit... siapa yang dominan sehingga itu yang kita anggap arah entri". CVD di-smooth pakai EMA (time-constant sekian MENIT) sebelum dipakai nentuin arah - 5 menit = selaras M5 (TF tercepat di cascade CMP), lebih responsif dari 30 menit (M30) tapi jauh lebih stabil dari CVD mentah per-tick. Naikin ke 30 kalau masih kerasa jumpy.

// v52.45: FUSION H1/H4 signal - hasil riset penuh 2026-08-19 (sim/ pakai
// data XAUUSD asli 2025-04..2026-08, kode di
// D:\PROJECT TRADING\backtest\fusion_sim\, sumber asli
// github.com/dadangwahyuono-eng/fusion-daily-deploy). Beda dari cascade
// H4->M30->M5 di atas (yang v ini TIDAK diubah/disentuh) - ini pair
// TERPISAH: H1 = entry TF, H4 = master. Arah = CMP H4 aktif (jangan pernah
// lawan - 3 percobaan reversal terpisah hari itu SEMUA gagal). VR = H1
// breakout berlawanan H4. CF = H1 balik searah H4 TAPI wajib retest ZONA
// LEVEL H4 (bukan cuma level H1) dalam toleransi InpFusionZoneTolUsd - ini
// SATU filter paling kuat yang ketemu hari itu (PF ~1.0 -> PF 1.76+). CF
// dites INTRABAR (harga M5 nembus level, plus M5 sendiri fresh breakout
// searah - "pembentukan candle") bukan nunggu H1 resmi close - PF full-
// sample 2.47, TRAIN 2.77, TEST 1.94 (dua2nya selalu profitable, gak
// pernah collapse). Exit STRUKTURAL MURNI - hold sampai H4 sendiri flip,
// TANPA SL harga normal (worst case historis backtest -1321 pip / -$132
// per unit price). InpFusionEmergencySLUsd BUKAN exit yang diharapkan -
// itu backstop kalau EA/koneksi mati doang, dibulatin di atas worst-case
// historis. WAJIB InpUseRisk=true + InpRiskPct kecil (5-10% modal sesuai
// SNR_METHOD.md) supaya lot ke-size otomatis kecil buat SL selebar itu.
// DEFAULT OFF - Dadang harus tes di demo dulu sebelum ON, sama disiplin
// persis kayak VA Retest trigger di atas.
// v52.46: Wall Sweep signal - Dadang 2026-08-19 (live, sambil ngamatin "BID
// ZONE SWEPT: LANJUT (275s) - 3 wall (192 lot)" beneran kejadian di chart):
// "apa lagi ada zone sweep di sana, makanya kita perlu upgrade EA-nya."
// Ditemukan: g_bmSweepSide/Size/Status UDAH dibaca dari bridge dan digambar
// di chart sejak v52.26 (lihat DrawWallSweepLine/UpdateSweepPanel dkk) tapi
// SAMA SEKALI belum pernah dipakai buat keputusan trading - murni visual.
// Ini nyambungin ke TryOpen() lewat pola WARNING/BOOST yang SAMA PERSIS
// kayak Absorption/POC/Liquidity di atas (kecilin/naikin lot, BUKAN block).
//   REVERSAL_CONFIRMED = wall SEMPAT ditembus tapi harga balik lagi ke sisi
//     asal (fakeout-lalu-reject, sama konsep kayak PMB/ICT liquidity sweep
//     yang dibahas siang tadi) -> wall itu TERBUKTI kuat -> kalau entry BARU
//     ini justru mau LAWAN sisi yang barusan menang (mis. BID wall reject
//     ke atas, tapi kita entry SELL), kecilin lot.
//   CONTINUATION = wall ditembus DAN harga terus jalan ke arah situ (wall
//     GAGAL nahan) -> konfirmasi genuine kalau entry baru SEARAH arah itu,
//     naikin lot (sama semangat kayak BookmapStrongConfirm boost di atas).
input group "=== WALL SWEEP SIGNAL (v52.46, live-only - g_bookmapOnline selalu false pas backtest) ==="
input bool                InpUseWallSweepSignal      = true;   // Aktifkan warning/boost dari status sweep (REVERSAL_CONFIRMED / CONTINUATION)
input double              InpWallSweepWarnLotFactor  = 0.5;    // Lot dikali segini kalau sweep REVERSAL_CONFIRMED lawan arah entry (wall barusan kebukti kuat)
input double              InpWallSweepBoostLotFactor = 1.5;    // Lot dikali segini kalau sweep CONTINUATION searah entry (wall barusan kebukti jebol)
input double              InpWallSweepMaxAgeSec      = 60.0;   // Sweep dianggap masih relevan kalau umurnya (g_bmSweepSinceSec) di bawah ini - sweep basi diabaikan

input group "=== FUSION H1/H4 SIGNAL (riset 2026-08-19, structural exit, TANPA SL harga normal) ==="
input bool                InpUseFusionH1H4       = true;   // v53: default ON - Dadang: "lo on kan bro jngn minta gw setting2 gw gak paham". Akun ini demo-only + alat pantau, keputusan real tetep manual (lihat komentar InpUseZoneCFEntry)
input double              InpFusionZoneTolUsd    = 4.0;    // Toleransi retest ke ZONA H4 (USD) - dipakai HANYA sebagai fallback kalau InpUseZoneCFEntry aktif tapi zones_v2.csv belum ada datanya
input double              InpFusionEmergencySLUsd= 140.0;  // SL DARURAT (USD, backstop doang bukan exit normal) - worst case historis -$132.1, dibulatin ke atas. Juga jadi buffer di seberang zona SND kalau InpUseZoneCFEntry aktif
input int                 InpFusionCooldownMin   = 5;      // Jeda minimum antar fire (menit) - anti-spam

// v53: Dadang 2026-08-26 - "wall yang lama di v1 kita rubah jadi supply
// demand... cf atau chain yang terjadi di area SND ini yang akan kita
// pakai entri". Fusion H1/H4's own "inZone" check above already existed
// (a flat +/-InpFusionZoneTolUsd band around H4's single flip level) -
// this replaces THAT check with the real Bookmap-derived Supply/Demand
// zones (zones_v2.csv, written every cycle by bookmap-bridge-v2's
// bookmap_addon_v2.py) when available: an actual scored, multi-wall,
// lifecycle-tracked zone instead of an arbitrary USD tolerance around one
// price. Falls back to the old tolerance-band check if the zone file is
// missing/empty (Bookmap addon not running) - same "warning/degrade, don't
// block" spirit as every other optional live-data feature in this EA.
input group "=== ZONE CF ENTRY (upgrade Fusion's zone-check to real SND zones, 2026-08-26) ==="
input bool                InpUseZoneCFEntry      = true;   // Pakai zona Supply/Demand asli (zones_v2.csv) ketimbang tolerance band H4 flat - Dadang: "gak perlu diuji, harus jadi V2 ini"
input int                 InpZoneCFMinScore      = 30;     // Skor zona minimum buat ENTRY/TP (SEDANG/KUAT) - zona LEMAH diabaikan, terlalu noisy buat jadi dasar entry beneran
input int                 InpMinScoreToShowChart = 20;     // Skor zona minimum buat TAMPIL di chart (terpisah dari syarat entry) - v53.8: dinaikin dari 0 - Dadang: "zona zona yang penting aja bro, kalo banyak banget gimana mau trading" - zona LEMAH banget (baru kebentuk, <20) sekarang gak digambar dulu, biar chart gak penuh
input bool                InpShowZonesOnChart    = true;   // Gambar kotak SUPPLY/DEMAND langsung di chart EA ini - Dadang: "mana zone yang kita bangun tadi... kita buat v2 ini upgrade bukan membuang isi v1" - satu EA, keliatan DAN dipake entry, gak perlu EA kedua
input int                 InpMaxZonesPerSideChart= 20;     // Maks berapa zona per sisi yang digambar - v53.21: naik dari 3 ke 20 (efektif "semua") - Dadang: "sekarang tampilin semua zona SND yang ada bro", aman sekarang karena semua kotak cuma outline (gak nutupin candle lagi, lihat v53.20). Makin jauh dari S1/D1, makin redup/tipis otomatis (lihat DrawZoneBox()) - turunin lagi kalau kerasa ramai

// v53.18: S&D MOMENTUM BREAK ENGINE - Dadang's 35-section spec, 2026-08-26.
// DETEKSI + PENILAIAN + TAMPILAN saja - TIDAK menyentuh entry logic, TIDAK
// mengganti Chain Reaction/Fusion, TIDAK membuat zone engine baru. State
// machine per S1(SUPPLY)/D1(DEMAND) - dua zona yang sudah dianggap "yang
// penting" di seluruh sistem ini (chart box solid, panel FOKUS/Posisi).
input group "=== S&D MOMENTUM BREAK ENGINE (deteksi break status, BUKAN entry) ==="
input bool                 InpEnableSDBreakEngine      = true;   // Master switch - kalau off, break status selalu "NONE" dan gak ada marker/debug
input bool                 InpEnableSDBreakDebug       = false;  // Print() detail tiap bar baru (geometry, score, state) - Dadang: "jangan spam log" kalau off
input double               InpMomentumMinBodyRatio     = 0.45;   // body/range >= ini buat lolos syarat "body candle cukup solid" (bukan wick doang)
input double               InpMomentumMinRangeATR      = 0.8;    // candle range >= ATR(aktif) * ini buat lolos syarat "candle-nya cukup besar"
input double               InpMomentumMinBreakDistance = 0.3;    // USD - close harus lewat tepi zona minimal segini biar dianggap displacement nyata, bukan "baru lewat dikit"
input int                  InpBreakConfirmationBars    = 1;      // Berapa bar SETELAH close break buat nunggu follow-through sebelum BREAK_CONFIRMED
input double               InpFollowThroughMinRangeATR = 0.4;    // Bar follow-through minimal sebesar ini x ATR(aktif) - kalau kurang, dianggap gagal lanjut (bukan otomatis FALSE_BREAK, cuma nunda)
input double               InpMinZoneSeparation        = 3.0;    // USD - kalau S1-D1 lebih deket dari ini, ditandai NO_TRADE_ZONE (informational, gak nge-block apa pun)
input double               InpNearZoneDistance         = 1.0;    // USD - dalam jarak ini dari tepi zona dianggap ZONE_TEST walau belum benar-benar masuk
input int                  InpChoppyFalseBreakCount    = 3;      // Total FALSE_BREAK+REJECTION (gabungan S1+D1) sebelum market dibaca CHOPPY

// v52.71: MOMENTUM ENTRY - Dadang 2026-08-19, live discussion abis trade
// +16738 poin hari itu: "ikut arah break out M5 bro karena jika itu terjadi
// rantainya akan terbentuk dengan sendirinya, gw udah uji kemaren" + "kalo
// masih weak tidak usah entri" + "kita tp ketika momentum m5 nya berubah
// dari buy ke sell atau sebaliknya". Deliberately DOESN'T require H4/M30
// alignment or a minimum Rantai depth - Dadang: "gak usah mikir chain ea
// nya biar gw yang mikir" (he judges the chain context himself manually,
// EA's only job is the momentum gate). Own independent trigger, same
// pattern as Fusion H1/H4 / VA-Retest - never touches the main cascade.
input group "=== MOMENTUM ENTRY (riset 2026-08-19, ikut breakout M5 + gate Momentum) ==="
input bool                InpUseMomentumEntryTrigger = false;  // Entry ikutin arah CMP M5 murni begitu Momentum M5 minimal NORMAL - OFF default, WAJIB tes demo dulu
input double              InpMomentumEntryMinRatio   = 0.5;    // Ambang minimal ratio Momentum M5 (0.5 = batas NORMAL/WEAK yang sama dipake baris panel) - di bawah ini (WEAK) gak boleh entry

input group "=== PANEL ==="
input bool                 InpShowPanel    = true;           // Tampilkan dashboard di chart
input string                InpPanelName    = "CHAIN REACTION SYSTEM"; // Judul panel
input string                InpOwnerName    = "Commander Dadang Wahyuono"; // Nama pemilik
input int                   InpMomentumHoldSec = 2;   // v52.97 - detik minimal arah baru harus konsisten sebelum baris Momentum (M5/Bookmap/Footprint) boleh flip tampilannya - saring kedip cepat tanpa nunggu candle close. Dadang: "kalo bolak balik stress"

//======================================================================
string   g_masterDir        = "WAIT";   // H4
string   g_scalpMasterDir   = "WAIT";   // M30 - the direction actually being traded
string   g_scalpEntryDir    = "WAIT";   // M5

//--- STRICT DOCTRINE STATE MACHINE (Diagrams 1.png - 4.png)
string   g_cmpStatus      = "NORMAL"; // Status: NORMAL, VR, CF
bool     g_hasVr          = false;    // True if M5 made a VR (retest opposite to M30) after M30 regime started
datetime g_m30PullbackTime= 0;        // Timestamp of completed M30 pullback candle
bool     g_m30PullbackActive= false;   // True if pullback trigger is primed

datetime g_masterChangeTime = 0;
datetime g_scalpMasterChangeTime = 0;   // M30's own regime-start time (Time Law reference)

// FIRE/STOP/RESUME state machine (Dadang's own rule, dictated verbatim
// 2026-08-09 - see header doctrine comment). g_m5FiringEnabled gates every
// entry: true = fire on each fresh M5 breakout event; false = paused. Only
// two things change it: M5 flipping against M30 (-> false) and a fresh M30
// bar opening while M30 hasn't flipped away and M5 already agrees (-> true).
bool     g_m5FiringEnabled = false;
datetime g_lastM30BarTime  = 0;    // detects a fresh M30 bar open (RESUME check point)
datetime g_lastM5EventTime = 0;    // last-seen BreakoutEventTimeBuffer value - detects each fresh M5 event

int      g_hMaster = INVALID_HANDLE;
int      g_hScalpMaster = INVALID_HANDLE;
int      g_hScalpEntry  = INVALID_HANDLE;
int      g_hWeekly = INVALID_HANDLE;   // W1 - for InpAvoidBigSNR only, not part of the trading cascade
int      g_hDaily  = INVALID_HANDLE;   // D1 - for InpAvoidBigSNR only, not part of the trading cascade
int      g_hH1     = INVALID_HANDLE;   // H1 - Daily zone's rejection-confirmation TF, InpAvoidBigSNR only

// v34: dedicated handles for the SULTAN SNIPER web dashboard export
// (WriteSultanStatus()) - deliberately SEPARATE from g_hDaily/g_hH1 above
// (those are conditional on InpAvoidBigSNR and used for trading-logic
// filters; these are always-loaded and export-only, zero risk of changing
// entry behavior). D1/H1/M15 read here purely for the "Market Regime"
// table - MT5 always has full history for these (unlike Bookmap's own
// tick-only CMP, which needs hours/days to warm up after every restart).
int      g_hExportD1  = INVALID_HANDLE;
int      g_hExportH1  = INVALID_HANDLE;
int      g_hExportM15 = INVALID_HANDLE;
int      g_hExportM1  = INVALID_HANDLE;   // v37: M1 passthrough for udp_listener.py's MT5 overlay (was Pine-only before)
int      g_hATR       = INVALID_HANDLE;   // ATR(14) on H1, for the LOCATION panel

// RSI/ADX filter handles - checked against M5 (the only entry trigger now).

// M1 confirmation - one level below Scalp Entry (M5). Per Dadang's candle-
// formation doctrine, a lower TF's breakout direction tends to drag the
// parent TF's forming candle with it, so M1 breaking out first is read as
// an early confirmation that M5 is about to (or already did) follow suit.
int      g_hM1             = INVALID_HANDLE;

// Bookmap live-bridge state (read from Common\Files\bookmap_live_signal.csv,
// written by udp_listener.py - see that file's MT5_BRIDGE_FILE comment).
// Absorption wired into entry lot-sizing (v23), rest still informational.
bool     g_bookmapOnline    = false;
double   g_bookmapPrice     = 0.0;   // Bookmap's OWN instrument price (GCZ6 futures, NOT XAUUSD) - for wall price conversion
double   g_bookmapCvd       = 0.0;
double   g_bookmapFootBuyVol  = 0.0;   // v52.79: buy/sell volume traded AT the current Bookmap price (rolling window, see FootprintEngine)
double   g_bookmapFootSellVol = 0.0;
double   g_bookmapFootM1BuyVol  = 0.0;   // v52.95: TIME-scoped (last 60s, any price) - early-warning read, informational only
double   g_bookmapFootM1SellVol = 0.0;
double   g_bookmapPulsePct  = 0.0;   // = buyer_aggression_pct 0-100 (kekuatan buyer/seller)
string   g_bookmapAbsorption = "NONE";
// v29: Volume Profile (session, resets 07:00 WIB like CVD) - POC = price
// level with the most TOTAL traded volume this session, distinct from CVD
// (buy-sell delta) and from the wall ladder (resting order size, not volume
// that actually traded). VolRatio = session buy% of total traded volume.
double   g_bookmapPocPrice       = 0.0;   // Bookmap's OWN instrument price - needs offset conversion like walls
double   g_bookmapPocVolume      = 0.0;
double   g_bookmapVolRatioBuyPct = 50.0;
double   g_bookmapBuyVolSession  = 0.0;
double   g_bookmapSellVolSession = 0.0;
// v33: VAH/VAL (Value Area High/Low) - turns POC from a single line into the
// 70%-of-volume ZONE around it (both Bookmap's OWN price scale, need offset
// conversion like POC). Iceberg = hidden refilling order detected on either
// side (IcebergEngine) - price/displayed size/ratio, 0s if none detected.
// v52.1/52.2: iceberg is now wired (HasLiquiditySupport/HasIcebergSupport/
// BookmapStrongConfirm) - VAH/VAL stays display + ComputeConviction() only.
double   g_bookmapVal = 0.0, g_bookmapVah = 0.0;
double   g_bookmapBidIcePx = 0.0, g_bookmapBidIceSz = 0.0, g_bookmapBidIceRatio = 0.0;
double   g_bookmapAskIcePx = 0.0, g_bookmapAskIceSz = 0.0, g_bookmapAskIceRatio = 0.0;
// v52.84 - HVN/LVN (High/Low Volume Node) NEAREST to current price, from
// volume_profile_engine.py's get_hvn_lvn() - finer-grained cousin of POC:
// POC is the single biggest peak all session, HVN/LVN here are the closest
// peak/valley to where price actually is right now. HVN = price tends to
// stall/bounce there (thick, defended). LVN = price tends to slip through
// fast (thin, skipped). Same raw-Bookmap-price-needs-offset convention.
double   g_bookmapHvnPrice = 0.0, g_bookmapHvnVolume = 0.0;
double   g_bookmapLvnPrice = 0.0, g_bookmapLvnVolume = 0.0;

// v52.74 - iceberg reload counter ("kalo perlu suaranya beda" pitch, built
// MT5-first). An iceberg that DISAPPEARS then REAPPEARS at the same price
// is a hidden player refreshing the same level - more committed than just
// "still sitting there". Tracked per side: last known price, whether it's
// currently present, and how many times it's reloaded.
double   g_iceLastPx[2]     = {0.0, 0.0};   // 0=BID, 1=ASK
bool     g_icePresent[2]    = {false, false};
int      g_iceReloadCount[2] = {0, 0};
datetime g_lastBookmapTriggerTime = 0;   // v52.3: cooldown tracker for CheckBookmapTrigger()

// v52.42: VA RETEST trigger state - see CheckVaRetestTrigger()
datetime g_lastVaRetestTime = 0;         // cooldown tracker
string   g_vaRetestArmedDir = "";        // "" / "BUY" / "SELL" - set once a breakout confirms, cleared on fire or invalidation
ulong    g_vaRetestTicket   = 0;         // ticket of the position this trigger opened (0 = none active) - drives SL trailing
double   g_vaRetestExtreme  = 0.0;       // v52.44 bugfix - highest(BUY)/lowest(SELL) price seen since arming, proves a REAL pullback happened (not an instant trivial match on a narrow breakout candle)

// v52.45: FUSION H1/H4 signal state - see input group comment above for the
// full mechanism. g_fusionDir/g_fusionMct snapshot H4's current direction +
// change-time (any difference = H4 flipped, full reset of the VR cycle).
int      g_hFusionM5        = INVALID_HANDLE;   // dedicated M5 handle - decoupled from InpScalpEntryTF so a config change there can't silently break this signal's "M5 confirms" check
ulong    g_fusionTicket     = 0;         // open position ticket from this trigger (0 = none active) - drives the H4-flip structural exit
string   g_fusionDir        = "WAIT";    // H4 direction being tracked
datetime g_fusionMct        = 0;         // H4 change-time snapshot
bool     g_fusionVrSet      = false;     // H1 VR (opposite H4) detected, armed and waiting for zone-retest + M5-confirmed CF
datetime g_fusionVrTime     = 0;         // H1's change-time when VR was armed
double   g_fusionVrLevel    = 0.0;       // H1's frozen flip-level at VR moment (the level CF must cross back through)
double   g_fusionVrExtreme  = 0.0;       // highest(SELL)/lowest(BUY) price seen since VR armed - proves the pullback genuinely reached H4's zone
datetime g_fusionLastCf     = 0;         // gate - a new VR must be fresher than this (prevents re-arming on a stale/already-used H1 flip)
datetime g_fusionLastM5Event= 0;         // last-seen M5 BreakoutEventTime (buffer 7) - detects a NEW M5 breakout event ("pembentukan candle" confirmation)
datetime g_fusionLastFireTime=0;         // cooldown clock

// v53: SND ZONE state - see ReadZonesCsv()/ZoneCheck(). Refreshed once per
// tick from zones_v2.csv, written by bookmap-bridge-v2/bookmap_addon_v2.py
// every cycle. Already MT5/XAUUSD price scale (converted Python-side) -
// no offset math needed here, unlike the old bookmap_live_signal.csv wall
// fields which are Bookmap-GCZ6-native and need g_bmOffset applied.
string   g_zoneSide[];
double   g_zoneLo[], g_zoneHi[], g_zoneScore[], g_zoneTotalLot[];
string   g_zoneStatus[];
int      g_zoneWallCount[], g_zoneRetest[], g_zoneAbsorb[];
int      g_zoneCount = 0;
bool     g_zoneDataAvailable = false;   // false = bridge never ran / file missing - callers fall back to the old tolerance-band check

// v53 TAHAP 1/7/9/17: Zone Relevance / S&D Price Map - Dadang's 22-tahap
// spec, 2026-08-26. Roadmap arrays (nearest-first per side, index 0 =
// NEAREST/rank0) rebuilt every DrawAllZones() cycle - "jangan hapus zone
// jauh, tetap tersedia sebagai roadmap/TP" - these hold up to
// SDPM_MAX_ROADMAP zones regardless of how many actually get drawn on the
// chart (InpMaxZonesPerSideChart only caps the chart, not the roadmap).
#define SDPM_MAX_ROADMAP 5
double   g_supplyRoadLo[SDPM_MAX_ROADMAP], g_supplyRoadHi[SDPM_MAX_ROADMAP], g_supplyRoadScore[SDPM_MAX_ROADMAP];
int      g_supplyRoadCount = 0;
double   g_demandRoadLo[SDPM_MAX_ROADMAP], g_demandRoadHi[SDPM_MAX_ROADMAP], g_demandRoadScore[SDPM_MAX_ROADMAP];
int      g_demandRoadCount = 0;

// Decision Context (TAHAP 17) - one place every S&D Price Map panel field
// reads from, rebuilt each cycle by BuildDecisionContext(). Deliberately
// display-only right now - does NOT feed CheckZoneBreakoutEntry() or any
// other real entry trigger (that's TAHAP 5, a separate, not-yet-built
// step Dadang explicitly agreed to sequence after this display layer).
string   g_sdmLocation    = "OUTSIDE_ACTIVE_RANGE";
string   g_sdmMarketState = "-";
string   g_sdmSetup       = "NONE";
string   g_sdmReason      = "-";
double   g_sdmBuyerPct    = 50.0;
double   g_sdmSellerPct   = 50.0;

// v53.18: S&D MOMENTUM BREAK ENGINE state - one instance per side (SUPPLY
// tracked against S1/rank0, DEMAND against D1/rank0). See
// UpdateSDBreakEngine()/UpdateSDBreakState(). Detection/display ONLY -
// never read by CheckZoneBreakoutEntry() or any other entry trigger.
int      g_hATR_Active = INVALID_HANDLE;   // ATR(14) on the ACTIVE chart timeframe (_Period) - separate from g_hATR (fixed H1, used by the Location panel) since this engine must "prioritaskan timeframe aktif" per spec
string   g_sdBrkState_S = "NONE", g_sdBrkState_D = "NONE";
double   g_sdBrkZoneLo_S = 0, g_sdBrkZoneHi_S = 0, g_sdBrkZoneLo_D = 0, g_sdBrkZoneHi_D = 0;
int      g_sdBrkFollowBars_S = 0, g_sdBrkFollowBars_D = 0;
string   g_sdBrkMomentum_S = "-", g_sdBrkMomentum_D = "-";
int      g_sdBrkFalseCount_S = 0, g_sdBrkFalseCount_D = 0;   // rolling tally feeding CHOPPY read - decays on a real BREAK_CONFIRMED
datetime g_sdBrkLastBar = 0;                                  // new-bar gate, shared (both sides evaluated together)
string   g_sdMarketRead = "NORMAL";                            // NORMAL / COMPRESSION / CHOPPY - combined read for the panel

// v52.71: MOMENTUM ENTRY trigger state - see input group comment above.
ulong    g_momEntryTicket    = 0;        // open position ticket from this trigger (0 = none active)
datetime g_momEntryLastEvent = 0;        // last M5 BreakoutEventTime (buffer 7) already acted on - avoid re-firing on the same event

// v52.60: BARRIER QUEUE - Dadang drew it out: a barrier is NOT just the one
// most-recent flip level per TF, it's a whole STAIRCASE of them - every
// swing along a cascade leaves its own barrier behind, and when CMP finally
// reverses, EACH one has to be broken in turn ("BARIER, BARIER, BARIER..."
// stacked in his diagram, "CMP SELL berubah jadi BUY maka yang SELL lama
// ADALAH BARRIER yang WAJIB DIJEBOL SEBELUM NAIK TERUS" - and the second
// diagram shows them breaking one by one on the way back up). Replaces
// v52.47-v52.59's single OldBarrierDir/OldBarrierLevel pair per TF with a
// BarrierEntry queue: every flip PUSHES the level it's leaving onto the
// queue (instead of overwriting), and QueuePrune() removes an entry the
// moment price genuinely closes past it (permanently - once jebol, always
// jebol, never re-added). LastDir/LastLevel (flip DETECTION) unchanged.
struct BarrierEntry { string dir; double level; };
#define MAX_BARRIER_QUEUE 8

string       g_h4LastDir = "WAIT";   double g_h4LastLevel = 0.0;
BarrierEntry g_h4Queue[];
string       g_h1BarrierLastDir = "WAIT";   double g_h1BarrierLastLevel = 0.0;
BarrierEntry g_h1Queue[];
string       g_m30LastDir = "WAIT";   double g_m30LastLevel = 0.0;
BarrierEntry g_m30Queue[];
// v52.59: M15/M5 barrier AWARENESS (display/warning only, NOT wired into
// BarrierVetoes()'s hard entry-block - that stays H4/H1/M30 per Dadang's
// original "minimal H4 harus jebol" doctrine). Dadang: "barrier ... misal
// awas sampai barier m5 m15 m30 h1 h4 dstusnya" - wants to SEE every TF's
// barrier as a watch/warning zone, not necessarily have every TF veto entries.
string       g_m15LastDir = "WAIT";   double g_m15LastLevel = 0.0;
BarrierEntry g_m15Queue[];
string       g_m5LastDir = "WAIT";    double g_m5LastLevel = 0.0;
BarrierEntry g_m5Queue[];
// v52.61: D1 queue added ONLY as H4's "parent" for the self+parent nearest-
// barrier pairing (Dadang: "h4 mencari h4 dan dayli") - awareness only,
// same as M15/M5, never checked by BarrierVetoes().
string       g_d1LastDir = "WAIT";    double g_d1LastLevel = 0.0;
BarrierEntry g_d1Queue[];

// v52.6: the 5-step Bookmap read, narrated - Dadang: "dari 5 urutan itu bisa
// gak kalo masukin ke ea dan web gw sebagai narasi tapi di ea dia entri
// beneran" - see ComputeBookmapNarrative(). g_bmNarrVerdict is computed by
// literally calling BookmapTriggerDirection(), so what's narrated here and
// what actually fires a real entry can never drift apart.
string g_bmNarrWall     = "-";
string g_bmNarrCvd      = "-";
string g_bmNarrAbsorb   = "-";
string g_bmNarrIceberg  = "-";
string g_bmNarrLocation = "-";
string g_bmNarrVerdict  = "OFFLINE";

// v52.13: EMA-smoothed CVD, time-constant InpBookmapCvdSmoothMin. Continuous-
// time decay (not sample-count based) since ticks arrive irregularly -
// after InpBookmapCvdSmoothMin minutes with no new extreme values, the EMA
// has decayed ~63% toward whatever's been happening since. See UpdateCvdEma().
double   g_bmCvdEma     = 0.0;
datetime g_bmCvdEmaTime = 0;
#define WALL_SLOTS_PER_SIDE 20   // v29: 5 live-nearest + 5 historical -> v52.24: 5 near + 15 historical (Dadang: "tune up bro agar lebih maximal" right after the stale-addon fix unlocked real depth data) - keep in sync with WALL_NEAR/HIST_SLOTS_PER_SIDE in udp_listener.py's write_mt5_bridge_file()
double   g_bookmapBidPx[WALL_SLOTS_PER_SIDE], g_bookmapBidSz[WALL_SLOTS_PER_SIDE];
double   g_bookmapAskPx[WALL_SLOTS_PER_SIDE], g_bookmapAskSz[WALL_SLOTS_PER_SIDE];
// v52.14: seconds since each wall was first seen (WallLadderTracker.wall_age_sec()
// on the Python side) - lets HasLiquiditySupport() require a wall to have
// actually persisted before trusting it, instead of any price+size pair
// that happens to be sitting in slot 0 right now (could be a "bait" wall
// about to get pulled - see bookmap.com's writeup on fake liquidity).
double   g_bookmapBidAge[WALL_SLOTS_PER_SIDE], g_bookmapAskAge[WALL_SLOTS_PER_SIDE];

// v52.74 - wall consumption speed ("kecepatan wall dimakan" idea, built
// MT5-first per Dadang's standing instruction). Tracks each SLOT's own
// last-seen price+size+time - slot index roughly tracks the same ranked
// wall tick to tick, so WallEatRate() double-checks the price still
// matches (tolerance) before trusting the size delta as a real eat-rate,
// not two unrelated walls that happened to land in the same slot.
#define WALL_EAT_FAST_LOT_PER_SEC 1.5
double   g_prevBidPx[WALL_SLOTS_PER_SIDE], g_prevBidSz[WALL_SLOTS_PER_SIDE];
double   g_prevAskPx[WALL_SLOTS_PER_SIDE], g_prevAskSz[WALL_SLOTS_PER_SIDE];
datetime g_prevBidTime[WALL_SLOTS_PER_SIDE], g_prevAskTime[WALL_SLOTS_PER_SIDE];

// v52.84 - Reload Level ("Reload Level" konsep bootcamp Pavlovic: level yang
// PERNAH dites kuat tapi keserap/kalah, terus BELAKANGAN akhirnya jebol ->
// kalau harga balik retest level itu, ekspektasinya sisi yang dulu kalah
// "reload" (masuk lagi) dan bikin akselerasi. Beda dari wall biasa - butuh
// MEMORI 2 tahap (dulu-pernah-dites -> belakangan-jebol), bukan cuma wall
// yang lagi ada sekarang. EA-only, gak butuh perubahan bridge Python - cuma
// mengingat wall NEAR-live (slot 0..WALL_NEAR_SLOTS-1) yang hilang dari
// ladder SEKALIGUS harga udah lewat level itu (jebol beneran, bukan cuma
// wall pindah slot/re-quote).
#define WALL_NEAR_SLOTS 5   // near-live slot count, harus sama kayak WALL_NEAR_SLOTS_PER_SIDE di udp_listener.py
#define RELOAD_MAX 8
double   g_reloadPrice[RELOAD_MAX];
double   g_reloadSize[RELOAD_MAX];
bool     g_reloadIsBid[RELOAD_MAX];   // true = dulunya BID wall (breakdown lewatnya = ekspektasi jual lanjut kalau di-retest)
datetime g_reloadTime[RELOAD_MAX];
int      g_reloadCount = 0;
// snapshot KHUSUS buat deteksi Reload Level - sengaja terpisah dari
// g_prevBidPx/g_prevAskPx (punya WallEatRate(), diupdate per-slot pas
// DrawWallLine jalan) biar urutan pemanggilan gak saling ganggu.
double   g_reloadPrevBidPx[WALL_NEAR_SLOTS], g_reloadPrevBidSz[WALL_NEAR_SLOTS];
double   g_reloadPrevAskPx[WALL_NEAR_SLOTS], g_reloadPrevAskSz[WALL_NEAR_SLOTS];
bool     g_reloadPrevInit = false;

// v52.26: wall SWEEP + reversal - Dadang: "ide gila lagi bro?" -> stop-hunt/
// liquidity-grab detection. A big/persistent wall traded clean through
// ("jebol") then either reclaimed (REVERSAL_CONFIRMED - the classic hunt-
// then-bounce) or not (CONTINUATION - genuine breakout). Detection/
// resolution is 100% Python-side (cr_master_engine.py's WallLadderTracker),
// this is just the latest event read straight off the bridge CSV -
// display-only for now (chart marker + panel row), NOT wired into
// TryOpen() sizing/trigger yet - same two-phase pattern POC followed
// (recorded first, wired later once real data existed to validate against).
string   g_bmSweepSide     = "";
double   g_bmSweepPrice    = 0.0;
double   g_bmSweepSize     = 0.0;
double   g_bmSweepAgeSec   = 0.0;      // how long the wall persisted before being swept
string   g_bmSweepStatus   = "NONE";   // NONE / PENDING / REVERSAL_CONFIRMED / CONTINUATION
double   g_bmSweepSinceSec = 0.0;      // how long ago the sweep happened
bool     g_sweepDrawnOnWallLine = false;   // v52.27b - true when DrawWallLine() repainted the swept wall's OWN slot this cycle (see UpdateSweepMarker()'s fallback)
// v52.69: PERSISTENT sweep record - Dadang: "maksudnya ke record dan dia
// ilang ketika di jebol bro selama belum kejebol masih tercatat di panel" -
// stays active until genuinely broken by candle CLOSE (same rule as barrier
// tracking), not by an arbitrary time limit. See UpdateSweepRecord().
bool     g_sweepRecActive    = false;
string   g_sweepRecSide      = "";
double   g_sweepRecPriceMt5  = 0.0;
double   g_sweepRecSize      = 0.0;
string   g_sweepRecStatus    = "";
datetime g_sweepRecFirstSeen = 0;

// v52.74 - "Mega Sweep": 3+ sweep events on the SAME side within 5 min -
// the staircase pattern from the 2026-08-20 history analysis (a wall gets
// swept, price tests the next one down/up, repeat, until the real
// reversal). Ring buffer of recent sweep sides+times, recomputed every
// tick (not just on a new sweep) so it correctly clears itself once the
// window empties out even without a fresh event. Dadang: "setiap kerja
// duluin mt5 nya baru ke web" - built here first, web version (logic.js)
// already existed from earlier the same night.
#define MEGA_SWEEP_WINDOW_SEC 300
#define MEGA_SWEEP_MIN_COUNT  3
#define MEGA_SWEEP_LOG_LEN    12
string   g_sweepLogSide[MEGA_SWEEP_LOG_LEN];
datetime g_sweepLogTime[MEGA_SWEEP_LOG_LEN];
int      g_sweepLogHead   = 0;
int      g_sweepLogFilled = 0;
bool     g_megaSweepActive = false;
string   g_megaSweepSide   = "";
int      g_megaSweepCount  = 0;
bool     g_bidClustered[WALL_SLOTS_PER_SIDE], g_askClustered[WALL_SLOTS_PER_SIDE];   // v52.34 - filled by UpdateWallZones() (runs first), read by UpdateWallLines() to skip a clustered wall's own redundant text label (zone box's aggregate label already covers it) - the line itself is unaffected either way

// v34: SULTAN SNIPER ENGINE web dashboard export - Dadang: "gak usah baca
// pine langsung mt5 aja" + "web dashboard buat semaximal mungkin". CVD
// minute-history ring buffer for the "Delta Progress" mini-chart (1-minute
// CVD deltas, newest last) - sampled once per real minute in OnTick(), NOT
// tied to chart timeframe/bars.
#define CVD_HIST_LEN 30
double   g_cvdMinuteSamples[CVD_HIST_LEN];   // raw g_bookmapCvd snapshots, one per minute
int      g_cvdSampleCount = 0;                // how many slots filled so far (<CVD_HIST_LEN early on)
int      g_lastCvdSampleMinute = -1;          // detects a real minute rollover (not chart-bar-based)

// v52.41: POC minute-history ring buffer, same sampling mechanism as the
// CVD one above - Dadang, watching POC move live: "poc ini ternyata bisa
// langsung pindah ke atas atau ke bawah ini artinya apa" -> a POC that
// migrates WITH the trend confirms real value acceptance; one that stays
// put means the move hasn't been "accepted" yet. See IsPocMigrating().
double   g_pocMinuteSamples[CVD_HIST_LEN];   // raw g_bookmapPocPrice snapshots, one per minute
int      g_pocSampleCount = 0;
int      g_lastPocSampleMinute = -1;
datetime g_lastSultanExportTime = 0;          // throttle WriteSultanStatus() to ~1/sec
// v52.85 - DNA Vault: throttle for the per-day history log append (once/min,
// not every ~1/sec WriteSultanStatus() call) - see the append block at the
// end of WriteSultanStatus() for why.
int      g_dnaVaultLastMin  = -1;
int      g_dnaVaultLastHour = -1;
double   g_bookmapAgeMs = -1.0;               // set in ReadBookmapBridge() - bridge latency for the dashboard

// v31: Strategy Tester replay of Bookmap history - Dadang: "siapin semuanya
// bro" (buat backtest weekend). The LIVE bridge file above can't be used
// during backtest by design (real wall-clock timestamp never matches
// simulated time). This instead loads udp_listener.py's own
// Common\Files\bookmap_history\bookmap_history_YYYY-MM-DD.csv archive (one
// row/5s, written continuously since 2026-08-10) and looks up the closest
// recorded row for each simulated bar's REAL timestamp - only produces
// results for date ranges that overlap with when that archive was actually
// being recorded (nothing before 2026-08-10). Wall ladder isn't in the
// archive (only CVD/Pulse/Absorption/POC), so no wall lines during replay -
// only Absorption + POC-overextend (the two TryOpen() actually uses) get to
// participate in backtests going forward.
bool     g_bmHistLoaded = false;
int      g_bmHistCount  = 0;
datetime g_bmHistTime[];
double   g_bmHistBmPrice[];
double   g_bmHistCvd[];
double   g_bmHistPulse[];
string   g_bmHistAbsorb[];
double   g_bmHistPocPrice[];
double   g_bmHistPocVolume[];
double   g_bmHistVal[];    // v33
double   g_bmHistVah[];    // v33
// v52.4: full wall ladder + iceberg, now actually replayed (previously read-
// and-discarded even where present in the v33 CSV - see LoadOneBookmapHistoryFile()).
double   g_bmHistBidIcePx[], g_bmHistBidIceSz[], g_bmHistBidIceRatio[];
double   g_bmHistAskIcePx[], g_bmHistAskIceSz[], g_bmHistAskIceRatio[];
double   g_bmHistBidPx[][WALL_SLOTS_PER_SIDE], g_bmHistBidSz[][WALL_SLOTS_PER_SIDE];
double   g_bmHistAskPx[][WALL_SLOTS_PER_SIDE], g_bmHistAskSz[][WALL_SLOTS_PER_SIDE];
double   g_bmHistBidAge[][WALL_SLOTS_PER_SIDE], g_bmHistAskAge[][WALL_SLOTS_PER_SIDE];   // v52.14
#define BM_HIST_DIR "bookmap_history\\"
#define BM_HIST_GLOB "bookmap_history_v7_*.csv"   // v52.76: schema bumped v7 (added 3 mega-sweep columns, read-and-discarded - see LoadOneBookmapHistoryFile()) - glob only matches v7+ files, skips older-schema files (would desync the fixed-column reader). v52.26 had bumped it to v6 the same way (6 wall-sweep columns).

#define DASH_PREFIX "DD_DASH_"
#define WALL_PREFIX "DD_WALL_"
#define SDZ_PREFIX  "DD_SDZ_"   // v53 - SND zone boxes (Supply/Demand), see DrawZoneBox()/DrawAllZones()
#define SDPM_PREFIX "DD_SDPM_"  // v53 TAHAP 9 - S&D Price Map panel, see CreateSDPMPanel()/UpdateSDPMPanel()
#define SDRM_PREFIX "DD_SDRM_"  // v53.3 - roadmap HLINEs, see UpdateRoadmapLines()
#define SDBRK_PREFIX "DD_SDBRK_" // v53.18 - S&D Momentum Break Engine markers, see DrawSDBreakMarker()
#define WALL_ZONE_PREFIX "ZONE"   // v52.31: sub-namespace under WALL_PREFIX for cluster zone overlays, e.g. WALL_PREFIX+WALL_ZONE_PREFIX+"BID1"
// v39: panel geometry/palette globals now live next to CreatePanel()/
// UpdatePanel() themselves (Canvas-rendered panel) - see PNL_* below.

//--- pip size. 3/5-digit forex brokers: 1 pip = 10 points. XAUUSD is
//--- typically quoted 2-digit (e.g. 3330.92) where the same 1-pip-=-10-point
//--- gold convention applies (1 pip = $0.10) - NOT 1 point = 1 pip like a
//--- plain 2-digit forex quote. Without this, all *_Pips inputs (SL,
//--- trailing) come out 10x too tight and get hunted by normal noise.
double PipSize()
{
   return (_Digits == 3 || _Digits == 5 || _Digits == 2) ? _Point * 10.0 : _Point;
}

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);

   // v52.11: restore the Bookmap-trigger cooldown clock across reload -
   // without this, reattaching/recompiling the EA silently zeroes the
   // 15-minute cooldown even if a real trigger fired 30 seconds ago.
   if(GlobalVariableCheck(GV_BOOKMAP_TRIGGER_TIME))
      g_lastBookmapTriggerTime = (datetime)GlobalVariableGet(GV_BOOKMAP_TRIGGER_TIME);
   if(GlobalVariableCheck(GV_VARETEST_TRIGGER_TIME))   // v52.42: same reload-survival as above
      g_lastVaRetestTime = (datetime)GlobalVariableGet(GV_VARETEST_TRIGGER_TIME);
   if(GlobalVariableCheck(GV_VARETEST_TICKET))   // v52.44: restore SL-trailing target across reload
   {
      ulong savedTicket = (ulong)GlobalVariableGet(GV_VARETEST_TICKET);
      if(savedTicket != 0 && PositionSelectByTicket(savedTicket))
         g_vaRetestTicket = savedTicket;   // position still open on the broker side - resume trailing it
      else
         GlobalVariableDel(GV_VARETEST_TICKET);   // position already closed while EA was reloading - clean up the stale marker
   }
   if(GlobalVariableCheck(GV_FUSION_TICKET))   // v52.45: same reload-survival as VARETEST above
   {
      ulong savedFusionTicket = (ulong)GlobalVariableGet(GV_FUSION_TICKET);
      if(savedFusionTicket != 0 && PositionSelectByTicket(savedFusionTicket))
         g_fusionTicket = savedFusionTicket;   // position still open - resume watching for the H4-flip structural exit
      else
         GlobalVariableDel(GV_FUSION_TICKET);
   }
   if(GlobalVariableCheck(GV_MOMENTUM_TICKET))   // v52.71: same reload-survival as VARETEST/FUSION above
   {
      ulong savedMomTicket = (ulong)GlobalVariableGet(GV_MOMENTUM_TICKET);
      if(savedMomTicket != 0 && PositionSelectByTicket(savedMomTicket))
         g_momEntryTicket = savedMomTicket;   // position still open - resume watching for the M5-CMP-flip structural exit
      else
         GlobalVariableDel(GV_MOMENTUM_TICKET);
   }

   g_hMaster      = iCustom(_Symbol, InpMasterTF,      "DD_CMP_Indicator");
   g_hScalpMaster = iCustom(_Symbol, InpScalpMasterTF, "DD_CMP_Indicator");
   g_hScalpEntry  = iCustom(_Symbol, InpScalpEntryTF,  "DD_CMP_Indicator");
   if(g_hMaster == INVALID_HANDLE || g_hScalpMaster == INVALID_HANDLE || g_hScalpEntry == INVALID_HANDLE)
   {
      Print("ERROR: gagal load DD_CMP_Indicator - pastikan DD_CMP_Indicator.ex5 ada di folder Indicators.");
      return(INIT_FAILED);
   }
         if(InpUseM1Confirm)
   {
      g_hM1 = iCustom(_Symbol, PERIOD_M1, "DD_CMP_Indicator");
      if(g_hM1 == INVALID_HANDLE)
         Print("WARNING: gagal load DD_CMP_Indicator buat M1 confirmation - filter M1 di-skip (bukan fatal).");
   }
   if(InpAvoidBigSNR)
   {
      g_hWeekly = iCustom(_Symbol, PERIOD_W1, "DD_CMP_Indicator");
      g_hDaily  = iCustom(_Symbol, PERIOD_D1, "DD_CMP_Indicator");
      if(g_hWeekly == INVALID_HANDLE || g_hDaily == INVALID_HANDLE)
         Print("WARNING: gagal load DD_CMP_Indicator buat W1/D1 - filter InpAvoidBigSNR di-skip (bukan fatal).");
   }
   if(InpAvoidBigSNR || InpRequireH1ForScalp || InpUseFusionH1H4 || InpUseBarrierVeto)
   {
      g_hH1 = iCustom(_Symbol, PERIOD_H1, "DD_CMP_Indicator");   // dipake InpAvoidBigSNR (Daily zone confirm), InpRequireH1ForScalp, InpUseFusionH1H4 (v52.45), DAN InpUseBarrierVeto (v52.47)
      if(g_hH1 == INVALID_HANDLE)
         Print("WARNING: gagal load DD_CMP_Indicator buat H1 - filter yang butuh H1 di-skip (bukan fatal).");
   }
   if(InpUseFusionH1H4)
   {
      g_hFusionM5 = iCustom(_Symbol, PERIOD_M5, "DD_CMP_Indicator");   // v52.45: dedicated M5 handle, decoupled dari InpScalpEntryTF
      if(g_hFusionM5 == INVALID_HANDLE)
         Print("WARNING: gagal load DD_CMP_Indicator buat Fusion M5 - sinyal Fusion H1/H4 gak akan fire (bukan fatal, sinyal lain tetep jalan).");
   }

   // v34: always-on handles for the SULTAN SNIPER web dashboard export -
   // separate from the conditional ones above (trading-logic filters), so
   // toggling InpAvoidBigSNR/InpRequireH1ForScalp never affects what the
   // dashboard can show.
   g_hExportD1  = iCustom(_Symbol, PERIOD_D1,  "DD_CMP_Indicator");
   g_hExportH1  = iCustom(_Symbol, PERIOD_H1,  "DD_CMP_Indicator");
   g_hExportM15 = iCustom(_Symbol, PERIOD_M15, "DD_CMP_Indicator");
   g_hExportM1  = iCustom(_Symbol, PERIOD_M1,  "DD_CMP_Indicator");
   g_hATR       = iATR(_Symbol, PERIOD_H1, 14);
   g_hATR_Active = iATR(_Symbol, _Period, 14);   // v53.18: S&D Break Engine - ATR on the chart's OWN timeframe, not fixed H1

   if(InpUseBarrierVeto)   // v52.56/v52.60/v52.63: learn existing barrier QUEUES from history - first attempt here,
      TryBootstrapAllBarriers();                       // retried every OnTick (see there) until every TF's indicator is actually ready

   // v43.1: prefer a real dollar index, fall back to EURUSD. The contract
   // month is discovered rather than hardcoded, so the September -> December
   // roll (DXY_U6 -> DXY_Z6) doesn't silently kill the reading. A candidate
   // only wins if it actually carries enough H4 history to compute CMP on.
   // Only the NAME is resolved here. MT5 loads a freshly selected symbol's
   // history asynchronously, so iBars() still reads 0 at OnInit time even
   // though DXY_U6 actually holds ~2962 H4 bars - gating on bar count here
   // rejected it every time and silently fell back to EURUSD. The bar check
   // moved into ReadUsdFundamental(), which adopts the candidate as soon as
   // its history has finished downloading.
   g_usdSymbol    = "";
   g_usdInverted  = false;
   g_usdCandidate = "";
   int symTotal = SymbolsTotal(false);
   for(int i = 0; i < symTotal; i++)
   {
      string nm = SymbolName(i, false);
      if(StringFind(nm, "DXY_") != 0) continue;
      if(StringFind(nm, ".") >= 0)    continue;   // skips equity tickers like DXYZ.NYSE-24
      if(!SymbolSelect(nm, true))     continue;
      g_usdCandidate = nm;
      iBars(nm, PERIOD_H4);                       // kick off the async history download
      break;
   }
   // Start on EURUSD (always loaded, always ticking) and upgrade to DXY later.
   g_usdSymbol   = USD_SYMBOL;
   g_usdInverted = true;
   SymbolSelect(g_usdSymbol, true);
   g_hEurUsdH4 = iCustom(g_usdSymbol, PERIOD_H4, "DD_CMP_Indicator");
   if(g_hEurUsdH4 == INVALID_HANDLE)
      Print("INFO: gagal load DD_CMP_Indicator buat ", g_usdSymbol,
            " - baris USD di panel bakal kosong (bukan fatal).");
   else
      Print("USD fundamental source: ", g_usdSymbol, g_usdInverted ? "  (inverted: naik = USD lemah)" : "  (direct: naik = USD kuat)");
   if(g_hExportD1 == INVALID_HANDLE || g_hExportH1 == INVALID_HANDLE || g_hExportM15 == INVALID_HANDLE || g_hExportM1 == INVALID_HANDLE || g_hATR == INVALID_HANDLE)
      Print("WARNING: gagal load salah satu handle export dashboard (D1/H1/M15/ATR) - beberapa field di web dashboard bisa kosong (bukan fatal).");

      Print("==========================================================================");
   Print("=== SULTAN SNIPER EA_VERSION ", EA_VERSION, " ACTIVATED ===");
   Print("=== STRICT DADANG FLOW: M30 Pullback Candle -> M5 BO AFTER Pullback -> ENTRY ===");
   Print("==========================================================================");

   if(InpShowPanel) CreatePanel();
   if(InpShowZonesOnChart) CreateSDPMPanel();   // v53 TAHAP 9

   // v31: load recorded Bookmap history ONCE for Strategy Tester/Optimization
   // replay (Dadang: "siapin semuanya bro" buat backtest weekend) - never
   // touches the live path (ReadBookmapBridge() branches on tester mode).
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      LoadBookmapHistory();

   Print("DD Chain Reaction Multi-TF EA [", EA_VERSION, "] aktif: H4=", EnumToString(InpMasterTF),
         " -> M30=", EnumToString(InpScalpMasterTF), " -> M5=", EnumToString(InpScalpEntryTF));
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, SDZ_PREFIX);   // v53 - SND zone boxes
   ObjectsDeleteAll(0, SDPM_PREFIX);  // v53 TAHAP 9 - S&D Price Map panel
   ObjectsDeleteAll(0, SDRM_PREFIX);  // v53.3 - roadmap HLINEs
   ObjectsDeleteAll(0, SDBRK_PREFIX); // v53.18 - S&D Momentum Break Engine markers
   ObjectDelete(0, "DD_H4OpenArrow");    // v52.48-v52.57 legacy names, harmless if already gone
   ObjectDelete(0, "DD_M30OpenArrow");
   ObjectDelete(0, "DD_M5OpenArrow");
   ObjectDelete(0, "DD_H4OpenTxt");
   ObjectDelete(0, "DD_M30OpenTxt");
   ObjectDelete(0, "DD_M5OpenTxt");
   ObjectDelete(0, "DD_H4BarrierArrow");  // v52.61: current single-nearest-marker names (also matches v52.58's, reused)
   ObjectDelete(0, "DD_H4BarrierTxt");
   ObjectDelete(0, "DD_H1BarrierArrow");
   ObjectDelete(0, "DD_H1BarrierTxt");
   ObjectDelete(0, "DD_M30BarrierArrow");
   ObjectDelete(0, "DD_M30BarrierTxt");
   ObjectDelete(0, "DD_M15BarrierArrow");
   ObjectDelete(0, "DD_M15BarrierTxt");
   ObjectDelete(0, "DD_M5BarrierArrow");
   ObjectDelete(0, "DD_M5BarrierTxt");
   string barrierPfx[5] = {"DD_H4Barrier", "DD_H1Barrier", "DD_M30Barrier", "DD_M15Barrier", "DD_M5Barrier"};   // v52.60 legacy indexed queue markers, harmless if already gone
   for(int bp = 0; bp < 5; bp++)
      for(int bi = 0; bi < MAX_BARRIER_QUEUE; bi++)
      {
         ObjectDelete(0, barrierPfx[bp] + "_A" + IntegerToString(bi));
         ObjectDelete(0, barrierPfx[bp] + "_T" + IntegerToString(bi));
      }
   ObjectDelete(0, "DD_CD_BG");         // v52.50
   ObjectDelete(0, "DD_CD_TITLE");
   ObjectDelete(0, "DD_CD_H4");
   ObjectDelete(0, "DD_CD_H1");         // v52.51
   ObjectDelete(0, "DD_CD_M30");
   ObjectDelete(0, "DD_CD_M15");        // v52.51
   ObjectDelete(0, "DD_CD_M5");
   ObjectDelete(0, "DD_CD_M1");         // v52.51
   if(g_hMaster != INVALID_HANDLE) IndicatorRelease(g_hMaster);
   if(g_hScalpMaster != INVALID_HANDLE) IndicatorRelease(g_hScalpMaster);
   if(g_hScalpEntry  != INVALID_HANDLE) IndicatorRelease(g_hScalpEntry);
   if(g_hM1             != INVALID_HANDLE) IndicatorRelease(g_hM1);
   if(g_hWeekly         != INVALID_HANDLE) IndicatorRelease(g_hWeekly);
   if(g_hDaily          != INVALID_HANDLE) IndicatorRelease(g_hDaily);
   if(g_hH1             != INVALID_HANDLE) IndicatorRelease(g_hH1);
   if(g_hFusionM5       != INVALID_HANDLE) IndicatorRelease(g_hFusionM5);   // v52.45
   if(g_hExportD1       != INVALID_HANDLE) IndicatorRelease(g_hExportD1);
   if(g_hExportH1       != INVALID_HANDLE) IndicatorRelease(g_hExportH1);
   if(g_hExportM15      != INVALID_HANDLE) IndicatorRelease(g_hExportM15);
   if(g_hExportM1       != INVALID_HANDLE) IndicatorRelease(g_hExportM1);
   if(g_hATR            != INVALID_HANDLE) IndicatorRelease(g_hATR);
   if(g_hATR_Active     != INVALID_HANDLE) IndicatorRelease(g_hATR_Active);
   if(g_hEurUsdH4       != INVALID_HANDLE) IndicatorRelease(g_hEurUsdH4);
   g_panelCanvas.Destroy();
   ObjectsDeleteAll(0, DASH_PREFIX);
   ObjectsDeleteAll(0, WALL_PREFIX);
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| On-chart live panel - Canvas-rendered (raster bitmap), matching   |
//| the Sultan Sniper Engine web dashboard's visual language. v39:    |
//| Dadang pushed through several rounds on the standalone preview EA |
//| ("ternyata bisa keren... buat yang keren dong" -> "hurufnya masih |
//| kurang jelas" -> "produksi aja ke panel lama") - this replaces    |
//| the old flat OBJ_LABEL/OBJ_RECTANGLE_LABEL panel entirely: true   |
//| rounded corners, a soft drop shadow, a gold gradient top accent,  |
//| a real smooth-gradient semicircle Price Pressure gauge. v39.1:    |
//| Dadang: "sama aja rubah fontnya bro... rubah semua jenis font nya |
//| dan buat SOLID" - every piece of text that went missing used the  |
//| 4x-offset "fake bold" stamp (PnlTxtB); everything drawn with a    |
//| single TextOut call rendered fine regardless of font name. That   |
//| points at the stamping trick itself, not the font. Fix: ONE font  |
//| everywhere (Arial - the most universally-resolvable Windows font, |
//| safer than Segoe UI/Consolas/Lucida Console for Canvas's GDI      |
//| lookup), and PnlTxtB now just draws once at a bigger size instead |
//| of stamping - the exact same code path as PnlTxt(), which was     |
//| never in question. Row's value column also switched from a       |
//| computed-width right-align to a fixed offset, removing another    |
//| guess (monospace character-width assumption) from the render path.|
//+------------------------------------------------------------------+
color DirColor(string d) { return (d == "BUY") ? clrLime : (d == "SELL" ? clrTomato : clrSilver); }

CCanvas g_panelCanvas;
uint    g_lastPanelDrawMs = 0;

#define PNL_RGB(r,g,b) ((color)((uchar)(r) + ((uchar)(g) << 8) + ((uchar)(b) << 16)))
#define PNL_FONT "Arial"   // single font for the whole panel - most universally available on Windows

color PNL_GOLD    = C'217,180,101';
color PNL_EMERALD = C'52,211,153';
color PNL_ROSE    = C'251,113,133';
color PNL_SILVER  = C'139,149,167';
// v39.9: verified by screenshotting the live chart directly (not from a
// described symptom) - the outline bold from v39.8 IS rendering; values
// are visibly heavier than their labels. What still read as "tipis" was
// two other things: label text at 9px is simply tiny, and PNL_SILVER is
// too dim against the near-black panel. Labels get their own brighter
// tone here, and every font size steps up (see DrawPanel below), while
// the panel stays compact per "kecilin dikit".
// v40: Dadang pointed at the "BIAS — SIDEWAYS" line as the reference -
// "buat aja seperti ini soalnya warnanya itu redup tenggelam". That line
// was the one piece already drawn bold-with-outline in a bright tone;
// everything else used dim silver with no outline and sank into the dark
// panel. So: labels get near-white AND the same outline treatment as the
// values - no plain/dim text left anywhere in the panel.
// v40.1: Dadang - "lo putihkan teksnya coba atau itu sudah mentok" - it
// wasn't maxed; this was 214,222,235 (a slightly blue-tinted white). Now
// pure 255. The semantic colors (emerald/rose/gold on the VALUES) stay as
// they are - those encode direction and status, not emphasis.
color PNL_LABEL   = C'255,255,255';
color PNL_WHITE   = C'255,255,255';   // Dadang: "huruf putih masih redup, buat solid" - pure white
color PNL_BG      = C'14,16,23';
color PNL_RULE    = C'52,45,30';
color PNL_SHADOW  = C'0,0,0';

int PNL_PX = 12, PNL_PY = 18, PNL_W = 350, PNL_H = 926;   // v53.18: +16 for the new "Break Status" row (S&D Momentum Break Engine). v53.16: back to 910 - the S1-S3/D1-D3 roadmap rows (v53.14's +130) removed again, Dadang: "kepanjangan, kan sudah ada di chart". v53.10: +110 for the merged S&D PRICE MAP section. v53.11: -100 for the 7 removed Vol Ratio/POC/Value Area/VA Bias/VA Retest/Fusion H1H4/Barrier rows (worst case ~112px, kept a little margin rather than shave the exact amount)   // v52.93: 808->900 - actually summed every y+= in UpdatePanel() for the worst realistic case (Bookmap LIVE + VA Retest + Fusion H1/H4 + Barrier + Momentum Entry all ON, mega sweep, USD bias+news, conviction block with sudah+lawan both present - very plausible right now, this branch IS the Fusion H1/H4 feature) and it comes to ~862px before the footer even starts, already past the OLD 808 border and close to blowing through the canvas bitmap's own buffer (bmpH = PNL_H + margins) entirely - not just "outside the gold box" but potentially silently clipped/undrawn. +92 gives real margin instead of another guess. Same "MT5 clips at the chart subwindow's own boundary" risk noted below applies in the other direction now - if this ever reads as too tall on Dadang's screen, that's the trade-off surfacing, distinct from every overflow bug fixed this session. v52.16: +18 for "Regime" row. v52.26: +18 for "Wall Sweep" row. v52.35: -34 for removed Win Rate/Closed Profit rows. v52.36: +16 for "VA Bias" row. v52.42: +16 reserved for conditional "VA Retest" row. v52.45: +16 reserved for conditional "Fusion H1/H4" row. v52.47: +16 reserved for conditional "Barrier (H4)" row. v52.49: -48, moved 3 candle-close-countdown rows off-panel onto chart (see UpdateCandleOpenMarker) - panel was too tall to fit on screen. v52.51: -96, removed 6 wall-summary rows (redundant with on-chart wall labels). v52.52: +16 for "Momentum (M5)" row. v52.62: -56 (shrunk Price Pressure gauge -40, merged USD+Efek-ke-Gold into 1 row -16) - recurring "panel kepotong" complaint even after v52.49/v52.51 trims; MT5 clips the canvas at the chart subwindow's own pixel boundary, unrelated to any internal margin, so the only real fix is a shorter total canvas. v52.71: +16 reserved for conditional "Momentum Entry" row (OFF by default, InpUseMomentumEntryTrigger). v52.92: PNL_W 310->350 - Dadang, screenshot of the merged 3-reason "lawan" line running past the right border: "keluar panel bro paqnjangin dikit kotak nya" - WIDTH was never touched by any earlier pass (all the above are HEIGHT), so a long combined line had less horizontal room than it needed.
int PNL_MARGIN = 14, PNL_RADIUS = 10, PNL_BORDER = 2;
int PNL_VALUE_COL = 140; // fixed x-offset (from a row's left edge) where the value text starts

color PnlLerp(uchar r1, uchar g1, uchar b1, uchar r2, uchar g2, uchar b2, double t)
{
   t = MathMax(0.0, MathMin(1.0, t));
   uchar r = (uchar)MathRound(r1 + (r2 - r1) * t);
   uchar g = (uchar)MathRound(g1 + (g2 - g1) * t);
   uchar b = (uchar)MathRound(b1 + (b2 - b1) * t);
   return PNL_RGB(r, g, b);
}

//--- true rounded rectangle: 2 overlapping full rects leave the 4 corner
//--- squares blank, then a full circle centered on each corner's inner
//--- point fills exactly the quarter-disk that belongs there.
void PnlFillRoundedRect(int x1, int y1, int x2, int y2, int r, uint argb)
{
   g_panelCanvas.FillRectangle(x1 + r, y1, x2 - r, y2, argb);
   g_panelCanvas.FillRectangle(x1, y1 + r, x2, y2 - r, argb);
   g_panelCanvas.FillCircle(x1 + r, y1 + r, r, argb);
   g_panelCanvas.FillCircle(x2 - r, y1 + r, r, argb);
   g_panelCanvas.FillCircle(x1 + r, y2 - r, r, argb);
   g_panelCanvas.FillCircle(x2 - r, y2 - r, r, argb);
}

// v39.4: Dadang - "lo coba pikir ulang atau browsing dulu" - the real bug
// was never the font NAME. CCanvas::FontSet()'s 3rd parameter ("flags") IS
// the font weight itself (0-1000, Win32 GDI's LOGFONT.lfWeight - 400 is
// normal, 700 is bold), passed straight through to CreateFont(). Every
// earlier attempt left this at its default (0 = FW_DONTCARE, i.e. regular)
// and instead tried to bake "bold" into the face-NAME string ("Arial
// Bold", "Arial Black") - which is why nothing ever actually got heavier.
#define PNL_WEIGHT_NORMAL 400
#define PNL_WEIGHT_BOLD   700

void PnlTxt(int x, int y, string s, color clr, int size = 11, uint anchor = TA_LEFT | TA_TOP)
{
   g_panelCanvas.FontSet(PNL_FONT, size, PNL_WEIGHT_NORMAL);
   g_panelCanvas.TextOut(x, y, s, ColorToARGB(clr, 255), anchor);
}

// v39.7: pushed the outline (picked as "E" in the mockup A/B test) much
// harder - 2px ring (16 offset points, not 8) instead of 1px, deliberately
// exaggerated so the result is unambiguous either way. EA_VERSION was
// also bumped to "v39.7-BOLDTEST" (shows in the panel title) specifically
// so it's visually obvious whether this exact build is the one actually
// loaded - if the panel still says "v39" (no suffix), MT5 is running a
// stale/cached copy and that's the real problem, not this function.
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

// v52.93 - full-width audit after 6 straight patch cycles on this panel
// (Dadang: "kenapa lo jadi bodoh bro" - fair, this should've been one
// pass from the start). PnlRow() got the TextWidth() truncation
// structural fix in v52.87/92, but a handful of FULL-WIDTH lines
// (version/owner header, the RANTAI chain header) are drawn with plain
// PnlTxtB() straight off x0 and were never given the same protection -
// both happen to sit close to budget already and get longer as more
// version suffixes / grade words are added over time. Same pattern as
// PnlRow(), generalized for any left-anchored full-width line.
void PnlTxtBFit(int x, int y, string s, color clr, int size, int maxW)
{
   g_panelCanvas.FontSet(PNL_FONT, size, PNL_WEIGHT_BOLD);
   while(StringLen(s) > 8 && g_panelCanvas.TextWidth(s) > maxW - 4)
      s = StringSubstr(s, 0, StringLen(s) - 2) + "…";
   PnlTxtB(x, y, s, clr, size);
}

void PnlRule(int x, int y, int w) { g_panelCanvas.FillRectangle(x, y, x + w, y + 1, ColorToARGB(PNL_RULE, 255)); }

// v52.87 - Dadang, chart screenshot: "panel masih berantakan banyak yang
// keluar kotak" - the value column is a FIXED pixel width (colW -
// PNL_VALUE_COL), but every row's text was hand-length-guessed against it
// (character-count math, not actual rendered pixels) - wrong more than
// once already (IVB alone needed fixing twice). This measures the value's
// REAL rendered width with the same font/size/weight it's about to be
// drawn with (CCanvas::TextWidth(), after the matching FontSet() call)
// and shortens with an ellipsis if it would overflow the panel's own
// right edge - a structural backstop so this bug class can't recur no
// matter what future row gets added or how long a price/value grows.
void PnlRow(int x, int y, int colW, string label, string value, color valueClr)
{
   PnlTxtB(x, y, label, PNL_LABEL, 11);
   int valueX = x + PNL_VALUE_COL;
   // v52.92: -4px safety margin - PnlTxtB() draws a 2px outline stroke
   // around the glyph (see its own comment), which bleeds a few pixels
   // past what TextWidth() reports for the bare glyph. Without this, text
   // measured as "just barely fits" could still visually clip its outline
   // past the column edge.
   int maxW = (x + colW) - valueX - 4;
   g_panelCanvas.FontSet(PNL_FONT, 13, PNL_WEIGHT_BOLD);
   while(StringLen(value) > 3 && g_panelCanvas.TextWidth(value) > maxW)
      value = StringSubstr(value, 0, StringLen(value) - 2) + "…";
   PnlTxtB(valueX, y - 1, value, valueClr, 13);
}

//--- same as PnlRow() but with a small colored accent bar to the left,
//--- for the numbers that deserve to stand out (matches the web
//--- dashboard's accent-bid/accent-ask idiom).
void PnlAccentRow(int x, int y, int colW, string label, string value, color valueClr, color accentClr)
{
   g_panelCanvas.FillRectangle(x - 9, y, x - 6, y + 14, ColorToARGB(accentClr, 255));
   PnlRow(x, y, colW, label, value, valueClr);
}

void PnlStatusDot(int x, int y, color clr) { g_panelCanvas.FillCircle(x, y, 3, ColorToARGB(clr, 255)); }

void CreatePanel()
{
   ObjectsDeleteAll(0, DASH_PREFIX); // clean out leftover flat objects from pre-v39 versions

   int bmpW = PNL_W + PNL_MARGIN * 2, bmpH = PNL_H + PNL_MARGIN * 2;
   g_panelCanvas.CreateBitmapLabel(DASH_PREFIX + "CANVAS", 15, 15, bmpW, bmpH, COLOR_FORMAT_ARGB_NORMALIZE);
   ObjectSetInteger(0, DASH_PREFIX + "CANVAS", OBJPROP_CORNER, CORNER_LEFT_UPPER);
}

void UpdatePanel()
{
   if(!InpShowPanel) return;
   // v41: the per-position P&L loop that used to run here (feeding the Open/
   // Float P&L, Closed (W/L) and Total Profit rows) was replaced by the
   // Bookmap liquidity block, so it was dropped. v52.35: the Win Rate/Closed
   // Profit rows added after that point are gone too now (Dadang: "win rate
   // dan total ini lo ilangin aja bro karena gw gak butuh") - RecalcStatsIfNeeded()
   // and the g_stat*/g_lastDealsTotal globals it fed were unused anywhere
   // else, so removed outright instead of left as dead code.

   // v39: a Canvas redraw is a raster operation (dozens of fill/text calls,
   // the gauge alone loops 180x) - too expensive to run on every tick like
   // the old ObjectSetString version could. Throttled to ~2x/sec, same
   // spirit as the web dashboard's 800ms poll - still reads as live.
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
                       // v39.8: alpha 255, NOT 245. The bold-text A/B mockup (where
                       // technique "E" visibly worked) filled its background fully
                       // opaque; production used 245, and on a COLOR_FORMAT_ARGB_NORMALIZE
                       // canvas the normalize pass washes out text stamped over
                       // semi-transparent pixels - which is why every bold attempt
                       // rendered identically here but not in the mockup.
                       PNL_RADIUS - PNL_BORDER, ColorToARGB(PNL_BG, 255));

   g_panelCanvas.FillRectangle(ox + PNL_RADIUS, oy, ox + PNL_W - PNL_RADIUS, oy + 4, ColorToARGB(PNL_GOLD, 255));
   for(int i = 0; i < 6; i++)
      g_panelCanvas.FillRectangle(ox + PNL_RADIUS, oy + 4 + i, ox + PNL_W - PNL_RADIUS, oy + 5 + i,
                                   ColorToARGB(PNL_GOLD, (uchar)(90 - i * 14)));

   int x0 = ox + 14, y = oy + 12, contentW = PNL_W - 28;

   PnlTxtB(x0, y, InpPanelName, PNL_GOLD, 14); y += 19;
   // v52.93: EA_VERSION grows a little every fix pass (each one appends a
   // new suffix) - not truncation-safe before, so this line was on a slow
   // collision course with the panel edge purely from version-string
   // creep, independent of any market data.
   PnlTxtBFit(x0, y, "[ " + EA_VERSION + " ]  " + InpOwnerName, PNL_LABEL, 10, contentW); y += 15;
   PnlTxtB(x0, y, "Engine: H1-CONFIRMED CUTLOSS", PNL_EMERALD, 10); y += 17;
   PnlRule(x0, y, contentW); y += 10;

   bool withH4 = (g_scalpMasterDir == g_masterDir);
   string modeTxt = g_scalpMasterDir == "WAIT" ? "Mode: WAIT" : (withH4 ? "Mode: WITH H4" : "*** MODE: AGAINST H4 ***");
   color modeClr  = g_scalpMasterDir == "WAIT" ? PNL_LABEL : (withH4 ? PNL_EMERALD : PNL_ROSE);
   PnlStatusDot(x0 + 3, y + 6, modeClr);
   PnlTxtB(x0 + 13, y, modeTxt, modeClr, 12); y += 19;
   PnlTxtB(x0, y, StringFormat("%s  >  %s  >  %s", EnumToString(InpMasterTF), EnumToString(InpScalpMasterTF), EnumToString(InpScalpEntryTF)), PNL_WHITE, 11); y += 17;
   PnlRow(x0, y, contentW, "H4  (Master)",  g_masterDir, DirColor(g_masterDir)); y += 16;
   PnlRow(x0, y, contentW, "Firing", g_m5FiringEnabled ? "ON" : "PAUSED", g_m5FiringEnabled ? PNL_EMERALD : PNL_LABEL); y += 16;
   PnlRow(x0, y, contentW, "M30 (Cascade)", g_scalpMasterDir, DirColor(g_scalpMasterDir)); y += 16;
   // v52.6: renamed from "M5 (Entry)" - Dadang: "kalo emang ini tidak entri
   // jangan ada kata entri di sana" - this row only ever showed M5's own CMP
   // DIRECTION (a role label, like H4's "Master"/M30's "Cascade" above it),
   // never whether a trade actually fired - that's "Firing"+"CMP Status"
   // below. The word "Entry" here was misleadingly implying action.
   PnlRow(x0, y, contentW, "M5  (CMP)",     g_scalpEntryDir,  DirColor(g_scalpEntryDir));  y += 16;

   // v52.96 - switched to the LiveMomentum* trio (candle-open-anchored,
   // display-only) - MomentumBreakoutText()/MomentumBookmapText()/
   // MomentumFootprintText() (CMP-anchored) still exist untouched, still
   // used by CheckMomentumEntryTrigger() via MomentumRatio() for real entries.
   color momClr;
   string momTxt = LiveMomentumPriceText(momClr);
   PnlRow(x0, y, contentW, "Momentum (M5)", momTxt, momClr); y += 16;

   color momBmClr;
   string momBmTxt = LiveMomentumBookmapText(momBmClr);
   PnlRow(x0, y, contentW, "Momentum M5 Bookmap", momBmTxt, momBmClr); y += 16;

   color momFpClr;
   string momFpTxt = LiveMomentumFootprintText(momFpClr);
   PnlRow(x0, y, contentW, "Momentum M5 Footprint", momFpTxt, momFpClr); y += 16;

   color fpM1Clr;
   string fpM1Txt = FootprintM1Text(fpM1Clr);
   PnlRow(x0, y, contentW, "Footprint (M1)", fpM1Txt, fpM1Clr); y += 16;

   string chainSigTxt; color chainSigClr;
   if(g_chainSigLayer > 0) { chainSigTxt = StringFormat("%s #%d (aktif)", g_chainSigMasterDir, g_chainSigLayer); chainSigClr = DirColor(g_chainSigMasterDir); }
   else                    { chainSigTxt = "menunggu breakout searah master"; chainSigClr = PNL_LABEL; }
   PnlRow(x0, y, contentW, "Chain Signal", chainSigTxt, chainSigClr); y += 16;

   color cvdDivClr;
   string cvdDivTxt = CvdDivergenceText(cvdDivClr);
   PnlRow(x0, y, contentW, "CVD Divergence", cvdDivTxt, cvdDivClr); y += 16;

   color ivbClr;
   string ivbTxt = IvbText(ivbClr);
   PnlRow(x0, y, contentW, "IVB (30min)", ivbTxt, ivbClr); y += 16;

   color dpfClr;
   string dpfTxt = DailyProfileFramingText(dpfClr);
   PnlRow(x0, y, contentW, "Daily Profile", dpfTxt, dpfClr); y += 16;

   color volNodeClr;
   string volNodeTxt = VolumeNodeText(volNodeClr);
   PnlRow(x0, y, contentW, "Volume Node", volNodeTxt, volNodeClr); y += 16;

   color reloadClr;
   string reloadTxt = ReloadLevelText(reloadClr);
   PnlRow(x0, y, contentW, "Reload Level", reloadTxt, reloadClr); y += 16;

   color statusClr = (g_cmpStatus == "CF") ? PNL_EMERALD : ((g_cmpStatus == "VR") ? PNL_GOLD : PNL_LABEL);
   PnlRow(x0, y, contentW, "CMP Status", g_cmpStatus, statusClr); y += 18;

   // v52.16: Dadang - "di panel harus ada tulisan yang menyatakan sydeway
   // atau trending bro karena ini penting baget bagi gw trader breakout" -
   // this reads straight off IsRegimeTrending() (v52.15, same formula the
   // web dashboard's Market Regime card and BookmapLocationOk() both use -
   // one definition, three consumers). TRENDING=emerald (breakout territory
   // - what Dadang's actually looking for), SIDEWAYS=amber (chop - a
   // breakout attempt here is exactly the trap volume-profile practice
   // warns about, see v52.15 notes).
   // v52.17: Dadang - "itu trending sell atau trending buy bro" - TRENDING
   // by definition means H4/M30/M5 all agree (that's the 100%-alignment
   // check inside IsRegimeTrending()), so the direction is just whichever
   // one they all agree on - g_masterDir. Label now says which.
   bool isTrending = IsRegimeTrending();
   string regimeTxt = isTrending ? ("TRENDING " + g_masterDir) : "SIDEWAYS";
   PnlRow(x0, y, contentW, "Regime", regimeTxt,
          isTrending ? PNL_EMERALD : C'251,191,36'); y += 18;

   // v52.48: candle-close countdown per TF - Dadang: "biar tau nunggunya
   // tinggal berapa lama". Uses the CURRENT (still-forming) bar's own open
   // time + that TF's period length, counted down against server time.

   PnlRule(x0, y, contentW); y += 10;

   // v52.51: wall-summary rows (Bid/Ask Wall nearest, Imbalance, wall
   // counts/lots) removed - Dadang: "toh gw banyak liat chart daripada
   // panel dan posisi wall nya di chart" (wall positions are already drawn
   // directly on the chart, this table was just duplicating that). Bal/Equity
   // kept per the earlier v41 instruction to keep it.
   PnlRow(x0, y, contentW, "Bal / Equity", StringFormat("%.2f / %.2f", AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY)), PNL_WHITE); y += 18;
   PnlRule(x0, y, contentW); y += 10;

   if(InpShowBookmapPanel)
   {
      if(g_bookmapOnline)
      {
         PnlStatusDot(x0 + 3, y + 5, PNL_GOLD);
         PnlTxtB(x0 + 13, y, "BOOKMAP  ·  LIVE", PNL_GOLD, 11); y += 18;

         // v52.6: the 5-step read as an actual NARRATIVE (not scattered
         // numbers the reader has to piece together themselves) - Dadang:
         // "dari 5 urutan itu bisa gak kalo masukin ke ea dan web gw sebagai
         // narasi tapi di ea dia entri beneran". Verdict is g_bmNarrVerdict,
         // which comes straight from BookmapTriggerDirection() - the exact
         // function that fires real Bookmap-trigger entries (CheckBookmapTrigger()) -
         // so this line can never say "BUY SETUP" without a real entry being
         // eligible to fire on the same tick.
         // v52.7: Dadang - "jadi terlalu panjang ke bawah bro sehingga pas gw
         // live tiktok gak kebaca" - collapsed from 6 lines (verdict + 5
         // separate) down to 2 (verdict + 1 packed line), same info.
         color bmVerdictClr = (StringFind(g_bmNarrVerdict, "BUY") >= 0)  ? PNL_EMERALD
                             : (StringFind(g_bmNarrVerdict, "SELL") >= 0) ? PNL_ROSE : PNL_LABEL;
         PnlRow(x0, y, contentW, "Bacaan Bookmap", g_bmNarrVerdict, bmVerdictClr); y += 15;
         string bmLine = StringFormat("W:%s C:%s A:%s I:%s L:%s",
                                       g_bmNarrWall, g_bmNarrCvd, g_bmNarrAbsorb, g_bmNarrIceberg, g_bmNarrLocation);
         PnlTxt(x0, y, bmLine, PNL_LABEL, 8); y += 14;
         PnlRule(x0, y, contentW); y += 10;

         PnlRow(x0, y, contentW, "CVD", StringFormat("%+.1f", g_bookmapCvd), g_bookmapCvd >= 0 ? PNL_EMERALD : PNL_ROSE); y += 16;

         color pulseClr = (g_bookmapAbsorption != "NONE") ? C'251,191,36' : PNL_LABEL;
         PnlRow(x0, y, contentW, "Pulse / Absorb", StringFormat("%.1f%%  %s", g_bookmapPulsePct, g_bookmapAbsorption), pulseClr); y += 18;

         // v38/v39: Price Pressure gauge - remap buyer_aggression_pct
         // (0..100) back to Bookmap's own -100..+100 "Price Change" scale
         // (same formula as sultan/logic.js's updatePulseGauge()), a real
         // smooth gradient semicircle (ring of small filled circles
         // lerping red->gray->green) with a needle, not a flat 3-segment bar.
         // v52.62: shrunk (gy offset 50->34, gr 48->32, needle 40->28) -
         // this gauge alone was eating 128px, the single biggest chunk of
         // the whole panel, and kept pushing the footer/last rows past
         // shorter MT5 windows ("PANEL MALAH KEPOTONG TERLLU KEBAWAH" -
         // recurring complaint even after 2 earlier trims elsewhere).
         double pricePct = MathMax(-100.0, MathMin(100.0, (g_bookmapPulsePct - 50.0) * 2.0));
         int gx = x0 + contentW / 2, gy = y + 34, gr = 32;
         for(double a = 180.0; a <= 360.0; a += 2.0)
         {
            double rad = a * M_PI / 180.0;
            int px2 = gx + (int)MathRound(gr * MathCos(rad));
            int py2 = gy + (int)MathRound(gr * MathSin(rad));
            double t = (a - 180.0) / 180.0;
            color c = (t < 0.5)
                        ? PnlLerp(150, 45, 60,  70, 70, 78,  t / 0.5)
                        : PnlLerp(70, 70, 78,  40, 140, 100, (t - 0.5) / 0.5);
            g_panelCanvas.FillCircle(px2, py2, 3, ColorToARGB(c, 235));
         }
         double needleAngle = 180.0 + ((pricePct + 100.0) / 200.0) * 180.0;
         double nrad = needleAngle * M_PI / 180.0;
         int tipx = gx + (int)MathRound(28 * MathCos(nrad));
         int tipy = gy + (int)MathRound(28 * MathSin(nrad));
         double ndx = tipx - gx, ndy = tipy - gy, nlen = MathSqrt(ndx * ndx + ndy * ndy);
         double nx = -ndy / nlen, ny = ndx / nlen;
         uint needleClr = ColorToARGB(PNL_WHITE, 255);
         g_panelCanvas.Line(gx, gy, tipx, tipy, needleClr);
         g_panelCanvas.Line((int)(gx + nx), (int)(gy + ny), (int)(tipx + nx), (int)(tipy + ny), needleClr);
         g_panelCanvas.Line((int)(gx - nx), (int)(gy - ny), (int)(tipx - nx), (int)(tipy - ny), needleClr);
         g_panelCanvas.FillCircle(gx, gy, 4, needleClr);

         color pressClr = (pricePct > 15.0) ? PNL_EMERALD : (pricePct < -15.0) ? PNL_ROSE : PNL_LABEL;
         PnlTxtB(x0, gy + gr + 8, "Price down", PNL_LABEL, 9);
         PnlTxtB(x0 + contentW - 56, gy + gr + 8, "Price up", PNL_LABEL, 9);
         PnlTxtB(gx - 24, gy + gr + 5, StringFormat("%+.0f%%", pricePct), pressClr, 14);
         y = gy + gr + 22;
         PnlRule(x0, y, contentW); y += 10;

         // v53.11: Dadang, screenshot of this whole block (Vol Ratio/POC/
         // Value Area/VA Bias/VA Retest/Fusion H1/H4/Barrier) - "area ini
         // sebenernya gak begitu penting gw juga gak liat soalnya kalo
         // sedang trading... buang aja karena terlalu panjang poc va
         // barrier gw bisa liat di chart". All 7 rows removed - POC/VAH/
         // VAL/Barrier already draw directly on the chart itself
         // (UpdatePocLine/UpdateValueAreaLines/barrier markers), so the
         // panel copy was pure duplication he never actually read. bmOffset
         // itself stays (still used below by the Iceberg rows).
         double bmOffset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;

         if(InpUseMomentumEntryTrigger)   // v52.71
         {
            string meTxt; color meClr;
            if(g_momEntryTicket != 0) { meTxt = "IN POSITION (tunggu M5 flip)"; meClr = PNL_EMERALD; }
            else                      { meTxt = "menunggu breakout M5 baru"; meClr = PNL_LABEL; }
            PnlRow(x0, y, contentW, "Momentum Entry", meTxt, meClr); y += 16;
         }

         // v33: strongest iceberg candidate (either side) - informational.
         // v52.75: append reload count (0=BID, 1=ASK slot in g_iceReloadCount).
         string iceTxt; color iceClr;
         if(g_bookmapBidIcePx > 0 && g_bookmapBidIceRatio >= g_bookmapAskIceRatio)
         {
            string bidReloadTxt = (g_iceReloadCount[0] > 0) ? StringFormat(" reload x%d", g_iceReloadCount[0]) : "";
            iceTxt = StringFormat("BID @ %.2f (%.1fx)%s", g_bookmapBidIcePx + bmOffset, g_bookmapBidIceRatio, bidReloadTxt);
            iceClr = clrMagenta;
         }
         else if(g_bookmapAskIcePx > 0)
         {
            string askReloadTxt = (g_iceReloadCount[1] > 0) ? StringFormat(" reload x%d", g_iceReloadCount[1]) : "";
            iceTxt = StringFormat("ASK @ %.2f (%.1fx)%s", g_bookmapAskIcePx + bmOffset, g_bookmapAskIceRatio, askReloadTxt);
            iceClr = clrMagenta;
         }
         else { iceTxt = "none"; iceClr = PNL_LABEL; }
         PnlRow(x0, y, contentW, "Iceberg", iceTxt, iceClr); y += 16;

         // v52.26/v52.69: wall SWEEP + reversal - Dadang: "ide gila lagi
         // bro?" -> stop-hunt/liquidity-grab detection (see
         // UpdateSweepRecord()'s comment for the full doctrine). v52.69:
         // shown for as long as g_sweepRecActive - Dadang: "dia ilang ketika
         // di jebol bro selama belum kejebol masih tercatat di panel" -
         // stays until the level is genuinely broken by a candle CLOSE, NOT
         // a time limit (was a 20-min cutoff before v52.69, arbitrary).
         string sweepTxt; color sweepClr;
         if(!g_sweepRecActive)
         {
            sweepTxt = "-"; sweepClr = PNL_LABEL;
         }
         else
         {
            // v52.27: fixed cyan/blue regardless of side/status (Dadang:
            // "garis wal lama sudah ijo dan merah, gimana mata gw bedain
            // dengan cepat") - same "sweep = blue, walls = green/red" split
            // as UpdateSweepMarker()'s chart arrow, so the panel row and the
            // chart marker teach the same color association instead of two
            // different ones.
            long   recAgeSec = (long)(TimeCurrent() - g_sweepRecFirstSeen);
            // v52.68: harga levelnya ditambahin - Dadang: "masalahnya price
            // nya di berapa tidak di catat sehingga gw gak tau kejebol atau
            // gak nanti" - dulu cuma sisi/size/status/umur, gak ada angka
            // harga sama sekali.
            // v52.70: "REVERSAL"/"lalu" dibuang - Dadang: "keluar gari panel
            // bro bikin jelek" (kepanjangan, tumpah keluar kolom value).
            // "REVERSAL" udah redundan sejak v52.69 - baris ini CUMA pernah
            // muncul buat event REVERSAL_CONFIRMED (satu2nya yang di-persist),
            // jadi nulis ulang kata itu gak nambah info baru.
            sweepTxt = StringFormat("%s %.0fL @%.2f (%s)", g_sweepRecSide, g_sweepRecSize, g_sweepRecPriceMt5, TimeAgoText(recAgeSec));
            sweepClr = clrDeepSkyBlue;
         }
         // v52.74 - Mega Sweep: 3+ sweeps same side in 5 min (staircase
         // pattern) - swaps the ROW LABEL itself (not just the value) so
         // it's impossible to miss scanning down the panel, gold to match
         // the "attention" color used elsewhere (Barrier row). Web version
         // built the same night in logic.js - Dadang: "setiap kerja duluin
         // mt5 nya baru ke web".
         string sweepLabel = "Wall Sweep";
         if(g_megaSweepActive)
         {
            sweepLabel = StringFormat("MEGA SWEEP (%dx)", g_megaSweepCount);
            sweepClr = clrGold;
         }
         PnlRow(x0, y, contentW, sweepLabel, sweepTxt, sweepClr); y += 18;
         PnlRule(x0, y, contentW); y += 12;

         // v32: BIAS BUY/SELL/SIDEWAYS - Dadang: "tambah tulisan bias buy
         // atau sell dan sideways agar lebih mantap" - see ComputeBias().
         // v42: macro row - 6E (Euro FX) as a dollar proxy. Informational
         // only, never gates an entry: it answers "is the dollar with me or
         // against me" for the direction the cascade is already working.
         // 6E up = EUR strong = USD weak = tailwind for gold.
         // v43: USD fundamental block. Two rows, both straight from MT5:
         // the dollar's own bias (via EURUSD's CMP) and the next high-impact
         // USD release. The verdict compares that bias against whatever
         // direction the cascade is working - still informational only.
         if(g_usdBias != "")
         {
            // v43.2: Dadang - "vs nya ke gold aja, jangan ke yang lain. USD
            // lemah gold naik, USD kuat gold turun, gitu aja." So this states
            // the dollar's implication for gold directly instead of grading it
            // against whatever direction the cascade happens to be working -
            // the relationship is a property of the market, not of the setup.
            // v52.62: merged with "Efek ke Gold" into 1 row (was 2) - part of
            // the same panel-height trim as the gauge shrink above.
            string goldEffect = (g_usdBias == "WEAK")   ? "NAIK"
                              : (g_usdBias == "STRONG") ? "TURUN" : "-";
            color  effClr     = (g_usdBias == "WEAK")   ? PNL_EMERALD
                              : (g_usdBias == "STRONG") ? PNL_ROSE : PNL_LABEL;
            PnlRow(x0, y, contentW, "USD (" + g_usdSymbol + ")",
                   StringFormat("%s %s -> %s", g_eurDir, g_usdBias, goldEffect), effClr); y += 16;
         }
         else
         {
            PnlRow(x0, y, contentW, "USD (" + g_usdSymbol + ")",
                   g_eurDir == "STALE" ? "data basi" : "-", PNL_LABEL); y += 16;
         }

         // Next high-impact USD release - the row that says "jangan entry
         // dulu" better than any indicator can.
         if(g_usdNextMins >= 0)
         {
            string cd = (g_usdNextMins >= 60)
                          ? StringFormat("%dj%dm", g_usdNextMins / 60, g_usdNextMins % 60)
                          : StringFormat("%dm", g_usdNextMins);
            string evName = g_usdNextEvent;
            if(StringLen(evName) > 16) evName = StringSubstr(evName, 0, 16);
            // Inside 30 minutes of a high-impact release, flag it red.
            color newsClr = (g_usdNextMins <= 30) ? PNL_ROSE
                            : (g_usdNextMins <= 120) ? C'251,191,36' : PNL_LABEL;
            PnlRow(x0, y, contentW, "USD News", StringFormat("%s  %s", cd, evName), newsClr); y += 18;
         }
         else
         {
            PnlRow(x0, y, contentW, "USD News", "-", PNL_LABEL); y += 18;
         }
         PnlRule(x0, y, contentW); y += 12;

         // v44: conviction block replaces the bare BIAS line - same headline
         // idea, but it now says how much of the collected evidence actually
         // backs the setup, and names what is arguing against it.
         color convClr = (g_convGrade == "SIAP")      ? PNL_EMERALD
                       : (g_convGrade == "HATI-HATI") ? C'251,191,36'
                       : (g_convGrade == "TAHAN - NEWS" || g_convGrade == "TUNGGU") ? PNL_ROSE : PNL_LABEL;
         if(g_convDir == "BUY" || g_convDir == "SELL")
         {
            // Chain depth leads (that IS the system), flow confirms on top.
            // v52.93: worst case ("SELL  RANTAI 6/6  ·  TAHAN - NEWS") ran
            // close enough to the old 282px budget to be a real risk once
            // any grade word grew - same TextWidth() safety net as
            // everywhere else on the panel now.
            PnlTxtBFit(x0, y, StringFormat("%s  RANTAI %d/6  ·  %s", g_convDir,
                    g_chainLen, g_convGrade), convClr, 13, contentW); y += 17;
            PnlTxtB(x0, y, g_convMode + (g_flowMax > 0 ? StringFormat("   flow %d/%d", g_flowScore, g_flowMax) : ""),
                    PNL_LABEL, 10); y += 15;

            // v52.87 tried capping this block's line count against the
            // fixed footer, but that zeroed it out entirely on a busy
            // snapshot ("ilang chain gw" - the "sudah:" line vanished).
            // v52.88 merged "lawan" reasons onto one compact line to need
            // less room. v52.91: the real fix - Dadang's screenshot showed
            // the footer's OWN rule line drawn straight through the RANTAI
            // header text, because the fixed footerY assumed less content
            // above it than a fully-loaded Bookmap-LIVE snapshot actually
            // draws. The footer below is now positioned dynamically off
            // the real cursor position instead of a fixed offset, so it
            // can never land on top of this block again - which means
            // this block no longer needs to self-limit against a fixed
            // boundary at all. Always draws both lines when present.
            string sudahLine = (g_chainDone != "") ? "sudah: " + g_chainDone : "";
            string lawanLine = "";
            if(g_convAgainst1 != "") lawanLine = g_convAgainst1;
            if(g_convAgainst2 != "") lawanLine += (lawanLine != "" ? " · " : "") + g_convAgainst2;
            if(g_convAgainst3 != "") lawanLine += (lawanLine != "" ? " · " : "") + g_convAgainst3;
            if(lawanLine != "") lawanLine = "lawan: " + lawanLine;

            // v52.92: -4px safety margin, same reasoning as PnlRow() - the
            // outline stroke bleeds a few px past the raw TextWidth().
            // Dadang caught the 3-reason merged "lawan" line running past
            // the right border ("keluar panel bro").
            int lawanMaxW = contentW - 4;
            g_panelCanvas.FontSet(PNL_FONT, 10, PNL_WEIGHT_BOLD);
            if(sudahLine != "")
            {
               while(StringLen(sudahLine) > 8 && g_panelCanvas.TextWidth(sudahLine) > lawanMaxW)
                  sudahLine = StringSubstr(sudahLine, 0, StringLen(sudahLine) - 2) + "…";
               PnlTxtB(x0, y, sudahLine, PNL_EMERALD, 10); y += 15;
            }
            if(lawanLine != "")
            {
               // Amber + outlined: these are the warnings, so they must not
               // be the faintest text on the panel - they were, at plain
               // 9px grey.
               while(StringLen(lawanLine) > 8 && g_panelCanvas.TextWidth(lawanLine) > lawanMaxW)
                  lawanLine = StringSubstr(lawanLine, 0, StringLen(lawanLine) - 2) + "…";
               PnlTxtB(x0, y, lawanLine, C'251,191,36', 10); y += 15;
            }
         }
         else
         {
            PnlTxtB(x0, y, "NO SETUP — M30 WAIT", PNL_LABEL, 13);
         }
      }
      else
      {
         PnlStatusDot(x0 + 3, y + 5, clrGray);
         PnlTxtB(x0 + 13, y, "BOOKMAP: OFFLINE", clrGray, 11); y += 18;
         PnlTxtB(x0, y, "(gak jalan / backtest)", clrGray, 10); y += 20;
         PnlTxtB(x0, y, "BIAS — N/A", clrGray, 11);
      }
   }

   // v41.1: Dadang - "ini ga terlalu lebar, atau lo beri label chain
   // reaction system by dadang wahyuono yang keren". There was dead space
   // between the BIAS line and the panel's bottom edge. Rather than just
   // shrinking the panel, this fills it with a signature footer - and it's
   // pinned to the bottom edge (measured back from PNL_H) instead of
   // flowing after y, so it stays put whether Bookmap is live or offline
   // (those two branches end at different heights).
   // v44.1: the system name moved to the panel HEADER (InpPanelName is now
   // "CHAIN REACTION SYSTEM" - Dadang: "sistem gw dari awal namanya chain
   // reaction system"), so the footer no longer repeats it; just the byline.
   // v52.91: pinning it to a FIXED offset assumed the content above always
   // fit within PNL_H - on a fully-loaded Bookmap-LIVE snapshot (every
   // optional row on at once) it doesn't, and Dadang caught a screenshot
   // of this footer's own rule line drawn straight through the RANTAI
   // chain text instead of below it. Now takes whichever is LOWER: the
   // usual fixed slot (unchanged in the normal case), or just past
   // wherever content actually ended (busy case) - so the footer can
   // slide down but can never again land on top of real content.
   // v53.10: Dadang - "kalo lo jadikan 1 di panel aja gimana bro di panel
   // original". S&D Price Map summary moved INTO this panel (was a
   // separate floating panel that kept losing legibility to roadmap
   // HLINEs crossing behind it, no working background of its own). Full
   // roadmap detail (Supply1-3/Demand1-3, exact ranges) stays on the
   // chart itself (roadmap HLINEs + zone boxes) - this is deliberately
   // just the headline + one line of support, not a repeat of everything.
   if(InpShowZonesOnChart)
   {
      PnlRule(x0, y, contentW); y += 10;
      PnlTxtB(x0, y, "S&D PRICE MAP", PNL_GOLD, 11); y += 17;

      color focusClr; string focusTxt = FocusText(focusClr);
      PnlTxtB(x0, y, focusTxt, focusClr, 13); y += 17;

      string whyLine = ReasonText(g_sdmReason);
      g_panelCanvas.FontSet(PNL_FONT, 9, PNL_WEIGHT_NORMAL);
      while(StringLen(whyLine) > 8 && g_panelCanvas.TextWidth(whyLine) > contentW - 4)
         whyLine = StringSubstr(whyLine, 0, StringLen(whyLine) - 2) + "…";
      PnlTxt(x0, y, whyLine, PNL_LABEL, 9); y += 15;

      PnlRow(x0, y, contentW, "Posisi", LocationText(g_sdmLocation), PNL_LABEL); y += 16;
      color bsClr2 = (g_sdmBuyerPct >= g_sdmSellerPct) ? PNL_EMERALD : PNL_ROSE;
      PnlRow(x0, y, contentW, "Buyer/Seller", StringFormat("%.0f%% / %.0f%%", g_sdmBuyerPct, g_sdmSellerPct), bsClr2); y += 16;
      // v53.16: Dadang - "ini terlalu panjang jadinya bro yang bawah hapus
      // aja itu kan sudah ada di chart" - the S1-S3/D1-D3 range list added
      // in v53.14 was genuinely redundant once DrawZoneBox() kept ranges IN
      // the on-chart labels (only lot/score/diuji/serap got stripped, not
      // the range itself) - removed again, panel stays FOKUS/Posisi/
      // Buyer-Seller only. The web dashboard keeps its own full list -
      // that surface has no on-chart equivalent to duplicate.
      if(InpEnableSDBreakEngine)
      {
         // v53.18 TAHAP 20-25: ONE line, not the full multi-field block his
         // examples showed - same lesson as the roadmap-list trim above,
         // kept deliberately compact from the start this time.
         g_panelCanvas.FontSet(PNL_FONT, 9, PNL_WEIGHT_NORMAL);
         string brkTxt = SDBreakStatusText();
         while(StringLen(brkTxt) > 8 && g_panelCanvas.TextWidth(brkTxt) > contentW - PNL_VALUE_COL)
            brkTxt = StringSubstr(brkTxt, 0, StringLen(brkTxt) - 2) + "…";
         PnlRow(x0, y, contentW, "Break Status", brkTxt, SDBreakStatusColor()); y += 16;
      }
   }

   int footerY = (int)MathMax(oy + PNL_H - 34, y + 8);
   PnlRule(x0, footerY, contentW);
   PnlTxtB(x0 + contentW / 2, footerY + 12, "by " + InpOwnerName, PNL_LABEL, 10, TA_CENTER | TA_TOP);

   g_panelCanvas.Update(true);
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

//--- reads buffer 5 (live sup) or 6 (live res) - these keep updating on
//--- EVERY new V/A-shape, unlike buffer 4 which freezes at the last flip.
double ReadLiveLevel(int handle, int bufferIndex)
{
   double buf[1];
   if(CopyBuffer(handle, bufferIndex, 0, 1, buf) <= 0) return 0.0;
   return buf[0];
}

//--- v52.60: BARRIER QUEUE plumbing. QueuePush appends the level a TF is
//--- LEAVING behind on every flip (instead of overwriting a single slot);
//--- QueuePrune permanently drops an entry the instant that TF's own candle
//--- CLOSE genuinely crosses it (never re-added - "sekali jebol, tetap
//--- jebol"). Cap MAX_BARRIER_QUEUE keeps this bounded even through a very
//--- long chop.
void QueuePush(BarrierEntry &q[], string dir, double level, string tag = "")
{
   if(dir == "" || level <= 0) return;
   int n = ArraySize(q);
   if(n > 0 && q[n-1].dir == dir && MathAbs(q[n-1].level - level) < 0.01) return;   // paranoia guard, shouldn't fire given flip-gating
   if(n >= MAX_BARRIER_QUEUE)
   {
      for(int i = 0; i < n - 1; i++) q[i] = q[i+1];   // drop oldest, shift left
      q[n-1].dir = dir; q[n-1].level = level;
   }
   else
   {
      ArrayResize(q, n + 1);
      q[n].dir = dir; q[n].level = level;
   }
   if(tag != "")   // v52.64: diagnostic - Dadang: "M30 BO BUY... mana M30 nya" - trace push/prune to Experts log to see what actually happens instead of guessing
      Print("BARRIER PUSH [", tag, "]: ", dir, " @ ", DoubleToString(level, 2), " (queue now ", ArraySize(q), ")");
}
void QueuePrune(BarrierEntry &q[], ENUM_TIMEFRAMES tf, string tag = "")
{
   int n = ArraySize(q);
   if(n == 0) return;
   double c = iClose(_Symbol, tf, 1);
   double tol = InpBarrierVetoZoneUsd;
   int w = 0;
   for(int i = 0; i < n; i++)
   {
      bool broken = (q[i].dir == "BUY") ? (c < q[i].level - tol) : (c > q[i].level + tol);
      if(!broken) { if(w != i) q[w] = q[i]; w++; }
      else if(tag != "")   // v52.64: diagnostic
         Print("BARRIER PRUNE [", tag, "]: ", q[i].dir, " @ ", DoubleToString(q[i].level, 2),
               " jebol (close=", DoubleToString(c, 2), ", tol=", DoubleToString(tol, 2), ")");
   }
   if(w != n) ArrayResize(q, w);
}
//--- true if `q` still has an unbroken entry of `dir` - queue is kept
//--- pre-pruned (see QueuePrune, called every tick), so "present in queue"
//--- already means "unbroken". Reports the nearest one (closest to current
//--- price - lowest SELL barrier from below, highest BUY barrier from
//--- above) plus how many total remain.
bool QueueHasDir(BarrierEntry &q[], string dir, string &reasonOut, string tfTag)
{
   int n = ArraySize(q);
   int count = 0; double nearest = 0; bool have = false;
   for(int i = 0; i < n; i++)
   {
      if(q[i].dir != dir) continue;
      count++;
      if(!have || (dir == "SELL" ? q[i].level < nearest : q[i].level > nearest)) { nearest = q[i].level; have = true; }
   }
   if(count == 0) return false;
   reasonOut = StringFormat("%s barrier queue: %s @ %.2f (sisa %d barrier) belum jebol", tfTag, dir, nearest, count);
   return true;
}
//--- v52.61: nearest UNBROKEN barrier considering BOTH a TF's own queue AND
//--- its immediate PARENT TF's queue - Dadang: "cmp buy m5 mencari barrier
//--- sell m5 dan m15 ... cmp buy m30 mencari barrier sell m30 dan h1 ...
//--- mereka biasanya sejajar atau cuman mepet2 jaraknya" (a TF's own barrier
//--- and its parent's tend to sit close together in price, so the practical
//--- "nearest wall" question spans both). Pairs: M5-M15, M15-M30, M30-H1,
//--- H1-H4, H4-D1. Display-only simplification (BarrierVetoes() keeps
//--- checking the FULL H4/H1/M30 queues, unrelated to this).
bool NearestBarrierInPair(BarrierEntry &selfQ[], BarrierEntry &parentQ[], string &dirOut, double &levelOut)
{
   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool have = false; double bestDist = 0;
   int ns = ArraySize(selfQ), np = ArraySize(parentQ);
   for(int i = 0; i < ns; i++)
   {
      double d = MathAbs(selfQ[i].level - curPrice);
      if(!have || d < bestDist) { bestDist = d; dirOut = selfQ[i].dir; levelOut = selfQ[i].level; have = true; }
   }
   for(int i = 0; i < np; i++)
   {
      double d = MathAbs(parentQ[i].level - curPrice);
      if(!have || d < bestDist) { bestDist = d; dirOut = parentQ[i].dir; levelOut = parentQ[i].level; have = true; }
   }
   return have;
}
//--- v52.60: serialize a barrier queue as a JSON array of {dir,level} - for
//--- the SULTAN web export.
string JsonBarrierQueue(BarrierEntry &q[])
{
   int n = ArraySize(q);
   string out = "[";
   for(int i = 0; i < n; i++)
      out += StringFormat("%s{\"dir\":\"%s\",\"level\":%.2f}", i > 0 ? "," : "", q[i].dir, q[i].level);
   out += "]";
   return out;
}

//--- v52.56/v52.60: bootstrap the FULL barrier queue from INDICATOR HISTORY
//--- at OnInit, so Barrier Veto isn't blind right after every reload -
//--- Dadang caught this live: "INI LAH KENAPA GW LARANG SELL DI BARRIER CMP
//--- OLD BUY H4 MESKI SMP H4 SELL" while the panel sat on "-" the whole
//--- time. Root cause: tracking only ever learned a barrier from a flip
//--- that happened WHILE the EA is attached - every reload wiped it blank.
//--- Fix: scan buffer 3 (change-time, constant across all bars in one
//--- regime) backward from bar 0, collecting EVERY past flip transition
//--- (not just the first one) up to MAX_BARRIER_QUEUE deep - that rebuilds
//--- the whole staircase, not just its most recent step.
//--- v52.63: returns bool now - Dadang: "barrier lama kan sudah ada sejak
//--- lama juga harusnya kan kebaca" (fair pushback after v52.62 showed
//--- empty queues even where a long-standing barrier should exist). Root
//--- cause: BarsCalculated(handle)<5 guard was checked ONCE at OnInit only -
//--- if a TF's indicator (esp. H4/D1, more history to chew through) hadn't
//--- finished its initial calculation pass by that exact moment, bootstrap
//--- silently no-op'd FOREVER (old comment even said "live tracking will
//--- catch it eventually" - false, live tracking only catches a flip that
//--- happens WHILE attached, and H4/D1 can go a long time between flips).
//--- The return value lets TryBootstrapAllBarriers() retry every tick until
//--- every TF actually succeeds, instead of gambling on one shot at OnInit.
bool BootstrapBarrierFromHistory(int handle, ENUM_TIMEFRAMES tf, string &lastDir, double &lastLevel, BarrierEntry &queue[])
{
   if(handle == INVALID_HANDLE) return false;
   if(BarsCalculated(handle) < 5) return false;   // indicator not warmed up yet - caller retries

   int    n = 2000;   // deep scan - want the whole recent staircase, not just 1 step back
   double ctBuf[], dirBuf[], lvlBuf[];
   if(CopyBuffer(handle, 3, 0, n, ctBuf) <= 0) return false;
   if(CopyBuffer(handle, 2, 0, n, dirBuf) <= 0) return false;
   if(CopyBuffer(handle, 4, 0, n, lvlBuf) <= 0) return false;
   int have = MathMin(MathMin(ArraySize(ctBuf), ArraySize(dirBuf)), ArraySize(lvlBuf));
   if(have < 2) return false;

   BarrierEntry found[];   // discovered newest-first while walking backward
   double prevChangeTime = ctBuf[0];
   for(int i = 1; i < have && ArraySize(found) < MAX_BARRIER_QUEUE; i++)
   {
      if(ctBuf[i] > 0 && ctBuf[i] != prevChangeTime)
      {
         string dir = (dirBuf[i] > 0.5) ? "BUY" : (dirBuf[i] < -0.5) ? "SELL" : "";
         if(dir != "")
         {
            int fn = ArraySize(found);
            ArrayResize(found, fn + 1);
            found[fn].dir = dir;
            found[fn].level = lvlBuf[i];
         }
         prevChangeTime = ctBuf[i];
      }
   }
   int cnt = ArraySize(found);
   ArrayResize(queue, cnt);
   for(int k = 0; k < cnt; k++) queue[k] = found[cnt - 1 - k];   // reverse -> oldest first, matches live-push order
   QueuePrune(queue, tf);   // some of these may have already been broken by price action since

   datetime ct;
   lastDir = ReadCMP(handle, ct);
   double curLevel = ReadLiveLevel(handle, 4);
   if(curLevel > 0) lastLevel = curLevel;
   return true;
}

//--- v52.63: retry wrapper - called from OnInit (first try) AND from every
//--- OnTick until it fully succeeds (indicators can still be warming up
//--- right after attach, especially H4/D1 with years of history to chew
//--- through). g_barrierBootstrapDone latches true only once ALL 6 tracked
//--- TFs report ready, so this stops costing anything once it's done; a
//--- 300-tick safety cap stops it from retrying forever if something is
//--- genuinely, permanently broken (handle invalid etc).
bool g_barrierBootstrapDone = false;
int  g_barrierBootstrapTries = 0;
void TryBootstrapAllBarriers()
{
   if(g_barrierBootstrapDone || g_barrierBootstrapTries >= 300) return;
   g_barrierBootstrapTries++;

   bool ok = true;
   ok = BootstrapBarrierFromHistory(g_hMaster,      InpMasterTF,      g_h4LastDir,        g_h4LastLevel,        g_h4Queue)  && ok;
   ok = BootstrapBarrierFromHistory(g_hH1,          PERIOD_H1,        g_h1BarrierLastDir, g_h1BarrierLastLevel, g_h1Queue)  && ok;
   ok = BootstrapBarrierFromHistory(g_hScalpMaster, InpScalpMasterTF, g_m30LastDir,       g_m30LastLevel,       g_m30Queue) && ok;
   ok = BootstrapBarrierFromHistory(g_hExportM15,   PERIOD_M15,       g_m15LastDir,       g_m15LastLevel,       g_m15Queue) && ok;
   ok = BootstrapBarrierFromHistory(g_hScalpEntry,  InpScalpEntryTF,  g_m5LastDir,        g_m5LastLevel,        g_m5Queue)  && ok;
   ok = BootstrapBarrierFromHistory(g_hExportD1,    PERIOD_D1,        g_d1LastDir,        g_d1LastLevel,        g_d1Queue)  && ok;

   if(ok)
   {
      g_barrierBootstrapDone = true;
      Print("Barrier bootstrap DONE (try #", g_barrierBootstrapTries, "): H4=", ArraySize(g_h4Queue),
            " H1=", ArraySize(g_h1Queue), " M30=", ArraySize(g_m30Queue), " M15=", ArraySize(g_m15Queue),
            " M5=", ArraySize(g_m5Queue), " D1=", ArraySize(g_d1Queue));
   }
}

//--- v52.47/v52.60: BARRIER QUEUE tracking - call once per OnTick for every
//--- tracked TF BEFORE any entry logic runs, so a flip that just happened
//--- this tick is already queued before TryOpen() checks it.
void UpdateBarrierTracking(int handle, ENUM_TIMEFRAMES tf, string &lastDir, double &lastLevel, BarrierEntry &queue[], string tag = "")
{
   if(handle == INVALID_HANDLE) return;
   datetime ct;
   string curDir = ReadCMP(handle, ct);
   if(curDir != "WAIT")
   {
      double curLevel = ReadLiveLevel(handle, 4);
      if(lastDir != "WAIT" && curDir != lastDir)
      {
         if(tag != "") Print("BARRIER FLIP [", tag, "]: ", lastDir, " -> ", curDir, " (old level was ", DoubleToString(lastLevel, 2), ")");
         QueuePush(queue, lastDir, lastLevel, tag);   // fresh flip - what we WERE tracking joins the queue
      }
      lastDir = curDir;
      if(curLevel > 0) lastLevel = curLevel;
   }
   QueuePrune(queue, tf, tag);   // every tick - self-clean as price closes beyond entries, permanently
}

//--- v52.65: just the TF NAMES, dropped price/dir - Dadang: "ini keluar
//--- kolom gw gak suka disitu keterangannya deket barier tf gitu aja" -
//--- v52.61's "AWAS M5 BUY@4354.98 | M15 BUY@..." overflowed the panel's
//--- value column badly with 2+ TFs active. Full price/dir per TF is still
//--- exactly what the chart markers show (DD_XXBarrierArrow tooltips too) -
//--- this row is now just a quick "which TFs to go check" pointer.
string BarrierWarningText(color &clrOut)
{
   string out = "";
   string dir; double lvl;
   if(NearestBarrierInPair(g_m5Queue,  g_m15Queue, dir, lvl)) out += (out == "" ? "" : ", ") + "M5";
   if(NearestBarrierInPair(g_m15Queue, g_m30Queue, dir, lvl)) out += (out == "" ? "" : ", ") + "M15";
   if(NearestBarrierInPair(g_m30Queue, g_h1Queue,  dir, lvl)) out += (out == "" ? "" : ", ") + "M30";
   if(NearestBarrierInPair(g_h1Queue,  g_h4Queue,  dir, lvl)) out += (out == "" ? "" : ", ") + "H1";
   if(NearestBarrierInPair(g_h4Queue,  g_d1Queue,  dir, lvl)) out += (out == "" ? "" : ", ") + "H4";

   if(out == "") { clrOut = PNL_LABEL; return "-"; }
   clrOut = C'251,191,36';
   return "DEKAT " + out;
}

//--- v52.47/v52.60: true if an entry in direction `buy` should be VETOED
//--- because ANY not-yet-broken "CMP lama" barrier of the opposite
//--- direction still sits in that TF's queue. Broken = that SAME TF's own
//--- last CLOSED candle has closed on the far side of the barrier (Dadang:
//--- "H4 harus CLOSE di bawah harga barrier CMP buy lama ini" - candle-close
//--- based, never a live tick, never just a wick) - enforced continuously
//--- by QueuePrune(), so any entry still present here is genuinely unbroken.
//--- Scope stays H4/H1/M30 only (the "minimal H4 harus jebol" doctrine) -
//--- M5/M15 queues are awareness-only, checked nowhere near TryOpen().
bool BarrierVetoes(bool buy, string &reasonOut)
{
   if(!InpUseBarrierVeto) return false;
   string neededOldDir = buy ? "SELL" : "BUY";   // an old SELL barrier blocks new BUY; an old BUY barrier blocks new SELL

   if(QueueHasDir(g_h4Queue, neededOldDir, reasonOut, "H4")) return true;
   if(QueueHasDir(g_h1Queue, neededOldDir, reasonOut, "H1")) return true;
   if(QueueHasDir(g_m30Queue, neededOldDir, reasonOut, "M30")) return true;
   return false;
}

// v52.72 - Dadang, abis cut-loss nyata: "entri ea sekarang kebalik tadi gw
// cut los sepertinya perlu lo upgrade tambah sweep jika sudah ada sweep
// kita cari pembalikan deh tidak maksa arah yang sama kecuali area sweep
// kejebol." g_sweepRecActive (v52.69) ONLY latches when the Bookmap bridge
// reports REVERSAL_CONFIRMED - by the time it's active, a level has already
// held and price already reclaimed past it, so entering the OPPOSITE
// direction (continuing into/through the swept zone) is exactly the setup
// that just got cut loss. Auto-releases the instant the level is genuinely
// broken - that's what already clears g_sweepRecActive (v52.69's own
// price-action cutoff), so "kecuali area sweep kejebol" needs no separate
// logic here, it falls out of the existing persistence design for free.
bool SweepReversalVeto(bool buy, string &reasonOut)
{
   if(!InpUseSweepReversalVeto) return false;
   if(!g_sweepRecActive) return false;
   // BID (support) sweep confirmed reversal -> expects price UP -> only BUY allowed
   // ASK (resistance) sweep confirmed reversal -> expects price DOWN -> only SELL allowed
   bool expectBuy = (g_sweepRecSide == "BID");
   if(buy != expectBuy)
   {
      reasonOut = StringFormat("Sweep %s @%.2f masih berlaku, cuma boleh %s",
                                g_sweepRecSide, g_sweepRecPriceMt5, expectBuy ? "BUY" : "SELL");
      return true;
   }
   return false;
}

//--- v52.48: "H4 close in 2h 15m" style countdown - Dadang: "biar tau
//--- nunggunya tinggal berapa lama". Current bar's own open time + that
//--- TF's period length, minus server TimeCurrent().
string CandleCountdownText(ENUM_TIMEFRAMES tf)
{
   datetime barOpen = iTime(_Symbol, tf, 0);
   if(barOpen == 0) return "-";
   int periodSec = PeriodSeconds(tf);
   long remain = (long)(barOpen + periodSec - TimeCurrent());
   if(remain < 0) remain = 0;
   int h = (int)(remain / 3600);
   int m = (int)((remain % 3600) / 60);
   int s = (int)(remain % 60);
   if(h > 0) return StringFormat("%dh %dm", h, m);
   if(m > 0) return StringFormat("%dm %ds", m, s);
   return StringFormat("%ds", s);
}

//--- v52.69: "how long ago" version (elapsed, not remaining) - used by the
//--- persistent sweep record so its age keeps counting up for as long as
//--- it stays unbroken, instead of just showing a raw seconds count.
string TimeAgoText(long elapsedSec)
{
   if(elapsedSec < 0) elapsedSec = 0;
   int h = (int)(elapsedSec / 3600);
   int m = (int)((elapsedSec % 3600) / 60);
   int s = (int)(elapsedSec % 60);
   if(h > 0) return StringFormat("%dh %dm", h, m);
   if(m > 0) return StringFormat("%dm %ds", m, s);
   return StringFormat("%ds", s);
}

//--- v52.57: raw seconds version for the SULTAN web export - JS can format/
//--- tick it down smoothly client-side instead of re-parsing a string.
int CandleCountdownSec(ENUM_TIMEFRAMES tf)
{
   datetime barOpen = iTime(_Symbol, tf, 0);
   if(barOpen == 0) return 0;
   long remain = (long)(barOpen + PeriodSeconds(tf) - TimeCurrent());
   return (int)MathMax(0, (double)remain);
}

//--- v52.61: back down to ONE marker per TF (was: one per queue entry,
//--- v52.58-v52.60) - Dadang, after confirming the native DD_CMP_Indicator
//--- arrows (green/red plot arrows, "ITU LAH BARRIER BRO") already ARE the
//--- visual staircase: "kalo perlu hanya cmp dan barrier terdekat aja tiap
//--- tf". So: keep the full queue for BarrierVetoes()'s "must clear ALL of
//--- them" logic, but the CHART/PANEL/WEB display now shows only the single
//--- NEAREST one per TF (self+parent pair, see NearestBarrierInPair).
void DrawOneBarrierMarker(string namePrefix, string tfTag, string dir, double level)
{
   string arrName = namePrefix + "Arrow", txtName = namePrefix + "Txt";
   color  clr = (dir == "BUY") ? PNL_EMERALD : PNL_ROSE;
   datetime t = TimeCurrent();
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(ObjectFind(0, arrName) < 0)
      ObjectCreate(0, arrName, OBJ_ARROW, 0, t, level);
   else
      ObjectMove(0, arrName, 0, t, level);
   ObjectSetInteger(0, arrName, OBJPROP_ARROWCODE, 241);
   ObjectSetInteger(0, arrName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, arrName, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, arrName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, arrName, OBJPROP_HIDDEN, true);
   ObjectSetString(0, arrName, OBJPROP_TOOLTIP, StringFormat("%s barrier terdekat: %s @ %.2f - belum jebol", tfTag, dir, level));

   // v52.66: Dadang - "tulisan apa mata gw gak bisa baca" - font 7 + only
   // 60pt clearance meant the label sat almost on top of the candle it was
   // marking, in whatever color (green/red) that candle's OWN body already
   // was - same hue on same hue, unreadable. Bigger font, ~2x more
   // clearance from the level, and a fixed gold/amber (matches the panel's
   // "Barrier" row accent) instead of green/red so it never blends into a
   // same-colored candle body - the ARROW still carries the direction color.
   double txtPx = level + (dir == "BUY" ? -130.0 : 130.0) * pt;
   if(ObjectFind(0, txtName) < 0)
      ObjectCreate(0, txtName, OBJ_TEXT, 0, t, txtPx);
   else
      ObjectMove(0, txtName, 0, t, txtPx);
   ObjectSetString(0, txtName, OBJPROP_TEXT, tfTag + " BARRIER");
   ObjectSetInteger(0, txtName, OBJPROP_COLOR, C'251,191,36');
   ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 9);
   ObjectSetString(0, txtName, OBJPROP_FONT, "Trebuchet MS Bold");
   ObjectSetInteger(0, txtName, OBJPROP_ANCHOR, (dir == "BUY") ? ANCHOR_UPPER : ANCHOR_LOWER);
   ObjectSetInteger(0, txtName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, txtName, OBJPROP_HIDDEN, true);
}
void ClearBarrierMarker(string namePrefix)
{
   ObjectDelete(0, namePrefix + "Arrow");
   ObjectDelete(0, namePrefix + "Txt");
}
void DrawNearestPairMarker(BarrierEntry &selfQ[], BarrierEntry &parentQ[], string tfTag, string namePrefix)
{
   string dir; double lvl;
   if(NearestBarrierInPair(selfQ, parentQ, dir, lvl))
      DrawOneBarrierMarker(namePrefix, tfTag, dir, lvl);
   else
      ClearBarrierMarker(namePrefix);
}
void UpdateAllCandleOpenMarkers()
{
   DrawNearestPairMarker(g_m5Queue,  g_m15Queue, "M5",  "DD_M5Barrier");
   DrawNearestPairMarker(g_m15Queue, g_m30Queue, "M15", "DD_M15Barrier");
   DrawNearestPairMarker(g_m30Queue, g_h1Queue,  "M30", "DD_M30Barrier");
   DrawNearestPairMarker(g_h1Queue,  g_h4Queue,  "H1",  "DD_H1Barrier");
   DrawNearestPairMarker(g_h4Queue,  g_d1Queue,  "H4",  "DD_H4Barrier");
}

//--- v52.50: small FIXED countdown mini-panel, top-right corner of the
//--- chart. Price-anchored text kept disappearing off-screen depending on
//--- zoom/autoscale ("yang muncul hanya M5"). Dadang: "buat panel kecil
//--- sebelah kanan buat hitung mundur candle" - corner-anchored labels are
//--- immune to price/zoom, always visible regardless of chart state.
#define CDPFX "DD_CD_"
void SetCornerLabel(string name, int xdist, int ydist, string text, color clr, int fontsize, bool bold=false)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetString(0, name, OBJPROP_FONT, bold ? "Trebuchet MS Bold" : "Trebuchet MS");
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, xdist);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, ydist);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontsize);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}
void UpdateCountdownMiniPanel()
{
   if(ObjectFind(0, CDPFX + "BG") < 0)
   {
      ObjectCreate(0, CDPFX + "BG", OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_CORNER, CORNER_RIGHT_UPPER);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_XDISTANCE, 8);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_YDISTANCE, 15);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_XSIZE, 168);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_YSIZE, 152);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_BGCOLOR, C'18,18,24');
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_COLOR, C'70,70,80');
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_BACK, false);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, CDPFX + "BG", OBJPROP_HIDDEN, true);
   }
   SetCornerLabel(CDPFX + "TITLE", 16, 22,  "CANDLE CLOSE IN", PNL_GOLD, 9, true);
   SetCornerLabel(CDPFX + "H4",    16, 42,  "H4   " + CandleCountdownText(InpMasterTF),      C'56,189,248',  10);
   SetCornerLabel(CDPFX + "H1",    16, 60,  "H1   " + CandleCountdownText(PERIOD_H1),        C'96,165,250',  10);
   SetCornerLabel(CDPFX + "M30",   16, 78,  "M30  " + CandleCountdownText(InpScalpMasterTF), C'168,85,247',  10);
   SetCornerLabel(CDPFX + "M15",   16, 96,  "M15  " + CandleCountdownText(PERIOD_M15),       C'244,114,182', 10);
   SetCornerLabel(CDPFX + "M5",    16, 114, "M5   " + CandleCountdownText(InpScalpEntryTF),  C'250,204,21',  10);
   SetCornerLabel(CDPFX + "M1",    16, 132, "M1   " + CandleCountdownText(PERIOD_M1),        C'163,163,163', 10);
}

//--- reads buffer 7 (BreakoutEventTimeBuffer) - the time of the MOST RECENT
//--- individual breakout past the latest pullback, repeating on EVERY such
//--- break (not just the first regime-flip like buffer 3/ChangeTimeBuffer).
//--- This is THE entry-firing signal per Dadang's rule (2026-08-09): compare
//--- against the last-seen value to detect each fresh event.
datetime ReadBreakoutEventTime(int handle)
{
   double buf[1];
   if(CopyBuffer(handle, 7, 0, 1, buf) <= 0) return 0;
   return (datetime)buf[0];
}

//--- v52.53: "Momentum Breakout" REDESIGNED to be truly real-time bidirectional -
//--- Dadang: "dia real time semakin kuat semakin nambahkan bro bukan hanya
//--- keliatan sebentar kan bro semakin lemah juga semakin mengurang kan".
//--- v52.52's first version measured a fixed CLOSED candle's range - once
//--- set it could only grow (a forming candle's high/low never shrinks) or
//--- jump to a new value on the next breakout event; it never faded back
//--- down tick-by-tick like Dadang expected. Fixed by tracking LIVE distance
//--- from the frozen flip-level (buffer 4 - the SNR that broke to cause this
//--- CMP) to CURRENT price, every tick: pushes further = ratio grows,
//--- pulls back toward that level = ratio shrinks, in real time. Still pure
//--- price-action (no ADX/RSI/EMA - CLAUDE.md "murni CMP/VR/CF" doctrine),
//--- just calibrated against a plain (non-smoothed) average range so the
//--- ratio means something regardless of TF.
//--- v52.71: factored the raw dir+ratio out of the display text (was
//--- inline-only) - CheckMomentumEntryTrigger() needs the NUMBER to gate
//--- entries on, not a formatted string to re-parse. Returns false (dir/
//--- ratio left untouched) if there's nothing valid to report - same cases
//--- MomentumBreakoutText() used to show "-" for.
bool MomentumRatio(ENUM_TIMEFRAMES tf, int cmpHandle, string &dirOut, double &ratioOut)
{
   datetime dummyT;
   dirOut = ReadCMP(cmpHandle, dummyT);
   if(dirOut != "BUY" && dirOut != "SELL") return false;
   bool isBuy = (dirOut == "BUY");

   double brkLevel = ReadLiveLevel(cmpHandle, 4);   // frozen flip-level - the level that broke
   if(brkLevel <= 0) return false;

   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double distance = isBuy ? (curPrice - brkLevel) : (brkLevel - curPrice);
   if(distance < 0) distance = 0;   // hasn't cleared its own barrier yet

   int    n = 10;
   double sumRange = 0.0;
   for(int i = 1; i <= n; i++)
      sumRange += (iHigh(_Symbol, tf, i) - iLow(_Symbol, tf, i));
   double avgRange = sumRange / n;
   if(avgRange <= 0) return false;

   ratioOut = distance / avgRange;
   return true;
}
string MomentumBreakoutText(ENUM_TIMEFRAMES tf, int cmpHandle, color &clrOut)
{
   string dir; double ratio;
   if(!MomentumRatio(tf, cmpHandle, dir, ratio)) { clrOut = PNL_LABEL; return "-"; }

   // v52.55 fix - Dadang: "maksud momentum week atau strong ini gimana...
   // maksudnya ijo atau merah gw masih bingung". Color used to mean
   // STRENGTH (green=strong/red=weak regardless of direction) which broke
   // the panel-wide convention that green=BUY/red=SELL everywhere else
   // (DirColor()) - direction was implicit, forcing a cross-check against
   // the "M5 (CMP)" row above just to read it. Now: color ALWAYS = direction
   // (matches every other row), and the word BUY/SELL is spelled out in the
   // text itself alongside the strength word - unambiguous standalone.
   clrOut = DirColor(dir);
   string strength = (ratio >= 1.5) ? "STRONG" : (ratio >= 0.5) ? "NORMAL" : "WEAK";
   return StringFormat("%s %s %.1fx", dir, strength, ratio);
}

// v52.78 - "Momentum M5 Bookmap": Aggression(M5) confluence pillar. Mid-
// discussion with Dadang about Fabio Valentini's Direction/Location/
// Aggression framework, MomentumRatio() above turned out to be 100% MT5
// candle price data - no Bookmap/order-flow involved at all (see its own
// comment). This is the missing pair: SAME idea (how far has it moved
// SINCE the M5 breakout, relative to typical recent scale) but measured in
// real CVD (buy/sell volume imbalance) instead of price distance. Dadang:
// "kalo sama2 kuat berarti momentum itu valid" - the two rows are meant to
// be read SIDE BY SIDE: price momentum alone can be a thin stop-run with
// no real participants behind it; CVD confirming the SAME direction means
// genuine order flow is backing the move, not just price drifting.
//
// Informational only, same "record first" discipline as POC/sweep/etc -
// NOT wired into TryOpen() or any entry/exit logic.
double   g_bmMomBaseCvd     = 0.0;   // CVD snapshot taken at the CURRENT M5 breakout event
datetime g_bmMomBaseEvtTime = 0;     // which M5 breakout event g_bmMomBaseCvd belongs to

string MomentumBookmapText(color &clrOut)
{
   if(!g_bookmapOnline) { clrOut = PNL_LABEL; return "-"; }

   datetime evtTime = ReadBreakoutEventTime(g_hScalpEntry);
   datetime ct; string dir = ReadCMP(g_hScalpEntry, ct);
   if(evtTime == 0 || (dir != "BUY" && dir != "SELL")) { clrOut = PNL_LABEL; return "-"; }

   if(evtTime != g_bmMomBaseEvtTime)   // fresh M5 breakout - snapshot CVD as the new baseline
   {
      g_bmMomBaseEvtTime = evtTime;
      g_bmMomBaseCvd     = g_bookmapCvd;
   }

   double cvdDelta = g_bookmapCvd - g_bmMomBaseCvd;
   bool   agrees   = (dir == "BUY") ? (cvdDelta > 0) : (cvdDelta < 0);

   // Normalize against the recent typical 1-minute CVD swing - reuses the
   // SAME ring buffer WriteSultanStatus() already maintains every tick
   // (g_cvdMinuteSamples/g_cvdSampleCount, see its "Bookmap Flow" comment),
   // rather than building a second parallel tracker for the same data.
   double sumAbsMove = 0.0; int nMoves = 0;
   int startIdx = CVD_HIST_LEN - g_cvdSampleCount;
   for(int i = MathMax(startIdx, 1); i < CVD_HIST_LEN; i++)
   {
      sumAbsMove += MathAbs(g_cvdMinuteSamples[i] - g_cvdMinuteSamples[i - 1]);
      nMoves++;
   }
   double avgMove = (nMoves > 0) ? (sumAbsMove / nMoves) : 0.0;
   if(avgMove <= 0) { clrOut = PNL_LABEL; return "-"; }

   double ratio = MathAbs(cvdDelta) / avgMove;
   if(!agrees)
   {
      // v52.90 - Dadang: "disana hanya ada buy n sell bukan lawan lawan
      // bikin pusing aja" - this field's job is to answer "what does CVD
      // say", full stop; conflict with M5's own direction is now conveyed
      // ONLY by the amber color (same language as every other conflict
      // flag on the panel), not by spelling out "LAWAN" + a raw delta
      // number in the text itself.
      clrOut = C'251,191,36';   // amber - same "caution/conflict" tone as ARMED/pending states elsewhere, not a direction color
      return dir;
   }
   clrOut = DirColor(dir);
   string strength = (ratio >= 1.5) ? "STRONG" : (ratio >= 0.5) ? "NORMAL" : "WEAK";
   return StringFormat("%s %s %.1fx", dir, strength, ratio);
}

// v52.79 - "Momentum M5 Footprint": 3rd confluence pillar alongside price
// Momentum(M5) and CVD-based Momentum M5 Bookmap. Dadang, same night:
// "valentini gw rasa dia pakai footprint bro" - confirmed, Fabio's
// Aggression pillar leans on footprint (per-PRICE buy/sell imbalance), not
// just CVD. Difference from CVD: CVD is session-wide and location-blind
// (net pressure anywhere); footprint is scoped to the CURRENT price level
// only (g_bookmapFootBuyVol/SellVol, from FootprintEngine.get_footprint_
// at_price() on Bookmap's side) - answers "is aggression happening RIGHT
// HERE at the breakout zone" rather than "somewhere in the session."
//
// Same event-anchored snapshot/diff pattern as MomentumBookmapText() -
// snapshot the buy/sell split at the M5 breakout, compare to now. No
// separate minute-bucket accumulator (Dadang's original "sejak M1" idea)
// needed - Bookmap's own rolling window already gives a live read, and
// diffing two live reads captures "did near-price aggression shift since
// the breakout" without new state on the Python side.
double   g_bmFootBaseDelta   = 0.0;   // (buyVol-sellVol) snapshot at the CURRENT M5 breakout
datetime g_bmFootBaseEvtTime = 0;

string MomentumFootprintText(color &clrOut)
{
   if(!g_bookmapOnline) { clrOut = PNL_LABEL; return "-"; }

   datetime evtTime = ReadBreakoutEventTime(g_hScalpEntry);
   datetime ct; string dir = ReadCMP(g_hScalpEntry, ct);
   if(evtTime == 0 || (dir != "BUY" && dir != "SELL")) { clrOut = PNL_LABEL; return "-"; }

   double curDelta = g_bookmapFootBuyVol - g_bookmapFootSellVol;
   if(evtTime != g_bmFootBaseEvtTime)   // fresh M5 breakout - snapshot as the new baseline
   {
      g_bmFootBaseEvtTime = evtTime;
      g_bmFootBaseDelta   = curDelta;
   }

   double deltaMove = curDelta - g_bmFootBaseDelta;
   bool   agrees    = (dir == "BUY") ? (deltaMove > 0) : (deltaMove < 0);

   double totalVol = g_bookmapFootBuyVol + g_bookmapFootSellVol;
   if(totalVol <= 0) { clrOut = PNL_LABEL; return "-"; }   // no trades at this price yet this window

   // Normalize against total volume currently visible at this price - own
   // reasonable scale (footprint has no natural "average move" history the
   // way CVD's minute-samples ring buffer does), tuned the same "record
   // first, recalibrate once real data shows whether 0.5/1.5 reads
   // sensibly for footprint too" way as everything else built tonight.
   double ratio = MathAbs(deltaMove) / totalVol * 2.0;
   if(!agrees)
   {
      // v52.90 - same simplification as MomentumBookmapText() above:
      // "LAWAN FP..." text dropped, conflict now conveyed by amber color
      // alone so this field only ever reads "BUY" or "SELL".
      clrOut = C'251,191,36';
      return dir;
   }
   clrOut = DirColor(dir);
   string strength2 = (ratio >= 1.5) ? "STRONG" : (ratio >= 0.5) ? "NORMAL" : "WEAK";
   return StringFormat("%s %s %.1fx", dir, strength2, ratio);
}

// v52.95 - "Footprint (M1)": Dadang wants to know from the M1 timeframe
// specifically whether buyers or sellers are starting to step in, as an
// early-warning read independent of M5's own CMP state - "supaya gw tau
// dari m1 bahwa seller atau buyer mulain masuk... ketika m5 ijo hanya
// nois dari m1 aja gitu" (so I know from M1 that a buyer/seller is
// starting to come in - so I can tell when an M5 green candle is just
// noise from M1's perspective). Deliberately NOT anchored to the M5
// breakout event the way MomentumFootprintText() above is - reads live,
// all the time, mirroring FootprintEngine.get_footprint_in_window()'s own
// BUY_DOMINANT/SELL_DOMINANT/NEUTRAL thresholds (60/40%) on the Python
// side. Purely informational - explicitly agreed with Dadang this doesn't
// gate or replace anything else on the panel, and doesn't move the M5
// floor the rest of the system respects.
string FootprintM1Text(color &clrOut)
{
   if(!g_bookmapOnline) { clrOut = PNL_LABEL; return "-"; }
   double totalVol = g_bookmapFootM1BuyVol + g_bookmapFootM1SellVol;
   if(totalVol <= 0) { clrOut = PNL_LABEL; return "-"; }
   double buyPct = g_bookmapFootM1BuyVol / totalVol * 100.0;
   if(buyPct >= 60.0) { clrOut = PNL_EMERALD; return StringFormat("BUYER MASUK %.0f%%", buyPct); }
   if(buyPct <= 40.0) { clrOut = PNL_ROSE; return StringFormat("SELLER MASUK %.0f%%", 100.0 - buyPct); }
   clrOut = PNL_LABEL;
   return StringFormat("NETRAL %.0f/%.0f", buyPct, 100.0 - buyPct);
}

// ============================================================================
// v52.96 - LIVE candle-anchored momentum trio, DISPLAY ONLY.
//
// Dadang caught that "Momentum (M5)"/"Momentum M5 Bookmap"/"Momentum M5
// Footprint" above all silently inherited their direction word from
// ReadCMP() - the SAME lagging status the separate "M5 (CMP)" row already
// shows - and reset their baseline on a CMP breakout EVENT. So while a
// candle was visibly ripping upward, all three "Momentum" rows still read
// SELL because CMP hadn't confirmed the flip yet: "candle kenceng naik
// datanya merah... kalo ini kita baca histori m5 namanya bukan candle
// yang jalan." Then, precisely: "ini beda dari cmp... namanya momentum
// bukan cmp yang kita baca" - Momentum is supposed to be its own signal,
// not a CMP echo with a ratio number bolted on.
//
// Redesigned anchor: the CURRENT (still-forming) M5 candle's own OPEN,
// not the last confirmed CMP breakout. Direction is simply "is
// price/CVD/footprint above or below where THIS candle started" -
// genuinely live, resets every new candle regardless of whether CMP ever
// flips: "kita baca momentum setiap candle... itu hanya baca momentum
// candel m5 footprint dan cvd nya."
//
// Scope, confirmed explicitly: "bukan buat entri bukan cf bukan cmp
// bukan lainya" - DISPLAY ONLY. MomentumRatio()/MomentumBreakoutText()/
// MomentumBookmapText()/MomentumFootprintText() above are UNTOUCHED and
// still key off CMP exactly as before - CheckMomentumEntryTrigger() (the
// real InpUseMomentumEntryTrigger entry logic) calls MomentumRatio()
// directly and never touches anything below this point.
// ============================================================================

string LiveCandleDir(ENUM_TIMEFRAMES tf, double &distOut)
{
   double openPx = iOpen(_Symbol, tf, 0);
   double curPx  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   distOut = curPx - openPx;
   if(openPx <= 0)        return "WAIT";
   if(curPx > openPx)     return "BUY";
   if(curPx < openPx)     return "SELL";
   return "WAIT";
}

// v52.97 - Dadang, right after the Live Momentum trio went genuinely
// tick-by-tick: "sekarang jadi cepet banget gimana cara nya kita tau itu
// akan bertahan agak lama... kalo bolak balik stress" - fully live meant
// direction could flicker BUY/SELL/BUY within a couple seconds whenever
// price chopped right around the candle's open. Requires a NEW direction
// to be seen consistently for InpMomentumHoldSec before it's actually
// displayed (filters sub-threshold noise, still far more responsive than
// waiting a full candle close), and tracks how long the DISPLAYED
// direction has held so the row can show "(sejak Xs)" - lets him see at a
// glance whether a read is fresh/shaky or has actually been holding.
struct MomentumStability
{
   string   dir;            // currently DISPLAYED direction
   datetime dirSince;       // when this displayed direction was confirmed
   string   pendingDir;     // a candidate new direction, not yet confirmed
   datetime pendingSince;   // when pendingDir first started being proposed
};

string StabilizeDir(MomentumStability &st, string rawDir, int &secHeldOut)
{
   datetime now = TimeCurrent();
   if(st.dir == "")   // first read ever - nothing to debounce against yet
   {
      st.dir = rawDir; st.dirSince = now; st.pendingDir = ""; st.pendingSince = 0;
   }
   else if(rawDir == st.dir)
   {
      st.pendingDir = ""; st.pendingSince = 0;   // raw agrees with what's shown - no pending flip
   }
   else if(rawDir == "BUY" || rawDir == "SELL")
   {
      if(st.pendingDir != rawDir) { st.pendingDir = rawDir; st.pendingSince = now; }
      else if(now - st.pendingSince >= InpMomentumHoldSec)
      {
         st.dir = rawDir; st.dirSince = now; st.pendingDir = ""; st.pendingSince = 0;   // held long enough - flip
      }
   }
   secHeldOut = (int)(now - st.dirSince);
   return st.dir;
}

MomentumStability g_stabMomPrice, g_stabMomBookmap, g_stabMomFootprint;

string LiveMomentumPriceText(color &clrOut)
{
   double dist;
   string rawDir = LiveCandleDir(InpScalpEntryTF, dist);
   if(rawDir == "WAIT" && g_stabMomPrice.dir == "") { clrOut = PNL_LABEL; return "-"; }
   int secHeld; string dir = StabilizeDir(g_stabMomPrice, rawDir, secHeld);

   int    n = 10;
   double sumRange = 0.0;
   for(int i = 1; i <= n; i++)
      sumRange += (iHigh(_Symbol, InpScalpEntryTF, i) - iLow(_Symbol, InpScalpEntryTF, i));
   double avgRange = sumRange / n;
   if(avgRange <= 0) { clrOut = PNL_LABEL; return "-"; }

   double ratio = MathAbs(dist) / avgRange;
   clrOut = DirColor(dir);
   string strength = (ratio >= 1.5) ? "STRONG" : (ratio >= 0.5) ? "NORMAL" : "WEAK";
   return StringFormat("%s %s %.1fx (%s)", dir, strength, ratio, TimeAgoText(secHeld));
}

double   g_liveMomBaseCvd = 0.0;
datetime g_liveMomBarTime = 0;

string LiveMomentumBookmapText(color &clrOut)
{
   if(!g_bookmapOnline) { clrOut = PNL_LABEL; return "-"; }
   double dist;
   string rawDir = LiveCandleDir(InpScalpEntryTF, dist);
   if(rawDir == "WAIT" && g_stabMomBookmap.dir == "") { clrOut = PNL_LABEL; return "-"; }
   int secHeld; string dir = StabilizeDir(g_stabMomBookmap, rawDir, secHeld);

   datetime barTime = iTime(_Symbol, InpScalpEntryTF, 0);
   if(barTime != g_liveMomBarTime)   // fresh M5 candle - snapshot CVD as the new baseline
   {
      g_liveMomBarTime = barTime;
      g_liveMomBaseCvd = g_bookmapCvd;
   }

   double cvdDelta = g_bookmapCvd - g_liveMomBaseCvd;
   bool   agrees   = (dir == "BUY") ? (cvdDelta > 0) : (cvdDelta < 0);

   double sumAbsMove = 0.0; int nMoves = 0;
   int startIdx = CVD_HIST_LEN - g_cvdSampleCount;
   for(int i = MathMax(startIdx, 1); i < CVD_HIST_LEN; i++)
   {
      sumAbsMove += MathAbs(g_cvdMinuteSamples[i] - g_cvdMinuteSamples[i - 1]);
      nMoves++;
   }
   double avgMove = (nMoves > 0) ? (sumAbsMove / nMoves) : 0.0;
   if(avgMove <= 0) { clrOut = PNL_LABEL; return "-"; }

   double ratio = MathAbs(cvdDelta) / avgMove;
   if(!agrees) { clrOut = C'251,191,36'; return StringFormat("%s (%s)", dir, TimeAgoText(secHeld)); }
   clrOut = DirColor(dir);
   string strength = (ratio >= 1.5) ? "STRONG" : (ratio >= 0.5) ? "NORMAL" : "WEAK";
   return StringFormat("%s %s %.1fx (%s)", dir, strength, ratio, TimeAgoText(secHeld));
}

double   g_liveMomFootBaseDelta = 0.0;
datetime g_liveMomFootBarTime   = 0;

string LiveMomentumFootprintText(color &clrOut)
{
   if(!g_bookmapOnline) { clrOut = PNL_LABEL; return "-"; }
   double dist;
   string rawDir = LiveCandleDir(InpScalpEntryTF, dist);
   if(rawDir == "WAIT" && g_stabMomFootprint.dir == "") { clrOut = PNL_LABEL; return "-"; }
   int secHeld; string dir = StabilizeDir(g_stabMomFootprint, rawDir, secHeld);

   double curDelta = g_bookmapFootBuyVol - g_bookmapFootSellVol;
   datetime barTime = iTime(_Symbol, InpScalpEntryTF, 0);
   if(barTime != g_liveMomFootBarTime)   // fresh M5 candle - snapshot as the new baseline
   {
      g_liveMomFootBarTime   = barTime;
      g_liveMomFootBaseDelta = curDelta;
   }

   double deltaMove = curDelta - g_liveMomFootBaseDelta;
   bool   agrees    = (dir == "BUY") ? (deltaMove > 0) : (deltaMove < 0);

   double totalVol = g_bookmapFootBuyVol + g_bookmapFootSellVol;
   if(totalVol <= 0) { clrOut = PNL_LABEL; return "-"; }

   double ratio = MathAbs(deltaMove) / totalVol * 2.0;
   if(!agrees) { clrOut = C'251,191,36'; return StringFormat("%s (%s)", dir, TimeAgoText(secHeld)); }
   clrOut = DirColor(dir);
   string strength = (ratio >= 1.5) ? "STRONG" : (ratio >= 0.5) ? "NORMAL" : "WEAK";
   return StringFormat("%s %s %.1fx (%s)", dir, strength, ratio, TimeAgoText(secHeld));
}

// v52.82 - CVD Divergence detector, M5-scoped (Dadang, from the CVD
// Divergences infographic he shared: "di M5 bro semua minimal m5 m1 hanya
// buat pesan" - M5 is the floor, matches the doctrine's own H4/M30/M5-only
// boundary). Uses the SAME 2-candle V/A-shape swing detector the whole CMP
// doctrine is already built on (body close, not wick) to find fresh M5
// swing highs/lows, then checks whether CVD confirmed that swing or not:
//   - price makes a HIGHER swing high, but CVD's value at that new high is
//     NOT higher than at the last swing high -> BEARISH divergence
//     (buy-side exhausted / hidden sell absorption)
//   - price makes a LOWER swing low, but CVD's value there is NOT lower
//     than at the last swing low -> BULLISH divergence (sell-side
//     exhausted / hidden buy absorption)
// Deliberately does NOT distinguish "exhaustion" vs "absorption" from the
// infographic - both produce the identical price/CVD signature, the
// difference is narrative framing, not a separate detectable condition.
//
// Dadang floated using this as an INSTANT entry trigger regardless of TF -
// discussed live, agreed to scope it to M5 and keep it INFORMATIONAL first
// (same "record first" discipline as every other confluence row tonight),
// not wired into TryOpen() - needs real data before it's trusted as a
// trigger.
string   g_cvdDivLastSwing      = "";    // "HIGH" or "LOW" - kind of the last recorded swing
double   g_cvdDivLastSwingPx    = 0.0;
double   g_cvdDivLastSwingCvd   = 0.0;
string   g_cvdDivStatus         = "-";
datetime g_cvdDivStatusTime     = 0;
datetime g_cvdDivLastCheckedBar = 0;

void UpdateCvdDivergence()
{
   if(!g_bookmapOnline) return;

   datetime curM5Bar = iTime(_Symbol, PERIOD_M5, 0);
   if(curM5Bar == g_cvdDivLastCheckedBar) return;   // only re-check once per fresh M5 bar
   g_cvdDivLastCheckedBar = curM5Bar;

   // bar 2 = two M5 bars ago (fully closed and confirmed, since bar 1 has
   // already closed after it); bar 1 = the bar that just closed.
   double o2 = iOpen(_Symbol, PERIOD_M5, 2), c2 = iClose(_Symbol, PERIOD_M5, 2);
   double o1 = iOpen(_Symbol, PERIOD_M5, 1), c1 = iClose(_Symbol, PERIOD_M5, 1);
   if(o2 <= 0 || o1 <= 0) return;

   bool isSwingLow  = (c2 < o2) && (c1 > o1);   // bearish then bullish = V-bottom (minor support)
   bool isSwingHigh = (c2 > o2) && (c1 < o1);   // bullish then bearish = A-top (minor resistance)
   if(!isSwingLow && !isSwingHigh) return;

   string kind     = isSwingHigh ? "HIGH" : "LOW";
   double swingPx  = isSwingHigh ? MathMax(c2, o2) : MathMin(c2, o2);   // body-based level, same convention as minor SNR everywhere else
   double swingCvd = g_bookmapCvd;

   if(g_cvdDivLastSwing == kind)   // only compare against the last swing of the SAME kind
   {
      if(kind == "HIGH" && swingPx > g_cvdDivLastSwingPx && swingCvd <= g_cvdDivLastSwingCvd)
      {
         g_cvdDivStatus     = "BEARISH (exhaustion)";
         g_cvdDivStatusTime = TimeCurrent();
         Print("CVD DIVERGENCE: BEARISH - price HH ", DoubleToString(swingPx, 2),
               " tapi CVD gak ikut (", DoubleToString(g_cvdDivLastSwingCvd, 0), " -> ", DoubleToString(swingCvd, 0), ")");
      }
      else if(kind == "LOW" && swingPx < g_cvdDivLastSwingPx && swingCvd >= g_cvdDivLastSwingCvd)
      {
         g_cvdDivStatus     = "BULLISH (exhaustion)";
         g_cvdDivStatusTime = TimeCurrent();
         Print("CVD DIVERGENCE: BULLISH - price LL ", DoubleToString(swingPx, 2),
               " tapi CVD gak ikut (", DoubleToString(g_cvdDivLastSwingCvd, 0), " -> ", DoubleToString(swingCvd, 0), ")");
      }
   }

   g_cvdDivLastSwing    = kind;
   g_cvdDivLastSwingPx  = swingPx;
   g_cvdDivLastSwingCvd = swingCvd;
}

string CvdDivergenceText(color &clrOut)
{
   if(!g_bookmapOnline || g_cvdDivStatus == "-") { clrOut = PNL_LABEL; return "-"; }
   long ageSec = (long)(TimeCurrent() - g_cvdDivStatusTime);
   if(ageSec > 1800) { clrOut = PNL_LABEL; return "-"; }   // fade after 30 min so it never looks falsely "still live"
   clrOut = (g_cvdDivStatus == "BEARISH (exhaustion)") ? PNL_ROSE : PNL_EMERALD;
   return StringFormat("%s (%s lalu)", g_cvdDivStatus, TimeAgoText(ageSec));
}

// v52.83 - IVB (Initial Value Balance): first-30-minutes-of-the-day High/
// Low, an order-flow reference concept Dadang found in outside research
// material and asked to adapt into the panel, informational-only. Anchored
// to the D1 bar's own open (broker day boundary) rather than hardcoding a
// specific session clock time - XAUUSD trades near 24h unlike the futures
// markets that concept normally gets applied to, so "the day's own open"
// is the closest self-consistent anchor available without guessing a
// session offset that could be wrong for this broker. Worth revisiting
// once there's live data to check whether that boundary reads sensibly.
datetime g_ivbDayStart = 0;
double   g_ivbHigh     = 0.0;
double   g_ivbLow      = 0.0;
bool     g_ivbLocked   = false;

void UpdateIVB()
{
   datetime d1Open = iTime(_Symbol, PERIOD_D1, 0);
   if(d1Open == 0) return;
   if(d1Open != g_ivbDayStart)
   {
      g_ivbDayStart = d1Open;
      g_ivbHigh     = 0.0;
      g_ivbLow      = 0.0;
      g_ivbLocked   = false;
   }
   if(g_ivbLocked) return;

   datetime windowEnd = g_ivbDayStart + 1800;   // 30 minutes
   if(TimeCurrent() < windowEnd) return;        // still inside the window - wait for it to fully close before locking

   int barEnd   = iBarShift(_Symbol, PERIOD_M5, windowEnd,     false);
   int barStart = iBarShift(_Symbol, PERIOD_M5, g_ivbDayStart, false);
   if(barStart < 0 || barEnd < 0 || barStart < barEnd) return;   // history not ready yet

   double hi = -1.0, lo = -1.0;
   for(int i = barEnd; i <= barStart; i++)
   {
      double h = iHigh(_Symbol, PERIOD_M5, i), l = iLow(_Symbol, PERIOD_M5, i);
      if(hi < 0 || h > hi) hi = h;
      if(lo < 0 || l < lo) lo = l;
   }
   if(hi > 0 && lo > 0)
   {
      g_ivbHigh   = hi;
      g_ivbLow    = lo;
      g_ivbLocked = true;
   }
}

string IvbText(color &clrOut)
{
   // v52.83 fix shortened "77006.45 - 77308.04 (di BAWAH - imbalance)"
   // (~43 chars) to "<STATUS> <low>-<high>" (~21-22 chars) - still too
   // wide once actually measured in pixels (v52.87: PnlRow() now measures
   // real rendered width instead of guessing off character count, which
   // is how this got caught). Switched to distance-past-the-boundary
   // instead of the raw range - shorter, and arguably more useful anyway
   // (how far outside IVB price has moved matters more once you already
   // know which side it's on).
   if(!g_ivbLocked) { clrOut = PNL_LABEL; return "belum kebentuk"; }
   double cur = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(cur > g_ivbHigh)      { clrOut = PNL_EMERALD; return StringFormat("ATAS %+.2f", cur - g_ivbHigh); }
   else if(cur < g_ivbLow)  { clrOut = PNL_ROSE;    return StringFormat("BAWAH %+.2f", cur - g_ivbLow); }
   clrOut = PNL_LABEL; return "DALAM";
}

// v52.83 - Daily Profile Framing: compare TODAY's Value Area/POC against
// YESTERDAY's snapshot - value shifting up/down across days = a slower,
// higher-timeframe bias layer, separate from "VA Bias" (which reads WHERE
// price sits right now vs today's own VA/POC, already live since v52.76).
// Snapshots are taken already CONVERTED to XAUUSD scale (using the live
// GCZ6-vs-XAUUSD offset at snapshot time), not raw Bookmap price - the
// basis between those two DRIFTS day to day (confirmed earlier tonight
// while debugging vol_compare_study.py), so comparing raw values across a
// 24h gap would mix real value-shift with basis drift. Converting each
// side at ITS OWN moment avoids that.
double   g_dpfYestVah  = 0.0;
double   g_dpfYestVal  = 0.0;
double   g_dpfYestPoc  = 0.0;
datetime g_dpfLastDay  = 0;

void UpdateDailyProfileFraming()
{
   datetime d1Open = iTime(_Symbol, PERIOD_D1, 0);
   if(d1Open == 0 || d1Open == g_dpfLastDay) return;

   if(g_dpfLastDay != 0 && g_bookmapVah > 0 && g_bookmapPrice > 0)   // skip the very first run (nothing to snapshot yet)
   {
      double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
      g_dpfYestVah = g_bookmapVah      + offset;
      g_dpfYestVal = g_bookmapVal      + offset;
      g_dpfYestPoc = g_bookmapPocPrice + offset;
   }
   g_dpfLastDay = d1Open;
}

string DailyProfileFramingText(color &clrOut)
{
   if(g_dpfYestPoc <= 0 || !g_bookmapOnline || g_bookmapPocPrice <= 0) { clrOut = PNL_LABEL; return "-"; }
   double offset   = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   double todayPoc = g_bookmapPocPrice + offset;
   double shift    = todayPoc - g_dpfYestPoc;
   if(MathAbs(shift) < 0.3) { clrOut = PNL_LABEL; return "NEUTRAL"; }
   if(shift > 0) { clrOut = PNL_EMERALD; return StringFormat("BULLISH POC%+.2f", shift); }
   clrOut = PNL_ROSE; return StringFormat("BEARISH POC%+.2f", shift);
}

// v52.84 - Volume Node: nearest HVN (harga cenderung MACET/mantul) vs
// nearest LVN (harga cenderung LICIN/lewat cepat) ke harga sekarang. Satu
// baris panel simpel, pilih yang JAUHNYA lebih deket ke harga sekarang biar
// gampang dibaca - gak nampilin dua-duanya sekaligus biar gak penuh.
string VolumeNodeText(color &clrOut)
{
   if(!g_bookmapOnline || (g_bookmapHvnPrice <= 0 && g_bookmapLvnPrice <= 0)) { clrOut = PNL_LABEL; return "-"; }
   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   double cur    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double hvnMt5 = g_bookmapHvnPrice > 0 ? g_bookmapHvnPrice + offset : 0.0;
   double lvnMt5 = g_bookmapLvnPrice > 0 ? g_bookmapLvnPrice + offset : 0.0;
   double dHvn   = hvnMt5 > 0 ? MathAbs(cur - hvnMt5) : DBL_MAX;
   double dLvn   = lvnMt5 > 0 ? MathAbs(cur - lvnMt5) : DBL_MAX;
   if(dHvn == DBL_MAX && dLvn == DBL_MAX) { clrOut = PNL_LABEL; return "-"; }
   if(dHvn <= dLvn) { clrOut = PNL_GOLD; return StringFormat("HVN %.2f macet", hvnMt5); }
   clrOut = PNL_SILVER; return StringFormat("LVN %.2f licin", lvnMt5);
}

// v52.84 - Reload Level: level yang PERNAH dites wall kuat (>=InpReloadMinLot)
// tapi BELAKANGAN jebol beneran (bukan cuma pindah slot) - lihat komentar
// g_reloadPrice di atas buat penjelasan konsepnya. UpdateReloadLevels()
// dipanggil tiap cycle bookmap update, mendeteksi transisi wall-hilang +
// harga-udah-lewat, lalu mencatatnya ke memori. ReloadLevelText() query nya
// buat panel - nunjukin kalau harga LAGI RETEST salah satu level itu.
void AddReloadLevel(double mt5Price, double size, bool wasBid)
{
   for(int i = 0; i < g_reloadCount; i++)
      if(MathAbs(g_reloadPrice[i] - mt5Price) < 0.5) { g_reloadTime[i] = TimeCurrent(); g_reloadSize[i] = size; return; }

   int slot;
   if(g_reloadCount < RELOAD_MAX) { slot = g_reloadCount; g_reloadCount++; }
   else   // ring buffer penuh - timpa yang paling lama dicatat
   {
      slot = 0;
      for(int i = 1; i < RELOAD_MAX; i++) if(g_reloadTime[i] < g_reloadTime[slot]) slot = i;
   }
   g_reloadPrice[slot] = mt5Price;
   g_reloadSize[slot]  = size;
   g_reloadIsBid[slot] = wasBid;
   g_reloadTime[slot]  = TimeCurrent();
}

void UpdateReloadLevels(double bookmapPrice)
{
   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - bookmapPrice;
   double cur    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(g_reloadPrevInit)
   {
      for(int i = 0; i < WALL_NEAR_SLOTS; i++)
      {
         // BID wall (support) ada size gede kemarin, sekarang HILANG dari
         // slot, DAN harga sekarang udah di BAWAH level itu -> jebol beneran
         // (breakdown), bukan cuma wall geser slot.
         if(g_reloadPrevBidPx[i] > 0 && g_reloadPrevBidSz[i] >= InpReloadMinLot
            && g_bookmapBidPx[i] <= 0 && cur < g_reloadPrevBidPx[i] + offset)
            AddReloadLevel(g_reloadPrevBidPx[i] + offset, g_reloadPrevBidSz[i], true);

         // ASK wall (resistance) jebol ke ATAS -> breakout.
         if(g_reloadPrevAskPx[i] > 0 && g_reloadPrevAskSz[i] >= InpReloadMinLot
            && g_bookmapAskPx[i] <= 0 && cur > g_reloadPrevAskPx[i] + offset)
            AddReloadLevel(g_reloadPrevAskPx[i] + offset, g_reloadPrevAskSz[i], false);
      }
   }
   for(int i = 0; i < WALL_NEAR_SLOTS; i++)
   {
      g_reloadPrevBidPx[i] = g_bookmapBidPx[i]; g_reloadPrevBidSz[i] = g_bookmapBidSz[i];
      g_reloadPrevAskPx[i] = g_bookmapAskPx[i]; g_reloadPrevAskSz[i] = g_bookmapAskSz[i];
   }
   g_reloadPrevInit = true;
}

string ReloadLevelText(color &clrOut)
{
   double cur     = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   datetime cutoff = TimeCurrent() - InpReloadWindowMin * 60;
   int bestIdx = -1; double bestDist = 0.0;
   for(int i = 0; i < g_reloadCount; i++)
   {
      if(g_reloadTime[i] < cutoff) continue;   // udah basi
      double d = MathAbs(cur - g_reloadPrice[i]);
      if(d <= InpReloadRetestUsd && (bestIdx < 0 || d < bestDist)) { bestDist = d; bestIdx = i; }
   }
   if(bestIdx < 0) { clrOut = PNL_LABEL; return "-"; }
   bool expectSell = g_reloadIsBid[bestIdx];   // dulu wall BID (support) yang jebol ke bawah -> retest = ekspektasi jual lanjut
   clrOut = expectSell ? PNL_ROSE : PNL_EMERALD;
   // row label already says "Reload Level" - dropping the redundant word
   // "RELOAD" from the value itself was the difference between fitting
   // the panel's value column and overflowing it.
   return StringFormat("%s @%.2f %.0fL", expectSell ? "JUAL" : "BELI", g_reloadPrice[bestIdx], g_reloadSize[bestIdx]);
}

//--- Momentum filter (eksperimen, off by default): skip entry if ADX on the
//--- last CLOSED bar is below InpADX_MinLevel (market too choppy/weak).
//--- Always returns true if InpUseADX is off or the handle wasn't created.

//--- RSI filter. Two modes:
//--- (a) InpRSI_UseNeutralZone=true (Dadang: "kita hanya entri ketika RSI
//---     di 50, jangan sampai kejebak di oversold atau overbought") - entry
//---     only allowed when RSI sits within InpRSI_NeutralBand of 50,
//---     REGARDLESS of direction. Stricter than just avoiding extremes.
//--- (b) InpRSI_UseNeutralZone=false - old behavior: only block BUY when
//---     already overbought, block SELL when already oversold.
//--- Always true if InpUseRSI is off or the handle wasn't created.

//--- M1 confirmation (redesigned 2026-08-09 per Dadang's live observation:
//--- "kalo M5 BO buy kita entri dan M1 malah bikin BO sell, M5 balik arah
//--- flip sell, BE kita kena" - a plain snapshot check wasn't enough since
//--- M1 naturally lags M5's own fresh BO by a few ticks/bars. This version
//--- requires M1's OWN breakout to be FRESH too (tM1 >= sinceTime, i.e. at
//--- or after M5's fresh BO) - AND crucially, the caller must call this
//--- EVERY TICK without consuming the bar-gate until it passes, so the EA
//--- genuinely WAITS for M1 to catch up instead of giving up after one
//--- bar's snapshot (which was the old, ineffective behavior - see memory
//--- notes: M1Confirm previously just cut trade count with no quality
//--- gain, because it never actually waited).
//--- Always true kalau InpUseM1Confirm off atau handle-nya gagal load.
bool M1Ok(string dir, datetime sinceTime)
{
   if(!InpUseM1Confirm || g_hM1 == INVALID_HANDLE) return true;
   datetime tM1;
   string m1Dir = ReadCMP(g_hM1, tM1);
   if(m1Dir != dir) return false;
   return tM1 >= sinceTime;
}

//--- Bookmap live-bridge reader. Reads the tiny CSV udp_listener.py
//--- overwrites every write cycle (see that file's MT5_BRIDGE_FILE comment)
//--- via Common\Files so both processes can see it regardless of which
//--- MT5/Python instance is running. LIVE path only reachable outside
//--- Strategy Tester/Optimization (v31: those instead replay from the
//--- recorded archive - see ReadBookmapHistoryReplay() above - since the
//--- live file's real wall-clock timestamp never matches simulated time).
//--- Absorption (v23) and POC-overextend (v30) are wired into entry lot-
//--- sizing; the rest (CVD/Pulse/Vol Ratio/Wall) stays informational.
//--- v31: loads ONE day's bookmap_history_YYYY-MM-DD.csv into the g_bmHist*
//--- arrays (append-mode - safe to call once per file found). Schema (see
//--- udp_listener.py's log_cvd_history()): timestamp_utc,time_wib,price,
//--- cvd_session,pulse_pct,absorption,h4_cmp,poc_price,poc_volume,
//--- vol_ratio_buy_pct,buy_vol_session,sell_vol_session,best_bid_px,
//--- best_bid_sz,best_ask_px,best_ask_sz (16 columns) - only the first 8 are
//--- used here, rest read-and-discarded (kept for future use).
//--- v52.4 schema (64 columns, see udp_listener.py's log_cvd_history()):
//--- ...ask_ice_ratio (same 24 columns as v33) then bid1_px,bid1_sz..
//--- bid10_px,bid10_sz,ask1_px,ask1_sz..ask10_px,ask10_sz (40 more columns,
//--- same near+historical merge as the live bridge file). Iceberg AND the
//--- wall ladder are now both actually replayed (previously read-and-
//--- discarded even where present in the v33 CSV) - HasLiquiditySupport()/
//--- HasIcebergSupport()/BookmapTriggerDirection() can now be exercised in
//--- Tester once enough v3 history has accumulated.
void LoadOneBookmapHistoryFile(string relPath)
{
   int handle = FileOpen(relPath, FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) return;

   // v52.24: parameterized off WALL_SLOTS_PER_SIDE instead of another hardcoded
   // magic number (was 64 -> v52.14's 84 -> this) - 24 fixed columns + (px,sz,age)
   // per wall slot per side. v52.26: +6 wall-sweep columns. v52.76: +3 mega-
   // sweep columns (mega_sweep_active/side/count), both appended at the end.
   int histTotalFields = 24 + WALL_SLOTS_PER_SIDE * 3 * 2 + 6 + 3;
   for(int i = 0; i < histTotalFields && !FileIsEnding(handle); i++) FileReadString(handle);   // skip header row

   while(!FileIsEnding(handle))
   {
      double ts = StringToDouble(FileReadString(handle));
      if(FileIsEnding(handle)) break;   // trailing blank line guard
      FileReadString(handle);                              // time_wib (display-only, skip)
      double price   = StringToDouble(FileReadString(handle));
      double cvd     = StringToDouble(FileReadString(handle));
      double pulse   = StringToDouble(FileReadString(handle));
      string absorb  = FileReadString(handle);
      FileReadString(handle);                              // h4_cmp (not used here, skip)
      double poc     = StringToDouble(FileReadString(handle));
      double pocVol  = StringToDouble(FileReadString(handle));
      for(int i = 0; i < 3 && !FileIsEnding(handle); i++) FileReadString(handle);   // vol_ratio,buy_vol,sell_vol - skip
      double val     = StringToDouble(FileReadString(handle));
      double vah     = StringToDouble(FileReadString(handle));
      for(int i = 0; i < 4 && !FileIsEnding(handle); i++) FileReadString(handle);   // best_bid_px..best_ask_sz - skip
      double bidIcePx    = StringToDouble(FileReadString(handle));
      double bidIceSz    = StringToDouble(FileReadString(handle));
      double bidIceRatio = StringToDouble(FileReadString(handle));
      double askIcePx    = StringToDouble(FileReadString(handle));
      double askIceSz    = StringToDouble(FileReadString(handle));
      double askIceRatio = StringToDouble(FileReadString(handle));

      double bidPx[WALL_SLOTS_PER_SIDE], bidSz[WALL_SLOTS_PER_SIDE], bidAge[WALL_SLOTS_PER_SIDE];
      double askPx[WALL_SLOTS_PER_SIDE], askSz[WALL_SLOTS_PER_SIDE], askAge[WALL_SLOTS_PER_SIDE];
      for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
      {
         bidPx[i]  = StringToDouble(FileReadString(handle));
         bidSz[i]  = StringToDouble(FileReadString(handle));
         bidAge[i] = StringToDouble(FileReadString(handle));   // v52.14
      }
      for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
      {
         askPx[i]  = StringToDouble(FileReadString(handle));
         askSz[i]  = StringToDouble(FileReadString(handle));
         askAge[i] = StringToDouble(FileReadString(handle));
      }
      // v52.26: sweep_side..sweep_since_sec (6 cols) - not replayed yet (see
      // g_bmSweep* globals' comment), just consumed positionally so the
      // fixed-column reader doesn't desync on the columns after them.
      for(int i = 0; i < 6 && !FileIsEnding(handle); i++) FileReadString(handle);
      // v52.76: mega_sweep_active/side/count (3 cols) - same read-and-discard
      // pattern, not replayed yet either (Mega Sweep itself is brand new
      // today - needs real accumulated data before it's worth wiring in).
      for(int i = 0; i < 3 && !FileIsEnding(handle); i++) FileReadString(handle);

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
      ArrayResize(g_bmHistBidIcePx,    idx + 1, 50000);
      ArrayResize(g_bmHistBidIceSz,    idx + 1, 50000);
      ArrayResize(g_bmHistBidIceRatio, idx + 1, 50000);
      ArrayResize(g_bmHistAskIcePx,    idx + 1, 50000);
      ArrayResize(g_bmHistAskIceSz,    idx + 1, 50000);
      ArrayResize(g_bmHistAskIceRatio, idx + 1, 50000);
      ArrayResize(g_bmHistBidPx, idx + 1, 50000);
      ArrayResize(g_bmHistBidSz, idx + 1, 50000);
      ArrayResize(g_bmHistAskPx, idx + 1, 50000);
      ArrayResize(g_bmHistAskSz, idx + 1, 50000);
      ArrayResize(g_bmHistBidAge, idx + 1, 50000);   // v52.14
      ArrayResize(g_bmHistAskAge, idx + 1, 50000);

      g_bmHistTime[idx]      = (datetime)ts;
      g_bmHistBmPrice[idx]   = price;
      g_bmHistCvd[idx]       = cvd;
      g_bmHistPulse[idx]     = pulse;
      g_bmHistAbsorb[idx]    = absorb;
      g_bmHistPocPrice[idx]  = poc;
      g_bmHistPocVolume[idx] = pocVol;
      g_bmHistVal[idx]       = val;
      g_bmHistVah[idx]       = vah;
      g_bmHistBidIcePx[idx]    = bidIcePx;
      g_bmHistBidIceSz[idx]    = bidIceSz;
      g_bmHistBidIceRatio[idx] = bidIceRatio;
      g_bmHistAskIcePx[idx]    = askIcePx;
      g_bmHistAskIceSz[idx]    = askIceSz;
      g_bmHistAskIceRatio[idx] = askIceRatio;
      for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
      {
         g_bmHistBidPx[idx][i]  = bidPx[i];
         g_bmHistBidSz[idx][i]  = bidSz[i];
         g_bmHistAskPx[idx][i]  = askPx[i];
         g_bmHistAskSz[idx][i]  = askSz[i];
         g_bmHistBidAge[idx][i] = bidAge[i];   // v52.14
         g_bmHistAskAge[idx][i] = askAge[i];
      }
      g_bmHistCount++;
   }
   FileClose(handle);
}

//--- v31: scans Common\Files\bookmap_history\ for every bookmap_history_*.csv
//--- (FileFindNext returns them in filename order, which sorts chronologically
//--- since the date is ISO YYYY-MM-DD) and loads them all once at OnInit() -
//--- only relevant in Strategy Tester/Optimization, never called live (the
//--- live path keeps using the always-fresh single-row bridge file instead).
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
   ArrayResize(g_bmHistBidIcePx, 0);
   ArrayResize(g_bmHistBidIceSz, 0);
   ArrayResize(g_bmHistBidIceRatio, 0);
   ArrayResize(g_bmHistAskIcePx, 0);
   ArrayResize(g_bmHistAskIceSz, 0);
   ArrayResize(g_bmHistAskIceRatio, 0);
   ArrayResize(g_bmHistBidPx, 0);
   ArrayResize(g_bmHistBidSz, 0);
   ArrayResize(g_bmHistAskPx, 0);
   ArrayResize(g_bmHistAskSz, 0);
   ArrayResize(g_bmHistBidAge, 0);   // v52.14
   ArrayResize(g_bmHistAskAge, 0);

   string fname;
   long search = FileFindFirst(BM_HIST_DIR + BM_HIST_GLOB, fname, FILE_COMMON);
   if(search == INVALID_HANDLE)
   {
      Print("BookmapHistoryReplay: no files found in Common\\Files\\", BM_HIST_DIR,
            " - Absorption/POC-overextend warnings will stay inactive this backtest.");
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
   Print("BookmapHistoryReplay: loaded ", g_bmHistCount, " rows from ", fileCount,
         " file(s) - covers ",
         (g_bmHistCount > 0 ? TimeToString(g_bmHistTime[0], TIME_DATE|TIME_MINUTES) : "-"),
         " to ",
         (g_bmHistCount > 0 ? TimeToString(g_bmHistTime[g_bmHistCount-1], TIME_DATE|TIME_MINUTES) : "-"));
}

//--- v31: index of the latest recorded row at or before time t (binary
//--- search - g_bmHistTime[] is chronologically sorted by construction).
//--- Returns -1 if t is before the very first recorded row.
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

//--- v31: Strategy Tester substitute for the live bridge read - looks up the
//--- historical row closest to (at or before) the CURRENT SIMULATED time and
//--- treats it exactly like a live snapshot. Only "online" for backtest date
//--- ranges that overlap with when the archive was actually being recorded
//--- (nothing before 2026-08-10, and wall/iceberg specifically only from
//--- 2026-08-17 when the v3 schema started, see LoadOneBookmapHistoryFile())
//--- - correctly stays offline outside that range, same spirit as the live
//--- path staying offline when the bridge file is stale.
//--- v52.4: wall ladder + iceberg are now replayed too (previously left
//--- untouched here) - Dadang: "wall dimanapun harus terbaca DAN harus
//--- kerecord juga agar bisa kita jadikan histori dan tune up kedepannya".
void ReadBookmapHistoryReplay()
{
   g_bookmapOnline = false;
   if(!g_bmHistLoaded) return;

   int idx = FindBookmapHistoryIndex(TimeCurrent());
   if(idx < 0) return;

   double ageSec = (double)TimeCurrent() - (double)g_bmHistTime[idx];
   if(ageSec > InpBookmapStaleSec * 4.0) return;   // logged every 5s live - wider tolerance than the live staleness check to absorb gaps

   g_bookmapOnline     = true;
   g_bookmapPrice      = g_bmHistBmPrice[idx];
   g_bookmapCvd        = g_bmHistCvd[idx];
   g_bookmapPulsePct   = g_bmHistPulse[idx];
   g_bookmapAbsorption = g_bmHistAbsorb[idx];
   g_bookmapPocPrice   = g_bmHistPocPrice[idx];
   g_bookmapPocVolume  = g_bmHistPocVolume[idx];
   g_bookmapVal        = g_bmHistVal[idx];
   g_bookmapVah        = g_bmHistVah[idx];
   g_bookmapBidIcePx    = g_bmHistBidIcePx[idx];
   g_bookmapBidIceSz    = g_bmHistBidIceSz[idx];
   g_bookmapBidIceRatio = g_bmHistBidIceRatio[idx];
   g_bookmapAskIcePx    = g_bmHistAskIcePx[idx];
   g_bookmapAskIceSz    = g_bmHistAskIceSz[idx];
   g_bookmapAskIceRatio = g_bmHistAskIceRatio[idx];
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      g_bookmapBidPx[i]  = g_bmHistBidPx[idx][i];
      g_bookmapBidSz[i]  = g_bmHistBidSz[idx][i];
      g_bookmapAskPx[i]  = g_bmHistAskPx[idx][i];
      g_bookmapAskSz[i]  = g_bmHistAskSz[idx][i];
      g_bookmapBidAge[i] = g_bmHistBidAge[idx][i];   // v52.14
      g_bookmapAskAge[i] = g_bmHistAskAge[idx][i];
   }
}

//--- v42: macro correlation (6E Euro FX as a dollar-strength proxy), read
//--- from its OWN file. Kept separate from bookmap_live_signal.csv on
//--- purpose: that reader skips exactly totalFields header cells then reads
//--- positionally, so adding columns there would shift every field unless
//--- Python and the EA are updated in lockstep. A missing/stale file here
//--- just leaves g_macroActive=false and the panel shows "-".
//--- v43: USD FUNDAMENTAL. Dadang: "untuk tekanan CVD semuanya ikut gold,
//--- gw kan hanya butuh fundamentalnya USD, terserah data ambil dari mana,
//--- berita atau apa gitu." So this drops the order-flow angle entirely and
//--- reads two things straight out of MT5 - no Bookmap, no extra data
//--- subscription, nothing to rebuild:
//---   1. EURUSD's own CMP (same DD_CMP_Indicator doctrine as gold) -> a
//---      continuous dollar bias. EUR up = USD weak = tailwind for gold.
//---   2. MT5's built-in Economic Calendar -> the next HIGH-impact USD
//---      release and how long until it fires. This is the part that stops
//---      an entry 10 minutes before NFP/CPI, which no order-flow gauge can
//---      tell you. Also closes the "News calendar otomatis" backlog item.
//--- Calendar data isn't available in Strategy Tester and some brokers
//--- don't serve it, so every field degrades to "-" rather than failing.
int      g_hEurUsdH4     = INVALID_HANDLE;
string   g_usdBias       = "";      // WEAK / STRONG / NEUTRAL
string   g_eurDir        = "";      // source symbol's H4 CMP: BUY / SELL / WAIT

// v43.1: Dadang - "kenapa lo pakai EUR kalo mau baca DXY". Fair - and the
// assumption that the broker had no dollar index was never checked. It does:
// DXY_U6 (99.793 on H4, a real index value). Two caveats found by testing it:
//   - it has NO live tick stream (bid/ask both 0) - only bar data updates,
//     so it can go stale in a way EURUSD never does;
//   - the name carries the contract month, so DXY_U6 becomes DXY_Z6 at the
//     September roll and any hardcoded symbol silently dies.
// Hence: auto-detect the current DXY_* contract, use it when its bars are
// fresh, and fall back to EURUSD otherwise. The two read OPPOSITE ways -
// DXY up means a STRONG dollar, EURUSD up means a WEAK one - so the source
// carries an inversion flag rather than the mapping being assumed anywhere.
string   g_usdSymbol     = "";      // whichever symbol is actually in use
bool     g_usdInverted   = false;   // true when the symbol rises as USD weakens (EURUSD)
string   g_usdCandidate  = "";      // DXY contract found at init, adopted once its history loads
string   g_usdNextEvent  = "";
int      g_usdNextMins   = -1;      // minutes until next high-impact USD event
datetime g_lastCalScan   = 0;

void ReadUsdFundamental()
{
   //--- 0. Upgrade to the real dollar index once its history has loaded ---
   // (see the note in OnInit: MT5 downloads a newly-selected symbol's bars
   // asynchronously, so this can only be decided after the fact)
   if(g_usdCandidate != "" && g_usdSymbol != g_usdCandidate && iBars(g_usdCandidate, PERIOD_H4) >= 100)
   {
      int hNew = iCustom(g_usdCandidate, PERIOD_H4, "DD_CMP_Indicator");
      if(hNew != INVALID_HANDLE)
      {
         if(g_hEurUsdH4 != INVALID_HANDLE) IndicatorRelease(g_hEurUsdH4);
         g_hEurUsdH4   = hNew;
         g_usdSymbol   = g_usdCandidate;
         g_usdInverted = false;   // DXY rises when the dollar strengthens
         Print("USD fundamental source upgraded to ", g_usdSymbol, " (direct: naik = USD kuat)");
      }
   }

   //--- 1. Dollar bias from the chosen source symbol's H4 CMP ------------
   g_eurDir  = "";
   g_usdBias = "";
   if(g_hEurUsdH4 != INVALID_HANDLE)
   {
      datetime t;
      g_eurDir = ReadCMP(g_hEurUsdH4, t);
      // DXY rising = strong dollar; EURUSD rising = weak dollar. g_usdInverted
      // encodes which of the two we're actually reading.
      if(g_eurDir == "BUY")       g_usdBias = g_usdInverted ? "WEAK"   : "STRONG";
      else if(g_eurDir == "SELL") g_usdBias = g_usdInverted ? "STRONG" : "WEAK";
      else                        g_usdBias = "NEUTRAL";

      // DXY_* has no tick stream, so its bars can quietly stop advancing
      // while everything else keeps running. Anything older than two H4
      // bars is treated as no reading at all rather than a stale opinion.
      datetime lastBar = (datetime)SeriesInfoInteger(g_usdSymbol, PERIOD_H4, SERIES_LASTBAR_DATE);
      if(lastBar > 0 && (TimeCurrent() - lastBar) > 2 * PeriodSeconds(PERIOD_H4))
      {
         g_usdBias = "";
         g_eurDir  = "STALE";
      }
   }

   //--- 2. Economic Calendar: next HIGH-impact USD release ----------------
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION)) return;
   if(TimeCurrent() - g_lastCalScan < 60) return;   // calendar barely changes; scan once a minute
   g_lastCalScan = TimeCurrent();

   g_usdNextEvent = "";
   g_usdNextMins  = -1;

   MqlCalendarValue values[];
   int n = CalendarValueHistory(values, TimeCurrent(), TimeCurrent() + 3 * 86400, NULL, "USD");
   if(n <= 0) return;   // broker doesn't serve calendar data - stays "-"

   datetime bestTime = 0;
   for(int i = 0; i < n; i++)
   {
      if(values[i].time <= TimeCurrent()) continue;          // already released
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev)) continue;
      if(ev.importance != CALENDAR_IMPORTANCE_HIGH) continue;
      if(bestTime == 0 || values[i].time < bestTime)
      {
         bestTime = values[i].time;
         g_usdNextEvent = ev.name;
      }
   }
   if(bestTime > 0)
      g_usdNextMins = (int)((bestTime - TimeCurrent()) / 60);

   ExportTodayCalendar();
}

// v52.86 - Today's Catalyst export for the new "News & Catalyst" web tab.
// Dadang: "nyedot juga kapan akan ada news hari ini yang flag merah kayak
// FOMC PPI CPI dll." Same CalendarValueHistory/CalendarEventById pattern
// as g_usdNextEvent above, just widened from "single nearest upcoming" to
// "every HIGH-impact USD event today" and written out for the web to read
// (MQL5 can only write to its own Common\Files sandbox, same reason
// sultan_status.json needs sultan_dashboard_server.py to proxy it across).
// Deliberately just name/time/released - NOT actual/forecast/previous
// values, which MQL5's calendar API stores as scaled fixed-point longs
// that need per-event digit precision to decode correctly; safer to ship
// the reliable half now than guess at the scaling and show a wrong number.
void ExportTodayCalendar()
{
   datetime dayStart = iTime(_Symbol, PERIOD_D1, 0);
   if(dayStart == 0) return;
   datetime dayEnd = dayStart + 86400;

   MqlCalendarValue todayValues[];
   int nToday = CalendarValueHistory(todayValues, dayStart, dayEnd, NULL, "USD");

   string json = "[";
   bool first = true;
   for(int i = 0; i < nToday; i++)
   {
      MqlCalendarEvent ev;
      if(!CalendarEventById(todayValues[i].event_id, ev)) continue;
      if(ev.importance != CALENDAR_IMPORTANCE_HIGH) continue;
      if(!first) json += ",";
      first = false;
      bool released = todayValues[i].time <= TimeCurrent();
      int minsUntil = (int)((todayValues[i].time - TimeCurrent()) / 60);
      json += StringFormat("{\"name\":\"%s\",\"time\":\"%s\",\"released\":%s,\"mins_until\":%d}",
                            ev.name, TimeToString(todayValues[i].time, TIME_MINUTES),
                            released ? "true" : "false", minsUntil);
   }
   json += "]";

   int handle = FileOpen("today_calendar.json.tmp", FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE) return;
   FileWriteString(handle, json);
   FileClose(handle);
   FileDelete("today_calendar.json", FILE_COMMON);
   FileMove("today_calendar.json.tmp", FILE_COMMON, "today_calendar.json", FILE_COMMON);
}

bool     g_macroActive   = false;
string   g_macroDirection = "";
string   g_macroUsd      = "";
string   g_macroVerdict  = "";
double   g_macroCvd      = 0.0;
bool     g_macroFlowOk   = false;

void ReadMacroCorrelation()
{
   g_macroActive = false;
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION)) return;

   int h = FileOpen("macro_correlation.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(h == INVALID_HANDLE) return;

   for(int i = 0; i < 10 && !FileIsEnding(h); i++) FileReadString(h);   // skip header (10 cols)
   if(FileIsEnding(h)) { FileClose(h); return; }

   double ts        = StringToDouble(FileReadString(h));
   string activeStr = FileReadString(h);
   FileReadString(h);                                    // alias - not shown on the panel
   FileReadString(h);                                    // price - EUR quote, not useful next to gold
   FileReadString(h);                                    // change
   string dir       = FileReadString(h);
   string usd       = FileReadString(h);
   double cvd       = StringToDouble(FileReadString(h));
   string flowStr   = FileReadString(h);
   string verdict   = FileReadString(h);
   FileClose(h);

   // Same staleness rule as the main bridge - a file left behind by a dead
   // listener must not read as live.
   double ageSec = (double)TimeCurrent() - ts;
   if(ageSec > InpBookmapStaleSec || activeStr != "1") return;

   g_macroActive    = true;
   g_macroDirection = dir;
   g_macroUsd       = usd;
   g_macroCvd       = cvd;
   g_macroFlowOk    = (flowStr == "1");
   g_macroVerdict   = verdict;
}

//+------------------------------------------------------------------+
//| v44: CONVICTION SCORE                                            |
//| Dadang: "tugas lo buat EA dan web py gw buat kesimpulannya dengan|
//| data yang ada."                                                  |
//|                                                                   |
//| Deliberately NOT a second opinion on direction. The direction is  |
//| whatever M30's own CMP says - that is the doctrine and it stays   |
//| untouched. What this adds is: of the independent factors already  |
//| being collected, how many currently agree with that direction,    |
//| and - more useful - which ones don't. A trader who knows what     |
//| he is fighting sizes differently than one who only sees a verdict.|
//|                                                                   |
//| DISPLAY ONLY. Nothing here gates an entry, changes a lot size or  |
//| touches TryOpen(). Runs for a while first so its output can be    |
//| compared against real outcomes before it is ever trusted with     |
//| money.                                                            |
//+------------------------------------------------------------------+
string   g_convDir      = "";
int      g_convScore    = 0;
int      g_convMax      = 0;
string   g_convGrade    = "";
string   g_convMode     = "";   // AWAL / SCALP / BERKEMBANG / TREND / FULL CHAIN - depth of the chain
int      g_chainLen     = 0;    // how many rungs, M5 upward, have converted
string   g_chainDone    = "";   // e.g. "M5>M15>M30"
string   g_chainNext    = "";   // the first rung that hasn't flipped yet
string   g_chainPending = "";   // all rungs not yet converted
int      g_flowScore    = 0;    // order-flow / macro confirmation on top of the chain
int      g_flowMax      = 0;
string   g_convAgainst1 = "";
string   g_convAgainst2 = "";
string   g_convAgainst3 = "";
int      g_convAgainstN = 0;   // total opposing factors, including any beyond the 3 shown

// v44.2: was 2 slots, which hid the third blocker exactly when it mattered -
// at 5/8 three factors are failing but only two were ever printed, so the
// question "what would make this KUAT" was unanswerable from the panel.
// v52.1: shared by ComputeConviction() (display factor #4) and TryOpen()
// (lot-size warning, same pattern as Absorption/POC) - true if a resting
// wall OR an active iceberg refill sits on the ENTRY side (bid for BUY /
// ask for SELL) within nearDist of price. nearDist scales with volatility
// (ATR*0.3, floor $3) rather than a fixed number, same as the "wall
// blocking the path" check right next to it in ComputeConviction().
// v52.2: iceberg ALONE, split out from HasLiquiditySupport() below - an
// active refilling order is qualitatively stronger evidence than a resting
// wall (a wall can be pulled/spoofed in an instant; an iceberg has already
// proven it keeps coming back after being hit), so BookmapStrongConfirm()
// treats it as sufficient on its own rather than just one of several inputs.
// v52.13: Dadang - "lo harus ambil rata2 misal 30 menit atau 5 menit...
// siapa yang dominan sehingga itu yang kita anggap arah entri kita." Plain
// continuous-time EMA (dt-based decay, not a fixed sample count, since
// ticks don't arrive at a fixed rate): after InpBookmapCvdSmoothMin minutes
// of no new data the EMA has moved ~63% toward whatever's been happening
// since - a genuine "who's been dominant over the last N minutes" read,
// not an instantaneous per-tick snapshot. Called once per tick from
// OnTick() (before anything reads g_bmCvdEma), not from inside the
// direction-check functions themselves, so it updates exactly once per
// tick regardless of how many places read the result afterward.
void UpdateCvdEma()
{
   datetime now = TimeCurrent();
   if(g_bmCvdEmaTime == 0) { g_bmCvdEma = g_bookmapCvd; g_bmCvdEmaTime = now; return; }
   double dtSec = (double)(now - g_bmCvdEmaTime);
   if(dtSec <= 0) return;   // same tick, nothing to advance
   double windowSec = MathMax(1.0, InpBookmapCvdSmoothMin * 60.0);
   double decay = MathExp(-dtSec / windowSec);
   g_bmCvdEma = decay * g_bmCvdEma + (1.0 - decay) * g_bookmapCvd;
   g_bmCvdEmaTime = now;
}

bool HasIcebergSupport(bool buy, double price)
{
   double bmOffset = (g_bookmapPrice > 0) ? (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice) : 0.0;
   double atrBuf[1]; double atr = 0.0;
   if(g_hATR != INVALID_HANDLE && CopyBuffer(g_hATR, 0, 0, 1, atrBuf) > 0) atr = atrBuf[0];
   double nearDist = MathMax(3.0, atr * 0.3);
   double icePx = buy ? g_bookmapBidIcePx : g_bookmapAskIcePx;
   return (icePx > 0 && MathAbs((icePx + bmOffset) - price) <= nearDist);
}

// v52.14: wall must have actually PERSISTED (>= InpWallMinAgeSec) before it
// counts - a wall that just appeared could be "bait" about to get pulled
// the moment price gets close (see feedback_wall_persistence_manual_confirmation
// memory - Dadang already validates this manually: "wall besar & gak ilang
// = sinyal asli").
//
// v52.19: Dadang - "gw itidak bilang 10 lot bro gw mau semua wall kelihatan
// untuk area ya pasti yang kuat wall besar to bro" - market_data_engine.py's
// wall_threshold_size=10 is a VISIBILITY floor (show everything), NOT a
// "this counts as real support" bar - InpWallMinSizeLot (30) is the
// DECISION-grade bar.
//
// v52.20: Dadang - "makanya harus baca super jauh agar tau wall dimana dan
// udah berapa lama di sana nya bro... bukan hanya di sekitaran harga yang
// live kan" - this was still only checking slot[0] (the single NEAREST
// wall), throwing away the other 9 slots per side (5 near + 5 historical/
// far, already loaded via _merge_wall_slots() on the Python side and sent
// to MT5 since v29/v52.4) that this exact function has access to. Now
// scans ALL WALL_SLOTS_PER_SIDE slots on the entry side and accepts ANY
// one that qualifies (age + size), within InpWallSearchRangeUsd (wider than
// the old ~$3-5 "basically touching" distance - Dadang wants the search to
// actually reach out, not just glance at what's immediately under price).
bool HasLiquiditySupport(bool buy, double price)
{
   double bmOffset = (g_bookmapPrice > 0) ? (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice) : 0.0;

   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      double wallPxRaw = buy ? g_bookmapBidPx[i] : g_bookmapAskPx[i];
      if(wallPxRaw <= 0) continue;
      double wallPx  = wallPxRaw + bmOffset;
      double wallSz  = buy ? g_bookmapBidSz[i]  : g_bookmapAskSz[i];
      double wallAge = buy ? g_bookmapBidAge[i] : g_bookmapAskAge[i];
      if(MathAbs(wallPx - price) <= InpWallSearchRangeUsd &&
         wallAge >= InpWallMinAgeSec && wallSz >= InpWallMinSizeLot)
         return true;
   }
   return HasIcebergSupport(buy, price);
}

// v52.41: samples g_bookmapPocPrice once per REAL minute (wall-clock, not
// chart bars) into a ring buffer - same mechanism as g_cvdMinuteSamples.
// Called from ReadBookmapBridge() every cycle; the minute-bucket check
// makes repeat calls within the same minute a no-op.
void SamplePocIfNewMinute()
{
   if(g_bookmapPocPrice <= 0) return;
   MqlDateTime dtNow;
   TimeToStruct(TimeGMT(), dtNow);
   int curMinuteBucket = dtNow.hour * 60 + dtNow.min;
   if(curMinuteBucket == g_lastPocSampleMinute) return;
   g_lastPocSampleMinute = curMinuteBucket;
   for(int i = 0; i < CVD_HIST_LEN - 1; i++) g_pocMinuteSamples[i] = g_pocMinuteSamples[i + 1];
   g_pocMinuteSamples[CVD_HIST_LEN - 1] = g_bookmapPocPrice;
   if(g_pocSampleCount < CVD_HIST_LEN) g_pocSampleCount++;
}

// v52.41 - Dadang, watching POC move live: "poc ini ternyata bisa langsung
// pindah ke atas atau ke bawah ini artinya apa" -> explained: POC migrating
// WITH the trend = real value acceptance (strong), POC staying put while
// price runs = fragile/unaccepted move. Compares the latest minute-sampled
// POC against a sample from `lookbackMin` minutes ago - true if it moved at
// least InpPocMigrateUsd (Bookmap/GCZ6 scale, same units as g_bookmapPocPrice)
// in the `dir` direction. Not enough history yet -> false (don't claim
// migration without evidence).
bool IsPocMigrating(string dir, int lookbackMin)
{
   if(g_pocSampleCount < 2) return false;
   int back = MathMin(lookbackMin, g_pocSampleCount - 1);
   double oldPoc = g_pocMinuteSamples[CVD_HIST_LEN - 1 - back];
   double newPoc = g_pocMinuteSamples[CVD_HIST_LEN - 1];
   if(oldPoc <= 0 || newPoc <= 0) return false;
   double move = newPoc - oldPoc;
   if(dir == "BUY")  return move >=  InpPocMigrateUsd;
   if(dir == "SELL") return move <= -InpPocMigrateUsd;
   return false;
}

// v52.15: shared with WriteSultanStatus()'s own regime line (same formula -
// 100% of H4/M30/M5 agreeing = TRENDING, else SIDEWAYS) - extracted so
// BookmapLocationOk() below can use the identical definition instead of a
// second copy that could drift.
// v52.41 - Dadang: "berarti ini juga perlu lo rubah bro" (pointing at
// "Regime: SIDEWAYS" right after we discussed POC migration) - CMP
// alignment alone used to be sufficient for TRENDING; now ALSO requires POC
// to have actually migrated in g_masterDir's direction (IsPocMigrating()
// above) - a STRICTER bar than before, not a looser one. This feeds
// BookmapLocationOk() (a real entry gate for standalone Bookmap-only
// trades), so the practical effect is: fewer moments get classified
// TRENDING, which can only make that gate MORE conservative (rejects more
// overextended-location entries, never lets through ones the old formula
// would have blocked) - a safe direction to ship live without a full
// backtest cycle, unlike a loosening change would have been. No Bookmap POC
// data/history yet -> falls back to CMP-alignment-only (same as before this
// change), so this never blocks Regime entirely just because Bookmap is
// still warming up.
bool IsRegimeTrending()
{
   int buyCount = 0, sellCount = 0, validCount = 0;
   if(g_masterDir      == "BUY") buyCount++; else if(g_masterDir      == "SELL") sellCount++;
   if(g_scalpMasterDir == "BUY") buyCount++; else if(g_scalpMasterDir == "SELL") sellCount++;
   if(g_scalpEntryDir  == "BUY") buyCount++; else if(g_scalpEntryDir  == "SELL") sellCount++;
   validCount = (g_masterDir != "WAIT" ? 1 : 0) + (g_scalpMasterDir != "WAIT" ? 1 : 0) + (g_scalpEntryDir != "WAIT" ? 1 : 0);
   double alignmentPct = (validCount > 0) ? (MathMax(buyCount, sellCount) / 3.0 * 100.0) : 0.0;
   bool cmpAligned = alignmentPct >= 99.9;
   if(!cmpAligned) return false;

   if(g_bookmapPocPrice <= 0 || g_pocSampleCount < 2) return cmpAligned;   // no POC history yet - CMP-only fallback
   return IsPocMigrating(g_masterDir, InpPocMigrateLookbackMin);
}

// v52.6: 5th read - location vs POC (Dadang 2026-08-17: "dari 5 urutan itu
// bisa gak kalo masukin ke ea dan web gw sebagai narasi tapi di ea dia entri
// beneran" - the narrated 5-step read [wall/CVD/absorption/iceberg/
// location] must be the SAME thing that decides real entries, not just a
// look-alike explanation). Same overextension math already used as a lot-
// size warning in TryOpen() (InpPocOverextendUsd) - reused here as an
// outright DISQUALIFIER for a Bookmap-only trigger (no CMP backup to lean
// on, so chasing an already-extended move is a strictly worse idea here
// than for a CMP-confirmed entry, where it only earns a smaller lot).
//
// v52.15: Dadang - "sekarang lo browsing sebagai ahli" - volume-profile
// trading practice treats an extended move DIFFERENTLY depending on regime:
// SIDEWAYS/balanced -> fade it (mean-reversion, the ONLY behavior this
// function had before). TRENDING -> a close beyond VAH/VAL is CONTINUATION,
// not something to avoid. Only relax the block when BOTH hold: regime is
// genuinely trending AND the trade direction agrees with H4 (g_masterDir) -
// this can never green-light a countertrend chase, only a trend-following
// one. Toggle-able (InpLocationRegimeAware) so the old strict-always-block
// behavior is one click away if this doesn't earn its keep.
bool BookmapLocationOk(bool buy)
{
   if(g_bookmapPocPrice <= 0 || g_bookmapPrice <= 0) return true;   // no data yet - don't block on it
   double bmOffset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   double pocMt5   = g_bookmapPocPrice + bmOffset;
   double px       = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double distFromPoc = buy ? (px - pocMt5) : (pocMt5 - px);
   if(distFromPoc < InpPocOverextendUsd) return true;   // not extended - always fine

   if(InpLocationRegimeAware)
   {
      string dir = buy ? "BUY" : "SELL";
      if(IsRegimeTrending() && g_masterDir == dir) return true;   // trend continuation, not a chase
   }
   return false;   // sideways market, or extended AGAINST H4 - still overextended/risky
}

// v52.2: Dadang 2026-08-17 - "EA tidak boleh takut entri apa lagi jika
// bookmap data mendukung karena satu-satunya data real kita hanya bookmap."
// Three INDEPENDENT live order-flow facts (CVD direction, Absorption
// actually FAVORING this side - not merely "not against" - and Liquidity
// Support): needs at least 2 of 3 to call it "strongly confirmed", because
// any single one alone can be noise. An iceberg specifically is the
// exception - it qualifies alone (see HasIcebergSupport() above).
bool BookmapStrongConfirm(bool buy, double price)
{
   int hits = 0;
   if((buy && g_bmCvdEma > 0) || (!buy && g_bmCvdEma < 0)) hits++;   // v52.13: EMA, not raw tick
   bool absorptionFavors = (buy && g_bookmapAbsorption == "SELLER_ABSORBED") ||
                           (!buy && g_bookmapAbsorption == "BUYER_ABSORBED");
   if(absorptionFavors) hits++;
   if(HasLiquiditySupport(buy, price)) hits++;
   return (hits >= 2) || HasIcebergSupport(buy, price);
}

void AddAgainst(string reason)
{
   g_convAgainstN++;
   if(g_convAgainst1 == "")      g_convAgainst1 = reason;
   else if(g_convAgainst2 == "") g_convAgainst2 = reason;
   else if(g_convAgainst3 == "") g_convAgainst3 = reason;
}

void ComputeConviction()
{
   g_convScore = 0; g_convMax = 0;
   g_convGrade = ""; g_convMode = "";
   g_chainLen = 0; g_chainDone = ""; g_chainNext = ""; g_chainPending = "";
   g_flowScore = 0; g_flowMax = 0;
   g_convAgainst1 = ""; g_convAgainst2 = ""; g_convAgainst3 = ""; g_convAgainstN = 0;

   //=== THE CHAIN ITSELF ===================================================
   // v45: Dadang, describing the mechanic the whole system is named after:
   //   "kita akan sell jika M5 BO sell terus, dan tiap bisa flip TF atasnya
   //    makin kuat. Contoh M5 sell terus berhasil merubah M15 jadi sell maka
   //    skor tambah, jika M30 juga ikut sell maka tambah lagi, jika H1 juga
   //    ikut tambah lagi, dan seterusnya."
   //
   // So strength is not "how many timeframes happen to agree" measured as a
   // static snapshot - it is HOW FAR UP THE LADDER the conversion has
   // actually propagated, starting from M5 and climbing. That reframes a
   // counter-daily setup correctly: it isn't a weak trade, it's an EARLY one.
   // The chain breaks at the first timeframe that hasn't converted yet, and
   // that timeframe is the next target - which is exactly the thing worth
   // watching, so it's surfaced by name.
   string tfName[6] = {"M5", "M15", "M30", "H1", "H4", "D1"};
   int    tfHandle[6];
   tfHandle[0] = g_hScalpEntry;    // M5  - where the chain starts
   tfHandle[1] = g_hExportM15;
   tfHandle[2] = g_hScalpMaster;   // M30
   tfHandle[3] = g_hExportH1;
   tfHandle[4] = g_hMaster;        // H4
   tfHandle[5] = g_hExportD1;

   string tfDir[6];
   datetime tTmp;
   for(int i = 0; i < 6; i++)
      tfDir[i] = (tfHandle[i] != INVALID_HANDLE) ? ReadCMP(tfHandle[i], tTmp) : "";

   // The direction is whatever M5 - the origin of the chain - is breaking.
   g_convDir = tfDir[0];
   if(g_convDir != "BUY" && g_convDir != "SELL")
   {
      g_convDir = g_scalpMasterDir;        // fall back to M30 while M5 is undecided
      if(g_convDir != "BUY" && g_convDir != "SELL") { g_convGrade = "NO SETUP"; return; }
   }
   bool isBuy = (g_convDir == "BUY");

   // Climb: count consecutive converted rungs, stop at the first that hasn't.
   // v52.5 BUG FIX (Dadang 2026-08-17, screenshot showing "sudah: M5>M15>
   // M30>H4 / lawan: H1 belum flip" - H4 was being credited as "done" even
   // though H1, which sits BETWEEN M30 and H4 in the real ladder, hadn't
   // converted): the loop below never actually stopped at the first
   // mismatch - it kept scanning all 6 TFs and credited ANY of them that
   // happened to independently agree with g_convDir, even past a break.
   // That's exactly the "static snapshot" counting the header comment says
   // this ISN'T supposed to be. Fixed with an explicit chainBroken latch -
   // once one rung fails to convert, every rung after it (matching or not)
   // goes to pending, never back into "done".
   bool chainBroken = false;
   for(int i = 0; i < 6; i++)
   {
      if(!chainBroken && tfDir[i] == g_convDir)
      {
         g_chainLen++;
         g_chainDone += (g_chainDone == "" ? "" : ">") + tfName[i];
      }
      else
      {
         chainBroken = true;
         if(g_chainNext == "") g_chainNext = tfName[i];
         g_chainPending += (g_chainPending == "" ? "" : " ") + tfName[i];
      }
   }

   // Chain depth names the trade type. Deeper chain = the move has convinced
   // bigger timeframes = it can be given room. Shallow = take it, but quick.
   if(g_chainLen >= 5)      g_convMode = "FULL CHAIN";
   else if(g_chainLen == 4) g_convMode = "TREND";
   else if(g_chainLen == 3) g_convMode = "BERKEMBANG";
   else if(g_chainLen == 2) g_convMode = "SCALP";
   else                     g_convMode = "AWAL";

   if(g_chainNext != "")
      AddAgainst(g_chainNext + " belum flip - target berikutnya");

   //=== FLOW SUPPORT - does live order flow back the chain right now? ======
   //--- Bookmap-derived factors only count when the feed is actually live.
   if(g_bookmapOnline)
   {
      double bmOffset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
      double px = SymbolInfoDouble(_Symbol, SYMBOL_BID);

      //--- 1. Order flow (CVD) pointing the same way. v52.13: EMA-smoothed
      //--- (InpBookmapCvdSmoothMin), not the raw per-tick value - same
      //--- "who's actually dominant over the last few minutes" read used
      //--- by BookmapTriggerDirection()/BookmapStrongConfirm().
      g_flowMax++;
      if((isBuy && g_bmCvdEma > 0) || (!isBuy && g_bmCvdEma < 0)) g_flowScore++;
      else AddAgainst(StringFormat("CVD %+.0f lawan", g_bmCvdEma));

      //--- 2. No absorption working against this direction
      g_flowMax++;
      bool absorbAgainst = (isBuy  && g_bookmapAbsorption == "BUYER_ABSORBED") ||
                           (!isBuy && g_bookmapAbsorption == "SELLER_ABSORBED");
      if(!absorbAgainst) g_flowScore++;
      else AddAgainst("Absorption: " + g_bookmapAbsorption);

      //--- 3. Path to target not blocked by a wall sitting right in front.
      //--- "Right in front" scales with volatility rather than a fixed number.
      double atrBuf[1]; double atr = 0.0;
      if(g_hATR != INVALID_HANDLE && CopyBuffer(g_hATR, 0, 0, 1, atrBuf) > 0) atr = atrBuf[0];
      double nearDist = MathMax(3.0, atr * 0.3);
      double blockPx = isBuy ? (g_bookmapAskPx[0] > 0 ? g_bookmapAskPx[0] + bmOffset : 0.0)
                             : (g_bookmapBidPx[0] > 0 ? g_bookmapBidPx[0] + bmOffset : 0.0);
      double blockSz = isBuy ? g_bookmapAskSz[0] : g_bookmapBidSz[0];
      g_flowMax++;
      if(blockPx <= 0 || MathAbs(blockPx - px) > nearDist) g_flowScore++;
      else AddAgainst(StringFormat("%s wall %.0f lot di jalur", isBuy ? "Ask" : "Bid", blockSz));

      //--- 4. Liquidity support: real resting size (wall) or active refill
      //--- (iceberg) sitting on the ENTRY side near price - proof the zone is
      //--- actually being defended by real order flow, not just "CMP bilang
      //--- ini support/resistance" from historical bars. Mirror of #3 (which
      //--- checks the OPPOSING side blocking the path) - this checks the
      //--- ENTRY side backing it up. Shared with TryOpen()'s lot-size
      //--- warning via HasLiquiditySupport() - see there for the gate.
      g_flowMax++;
      if(HasLiquiditySupport(isBuy, px)) g_flowScore++;
      else AddAgainst(StringFormat("Gak ada %s wall/iceberg support deket harga", isBuy ? "bid" : "ask"));

      //--- 5. Location: chasing an already-extended move is where entries
      //--- get filled right before the pullback.
      if(g_bookmapVah > g_bookmapVal && g_bookmapVal > 0)
      {
         double vah = g_bookmapVah + bmOffset, val = g_bookmapVal + bmOffset;
         g_flowMax++;
         bool extended = (isBuy && px > vah) || (!isBuy && px < val);
         if(!extended) g_flowScore++;
         else AddAgainst(isBuy ? "Harga udah di atas VAH" : "Harga udah di bawah VAL");
      }
   }

   //--- 5. USD backdrop counts as flow support too: weak dollar behind a
   //--- gold BUY is the macro equivalent of CVD pointing the right way.
   if(g_usdBias == "WEAK" || g_usdBias == "STRONG")
   {
      g_flowMax++;
      if((isBuy && g_usdBias == "WEAK") || (!isBuy && g_usdBias == "STRONG")) g_flowScore++;
      else AddAgainst("USD " + g_usdBias + " lawan");
   }

   //--- Headline strength: the chain is what the system is built on, so it
   //--- leads. Flow is the confirmation layer on top - a deep chain with
   //--- flow against it is still worth naming as such rather than hidden
   //--- inside one averaged number.
   g_convScore = g_chainLen;
   g_convMax   = 6;
   double flowPct = (g_flowMax > 0) ? (100.0 * g_flowScore / g_flowMax) : -1.0;

   if(g_chainLen <= 1)          g_convGrade = "AWAL";
   else if(flowPct < 0)         g_convGrade = "NO FLOW";     // Bookmap offline
   else if(flowPct >= 75.0)     g_convGrade = "SIAP";
   else if(flowPct >= 50.0)     g_convGrade = "HATI-HATI";
   else                         g_convGrade = "FLOW LAWAN";

   //--- News proximity overrides everything: no chain depth survives a bad
   //--- print, and spreads blow out regardless of direction.
   if(g_usdNextMins >= 0 && g_usdNextMins <= 30)
   {
      g_convGrade = "TAHAN - NEWS";
      AddAgainst(StringFormat("Rilis USD %dm lagi", g_usdNextMins));
   }
}

void ReadBookmapBridge()
{
   g_bookmapOnline = false;
   if(!InpShowBookmapPanel)
   {
      ObjectsDeleteAll(0, WALL_PREFIX);
      return;
   }

   // v31: Strategy Tester/Optimization can't use the live bridge file (real
   // wall-clock timestamp never matches simulated time) - replay from the
   // recorded archive instead, then return (skip the live-file read below,
   // which would immediately overwrite g_bookmapOnline=false anyway).
   if(MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
   {
      ReadBookmapHistoryReplay();
      return;
   }

   int handle = FileOpen("bookmap_live_signal.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE) { ObjectsDeleteAll(0, WALL_PREFIX); return; }   // bridge never ran, or udp_listener.py isn't up

   int totalFields = 18 + WALL_SLOTS_PER_SIDE * 3 * 2 + 6 + 2 + 2 + 4;   // timestamp,price,cvd,pulse,absorption,poc_price,poc_volume,vol_ratio,buy_vol,sell_vol,val,vah,bid_ice_px,bid_ice_sz,bid_ice_ratio,ask_ice_px,ask_ice_sz,ask_ice_ratio + (bid+ask)*(px+sz+age) per slot [v52.14: +age] + sweep_side,sweep_price,sweep_size,sweep_age_sec,sweep_status,sweep_since_sec [v52.26] + footprint_buy_vol,footprint_sell_vol [v52.79] + footprint_m1_buy_vol,footprint_m1_sell_vol [v52.95] + hvn_price,hvn_volume,lvn_price,lvn_volume [v52.84]
   for(int i = 0; i < totalFields && !FileIsEnding(handle); i++) FileReadString(handle);   // skip header row
   if(FileIsEnding(handle)) { FileClose(handle); ObjectsDeleteAll(0, WALL_PREFIX); return; }

   double ts    = StringToDouble(FileReadString(handle));
   double price = StringToDouble(FileReadString(handle));   // Bookmap's OWN instrument price (GCZ6, not XAUUSD)
   double cvd     = StringToDouble(FileReadString(handle));
   double pulse   = StringToDouble(FileReadString(handle));
   string absorb  = FileReadString(handle);
   double pocPrice   = StringToDouble(FileReadString(handle));
   double pocVolume  = StringToDouble(FileReadString(handle));
   double volRatio   = StringToDouble(FileReadString(handle));
   double buyVol     = StringToDouble(FileReadString(handle));
   double sellVol    = StringToDouble(FileReadString(handle));
   double val        = StringToDouble(FileReadString(handle));
   double vah         = StringToDouble(FileReadString(handle));
   double bidIcePx    = StringToDouble(FileReadString(handle));
   double bidIceSz    = StringToDouble(FileReadString(handle));
   double bidIceRatio = StringToDouble(FileReadString(handle));
   double askIcePx    = StringToDouble(FileReadString(handle));
   double askIceSz    = StringToDouble(FileReadString(handle));
   double askIceRatio = StringToDouble(FileReadString(handle));
   double bidPx[WALL_SLOTS_PER_SIDE], bidSz[WALL_SLOTS_PER_SIDE], bidAge[WALL_SLOTS_PER_SIDE];
   double askPx[WALL_SLOTS_PER_SIDE], askSz[WALL_SLOTS_PER_SIDE], askAge[WALL_SLOTS_PER_SIDE];
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      bidPx[i]  = StringToDouble(FileReadString(handle));
      bidSz[i]  = StringToDouble(FileReadString(handle));
      bidAge[i] = StringToDouble(FileReadString(handle));   // v52.14: seconds since this wall was first seen
   }
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      askPx[i]  = StringToDouble(FileReadString(handle));
      askSz[i]  = StringToDouble(FileReadString(handle));
      askAge[i] = StringToDouble(FileReadString(handle));
   }
   // v52.26: wall SWEEP + reversal - see g_bmSweep* globals' comment.
   string sweepSide     = FileReadString(handle);
   double sweepPrice    = StringToDouble(FileReadString(handle));
   double sweepSize     = StringToDouble(FileReadString(handle));
   double sweepAgeSec   = StringToDouble(FileReadString(handle));
   string sweepStatus   = FileReadString(handle);
   double sweepSinceSec = StringToDouble(FileReadString(handle));
   // v52.79: near-price footprint (buy/sell volume actually TRADED at the
   // current Bookmap price, rolling window - see udp_listener.py's
   // write_mt5_bridge_file() comment). Raw buy/sell volumes, not a
   // pre-computed ratio - matches convention of buy_vol/sell_vol above.
   double footBuyVol  = StringToDouble(FileReadString(handle));
   double footSellVol = StringToDouble(FileReadString(handle));
   // v52.95: M1 (time-scoped, all prices, last 60s) footprint - Dadang:
   // "footprint itu m1 aja dari bookmap nya bro supaya gw tau dari m1
   // bahwa seller atau buyer mulain masuk". Informational only.
   double footM1BuyVol  = StringToDouble(FileReadString(handle));
   double footM1SellVol = StringToDouble(FileReadString(handle));
   // v52.84: HVN/LVN nearest to current price - see g_bookmapHvnPrice comment.
   double hvnPrice  = StringToDouble(FileReadString(handle));
   double hvnVolume = StringToDouble(FileReadString(handle));
   double lvnPrice  = StringToDouble(FileReadString(handle));
   double lvnVolume = StringToDouble(FileReadString(handle));
   FileClose(handle);

   // v24 fix: use MathAbs() instead of requiring ageSec>=0 - the old check
   // rejected EVERYTHING if TimeGMT() ever lagged slightly behind Python's
   // system clock (ageSec goes negative), no matter how large
   // InpBookmapStaleSec was set. Small clock skew either direction should
   // still count as "fresh" - only genuinely stale/old data (large positive
   // gap) or a backtest (huge gap, real timestamp vs simulated time) should
   // be rejected.
   double ageSec = (double)TimeGMT() - ts;
   if(MathAbs(ageSec) > InpBookmapStaleSec) { ObjectsDeleteAll(0, WALL_PREFIX); return; }   // stale/offline/backtest

   g_bookmapAgeMs      = MathAbs(ageSec) * 1000.0;   // v34: for the SULTAN dashboard's bridge latency display
   g_bookmapOnline     = true;
   g_bookmapPrice      = price;
   g_bookmapCvd        = cvd;
   g_bookmapPulsePct   = pulse;
   g_bookmapAbsorption = absorb;
   g_bookmapPocPrice       = pocPrice;
   g_bookmapPocVolume      = pocVolume;
   g_bookmapVolRatioBuyPct = volRatio;
   g_bookmapBuyVolSession  = buyVol;
   g_bookmapSellVolSession = sellVol;
   g_bookmapVal            = val;
   g_bookmapVah            = vah;
   g_bookmapBidIcePx       = bidIcePx;
   g_bookmapBidIceSz       = bidIceSz;
   g_bookmapBidIceRatio    = bidIceRatio;
   g_bookmapAskIcePx       = askIcePx;
   g_bookmapAskIceSz       = askIceSz;
   g_bookmapAskIceRatio    = askIceRatio;
   ArrayCopy(g_bookmapBidPx, bidPx);
   ArrayCopy(g_bookmapBidSz, bidSz);
   ArrayCopy(g_bookmapAskPx, askPx);
   ArrayCopy(g_bookmapAskSz, askSz);
   ArrayCopy(g_bookmapBidAge, bidAge);   // v52.14
   ArrayCopy(g_bookmapAskAge, askAge);
   g_bmSweepSide     = sweepSide;     // v52.26
   g_bmSweepPrice    = sweepPrice;
   g_bmSweepSize     = sweepSize;
   g_bmSweepAgeSec   = sweepAgeSec;
   g_bmSweepStatus   = sweepStatus;
   g_bmSweepSinceSec = sweepSinceSec;
   g_bookmapFootBuyVol  = footBuyVol;    // v52.79
   g_bookmapFootSellVol = footSellVol;
   g_bookmapFootM1BuyVol  = footM1BuyVol;    // v52.95
   g_bookmapFootM1SellVol = footM1SellVol;
   g_bookmapHvnPrice  = hvnPrice;    // v52.84
   g_bookmapHvnVolume = hvnVolume;
   g_bookmapLvnPrice  = lvnPrice;
   g_bookmapLvnVolume = lvnVolume;
   UpdateReloadLevels(price);   // v52.84 - must run BEFORE UpdateWallLines()/WallEatRate() below, uses its own dedicated prev-snapshot so order vs those doesn't actually matter, but keeping it here alongside the other bookmap-derived updates
   SamplePocIfNewMinute();   // v52.41 - feeds IsPocMigrating()/IsRegimeTrending()
   // v52.34: zones computed+drawn FIRST - UpdateWallLines() reads
   // g_bidClustered[]/g_askClustered[] (filled by UpdateWallZones()) to
   // decide which individual wall labels to skip.
   UpdateWallZones();
   UpdateWallLines();
   UpdatePocLine();
   UpdateValueAreaLines();
   UpdateIcebergLines();
   UpdateSweepMarker();
}

//+------------------------------------------------------------------+
//| v53: zones_v2.csv - one line per zone, no header (variable row     |
//| count) - side,lo,hi,wall_count,total_lot,status,retest_count,      |
//| absorption_hits,score. Written by bookmap-bridge-v2's               |
//| bookmap_addon_v2.py (a SEPARATE addon from bookmap_bridge.py/       |
//| bookmap_addon.py above - different pipeline, different file,        |
//| already MT5-price-scale). Missing/unreadable file just means that   |
//| addon isn't running - g_zoneDataAvailable=false tells callers to    |
//| fall back to their own tolerance-band logic, same "degrade, don't   |
//| block" pattern as every other optional Bookmap-derived feature.     |
//+------------------------------------------------------------------+
void ReadZonesCsv()
{
   int handle = FileOpen("zones_v2.csv", FILE_READ | FILE_CSV | FILE_COMMON | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      g_zoneCount = 0;
      g_zoneDataAvailable = false;
      return;
   }

   ArrayResize(g_zoneSide, 0);
   ArrayResize(g_zoneLo, 0);
   ArrayResize(g_zoneHi, 0);
   ArrayResize(g_zoneStatus, 0);
   ArrayResize(g_zoneScore, 0);
   ArrayResize(g_zoneWallCount, 0);
   ArrayResize(g_zoneTotalLot, 0);
   ArrayResize(g_zoneRetest, 0);
   ArrayResize(g_zoneAbsorb, 0);
   int n = 0;

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

      ArrayResize(g_zoneSide, n + 1);      g_zoneSide[n]      = side;
      ArrayResize(g_zoneLo, n + 1);        g_zoneLo[n]        = lo;
      ArrayResize(g_zoneHi, n + 1);        g_zoneHi[n]        = hi;
      ArrayResize(g_zoneStatus, n + 1);    g_zoneStatus[n]    = status;
      ArrayResize(g_zoneScore, n + 1);     g_zoneScore[n]     = score;
      ArrayResize(g_zoneWallCount, n + 1); g_zoneWallCount[n] = wallCount;
      ArrayResize(g_zoneTotalLot, n + 1);  g_zoneTotalLot[n]  = totalLot;
      ArrayResize(g_zoneRetest, n + 1);    g_zoneRetest[n]    = retestCount;
      ArrayResize(g_zoneAbsorb, n + 1);    g_zoneAbsorb[n]    = absorptionHits;
      n++;
   }
   FileClose(handle);
   g_zoneCount = n;
   g_zoneDataAvailable = true;
}

//+------------------------------------------------------------------+
//| Draws every SND zone directly on THIS chart - Dadang: "kita buat V2 |
//| ini upgrade bukan membuang isi v1... mana zone yang kita bangun     |
//| tadi". The zone data was already being read for Fusion H1/H4's      |
//| entry check above; this makes it VISIBLE on the same chart/EA       |
//| instead of living only in the (separate, now redundant) standalone  |
//| ZoneEngine_v2.mq5 preview EA - one EA, sees zones AND trades off     |
//| them, matching how he actually wants to use this.                   |
//|                                                                       |
//| Same nearest-N-per-side cap + score filter as the standalone EA had -|
//| ported directly, same "gak sesak" fix applies here too.              |
//+------------------------------------------------------------------+
string ZoneStatusID(string status)
{
   if(status == "FRESH")    return "BARU";
   if(status == "ACTIVE")   return "AKTIF";
   if(status == "TESTED")   return "DIUJI";
   if(status == "WEAKENED") return "AUS";
   return status;
}
string ZoneStrengthID(double score) { return (score >= 60) ? "KUAT" : (score >= 30 ? "SEDANG" : "LEMAH"); }

// v53.14: full rewrite per Dadang's 21-section visual spec - "CHART HARUS
// BISA DIBACA DALAM 2-3 DETIK... DATA ZONE != VISUAL ZONE". Only the
// nearest zone per side (rank 0 = S1/D1) draws as a solid filled box;
// everything else is outline-only and progressively dimmer the further
// it is. No lot/score/diuji/serap/status text on the chart anymore - that
// detail still lives untouched in g_zone*/the panel's roadmap list, only
// the CHART presentation changed. Zero changes to zone_engine.py, entry
// logic, or which zones get computed - purely how they're drawn.
color BlendToBlack(color c, double factor)
{
   // MQL5 chart objects have no real alpha channel - "lighter/dimmer" is
   // approximated by scaling RGB toward black (this theme's background),
   // same visual effect as reduced opacity on a dark chart.
   int r = (int)MathRound(((int)c & 0xFF) * factor);
   int g = (int)MathRound((((int)c >> 8) & 0xFF) * factor);
   int b = (int)MathRound((((int)c >> 16) & 0xFF) * factor);
   return (color)(r | (g << 8) | (b << 16));
}

void DrawZoneBox(int idx, int rank, string side, double lo, double hi, int wallCount, double totalLot,
                  string status, int retestCount, int absorptionHits, double score)
{
   string key    = SDZ_PREFIX + side + "_" + IntegerToString(idx);
   string txtKey = key + "_TXT";
   bool   isDemand = (side == "DEMAND");

   // Score still picks the base hue (brighter = stronger zone) - a quick
   // visual read without needing the score NUMBER spelled out in text.
   color baseClr = isDemand
      ? (score >= 60 ? C'0,210,125' : (score >= 30 ? C'0,160,95' : C'0,105,65'))
      : (score >= 60 ? C'230,65,65' : (score >= 30 ? C'185,55,55' : C'120,45,45'));
   if(status == "BROKEN") baseClr = clrGray;

   // v53.20: Dadang - "kalo zonanya dikasih full warna pusing gw liat
   // breakoutnya kan gw masih butuh liat candlenya" - a SOLID filled box
   // (even just for S1/D1) hides the candles behind it, which defeats the
   // whole point of watching for a break. ALL ranks are outline-only now
   // (OBJPROP_FILL=false), never solid - detail (lot/KUAT/diuji/serap)
   // stays in the label text, border thickness+brightness alone carries
   // the "S1/D1 = most important" hierarchy.
   // v53.21: Dadang - "sekarang tampilin semua zona SND yang ada bro" -
   // InpMaxZonesPerSideChart raised so every qualifying zone gets drawn,
   // not just S1-S3/D1-D3. Opacity now decays smoothly past rank 2
   // instead of flattening at a fixed 0.60 - with potentially a dozen+
   // zones on screen, the far ones should keep fading out (floored at
   // 0.35 so nothing goes fully invisible again, per the v53.19 lesson).
   bool   filled  = false;
   double opacity = (rank == 0) ? 1.00 : (rank == 1) ? 0.80 : MathMax(0.35, 0.60 - (rank - 2) * 0.04);
   int    width   = (rank == 0) ? 3 : (rank == 1) ? 2 : 1;
   color  clr     = BlendToBlack(baseClr, opacity);
   // v53.24: Dadang - "bedain fres atau tidak ya bro" - FRESH gets its own
   // dotted style (distinct from WEAKENED's dash) so a just-formed zone is
   // spottable at a glance, same idea as the existing AUS/dash convention.
   ENUM_LINE_STYLE style = (status == "WEAKENED") ? STYLE_DASH : (status == "FRESH") ? STYLE_DOT : STYLE_SOLID;

   // v53.8: Dadang screenshot - a zone box filled the ENTIRE chart, solid
   // wall-to-wall color, candles invisible ("kayak di apit tembok"). Root
   // cause: the box's time span was a FIXED 60-bars-back/15-bars-forward
   // regardless of zoom - zoomed in tight (few bars visible), that fixed
   // span overflows both edges of the visible window and looks like a
   // solid fill. Now proportional to CHART_VISIBLE_BARS so it always sits
   // within roughly the visible window no matter the zoom level.
   int visibleBars = (int)ChartGetInteger(0, CHART_VISIBLE_BARS);
   if(visibleBars <= 5) visibleBars = 75;   // fallback if the chart isn't ready yet
   int spanBack  = MathMax(8, (int)(visibleBars * 0.55));
   int spanFwd   = MathMax(3, (int)(visibleBars * 0.12));
   datetime t1 = TimeCurrent() - PeriodSeconds(_Period) * spanBack;
   datetime t2 = TimeCurrent() + PeriodSeconds(_Period) * spanFwd;

   if(ObjectFind(0, key) < 0)
      ObjectCreate(0, key, OBJ_RECTANGLE, 0, t1, hi, t2, lo);
   else
      ObjectMove(0, key, 0, t1, hi);
   ObjectSetInteger(0, key, OBJPROP_TIME, 1, t2);
   ObjectSetDouble(0, key, OBJPROP_PRICE, 1, lo);
   ObjectSetInteger(0, key, OBJPROP_FILL, filled);
   ObjectSetInteger(0, key, OBJPROP_BACK, true);
   ObjectSetInteger(0, key, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, key, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, key, OBJPROP_STYLE, style);
   ObjectSetInteger(0, key, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, key, OBJPROP_COLOR, clr);

   // v53.17: Dadang - "kemana jumlah lot dan lain2nya tadi di chart bro
   // duh malah ilang" - v53.14 stripped ALL zones down to tag+range only,
   // but he still wants the full read (lot/strength/diuji/serap) for the
   // ONE zone that matters most (S1/D1, rank 0) - matches his own spec's
   // "SUPPLY 1 / DEMAND 1 = paling jelas". S2/S3-D2/D3 stay tag+range
   // only, so the "readable in 2-3 detik" goal survives - just 2 labels
   // on the whole chart carry full detail, not 6.
   // v53.23: Dadang - "kok gak ada tulisan kuat aus diuji dll bro" - v53.22
   // over-corrected. He meant "total lot aja SEPERTI AWALNYA" as in the
   // ORIGINAL full format (lot -> strength -> status -> diuji/serap),
   // never had a range in it either - just wanted the range dropped, not
   // the rest of the detail. Full detail now on EVERY zone, all ranks.
   string tag = (isDemand ? "D" : "S") + IntegerToString(rank + 1);
   string label = StringFormat(" %s %.0fL | %s %.0f (%s) | diuji %dx, serap %dx",
                                tag, totalLot, ZoneStrengthID(score), score, ZoneStatusID(status),
                                retestCount, absorptionHits);

   // v53: Dadang screenshot - "kalo gini gmana" (a SUPPLY zone's label
   // colliding with the DEMAND zone sitting right below it, at their
   // shared boundary). Biasing toward each zone's OWN outer edge (SUPPLY
   // near its top, DEMAND near its bottom) pushes the two labels apart
   // along price instead of sitting dead-center at the shared boundary.
   double midPrice = isDemand ? (lo + (hi - lo) * 0.25) : (lo + (hi - lo) * 0.75);
   // v53.26: Dadang - "zona2 yang jauh blm muncul total lotnya" - idx here
   // is DrawAllZones()'s GLOBAL draw counter (0..~39 now that up to 20
   // zones/side get drawn, v53.21) - staggering by the raw idx pushed
   // high-index zones' labels dozens of bars off to the right, past the
   // visible chart window entirely (box still drew, its text label just
   // landed off-screen). Wrapped with %6 so the stagger cycles through a
   // small, bounded range instead of growing unbounded with zone count.
   datetime labelTime = t1 + (datetime)((t2 - t1) * 0.35) + PeriodSeconds(_Period) * (idx % 6) * 3;
   if(ObjectFind(0, txtKey) < 0)
      ObjectCreate(0, txtKey, OBJ_TEXT, 0, labelTime, midPrice);
   else
      ObjectMove(0, txtKey, 0, labelTime, midPrice);
   ObjectSetInteger(0, txtKey, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, txtKey, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, txtKey, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetInteger(0, txtKey, OBJPROP_COLOR, (rank == 0) ? clrWhite : BlendToBlack(clrWhite, MathMin(1.0, opacity + 0.35)));
   ObjectSetInteger(0, txtKey, OBJPROP_FONTSIZE, (rank == 0) ? 9 : 8);
   ObjectSetString(0, txtKey, OBJPROP_TEXT, label);
}

// v53 TAHAP 1/7: builds the full distance-ranked roadmap per side (NOT
// capped by InpMaxZonesPerSideChart - "jangan hapus zone jauh, tetap
// tersedia sebagai roadmap/TP") into g_supplyRoad*/g_demandRoad*, THEN
// draws only the nearest InpMaxZonesPerSideChart of them on the chart
// (with relevance-tiered visual weight). Roadmap completeness and chart
// clutter are deliberately decoupled - TP3 can still reference a zone
// that isn't drawn on the chart at all.
void DrawAllZones()
{
   g_supplyRoadCount = 0;
   g_demandRoadCount = 0;

   if(!g_zoneDataAvailable || g_zoneCount == 0)
   {
      if(InpShowZonesOnChart) ObjectsDeleteAll(0, SDZ_PREFIX);
      return;
   }

   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(InpShowZonesOnChart) ObjectsDeleteAll(0, SDZ_PREFIX);

   string sides[2] = {"SUPPLY", "DEMAND"};
   int drawIdx = 0;
   for(int s = 0; s < 2; s++)
   {
      int sideIdx[]; int sc = 0;
      for(int i = 0; i < g_zoneCount; i++)
      {
         if(g_zoneSide[i] != sides[s]) continue;
         if(g_zoneStatus[i] == "BROKEN") continue;
         if(g_zoneScore[i] < InpMinScoreToShowChart) continue;   // display/roadmap threshold - separate from InpZoneCFMinScore (entry)
         ArrayResize(sideIdx, sc + 1); sideIdx[sc] = i; sc++;
      }

      double dist[]; ArrayResize(dist, sc);
      for(int k = 0; k < sc; k++)
      {
         int i = sideIdx[k];
         dist[k] = (sides[s] == "SUPPLY") ? MathAbs(g_zoneLo[i] - price) : MathAbs(g_zoneHi[i] - price);
      }
      // insertion sort sideIdx by dist ascending - sc is always small
      for(int a = 1; a < sc; a++)
      {
         int keyIdx = sideIdx[a]; double keyDist = dist[a]; int b = a - 1;
         while(b >= 0 && dist[b] > keyDist) { sideIdx[b + 1] = sideIdx[b]; dist[b + 1] = dist[b]; b--; }
         sideIdx[b + 1] = keyIdx; dist[b + 1] = keyDist;
      }

      // roadmap - top SDPM_MAX_ROADMAP regardless of chart draw cap
      for(int a = 0; a < sc && a < SDPM_MAX_ROADMAP; a++)
      {
         int i = sideIdx[a];
         if(sides[s] == "SUPPLY")
         {
            g_supplyRoadLo[a] = g_zoneLo[i]; g_supplyRoadHi[a] = g_zoneHi[i]; g_supplyRoadScore[a] = g_zoneScore[i];
            g_supplyRoadCount = a + 1;
         }
         else
         {
            g_demandRoadLo[a] = g_zoneLo[i]; g_demandRoadHi[a] = g_zoneHi[i]; g_demandRoadScore[a] = g_zoneScore[i];
            g_demandRoadCount = a + 1;
         }
      }

      // chart drawing - capped, relevance-tiered
      if(InpShowZonesOnChart)
      {
         for(int a = 0; a < sc && a < InpMaxZonesPerSideChart; a++)
         {
            int i = sideIdx[a];
            DrawZoneBox(drawIdx++, a, g_zoneSide[i], g_zoneLo[i], g_zoneHi[i], g_zoneWallCount[i], g_zoneTotalLot[i],
                        g_zoneStatus[i], g_zoneRetest[i], g_zoneAbsorb[i], g_zoneScore[i]);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Does testPrice fall inside a qualifying SUPPLY (wantSupply=true) or |
//| DEMAND (wantSupply=false) zone? Picks the HIGHEST-SCORING match if   |
//| more than one zone happens to overlap testPrice. Returns false if    |
//| no zone data or no qualifying match - caller decides the fallback.   |
//+------------------------------------------------------------------+
bool ZoneCheck(bool wantSupply, double testPrice, double &outLo, double &outHi, double &outScore)
{
   if(!g_zoneDataAvailable || g_zoneCount == 0) return false;
   string wantSide = wantSupply ? "SUPPLY" : "DEMAND";
   bool found = false;
   double bestScore = -1.0;

   for(int i = 0; i < g_zoneCount; i++)
   {
      if(g_zoneSide[i] != wantSide) continue;
      if(g_zoneStatus[i] == "BROKEN") continue;
      if(g_zoneScore[i] < InpZoneCFMinScore) continue;
      if(testPrice < g_zoneLo[i] || testPrice > g_zoneHi[i]) continue;

      if(g_zoneScore[i] > bestScore)
      {
         bestScore = g_zoneScore[i];
         outLo = g_zoneLo[i]; outHi = g_zoneHi[i]; outScore = g_zoneScore[i];
         found = true;
      }
   }
   return found;
}

//+------------------------------------------------------------------+
//| v53: Dadang - "kita bisa entri sell sampai demand terdekat karena
//| kita tau m30 sudah di tahan big player" - the nearest qualifying zone
//| on the OPPOSING side of refPrice, used as a real TP target. For a
//| SELL (wantSupply=false here, i.e. looking for the DEMAND target
//| below), picks the DEMAND zone whose hi (near edge) is closest above
//| price coming DOWN; for a BUY target (wantSupply=true, SUPPLY above),
//| picks the SUPPLY zone whose lo is closest above price. Same score gate
//| as ZoneCheck() - a weak/noisy zone isn't a credible target either.
//+------------------------------------------------------------------+
bool NearestOpposingZone(bool wantSupply, double refPrice, double &outEdge, double &outScore)
{
   if(!g_zoneDataAvailable || g_zoneCount == 0) return false;
   string wantSide = wantSupply ? "SUPPLY" : "DEMAND";
   bool found = false;
   double bestDist = DBL_MAX;

   for(int i = 0; i < g_zoneCount; i++)
   {
      if(g_zoneSide[i] != wantSide) continue;
      if(g_zoneStatus[i] == "BROKEN") continue;
      if(g_zoneScore[i] < InpZoneCFMinScore) continue;

      double edge;
      if(wantSupply) { if(g_zoneLo[i] <= refPrice) continue; edge = g_zoneLo[i]; }
      else           { if(g_zoneHi[i] >= refPrice) continue; edge = g_zoneHi[i]; }

      double d = MathAbs(edge - refPrice);
      if(d < bestDist) { bestDist = d; outEdge = edge; outScore = g_zoneScore[i]; found = true; }
   }
   return found;
}

//+------------------------------------------------------------------+
//| v53 TAHAP 2: Market Location. Uses roadmap[0] (NEAREST) per side -   |
//| already rebuilt every cycle by DrawAllZones(). NEAR_* uses a fixed   |
//| $1.5 buffer (close enough to be "approaching" a zone without being   |
//| inside it yet) - not in Dadang's spec as a specific number, picked   |
//| as a reasonable watch-distance for XAUUSD, easy to retune later.     |
//+------------------------------------------------------------------+
#define SDM_NEAR_BUFFER_USD 1.5

string MarketLocation(double price)
{
   bool haveSupply = (g_supplyRoadCount > 0);
   bool haveDemand = (g_demandRoadCount > 0);

   if(haveSupply && price >= g_supplyRoadLo[0] && price <= g_supplyRoadHi[0]) return "INSIDE_SUPPLY";
   if(haveDemand && price >= g_demandRoadLo[0] && price <= g_demandRoadHi[0]) return "INSIDE_DEMAND";
   if(!haveSupply && !haveDemand) return "OUTSIDE_ACTIVE_RANGE";

   if(haveSupply)
   {
      double dSup = g_supplyRoadLo[0] - price;
      if(dSup >= 0 && dSup <= SDM_NEAR_BUFFER_USD) return "NEAR_SUPPLY";
   }
   if(haveDemand)
   {
      double dDem = price - g_demandRoadHi[0];
      if(dDem >= 0 && dDem <= SDM_NEAR_BUFFER_USD) return "NEAR_DEMAND";
   }
   return "BETWEEN_ZONES";
}

//+------------------------------------------------------------------+
//| v53 TAHAP 17: Decision Context - one place every S&D Price Map      |
//| panel field reads from. DELIBERATELY DISPLAY-ONLY: the "setup"       |
//| field here never says CONFIRMED, only _WATCH or NONE, because real   |
//| BUY/SELL confirmation needs Trigger Engine (TAHAP 5 - reaction +     |
//| close confirmation), which is a separate, not-yet-built step. This   |
//| does NOT feed CheckZoneBreakoutEntry() or any other real entry -     |
//| that logic is completely unchanged by this panel.                    |
//|                                                                        |
//| Buyer/Seller Control (TAHAP 3): no real per-zone order-flow data      |
//| exists yet. Per Dadang's own rule ("jangan mengarang... kalau belum   |
//| bisa dihitung valid, CONTROL = UNKNOWN/NEUTRAL, bukan angka palsu"),  |
//| this uses the EXISTING symbol-level Vol Ratio (g_bookmapVolRatioBuyPct)|
//| as an explicit, labelled PROXY - only shown while price is actually   |
//| at a zone (elsewhere it's meaningless), never presented as true       |
//| per-zone data.                                                        |
//+------------------------------------------------------------------+
// v53.4: Dadang - "ada suplay di bawah demant di atas numpuk juga itu
// gmana bacannya" - screenshot showed SUPPLY 1 and DEMAND 1 lines at the
// EXACT same price (4635.74 both). Not a rendering bug - the SUPPLY zone's
// bottom edge and the DEMAND zone directly below it's top edge are
// genuinely touching/coincident (no gap between them). This is exactly
// TAHAP 11 from his own spec ("ZONE COMPRESSION... belum boleh BUY/SELL
// sebelum breakout confirmation") - detected here and surfaced explicitly
// instead of leaving two confusingly-adjacent same-price labels unexplained.
#define SDM_COMPRESSION_USD 1.0

bool ZoneCompressionActive()
{
   if(g_supplyRoadCount == 0 || g_demandRoadCount == 0) return false;
   return (g_supplyRoadLo[0] - g_demandRoadHi[0]) <= SDM_COMPRESSION_USD;
}

void BuildDecisionContext(double price)
{
   g_sdmLocation = MarketLocation(price);
   g_sdmBuyerPct = 50.0; g_sdmSellerPct = 50.0;
   g_sdmSetup    = "NONE";
   g_sdmMarketState = "BALANCED";
   g_sdmReason   = "PRICE_BETWEEN_ZONES";

   if(ZoneCompressionActive())
   {
      g_sdmMarketState = "ZONE COMPRESSION";
      g_sdmSetup    = "NONE";
      g_sdmReason   = "SUPPLY_DEMAND_SQUEEZE_WAIT_FOR_BREAK";
      return;   // squeeze overrides the normal location/control read below - not actionable either way until it breaks one direction
   }

   bool atZone = (g_sdmLocation == "INSIDE_SUPPLY" || g_sdmLocation == "NEAR_SUPPLY" ||
                  g_sdmLocation == "INSIDE_DEMAND" || g_sdmLocation == "NEAR_DEMAND");
   if(atZone)
   {
      g_sdmBuyerPct  = g_bookmapOnline ? g_bookmapVolRatioBuyPct : 50.0;
      g_sdmSellerPct = 100.0 - g_sdmBuyerPct;
   }

   if(g_sdmLocation == "INSIDE_DEMAND" && g_sdmBuyerPct >= 60.0)
   {
      g_sdmSetup = "BUY_WATCH"; g_sdmMarketState = "BUYER CONTROL";
      g_sdmReason = "DEMAND_REACTION_BUYER_LEAN";
   }
   else if(g_sdmLocation == "INSIDE_SUPPLY" && g_sdmSellerPct >= 60.0)
   {
      g_sdmSetup = "SELL_WATCH"; g_sdmMarketState = "SELLER CONTROL";
      g_sdmReason = "SUPPLY_REACTION_SELLER_LEAN";
   }
   else if(g_sdmLocation == "INSIDE_DEMAND" || g_sdmLocation == "INSIDE_SUPPLY")
   {
      g_sdmMarketState = "BALANCED"; g_sdmReason = "BUYER_SELLER_BALANCED";
   }
   else if(g_sdmLocation == "NEAR_SUPPLY")
   {
      g_sdmMarketState = "APPROACHING SUPPLY"; g_sdmReason = "APPROACHING_SUPPLY";
   }
   else if(g_sdmLocation == "NEAR_DEMAND")
   {
      g_sdmMarketState = "APPROACHING DEMAND"; g_sdmReason = "APPROACHING_DEMAND";
   }
   else if(g_sdmLocation == "OUTSIDE_ACTIVE_RANGE")
   {
      g_sdmMarketState = "NO VALID ZONE"; g_sdmReason = "NO_VALID_ZONE";
   }
}

//+------------------------------------------------------------------+
//| v53 TAHAP 9: S&D PRICE MAP panel - a SEPARATE panel from the         |
//| existing Chain Reaction dashboard (untouched). Plain OBJ_LABEL/      |
//| OBJ_RECTANGLE_LABEL (the CCanvas panel attempt earlier this session   |
//| never rendered on Dadang's terminal for unknown reasons - this uses   |
//| the proven-reliable object types instead). CORNER_LEFT_LOWER - the    |
//| same corner a prior standalone zone panel used and was confirmed      |
//| visible; distinct from the main panel's LEFT_UPPER and its secondary  |
//| CDPFX panel's RIGHT_UPPER.                                            |
//+------------------------------------------------------------------+
// v53.10: Dadang - "kalo lo jadikan 1 di panel aja gimana bro di panel
// original". The separate floating S&D PRICE MAP panel (OBJ_LABEL-based,
// no working background, kept fighting with roadmap HLINEs crossing
// through it) is retired - its content now lives INSIDE the main Chain
// Reaction panel's own UpdatePanel() (a real CCanvas box with a genuinely
// solid background, no legibility fights possible). CreateSDPMPanel() is
// kept as a one-time cleanup call (wipes any leftover objects from a
// prior attach that used the old floating-panel design).
void CreateSDPMPanel()
{
   ObjectsDeleteAll(0, SDPM_PREFIX);
   ChartRedraw(0);
}

// v53.7: Dadang - "focus ke desain... agar enak diliat dan gampang aja".
// Raw enum codes (LOCATION: INSIDE_SUPPLY, REASON: SUPPLY_DEMAND_SQUEEZE_
// WAIT_FOR_BREAK) are precise but not something he'd ever say out loud -
// translated to the same plain-Indonesian voice he already uses himself
// ("nempel", "sempit", "fokus SELL/BUY"). The enum values themselves stay
// unchanged internally (BuildDecisionContext() logic untouched) - this is
// display-only translation, not a data-model change.
string LocationText(string loc)
{
   if(loc == "INSIDE_SUPPLY")        return "DI DALAM ZONA SUPPLY";
   if(loc == "INSIDE_DEMAND")        return "DI DALAM ZONA DEMAND";
   if(loc == "NEAR_SUPPLY")          return "DEKAT ZONA SUPPLY";
   if(loc == "NEAR_DEMAND")          return "DEKAT ZONA DEMAND";
   if(loc == "OUTSIDE_ACTIVE_RANGE") return "GAK ADA ZONA VALID DI SEKITAR";
   return "DI ANTARA DUA ZONA";   // BETWEEN_ZONES
}

string ReasonText(string reason)
{
   if(reason == "SUPPLY_DEMAND_SQUEEZE_WAIT_FOR_BREAK") return "Supply & demand lagi ketemu/sempit - tunggu salah satu jebol dulu";
   if(reason == "DEMAND_REACTION_BUYER_LEAN")            return "Di demand, buyer lebih dominan - watch buat BUY";
   if(reason == "SUPPLY_REACTION_SELLER_LEAN")           return "Di supply, seller lebih dominan - watch buat SELL";
   if(reason == "BUYER_SELLER_BALANCED")                 return "Buyer/seller seimbang di zona ini - belum ada arah jelas";
   if(reason == "APPROACHING_SUPPLY")                    return "Harga mendekati supply, belum masuk";
   if(reason == "APPROACHING_DEMAND")                    return "Harga mendekati demand, belum masuk";
   if(reason == "NO_VALID_ZONE")                         return "Gak ada zona valid di dekat harga sekarang";
   return "Harga di antara zona, belum ada yang relevan";   // PRICE_BETWEEN_ZONES
}

// FOKUS headline - the ONE thing he actually needs at a glance, everything
// else on the panel is supporting detail underneath it.
string FocusText(color &clrOut)
{
   if(g_sdmSetup == "BUY_WATCH")  { clrOut = clrLimeGreen; return "FOKUS: BUY"; }
   if(g_sdmSetup == "SELL_WATCH") { clrOut = clrTomato;    return "FOKUS: SELL"; }
   if(g_sdmMarketState == "ZONE COMPRESSION") { clrOut = clrOrange; return "FOKUS: TUNGGU (zona sempit)"; }
   clrOut = clrSilver;
   return "FOKUS: TUNGGU";
}

// v53.10: BuildDecisionContext() still needs to run once per tick, BEFORE
// UpdatePanel() reads g_sdm* (now printed inside the main panel) and
// BEFORE UpdateRoadmapLines() reads g_sdmLocation for its ENTRY AREA
// highlight - was previously hidden inside the now-removed UpdateSDPMPanel().
void RefreshDecisionContext()
{
   BuildDecisionContext(SymbolInfoDouble(_Symbol, SYMBOL_BID));
}

//+------------------------------------------------------------------+
//| S&D MOMENTUM BREAK ENGINE (v53.18) - Dadang's 35-section spec.    |
//| DETEKSI + PENILAIAN + TAMPILAN saja. TIDAK menyentuh entry logic, |
//| TIDAK mengganti Chain Reaction/Fusion, TIDAK bikin zone engine    |
//| baru. State per S1(SUPPLY)/D1(DEMAND) - dua zona yang sudah       |
//| dianggap "yang penting" di seluruh sistem ini.                    |
//|                                                                    |
//| State machine (rule 10): NONE -> ZONE_TEST -> WICK_BREAK/         |
//| CLOSE_BREAK -> MOMENTUM_BREAK -> FOLLOW_THROUGH -> BREAK_CONFIRMED|
//| dengan FALSE_BREAK/REJECTION sebagai jalan keluar kalau close      |
//| balik masuk zona lagi. RETEST dipakai kalau BREAK_CONFIRMED lalu  |
//| close balik masuk zona - versi ringan, bukan full FLIP_CONFIRMED  |
//| (rule 10 sendiri: "tidak semua state harus terjadi").             |
//|                                                                    |
//| CLOSE ONLY doctrine (rule 14): semua keputusan pakai bar YANG     |
//| SUDAH CLOSE (index 1), wick cuma informasi, gak pernah jadi       |
//| confirmation sendirian.                                           |
//+------------------------------------------------------------------+
// Marker kecil di bar yang barusan close, keyed by side+bartime biar gak
// dobel kalau function ini kepanggil lagi di bar yang sama. Cuma state
// yang genuinely notable yang dapet marker (rule 26/27: "jangan bikin
// chart ramai, jangan panah besar tiap candle").
void DrawSDBreakMarker(bool isSupply, string state, datetime barTime, double price)
{
   string glyph; color clr; int size;
   if(state == "WICK_BREAK")          { glyph = "•"; clr = PNL_SILVER; size = 8;  }
   else if(state == "CLOSE_BREAK")    { glyph = "○"; clr = clrOrange;  size = 9;  }
   else if(state == "MOMENTUM_BREAK") { glyph = "◆"; clr = clrOrange;  size = 10; }
   else if(state == "BREAK_CONFIRMED"){ glyph = isSupply ? "▲" : "▼"; clr = isSupply ? PNL_EMERALD : PNL_ROSE; size = 13; }
   else if(state == "FALSE_BREAK")    { glyph = "×"; clr = PNL_SILVER; size = 9;  }
   else if(state == "REJECTION")      { glyph = "×"; clr = PNL_SILVER; size = 9;  }
   else return;   // ZONE_TEST/NONE/FOLLOW_THROUGH/RETEST - gak usah dikasih marker

   string name = SDBRK_PREFIX + (isSupply ? "S_" : "D_") + IntegerToString((long)barTime);
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_TEXT, 0, barTime, price);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, isSupply ? ANCHOR_LOWER : ANCHOR_UPPER);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, size);
   ObjectSetString(0, name, OBJPROP_TEXT, glyph);
}

// Evaluasi 1 sisi (SUPPLY pakai zoneHi sebagai tepi yang harus ditembus,
// DEMAND pakai zoneLo) dari bar M yang SUDAH CLOSE. Dipanggil 1x per bar
// baru per sisi dari UpdateSDBreakEngine() - bukan tiap tick (rule 33).
void UpdateSDBreakState(bool isSupply, double zoneLo, double zoneHi, bool zoneValid, double atrActive,
                         string &state, double &zLo, double &zHi, int &followBars,
                         string &momentumOut, int &falseCount)
{
   if(!zoneValid)
   {
      state = "NONE"; zLo = 0; zHi = 0; followBars = 0; momentumOut = "-";
      return;
   }

   // zona berubah (S1/D1 baru kebentuk) - state lama gak relevan lagi buat zona ini
   bool zoneChanged = (zLo <= 0 || MathAbs(zoneLo - zLo) > 0.01 || MathAbs(zoneHi - zHi) > 0.01);
   if(zoneChanged) { state = "NONE"; followBars = 0; }
   zLo = zoneLo; zHi = zoneHi;

   double o = iOpen(_Symbol, _Period, 1), h = iHigh(_Symbol, _Period, 1),
          l = iLow(_Symbol, _Period, 1),  c = iClose(_Symbol, _Period, 1);
   double body  = MathAbs(c - o);
   double range = h - l;
   double bodyRatio = (range > 0) ? body / range : 0.0;
   double rangeAtr  = (atrActive > 0) ? range / atrActive : 0.0;
   double closeLoc  = (range > 0) ? (c - l) / range : 0.5;   // 0 = di low, 1 = di high

   double edge       = isSupply ? zoneHi : zoneLo;
   bool   wickBreak  = isSupply ? (h > edge) : (l < edge);
   bool   closeBreak = isSupply ? (c > edge) : (c < edge);
   double breakDist  = isSupply ? (c - edge) : (edge - c);
   bool   insideZone = (c >= zoneLo && c <= zoneHi);
   bool   nearZone   = isSupply ? (l <= zoneHi + InpNearZoneDistance && l >= zoneLo - InpNearZoneDistance)
                                 : (h >= zoneLo - InpNearZoneDistance && h <= zoneHi + InpNearZoneDistance);

   double closeLocScore = isSupply ? closeLoc : (1.0 - closeLoc);   // bullish mau closeLoc tinggi, bearish mau closeLoc rendah
   int score = 0;
   if(bodyRatio     >= InpMomentumMinBodyRatio) score++;
   if(rangeAtr      >= InpMomentumMinRangeATR)  score++;
   if(closeLocScore >= 0.6)                      score++;
   if(closeBreak && MathAbs(breakDist) >= InpMomentumMinBreakDistance) score++;
   string momentum = (score >= 3) ? "STRONG" : (score >= 2) ? "NORMAL" : "WEAK";
   momentumOut = momentum;

   string prev = state;

   if(closeBreak)
   {
      if(prev == "BREAK_CONFIRMED" || prev == "RETEST")
      {
         state = "BREAK_CONFIRMED";        // retest survived, tetap confirmed
         followBars = InpBreakConfirmationBars;
      }
      else if(prev == "CLOSE_BREAK" || prev == "MOMENTUM_BREAK" || prev == "FOLLOW_THROUGH")
      {
         followBars++;
         bool followOk = (atrActive <= 0) || (range >= InpFollowThroughMinRangeATR * atrActive);
         state = (followBars >= InpBreakConfirmationBars && followOk) ? "BREAK_CONFIRMED" : "FOLLOW_THROUGH";
      }
      else
      {
         bool momentumOk = (momentum != "WEAK") && MathAbs(breakDist) >= InpMomentumMinBreakDistance;
         state = momentumOk ? "MOMENTUM_BREAK" : "CLOSE_BREAK";   // rule 14: wick doang gak pernah masuk sini, closeBreak wajib true
         followBars = 0;
      }
   }
   else if(insideZone)
   {
      if(prev == "BREAK_CONFIRMED")
      {
         state = "RETEST";
      }
      else if(prev == "CLOSE_BREAK" || prev == "MOMENTUM_BREAK" || prev == "FOLLOW_THROUGH" || prev == "RETEST")
      {
         state = "FALSE_BREAK";
         falseCount++;
         followBars = 0;
      }
      else if(wickBreak)
      {
         state = "REJECTION";   // wick sempat nembus, tapi close balik masuk zona - rule 15
         falseCount++;
      }
      else
      {
         state = "ZONE_TEST";
      }
   }
   else if(wickBreak)
   {
      state = "WICK_BREAK";   // rule 2/14: wick doang, BUKAN break - close masih di luar (belum insideZone) tapi juga belum closeBreak sisi yang sama (kasus langka, misal gap) - tetap ditandai wick break, bukan close break
   }
   else if(nearZone)
   {
      state = (prev == "NONE" || prev == "") ? "ZONE_TEST" : prev;   // jangan reset state penting cuma karena satu bar gak nyentuh persis
   }
   else
   {
      state = "NONE";
      followBars = 0;
   }

   if(state == "BREAK_CONFIRMED") falseCount = 0;   // break beneran hapus tally choppy sisi ini

   datetime barTime = iTime(_Symbol, _Period, 1);
   // v53.26: Dadang - "dimana baris break struktunya bro" - marker used to
   // only draw on the exact bar the state CHANGED, so once it happened a
   // few bars back (or got lost among all the zone labels) there was
   // nothing at/near the current bar to spot. Now redraws every bar the
   // state stays "notable" (WICK/CLOSE/MOMENTUM_BREAK/CONFIRMED/FALSE/
   // REJECTION) - keyed by that bar's own time so bars don't duplicate,
   // just means a live break attempt always has a fresh marker right at
   // the latest closed bar, not just wherever it first fired.
   DrawSDBreakMarker(isSupply, state, barTime, isSupply ? h : l);

   if(InpEnableSDBreakDebug && state != prev)
      PrintFormat("[SDBreak] %s zone=%.2f-%.2f OHLC=%.2f/%.2f/%.2f/%.2f body=%.2f range=%.2f bodyRatio=%.2f atr=%.2f rangeATR=%.2f breakDist=%.2f momentum=%s state %s -> %s",
                  isSupply ? "SUPPLY" : "DEMAND", zoneLo, zoneHi, o, h, l, c, body, range, bodyRatio, atrActive, rangeAtr, breakDist, momentum, prev, state);
}

// Driver - dipanggil dari OnTick(), tapi cuma benar-benar jalan sekali per
// bar baru (rule 33: "jangan menghitung ulang semua candle setiap tick").
void UpdateSDBreakEngine()
{
   if(!InpEnableSDBreakEngine)
   {
      g_sdBrkState_S = "NONE"; g_sdBrkState_D = "NONE"; g_sdMarketRead = "NORMAL";
      return;
   }

   datetime curBar = iTime(_Symbol, _Period, 0);
   if(curBar == g_sdBrkLastBar) return;
   g_sdBrkLastBar = curBar;

   double atrBuf[1]; double atrActive = 0.0;
   if(g_hATR_Active != INVALID_HANDLE && CopyBuffer(g_hATR_Active, 0, 0, 1, atrBuf) > 0) atrActive = atrBuf[0];

   bool supplyValid = (g_supplyRoadCount > 0);
   bool demandValid = (g_demandRoadCount > 0);

   UpdateSDBreakState(true,  supplyValid ? g_supplyRoadLo[0] : 0.0, supplyValid ? g_supplyRoadHi[0] : 0.0, supplyValid, atrActive,
                       g_sdBrkState_S, g_sdBrkZoneLo_S, g_sdBrkZoneHi_S, g_sdBrkFollowBars_S, g_sdBrkMomentum_S, g_sdBrkFalseCount_S);
   UpdateSDBreakState(false, demandValid ? g_demandRoadLo[0] : 0.0, demandValid ? g_demandRoadHi[0] : 0.0, demandValid, atrActive,
                       g_sdBrkState_D, g_sdBrkZoneLo_D, g_sdBrkZoneHi_D, g_sdBrkFollowBars_D, g_sdBrkMomentum_D, g_sdBrkFalseCount_D);

   // TAHAP 16/17: pakai ULANG ZoneCompressionActive() yang udah ada (jangan
   // duplikasi) buat COMPRESSION; CHOPPY baru - beberapa FALSE_BREAK/
   // REJECTION bergantian tanpa BREAK_CONFIRMED beneran.
   if(ZoneCompressionActive())
      g_sdMarketRead = "COMPRESSION";
   else if(g_sdBrkFalseCount_S + g_sdBrkFalseCount_D >= InpChoppyFalseBreakCount)
      g_sdMarketRead = "CHOPPY";
   else
      g_sdMarketRead = "NORMAL";
}

// TAHAP 18: informational only - TIDAK nge-gate CheckZoneBreakoutEntry()
// atau trigger manapun (rule 29).
bool SDNoTradeZoneActive()
{
   if(g_supplyRoadCount == 0 || g_demandRoadCount == 0) return false;
   return (g_supplyRoadLo[0] - g_demandRoadHi[0]) < InpMinZoneSeparation;
}

// TAHAP 19: BREAKOUT DIRECTION - informational, BUKAN entry signal.
string SDBreakoutDirection()
{
   if(g_sdBrkState_S == "BREAK_CONFIRMED") return "BUY";    // supply jebol ke atas = buyer menang
   if(g_sdBrkState_D == "BREAK_CONFIRMED") return "SELL";   // demand jebol ke bawah = seller menang
   return "-";
}

// TAHAP 20-25: satu baris ringkas buat panel - prioritas: yang paling
// actionable/confirmed duluan, baru turun ke state yang masih building.
string SDBreakStatusText()
{
   if(g_sdBrkState_S == "BREAK_CONFIRMED") return StringFormat("S1 BREAK CONFIRMED (BUY, %s)", g_sdBrkMomentum_S);
   if(g_sdBrkState_D == "BREAK_CONFIRMED") return StringFormat("D1 BREAK CONFIRMED (SELL, %s)", g_sdBrkMomentum_D);
   if(g_sdMarketRead == "CHOPPY")          return "CHOPPY - WAIT";
   if(g_sdMarketRead == "COMPRESSION")     return "COMPRESSION - WAIT";
   if(g_sdBrkState_S == "FOLLOW_THROUGH")  return "S1 FOLLOW THROUGH...";
   if(g_sdBrkState_D == "FOLLOW_THROUGH")  return "D1 FOLLOW THROUGH...";
   if(g_sdBrkState_S == "MOMENTUM_BREAK")  return "S1 MOMENTUM BREAK (belum confirmed)";
   if(g_sdBrkState_D == "MOMENTUM_BREAK")  return "D1 MOMENTUM BREAK (belum confirmed)";
   if(g_sdBrkState_S == "CLOSE_BREAK")     return "S1 CLOSE BREAK (belum confirmed)";
   if(g_sdBrkState_D == "CLOSE_BREAK")     return "D1 CLOSE BREAK (belum confirmed)";
   if(g_sdBrkState_S == "WICK_BREAK")      return "S1 WICK BREAK (belum confirmed)";
   if(g_sdBrkState_D == "WICK_BREAK")      return "D1 WICK BREAK (belum confirmed)";
   if(g_sdBrkState_S == "REJECTION")       return "SUPPLY REJECTION";
   if(g_sdBrkState_D == "REJECTION")       return "DEMAND REJECTION";
   if(g_sdBrkState_S == "FALSE_BREAK")     return "S1 FALSE BREAK";
   if(g_sdBrkState_D == "FALSE_BREAK")     return "D1 FALSE BREAK";
   if(g_sdBrkState_S == "RETEST")          return "S1 RETEST";
   if(g_sdBrkState_D == "RETEST")          return "D1 RETEST";
   if(g_sdBrkState_S == "ZONE_TEST")       return "S1 ZONE TEST";
   if(g_sdBrkState_D == "ZONE_TEST")       return "D1 ZONE TEST";
   return "NONE";
}

color SDBreakStatusColor()
{
   if(g_sdBrkState_S == "BREAK_CONFIRMED") return PNL_EMERALD;
   if(g_sdBrkState_D == "BREAK_CONFIRMED") return PNL_ROSE;
   if(g_sdMarketRead == "CHOPPY" || g_sdMarketRead == "COMPRESSION") return PNL_GOLD;
   if(g_sdBrkState_S == "MOMENTUM_BREAK" || g_sdBrkState_S == "FOLLOW_THROUGH" ||
      g_sdBrkState_D == "MOMENTUM_BREAK" || g_sdBrkState_D == "FOLLOW_THROUGH" ||
      g_sdBrkState_S == "CLOSE_BREAK"    || g_sdBrkState_D == "CLOSE_BREAK"    ||
      g_sdBrkState_S == "WICK_BREAK"     || g_sdBrkState_D == "WICK_BREAK") return PNL_GOLD;
   if(g_sdBrkState_S == "FALSE_BREAK" || g_sdBrkState_D == "FALSE_BREAK" ||
      g_sdBrkState_S == "REJECTION"   || g_sdBrkState_D == "REJECTION") return PNL_SILVER;
   return PNL_LABEL;
}

//--- Maps wall size (10-1000 lot range) to a line width 1-5. Dadang 2026-08-10:
//--- "tidak bisa dibuat yang tampil mulai 10 lot sampai 1000 lot bro" - show
//--- the WHOLE range instead of a single on/off cutoff, bigger = more visually
//--- prominent (thicker + more saturated color) instead of just present/absent.
int WallWidth(double size)
{
   double frac = (size - 10.0) / (1000.0 - 10.0);
   frac = MathMax(0.0, MathMin(1.0, frac));
   return 1 + (int)MathRound(frac * 4.0);   // 1..5
}

//--- Interpolates from a faint/dim shade (small wall, ~10 lot) to the full
//--- vivid color (big wall, >=1000 lot). MQL5 color is 0x00BBGGRR (R = low
//--- byte), so R+G*256+B*65536 builds it directly - isBid picks green vs red.
color WallColor(bool isBid, double size)
{
   double frac = (size - 10.0) / (1000.0 - 10.0);
   frac = MathMax(0.0, MathMin(1.0, frac));
   int channel = 90 + (int)MathRound(frac * (255 - 90));   // 90 (dim) .. 255 (vivid)
   if(isBid) return (color)(channel * 256);                 // green channel only
   return (color)(channel);                                  // red channel only
}

//--- Draws (or updates) one Bookmap wall as a horizontal line on the MT5
//--- chart, width/color scaled by size (WallWidth/WallColor above).
//--- bookmapPrice comes straight from Bookmap's own instrument (e.g. GCZ6
//--- futures) - offset converts it to XAUUSD-equivalent. Deletes the object
//--- if this wall slot is empty (price<=0, sent that way by the Python side
//--- when fewer than 2 walls exist on that side).
// v52.74 - returns lot/sec the wall at this slot has shrunk since the last
// tick (positive = being eaten), or -1.0 if there's nothing meaningful to
// compare (first tick, price moved to a different wall, or too little time
// elapsed). Updates the tracking arrays for next time as a side effect.
double WallEatRate(bool isBid, int slot, double currentPx, double currentSz)
{
   double   prevPx = isBid ? g_prevBidPx[slot]   : g_prevAskPx[slot];
   double   prevSz = isBid ? g_prevBidSz[slot]   : g_prevAskSz[slot];
   datetime prevT  = isBid ? g_prevBidTime[slot] : g_prevAskTime[slot];

   if(isBid) { g_prevBidPx[slot] = currentPx; g_prevBidSz[slot] = currentSz; g_prevBidTime[slot] = TimeCurrent(); }
   else      { g_prevAskPx[slot] = currentPx; g_prevAskSz[slot] = currentSz; g_prevAskTime[slot] = TimeCurrent(); }

   if(prevPx <= 0 || prevT == 0 || MathAbs(currentPx - prevPx) > 0.05) return -1.0;
   double dtSec = (double)(TimeCurrent() - prevT);
   if(dtSec < 1.0) return -1.0;   // too soon since last sample to be meaningful
   return (prevSz - currentSz) / dtSec;
}

void DrawWallLine(string key, double bookmapPrice, double size, double offset, bool isBid, string sideLabel, int barsAhead = 8, bool showLabel = true, double eatRate = -1.0)
{
   string name     = WALL_PREFIX + key;
   string textName = WALL_PREFIX + key + "_TXT";
   if(bookmapPrice <= 0 || size <= 0)
   {
      if(ObjectFind(0, name) >= 0)     ObjectDelete(0, name);
      if(ObjectFind(0, textName) >= 0) ObjectDelete(0, textName);
      return;
   }
   double mt5Price = bookmapPrice + offset;

   // v52.27b - Dadang: "gimana kalo di tulisan wall aja di aks atau bid di
   // chart itu yang berubah ketika di sweep" - instead of a separate marker
   // object elsewhere on the chart, if THIS is the exact wall that just got
   // swept, repurpose ITS OWN existing line+label in place (color + text
   // change, same object, same spot) - no new element added to an already-
   // crowded chart. g_sweepDrawnOnWallLine tells UpdateSweepMarker() this
   // was handled here, so it doesn't ALSO draw a fallback marker.
   // v52.69: reads the PERSISTENT record (g_sweepRecActive) instead of the
   // raw bridge fields' time cutoff - stays true until genuinely broken.
   bool sweptHere = (g_sweepRecActive &&
                     MathAbs(mt5Price - g_sweepRecPriceMt5) < 0.05 &&
                     ((isBid && g_sweepRecSide == "BID") || (!isBid && g_sweepRecSide == "ASK")));

   color  clr;
   int    width;
   string lineText, labelText;
   if(sweptHere)
   {
      g_sweepDrawnOnWallLine = true;
      long ageSec = (long)(TimeCurrent() - g_sweepRecFirstSeen);
      clr       = clrDeepSkyBlue;   // fixed - never used by a normal wall, so this alone says "sweep event"
      width     = 3;
      lineText  = StringFormat("%s SWEPT %.0f lot @ %.2f - REVERSAL (%s lalu, masih berlaku)", sideLabel, size, mt5Price, TimeAgoText(ageSec));
      // v52.68/v52.69: harga ditambahin + sekarang PERSISTEN (gak ilang
      // sampe genuinely kejebol) - Dadang: "masalahnya price nya di berapa
      // tidak di catat sehingga gw gak tau kejebol atau gak nanti" +
      // "selama belum kejebol masih tercatat di panel"
      labelText = StringFormat(" %s SWEPT @%.2f: REVERSAL (%s)", sideLabel, mt5Price, TimeAgoText(ageSec));
   }
   else
   {
      clr       = WallColor(isBid, size);
      width     = WallWidth(size);
      lineText  = StringFormat("%s %.0f lot @ %.2f (bookmap %.2f)", sideLabel, size, mt5Price, bookmapPrice);
      labelText = StringFormat(" %s: %.0f lot", sideLabel, size);
      // v52.74 - "kecepatan wall dimakan": a wall shrinking fast signals
      // more urgency/conviction than one trickling down slowly, visible
      // even before it's fully swept.
      if(eatRate >= WALL_EAT_FAST_LOT_PER_SEC)
      {
         string eatSuffix = StringFormat(" -%.1fL/s", eatRate);
         lineText  += eatSuffix;
         labelText += eatSuffix;
      }
   }

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT, lineText);

   // Dadang 2026-08-10: "tampilkan lotnya di mt5 juga bro di garisnya" - the
   // HLINE's OBJPROP_TEXT above is only a hover tooltip. Add an always-VISIBLE
   // text label anchored a few bars into the future (blank space right of the
   // latest candle), same price/color as the line, so the lot size is
   // readable at a glance without hovering.
   //
   // v35 fix - Dadang: "m5 masih keluar dari kotak card... bid ask di chart
   // ini bisa gak di buat lebih rapi" (garbled/overlapping wall labels).
   // Root cause: EVERY label used the exact same fixed 8-bar anchor, so
   // walls sitting close in PRICE (common - most of the 5 "near" slots per
   // side cluster near current price) rendered their text at the same X,
   // stacking on top of each other. barsAhead now staggers each slot
   // further right (see UpdateWallLines()'s per-slot offset) so nearby-price
   // walls land in different horizontal "lanes" instead of colliding.
   //
   // v52.34 - Dadang: "tulisan di sini yang dikanan perlu dihilangkan...
   // kan sudah kita kelompokan, kecuali memang ada yang sendiri gitu baru
   // muncul lotnya" - once a wall is already summarized by its zone box's
   // aggregate label, its own individual TEXT is redundant clutter (that
   // overlapping mess is exactly what he screenshotted) - the LINE above is
   // unaffected either way (still useful to see exact levels). showLabel is
   // false for a wall UpdateWallLines() knows is clustered (via
   // g_bidClustered[]/g_askClustered[], filled by UpdateWallZones() which
   // runs first); a swept wall always shows its own label regardless
   // (sweptHere overrides) since that's a distinct, rarer event worth
   // calling out even inside a cluster.
   if(!showLabel && !sweptHere)
   {
      if(ObjectFind(0, textName) >= 0) ObjectDelete(0, textName);
      return;
   }
   datetime labelTime = TimeCurrent() + PeriodSeconds(_Period) * barsAhead;
   if(ObjectFind(0, textName) < 0)
   {
      ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, mt5Price);
      ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_LEFT);
   }
   ObjectSetInteger(0, textName, OBJPROP_TIME, labelTime);
   ObjectSetDouble(0, textName, OBJPROP_PRICE, mt5Price);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, clrWhite);   // Dadang 2026-08-10: "hurufnya buat putih aja" - readable regardless of wall color/darkness
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 12 + (width - 1) * 2);   // Dadang: "besarin lotnya" - was 8-12, now 12-20
   ObjectSetString(0, textName, OBJPROP_TEXT, labelText);
}

//--- Dadang 2026-08-10: "bisa gak berapa banyak lot di bookmap langsung
//--- tergaris di MT5 tapi harus lo cover sesuai harga bookmap nya" - Bookmap
//--- trades a DIFFERENT instrument (GCZ6 gold futures) than this EA's XAUUSD
//--- spot, so wall prices can't be plotted 1:1 - the futures/spot basis
//--- drifts over time, so the offset is recomputed EVERY update, never
//--- cached/hardcoded.
//---
//--- v52.29/30: briefly tried collapsing nearby walls into one shaded zone
//--- box instead of individual lines - Dadang: "malah aneh bro garis wall
//--- nya yang buat keren malah hanya lo kotakin bro wkwkwk." The individual
//--- colored lines were the thing he actually liked; his earlier "banyak
//--- wall numpuk" comment was him reading the ALREADY-CORRECT (v52.28) lines
//--- clustering visually on their own, not a request to replace them with a
//--- box. Reverted back to the flat per-slot loop below.
void UpdateWallLines()
{
   // v53: Dadang - "masih muncul" (ASK WALL/BID WALL individual-line labels
   // still showing after the wall-ZONE box was disabled) - SND zones are
   // meant to fully replace the old wall-based visualization, not just its
   // clustered-box form. Same gate as DrawWallZone() above.
   if(InpShowZonesOnChart)
   {
      ObjectsDeleteAll(0, WALL_PREFIX);
      return;
   }
   if(!g_bookmapOnline || g_bookmapPrice <= 0)
   {
      ObjectsDeleteAll(0, WALL_PREFIX);
      return;
   }
   g_sweepDrawnOnWallLine = false;   // v52.27b - set true by DrawWallLine() if it repaints the swept wall's own slot
   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;

   // v35: stagger each slot's label 3 bars further right than the last -
   // walls close in PRICE (common among the "near" slots) land in different
   // horizontal lanes instead of stacking their text on top of each other.
   // v52.34: showLabel = !clustered - a wall already summarized by its zone
   // box (g_bidClustered[]/g_askClustered[], filled by UpdateWallZones()
   // which runs before this) skips its own redundant text; line stays.
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      string key   = StringFormat("BID%d", i+1);
      string label = StringFormat("BID WALL %d", i+1);
      double rate  = WallEatRate(true, i, g_bookmapBidPx[i], g_bookmapBidSz[i]);
      DrawWallLine(key, g_bookmapBidPx[i], g_bookmapBidSz[i], offset, true, label, 8 + i * 3, !g_bidClustered[i], rate);
   }
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      string key   = StringFormat("ASK%d", i+1);
      string label = StringFormat("ASK WALL %d", i+1);
      double rate  = WallEatRate(false, i, g_bookmapAskPx[i], g_bookmapAskSz[i]);
      DrawWallLine(key, g_bookmapAskPx[i], g_bookmapAskSz[i], offset, false, label, 8 + i * 3, !g_askClustered[i], rate);
   }
}

//--- v52.31: zone box drawn as an ADDITIVE overlay, not a replacement - v52.29
//--- tried collapsing clustered walls into a single box INSTEAD OF the
//--- individual lines and Dadang rejected it (v52.30 reverted): "garis wall
//--- nya yang buat keren malah hanya lo kotakin." His actual ask afterward:
//--- "kotaknya boleh aja tapi garis2 wall tadi kalo bisa tetap ada... dalam
//--- kotakan itu lo beri tulisan total wall nya aja, kalo ilang berkurang
//--- kalo nambah bertambah" - keep EVERY individual line/label exactly as
//--- UpdateWallLines() above already draws them (untouched), and layer a
//--- dim outline box + a live wall-COUNT label UNDERNEATH/AROUND any cluster
//--- of 2+ walls within InpWallZoneClusterUsd of each other - purely additive,
//--- never suppresses an individual line. Also gives him a way to tell "this
//--- box is the system's, not one I drew myself" (the live-updating count).
void DrawWallZone(string sideName, int zoneIdx, double loPriceBm, double hiPriceBm, double totalLot, int wallCount, double offset, bool isBid)
{
   string key      = WALL_PREFIX + WALL_ZONE_PREFIX + sideName + IntegerToString(zoneIdx);
   string textName = key + "_TXT";

   // v53: Dadang - "kita bikin v2 buat gantikan v1 dengan tambahan mapping
   // snd tadi" - the real Bookmap-scored SND zones (DrawZoneBox(), SUPPLY/
   // DEMAND) are the intended UPGRADE of this exact concept (a box around a
   // wall cluster), not an addition alongside it - the two were drawing
   // overlapping/garbled boxes on the same chart. This old BID/ASK box is
   // now skipped whenever the new zones are showing; individual wall LINES
   // (UpdateWallLines(), a separate feature Dadang explicitly wanted kept
   // even after the box existed - v52.30) are untouched either way.
   if(InpShowZonesOnChart)
   {
      ObjectDelete(0, key);
      ObjectDelete(0, textName);
      return;
   }

   double loPrice  = loPriceBm + offset, hiPrice = hiPriceBm + offset;

   // v52.69: persistent record (g_sweepRecActive), not the time-cutoff -
   // see UpdateWallLines()'s sweptHere comment for the full reasoning.
   bool sweptHere = (g_sweepRecActive &&
                     g_sweepRecPriceMt5 >= (loPrice - 0.05) && g_sweepRecPriceMt5 <= (hiPrice + 0.05) &&
                     ((isBid && g_sweepRecSide == "BID") || (!isBid && g_sweepRecSide == "ASK")));
   color  clr;
   string labelText;
   if(sweptHere)
   {
      long ageSec = (long)(TimeCurrent() - g_sweepRecFirstSeen);
      clr = clrDeepSkyBlue;
      // v52.68/v52.69: harga + persisten - lihat komentar di UpdateWallLines()
      labelText = StringFormat(" %s ZONE SWEPT @%.2f: REVERSAL (%s) - %d wall (%.0f lot)", sideName, g_sweepRecPriceMt5, TimeAgoText(ageSec), wallCount, totalLot);
   }
   else
   {
      clr = isBid ? C'40,160,90' : C'190,60,60';   // dim solid border - distinguishable from the size-scaled individual wall lines
      // Dadang: "tulisan total wall nya aja kalo ilang berkurang kalo nambah
      // bertambah" - wall COUNT leads the label (recomputed fresh every
      // cycle from live data, so it naturally ticks up/down on its own).
      labelText = StringFormat(" %s ZONE: %d wall (%.0f lot)", sideName, wallCount, totalLot);
   }

   datetime t1 = TimeCurrent() - PeriodSeconds(_Period) * 40;
   datetime t2 = TimeCurrent() + PeriodSeconds(_Period) * 8;
   ObjectCreate(0, key, OBJ_RECTANGLE, 0, t1, hiPrice, t2, loPrice);
   ObjectSetInteger(0, key, OBJPROP_FILL, false);
   ObjectSetInteger(0, key, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, key, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, key, OBJPROP_BACK, true);
   ObjectSetInteger(0, key, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, key, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, key, OBJPROP_COLOR, clr);
   ObjectSetString(0, key, OBJPROP_TEXT, labelText);

   // v52.32 fix - Dadang: "dalam kotakan itu lo beri tulisan" (INSIDE the
   // box) - the old +75-bar lane put it way past the wall labels' own lane
   // (8-65), off the right edge of whatever's currently in view. Centered
   // in the box's own time span instead (t1..t2) - always visible together
   // with the box itself, no separate scrolling needed, and it's genuinely
   // "inside" like he asked instead of off in a distant lane.
   double midPrice = (loPrice + hiPrice) / 2.0;
   datetime labelTime = t1 + (t2 - t1) / 2;
   ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, midPrice);
   ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_CENTER);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, clrWhite);
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 13);
   ObjectSetString(0, textName, OBJPROP_TEXT, labelText);
}

//--- v52.31: additive clustering pass - never SUPPRESSES an individual line
//--- (UpdateWallLines() always draws every slot's HLINE regardless). Decides
//--- where to layer a DrawWallZone() box: any 2+ walls within
//--- InpWallZoneClusterUsd of each other. Sorts a local copy by price first
//--- (slots arrive near-then-historical, NOT price-sorted) then a single
//--- greedy pass - WALL_SLOTS_PER_SIDE is small (20) so an O(n^2) insertion
//--- sort is fine.
//---
//--- v52.34: also fills clusteredOut[] (indexed by ORIGINAL slot index, not
//--- the sorted position) so UpdateWallLines() - which runs AFTER this -
//--- knows which walls' own TEXT labels are now redundant (Dadang: "tulisan
//--- di sini yang dikanan perlu dihilangkan... kan sudah kita kelompokan").
//--- The LINE itself is untouched either way - only the overlapping text.
void ClusterAndDrawWallZones(double &pxArr[], double &szArr[], int n, double offset, bool isBid, string sideName, bool &clusteredOut[])
{
   ObjectsDeleteAll(0, WALL_PREFIX + WALL_ZONE_PREFIX + sideName);   // wipe last cycle's zones for this side, rebuilt fresh below
   ArrayInitialize(clusteredOut, false);

   double cp[]; double cs[]; int ci[];
   ArrayResize(cp, n); ArrayResize(cs, n); ArrayResize(ci, n);
   int cnt = 0;
   for(int i = 0; i < n; i++)
   {
      if(pxArr[i] <= 0 || szArr[i] <= 0) continue;
      cp[cnt] = pxArr[i]; cs[cnt] = szArr[i]; ci[cnt] = i;
      cnt++;
   }
   for(int i = 1; i < cnt; i++)   // insertion sort by price ascending
   {
      double kp = cp[i], ks = cs[i]; int ki = ci[i];
      int j = i - 1;
      while(j >= 0 && cp[j] > kp) { cp[j+1] = cp[j]; cs[j+1] = cs[j]; ci[j+1] = ci[j]; j--; }
      cp[j+1] = kp; cs[j+1] = ks; ci[j+1] = ki;
   }

   // v52.33 fix - Dadang: "apa tidak terlalu lebar bro kan kita hanya kasih
   // box yang rapat2 aja ngumpul wall nya" - root cause: this was CHAIN
   // clustering, only checking the gap to the NEXT wall (<= threshold) one
   // hop at a time. A staircase of walls each 1-2 apart could chain into a
   // box spanning 10+ USD total even though every individual STEP looked
   // "tight" - exactly what happened to the BID box (4388.7-4399). Now
   // bounds the box's TOTAL SPAN from its first wall (cp[i]), not the
   // consecutive step - a zone can never be wider than InpWallZoneClusterUsd
   // no matter how many walls chain together.
   int zoneIdx = 0;
   int i = 0;
   while(i < cnt)
   {
      int j = i;
      while(j + 1 < cnt && (cp[j+1] - cp[i]) <= InpWallZoneClusterUsd) j++;
      if(j > i)   // 2+ walls clustered - overlay a zone box (individual lines still drawn separately, just their text suppressed)
      {
         double totalLot = 0.0;
         for(int k = i; k <= j; k++) { totalLot += cs[k]; clusteredOut[ci[k]] = true; }
         zoneIdx++;
         DrawWallZone(sideName, zoneIdx, cp[i], cp[j], totalLot, j - i + 1, offset, isBid);
      }
      i = j + 1;
   }
}

void UpdateWallZones()
{
   if(!g_bookmapOnline || g_bookmapPrice <= 0)
   {
      ObjectsDeleteAll(0, WALL_PREFIX + WALL_ZONE_PREFIX);
      ArrayInitialize(g_bidClustered, false);
      ArrayInitialize(g_askClustered, false);
      return;
   }
   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   ClusterAndDrawWallZones(g_bookmapBidPx, g_bookmapBidSz, WALL_SLOTS_PER_SIDE, offset, true,  "BID", g_bidClustered);
   ClusterAndDrawWallZones(g_bookmapAskPx, g_bookmapAskSz, WALL_SLOTS_PER_SIDE, offset, false, "ASK", g_askClustered);
}

//--- v52.69: latches the most recent REVERSAL_CONFIRMED sweep (the "proven
//--- wall" case - PENDING/CONTINUATION aren't meaningful to persist the same
//--- way) into g_sweepRec* and keeps it there until InpScalpEntryTF's own
//--- candle CLOSE genuinely crosses the level - mirrors BarrierIsBroken()'s
//--- close-based, never-a-wick rule. Call once per tick, right after
//--- ReadBookmapBridge() so g_bmSweep* is fresh.
// v52.74 - pushes one entry into the ring buffer, called only on a
// genuinely NEW sweep (same isNewEvent gate UpdateSweepRecord() already
// uses for everything else).
void LogSweepForMega(string side)
{
   g_sweepLogSide[g_sweepLogHead] = side;
   g_sweepLogTime[g_sweepLogHead] = TimeCurrent();
   g_sweepLogHead = (g_sweepLogHead + 1) % MEGA_SWEEP_LOG_LEN;
   if(g_sweepLogFilled < MEGA_SWEEP_LOG_LEN) g_sweepLogFilled++;
}

// v52.74 - recomputed every tick (not just on a new sweep) so g_megaSweepActive
// correctly clears itself once the window empties out, same "prune every
// poll" fix the web version (logic.js) needed.
void RecomputeMegaSweep()
{
   int bidCount = 0, askCount = 0;
   datetime cutoff = TimeCurrent() - MEGA_SWEEP_WINDOW_SEC;
   for(int i = 0; i < g_sweepLogFilled; i++)
   {
      if(g_sweepLogTime[i] < cutoff) continue;
      if(g_sweepLogSide[i] == "BID") bidCount++;
      else if(g_sweepLogSide[i] == "ASK") askCount++;
   }
   if(bidCount >= MEGA_SWEEP_MIN_COUNT)
   {
      g_megaSweepActive = true; g_megaSweepSide = "BID"; g_megaSweepCount = bidCount;
   }
   else if(askCount >= MEGA_SWEEP_MIN_COUNT)
   {
      g_megaSweepActive = true; g_megaSweepSide = "ASK"; g_megaSweepCount = askCount;
   }
   else
   {
      g_megaSweepActive = false; g_megaSweepSide = ""; g_megaSweepCount = 0;
   }
}

void UpdateSweepRecord()
{
   if(!g_bookmapOnline) return;
   RecomputeMegaSweep();
   double offset   = (g_bookmapPrice > 0) ? (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice) : 0.0;
   double mt5Price = g_bmSweepPrice + offset;

   bool isNewEvent = (g_bmSweepStatus == "REVERSAL_CONFIRMED") && g_bmSweepPrice > 0 &&
                      (!g_sweepRecActive || g_sweepRecSide != g_bmSweepSide || MathAbs(g_sweepRecPriceMt5 - mt5Price) > 0.05);
   if(isNewEvent)
   {
      g_sweepRecActive    = true;
      g_sweepRecSide      = g_bmSweepSide;
      g_sweepRecPriceMt5  = mt5Price;
      g_sweepRecSize      = g_bmSweepSize;
      g_sweepRecStatus    = g_bmSweepStatus;
      g_sweepRecFirstSeen = TimeCurrent();
      LogSweepForMega(g_bmSweepSide);
      // v52.73 tried a PlaySound() alert here - Dadang: "kalo di EA apa
      // bisa distop manual, kawatirnya bunyi terus2an" (a cluster of sweeps
      // in quick succession, like the staircase pattern seen earlier today,
      // would fire it repeatedly with no fast way to silence it mid-session
      // - the MT5 Properties dialog to flip an input isn't quick enough).
      // Moved to the web dashboard instead (sultan/logic.js) where a mute
      // button is one click, no dialog needed - see v52.73b there.
   }

   if(g_sweepRecActive)
   {
      double c   = iClose(_Symbol, InpScalpEntryTF, 1);
      double tol = InpBarrierVetoZoneUsd;
      bool broken = (g_sweepRecSide == "ASK") ? (c > g_sweepRecPriceMt5 + tol) : (c < g_sweepRecPriceMt5 - tol);
      if(broken)
      {
         Print("SWEEP RECORD JEBOL: ", g_sweepRecSide, " @ ", DoubleToString(g_sweepRecPriceMt5, 2),
               " (", EnumToString(InpScalpEntryTF), " close ", DoubleToString(c, 2), ")");
         g_sweepRecActive = false;
      }
   }
}

//--- v52.26/27/27b: wall SWEEP + reversal marker - Dadang: "ide gila lagi
//--- bro?" -> stop-hunt/liquidity-grab detection. Detection/resolution is
//--- 100% Python-side (cr_master_engine.py's WallLadderTracker).
//---
//--- v52.27b - Dadang looked at the actual chart (dozens of overlapping
//--- "ASK/BID WALL N: X lot" labels already crowding it) and asked: "gimana
//--- kalo di tulisan wall aja di aks atau bid di chart itu yang berubah
//--- ketika di sweep" - rather than adding YET ANOTHER separate marker
//--- object to an already-busy chart, the PRIMARY path is now
//--- DrawWallLine() repainting the swept wall's OWN existing line+label in
//--- place (see its sweptHere check) - same object, same spot, just its
//--- color/text changes to blue+"SWEPT". This function is now only the
//--- FALLBACK: it draws a standalone marker ONLY if that wall has already
//--- fully dropped out of every export slot (crowded out / genuinely gone)
//--- by the time this runs, so the read is never silently lost. Fixed
//--- cyan/blue (clrDeepSkyBlue, matches DrawWallLine()'s sweptHere color) -
//--- never used elsewhere (walls=green/red, POC=gold, VAH/VAL=dim gold,
//--- Iceberg=magenta) - "blue = sweep event" either way. v52.69: persists
//--- until g_sweepRecActive clears (genuinely broken), not a time limit -
//--- Dadang: "selama belum kejebol masih tercatat di panel".
void UpdateSweepMarker()
{
   string name     = WALL_PREFIX + "SWEEP_FALLBACK";
   string textName = WALL_PREFIX + "SWEEP_FALLBACK_TXT";
   if(!g_sweepRecActive || g_sweepDrawnOnWallLine)   // already shown on the wall's own slot - nothing more to draw
   {
      if(ObjectFind(0, name) >= 0)     ObjectDelete(0, name);
      if(ObjectFind(0, textName) >= 0) ObjectDelete(0, textName);
      return;
   }

   double mt5Price = g_sweepRecPriceMt5;
   long   ageSec   = (long)(TimeCurrent() - g_sweepRecFirstSeen);

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrDeepSkyBlue);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT,
      StringFormat("SWEEP %s %.0f lot @ %.2f - REVERSAL (%s lalu, masih berlaku)", g_sweepRecSide, g_sweepRecSize, mt5Price, TimeAgoText(ageSec)));

   datetime labelTime = TimeCurrent() + PeriodSeconds(_Period) * 70;   // own lane, past wall/POC/VAH/VAL/Iceberg (8-65)
   if(ObjectFind(0, textName) < 0)
   {
      ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, mt5Price);
      ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_LEFT);
   }
   ObjectSetInteger(0, textName, OBJPROP_TIME, labelTime);
   ObjectSetDouble(0, textName, OBJPROP_PRICE, mt5Price);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, clrDeepSkyBlue);
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 14);
   ObjectSetString(0, textName, OBJPROP_TEXT,
      StringFormat(" SWEEP %s: REVERSAL (%s)", g_sweepRecSide, TimeAgoText(ageSec)));
}

//--- v29: POC (Point of Control) - price level with the most TOTAL traded
//--- volume this session (VolumeProfileEngine, Bookmap side) - distinct
//--- from the wall lines above (those are resting ORDER book size, this is
//--- volume that actually TRADED). Drawn as one solid gold line, uses the
//--- WALL_PREFIX namespace so it gets cleaned up by the same
//--- ObjectsDeleteAll(0, WALL_PREFIX) calls that clear wall lines when
//--- Bookmap goes offline/stale.
//--- v52.37: returns the TIME at (near) the chart's actual visible RIGHT
//--- EDGE right now - Dadang: "beri nama garis vah dan val dan poc nya di
//--- ujung kanan yang keren" - unlike anchoring N bars ahead of
//--- TimeCurrent() (which drifts off whatever's actually in view depending
//--- on how far the chart is scrolled/zoomed - the same class of bug fixed
//--- for the sweep-zone label earlier), this converts the chart's own pixel
//--- width back to a time value, so POC/VAH/VAL labels always sit right at
//--- the edge no matter the zoom/scroll state. marginPx staggers multiple
//--- labels a bit apart so they don't stack directly on top of each other.
datetime ChartRightEdgeTime(int marginPx = 20)
{
   int w = (int)ChartGetInteger(0, CHART_WIDTH_IN_PIXELS);
   int sub = 0;
   datetime t; double p;
   if(w <= 0 || !ChartXYToTimePrice(0, w - marginPx, 50, sub, t, p))
      return TimeCurrent() + PeriodSeconds(_Period) * 40;   // fallback if the chart isn't ready yet
   return t;
}

void UpdatePocLine()
{
   string name     = WALL_PREFIX + "POC";
   string textName = WALL_PREFIX + "POC_TXT";
   if(!g_bookmapOnline || g_bookmapPocPrice <= 0 || g_bookmapPocVolume <= 0)
   {
      if(ObjectFind(0, name) >= 0)     ObjectDelete(0, name);
      if(ObjectFind(0, textName) >= 0) ObjectDelete(0, textName);
      return;
   }
   double offset   = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   double mt5Price = g_bookmapPocPrice + offset;

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT,
      StringFormat("POC %.0f vol @ %.2f (bookmap %.2f)", g_bookmapPocVolume, mt5Price, g_bookmapPocPrice));

   // v52.37: pinned to the chart's actual visible right edge (see
   // ChartRightEdgeTime()) instead of a fixed bar-count lane - always
   // visible regardless of zoom/scroll.
   datetime labelTime = ChartRightEdgeTime(20);
   if(ObjectFind(0, textName) < 0)
   {
      ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, mt5Price);
      ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_RIGHT);
   }
   ObjectSetInteger(0, textName, OBJPROP_TIME, labelTime);
   ObjectSetDouble(0, textName, OBJPROP_PRICE, mt5Price);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, clrGold);
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 14);
   ObjectSetString(0, textName, OBJPROP_TEXT, StringFormat("POC: %.0f vol ", g_bookmapPocVolume));
}

//--- v52.36: 5-state POC/Value-Area location, POC/VA-only (no H4 mixed in -
//--- see below). Dadang, after getting POC/VAH/VAL explained: "jika di area
//--- tengah 2 statusnya sideways bro dan jika di atas poc atau di bawah poc
//--- statusnya apa ya mungkin potensi atau apa gitu bro." Splits the old
//--- "anything inside VA = flat SIDEWAYS" read (this replaces the unused-
//--- since-a-while-ago ComputeBias(), which did that + folded in H4
//--- agreement) into two READING zones on either side of POC:
//---   > VAH            -> "BUY (breakout)"     - price has left value entirely, strong
//---   POC < price ≤ VAH -> "POTENTIAL BUY"      - still inside value, but leaning up
//---   VAL ≤ price < POC -> "POTENTIAL SELL"     - still inside value, but leaning down
//---   < VAL             -> "SELL (breakout)"     - strong
//---   == POC exactly    -> "SIDEWAYS"           - dead center, no lean either way
//--- Deliberately POC/VA-only, unlike the old ComputeBias() - Dadang's
//--- question was specifically about reading POC/VAH/VAL alone; H4
//--- alignment already has its own row elsewhere in the panel, meant to be
//--- read side-by-side rather than pre-blended into one string.
//--- v52.40: BUY/SELL (breakout) requires a CONFIRMED M5 candle close past
//--- VAH/VAL, not a live/running tick price - see the close-vs-wick note
//--- inside the function.
string ComputeVaLocation()
{
   if(!g_bookmapOnline || g_bookmapPocPrice <= 0 || g_bookmapPrice <= 0)
      return "N/A";

   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   // v52.40 fix - Dadang: "breakout val dan vah ini valid ketika body
   // breakout atau meski masih running?" - per the same doctrine as CMP
   // (CLAUDE.md: "Candle CLOSE melampaui minor SNR, bukan wick") a breakout
   // must be a CONFIRMED candle close, not a live/running tick price that
   // could still reverse before the candle finishes. Was
   // SymbolInfoDouble(SYMBOL_BID) - live, tick-by-tick, could flicker
   // BUY(breakout)/SIDEWAYS/SELL(breakout) within a single still-forming
   // candle just off a wick.
   // v52.48 bumped this from M5 to InpScalpMasterTF (M30) to kill flicker,
   // but that made VA Bias/VA Retest go blind to intrabar reversals for up
   // to 30 minutes (M30's own close-1 candle can be stale mid-bar even as
   // price already rallies/dumps hard) - Dadang caught this live 2026-08-21
   // looking at a panel stuck on "SELL (breakout)" while the chart was
   // clearly ripping back up, and chose to trade the flicker risk back for
   // reactivity: "balikin ke M5 close". Reverted to InpScalpEntryTF (the
   // system's own M5 slot, not a hardcoded PERIOD_M5) so it stays in sync if
   // that input ever changes.
   double refPrice = iClose(_Symbol, InpScalpEntryTF, 1);
   if(refPrice <= 0) refPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);   // fallback if M30 history isn't ready yet
   double pocMt5 = g_bookmapPocPrice + offset;

   if(g_bookmapVah > g_bookmapVal && g_bookmapVal > 0)
   {
      double vahMt5 = g_bookmapVah + offset;
      double valMt5 = g_bookmapVal + offset;
      if(refPrice > vahMt5) return "BUY (breakout)";
      if(refPrice < valMt5) return "SELL (breakout)";
      if(refPrice > pocMt5) return "POTENTIAL BUY";
      if(refPrice < pocMt5) return "POTENTIAL SELL";
      return "SIDEWAYS";
   }
   // VAH/VAL not formed yet this session - fall back to the flat $ zone
   // around POC (same InpPocSidewaysZoneUsd used elsewhere for this purpose).
   double diff = refPrice - pocMt5;
   if(diff > InpPocSidewaysZoneUsd)  return "POTENTIAL BUY";
   if(diff < -InpPocSidewaysZoneUsd) return "POTENTIAL SELL";
   return "SIDEWAYS";
}

//--- v34: SULTAN SNIPER ENGINE web dashboard export. Dadang: "gak usah baca
//--- pine langsung mt5 aja supaya bagus tv nya kita close" - MT5's own
//--- DD_CMP_Indicator always has full historical bars (unlike Bookmap's own
//--- tick-only CMP, which needs hours/days to warm up and resets on every
//--- udp_listener.py restart) - so this exports Market Regime directly from
//--- MT5, no TradingView/Pine dependency anywhere in this pipeline anymore.
//--- Writes Common\Files\sultan_status.json, read by the new web dashboard
//--- (sultan_dashboard_server.py + sultan/index.html) - throttled to ~1/sec.
//--- Formulas for "ratio"/"imbalance" fields are this EA's OWN reasonable
//--- interpretation (documented inline), not a reverse-engineered replica of
//--- any specific external mockup's exact numbers.
void WriteSultanStatus()
{
   if((int)(TimeGMT() - g_lastSultanExportTime) < 1) return;   // throttle ~1/sec
   g_lastSultanExportTime = TimeGMT();

   //--- Market Regime: D1/H1/M15 read fresh from MT5 (full history, no
   //--- warm-up) purely for display - NOT part of the H4/M30/M5 trading
   //--- cascade, which stays exactly as-is.
   datetime tD1, tH1, tM15, tM1;
   string d1Dir  = ReadCMP(g_hExportD1,  tD1);
   string h1Dir  = ReadCMP(g_hExportH1,  tH1);
   string m15Dir = ReadCMP(g_hExportM15, tM15);
   string m1Dir  = ReadCMP(g_hExportM1,  tM1);   // v37: passthrough for udp_listener.py's M1-leading-indicator commentary (was Pine-only before)

   int buyCount = 0, sellCount = 0, validCount = 0;
   if(g_masterDir      == "BUY") buyCount++; else if(g_masterDir      == "SELL") sellCount++;
   if(g_scalpMasterDir == "BUY") buyCount++; else if(g_scalpMasterDir == "SELL") sellCount++;
   if(g_scalpEntryDir  == "BUY") buyCount++; else if(g_scalpEntryDir  == "SELL") sellCount++;
   validCount = (g_masterDir != "WAIT" ? 1 : 0) + (g_scalpMasterDir != "WAIT" ? 1 : 0) + (g_scalpEntryDir != "WAIT" ? 1 : 0);
   // Alignment % = how much of H4/M30/M5 agree with the MAJORITY direction -
   // 100% = all 3 same, else SIDEWAYS. Own formula, not a replica of any
   // specific external reference. Exported as-is (alignment alone) for
   // context; the actual TRENDING/SIDEWAYS call below now goes through
   // IsRegimeTrending() (v52.41: also requires POC to have migrated with
   // the trend, not just CMP alignment - was a duplicated inline copy of
   // this same formula before, now the single shared definition).
   double alignmentPct = (validCount > 0) ? (MathMax(buyCount, sellCount) / 3.0 * 100.0) : 0.0;
   string regime  = IsRegimeTrending() ? "TRENDING" : "SIDEWAYS";
   string htfBias = (g_masterDir == "BUY") ? "BULLISH" : (g_masterDir == "SELL") ? "BEARISH" : "NEUTRAL";
   string m5Status = (g_scalpEntryDir == "WAIT") ? "WAIT" : (g_scalpEntryDir == g_masterDir) ? "WITH_TREND" : "COUNTER_TREND";

   //--- Bookmap Flow: 1-minute CVD delta history, sampled once per REAL
   //--- minute (wall-clock, not chart bars) into a small ring buffer.
   MqlDateTime dtNow;
   TimeToStruct(TimeGMT(), dtNow);
   int curMinuteBucket = dtNow.hour * 60 + dtNow.min;
   if(curMinuteBucket != g_lastCvdSampleMinute)
   {
      g_lastCvdSampleMinute = curMinuteBucket;
      for(int i = 0; i < CVD_HIST_LEN - 1; i++) g_cvdMinuteSamples[i] = g_cvdMinuteSamples[i + 1];
      g_cvdMinuteSamples[CVD_HIST_LEN - 1] = g_bookmapCvd;
      if(g_cvdSampleCount < CVD_HIST_LEN) g_cvdSampleCount++;
   }
   double delta1m = (g_cvdSampleCount >= 2) ? (g_cvdMinuteSamples[CVD_HIST_LEN - 1] - g_cvdMinuteSamples[CVD_HIST_LEN - 2]) : 0.0;
   string flowDominant = (g_bookmapVolRatioBuyPct >= 50.0) ? "BUY" : "SELL";

   //--- Liquidity: nearest wall + summary across all slots. "Ratio" here =
   //--- size / 10-lot baseline (same baseline WallWidth()/WallColor() use
   //--- for chart line scaling) - a strength multiplier, own interpretation.
   double offset = (g_bookmapPrice > 0) ? (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice) : 0.0;
   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double bidWallPx = (g_bookmapBidPx[0] > 0) ? g_bookmapBidPx[0] + offset : 0.0;
   double askWallPx = (g_bookmapAskPx[0] > 0) ? g_bookmapAskPx[0] + offset : 0.0;
   double bidWallSz = g_bookmapBidSz[0], askWallSz = g_bookmapAskSz[0];
   double distBid = (bidWallPx > 0) ? MathAbs(curPrice - bidWallPx) : 999999.0;
   double distAsk = (askWallPx > 0) ? MathAbs(curPrice - askWallPx) : 999999.0;
   string nearestWallSide = (distBid <= distAsk) ? "BID" : "ASK";
   double nearestWallDist = MathMin(distBid, distAsk);

   int bidWallCount = 0, askWallCount = 0;
   double bidTotalLot = 0.0, askTotalLot = 0.0;
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      if(g_bookmapBidPx[i] > 0) { bidWallCount++; bidTotalLot += g_bookmapBidSz[i]; }
      if(g_bookmapAskPx[i] > 0) { askWallCount++; askTotalLot += g_bookmapAskSz[i]; }
   }
   double wallImbalance = (bidTotalLot + askTotalLot > 0) ? (bidTotalLot - askTotalLot) / MathMax(bidTotalLot, askTotalLot) : 0.0;

   //--- Location: POC/VA position + distance, plus ATR(14 on H1)/24h range.
   double pocMt5 = (g_bookmapPocPrice > 0) ? g_bookmapPocPrice + offset : 0.0;
   double valMt5 = (g_bookmapVal > 0) ? g_bookmapVal + offset : 0.0;
   double vahMt5 = (g_bookmapVah > 0) ? g_bookmapVah + offset : 0.0;
   string position = "UNKNOWN";
   if(vahMt5 > valMt5 && valMt5 > 0)
      position = (curPrice > vahMt5) ? "ABOVE_VA" : (curPrice < valMt5) ? "BELOW_VA" : "INSIDE_VA";
   double distToPoc = (pocMt5 > 0) ? (curPrice - pocMt5) : 0.0;
   double vaWidth = (vahMt5 > valMt5) ? (vahMt5 - valMt5) : 0.0;
   double distToPocPct = (vaWidth > 0) ? (MathAbs(distToPoc) / vaWidth * 100.0) : 0.0;

   double atr14 = 0.0;
   double atrBuf[1];
   if(g_hATR != INVALID_HANDLE && CopyBuffer(g_hATR, 0, 0, 1, atrBuf) > 0) atr14 = atrBuf[0];

   double hi24 = -1.0, lo24 = 999999.0;
   for(int i = 0; i < 24; i++)
   {
      double h = iHigh(_Symbol, PERIOD_H1, i);
      double l = iLow(_Symbol, PERIOD_H1, i);
      if(h > hi24) hi24 = h;
      if(l < lo24 && l > 0) lo24 = l;
   }
   double range24h = (hi24 > 0) ? (hi24 - lo24) : 0.0;

   //--- Context Summary: plain-English synthesis of everything above.
   string liquidityCtx = (nearestWallSide == "BID") ? "BID_SUPPORT" : "ASK_RESISTANCE";
   string action = "WAIT_OBSERVE";
   if(regime == "TRENDING" && htfBias != "NEUTRAL" &&
      ((htfBias == "BULLISH" && flowDominant == "BUY") || (htfBias == "BEARISH" && flowDominant == "SELL")))
      action = (htfBias == "BULLISH") ? "FAVOR_BUY" : "FAVOR_SELL";

   //--- Build delta history JSON array (oldest first).
   string deltaHistJson = "[";
   int startIdx = CVD_HIST_LEN - g_cvdSampleCount;
   for(int i = startIdx; i < CVD_HIST_LEN; i++)
   {
      double d = (i == startIdx) ? 0.0 : (g_cvdMinuteSamples[i] - g_cvdMinuteSamples[i - 1]);
      deltaHistJson += StringFormat("%.1f", d);
      if(i < CVD_HIST_LEN - 1) deltaHistJson += ",";
   }
   deltaHistJson += "]";

   string json = "{";
   json += StringFormat("\"timestamp\":%.0f,", (double)TimeGMT());
   json += StringFormat("\"online\":%s,", g_bookmapOnline ? "true" : "false");
   json += StringFormat("\"symbol\":\"%s\",", _Symbol);
   json += StringFormat("\"price\":%.2f,", curPrice);
   json += StringFormat("\"balance\":%.2f,\"equity\":%.2f,",
                         AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY));
   json += StringFormat("\"ea_version\":\"%s\",", EA_VERSION);

   json += "\"regime\":{";
   json += StringFormat("\"h4\":\"%s\",\"m30\":\"%s\",\"m5\":\"%s\",", g_masterDir, g_scalpMasterDir, g_scalpEntryDir);
   json += StringFormat("\"d1\":\"%s\",\"h1\":\"%s\",\"m15\":\"%s\",\"m1\":\"%s\",", d1Dir, h1Dir, m15Dir, m1Dir);
   json += StringFormat("\"alignment_pct\":%.1f,\"regime\":\"%s\",\"htf_bias\":\"%s\",\"m5_status\":\"%s\"",
                         alignmentPct, regime, htfBias, m5Status);
   json += "},";

   json += "\"flow\":{";
   json += StringFormat("\"cvd\":%.1f,\"delta_1m\":%.1f,\"delta_history\":%s,", g_bookmapCvd, delta1m, deltaHistJson);
   json += StringFormat("\"vol_ratio_buy_pct\":%.1f,\"pulse_pct\":%.1f,\"absorption\":\"%s\",\"flow_dominant\":\"%s\"",
                         g_bookmapVolRatioBuyPct, g_bookmapPulsePct, g_bookmapAbsorption, flowDominant);
   json += "},";

   // v36: full ladder (not just nearest) - Dadang wants a proper vertical
   // wall ladder widget (red asks above price, green bids below, like a DOM)
   // in the web dashboard, not just a single "nearest wall" line. Exports
   // every non-zero wall slot (already offset-converted to MT5/XAUUSD scale)
   // - the frontend sorts/renders them, MQL5 just serializes what it has.
   string bidLadderJson = "[", askLadderJson = "[";
   bool bidFirst = true, askFirst = true;
   for(int i = 0; i < WALL_SLOTS_PER_SIDE; i++)
   {
      if(g_bookmapBidPx[i] > 0)
      {
         if(!bidFirst) bidLadderJson += ",";
         bidLadderJson += StringFormat("[%.2f,%.1f]", g_bookmapBidPx[i] + offset, g_bookmapBidSz[i]);
         bidFirst = false;
      }
      if(g_bookmapAskPx[i] > 0)
      {
         if(!askFirst) askLadderJson += ",";
         askLadderJson += StringFormat("[%.2f,%.1f]", g_bookmapAskPx[i] + offset, g_bookmapAskSz[i]);
         askFirst = false;
      }
   }
   bidLadderJson += "]";
   askLadderJson += "]";

   json += "\"liquidity\":{";
   json += StringFormat("\"bid_wall_price\":%.2f,\"bid_wall_size\":%.1f,\"bid_wall_ratio\":%.1f,",
                         bidWallPx, bidWallSz, bidWallSz / 10.0);
   json += StringFormat("\"ask_wall_price\":%.2f,\"ask_wall_size\":%.1f,\"ask_wall_ratio\":%.1f,",
                         askWallPx, askWallSz, askWallSz / 10.0);
   json += StringFormat("\"nearest_wall_side\":\"%s\",\"nearest_wall_distance\":%.2f,", nearestWallSide, nearestWallDist);
   json += StringFormat("\"wall_imbalance\":%.2f,\"bid_wall_count\":%d,\"ask_wall_count\":%d,",
                         wallImbalance, bidWallCount, askWallCount);
   json += StringFormat("\"bid_wall_total_lot\":%.1f,\"ask_wall_total_lot\":%.1f,", bidTotalLot, askTotalLot);
   json += "\"bid_ladder\":" + bidLadderJson + ",\"ask_ladder\":" + askLadderJson;
   json += "},";

   // v52.26: wall SWEEP + reversal - Dadang: "ide gila lagi bro?" -> stop-
   // hunt/liquidity-grab detection, same passthrough pattern as everything
   // else in this export (Python computes, MQL5 offset-converts + forwards).
   // v52.69: sourced from the PERSISTENT record now (g_sweepRec*), not the
   // raw bridge fields - stays consistent with the MT5 panel/chart, which no
   // longer hides this after 20 min, only when genuinely broken. "active"
   // added for a future web frontend update to drop its own time-window gate.
   long sweepRecAgeSec = g_sweepRecActive ? (long)(TimeCurrent() - g_sweepRecFirstSeen) : 0;
   json += StringFormat("\"wall_sweep\":{\"active\":%s,\"side\":\"%s\",\"price\":%.2f,\"size\":%.1f,\"status\":\"%s\",\"since_sec\":%.0f},",
                         g_sweepRecActive ? "true" : "false", g_sweepRecSide, g_sweepRecPriceMt5, g_sweepRecSize,
                         g_sweepRecActive ? g_sweepRecStatus : "NONE", (double)sweepRecAgeSec);

   // v42: macro correlation passthrough - lets the Sultan web dashboard show
   // the same dollar-vs-setup readout as the chart panel, from one source.
   // v43.2: USD fundamental now comes from MT5 itself (DXY, EURUSD fallback)
   // plus the economic calendar - the Bookmap 6E fields are kept but are only
   // populated if that path is ever re-enabled.
   string goldEffectJson = (g_usdBias == "WEAK") ? "GOLD NAIK" : (g_usdBias == "STRONG") ? "GOLD TURUN" : "-";
   json += StringFormat("\"macro\":{\"active\":%s,\"direction\":\"%s\",\"usd\":\"%s\",\"cvd\":%.1f,\"flow_confirms\":%s,\"verdict\":\"%s\"},",
                         g_macroActive ? "true" : "false", g_macroDirection, g_macroUsd,
                         g_macroCvd, g_macroFlowOk ? "true" : "false", g_macroVerdict);
   json += StringFormat("\"usd\":{\"symbol\":\"%s\",\"dir\":\"%s\",\"bias\":\"%s\",\"gold_effect\":\"%s\",\"next_event\":\"%s\",\"next_mins\":%d},",
                         g_usdSymbol, g_eurDir, g_usdBias, goldEffectJson,
                         g_usdNextEvent, g_usdNextMins);

   // v44: conviction score - display only, mirrors the chart panel block.
   json += StringFormat("\"conviction\":{\"dir\":\"%s\",\"mode\":\"%s\",\"score\":%d,\"max\":%d,\"grade\":\"%s\",\"chain_done\":\"%s\",\"chain_next\":\"%s\",\"chain_pending\":\"%s\",\"flow_score\":%d,\"flow_max\":%d,\"against\":[",
                         g_convDir, g_convMode, g_convScore, g_convMax, g_convGrade,
                         g_chainDone, g_chainNext, g_chainPending, g_flowScore, g_flowMax);
   if(g_convAgainst1 != "") json += "\"" + g_convAgainst1 + "\"";
   if(g_convAgainst2 != "") json += ",\"" + g_convAgainst2 + "\"";
   if(g_convAgainst3 != "") json += ",\"" + g_convAgainst3 + "\"";
   json += "]},";

   // v52.6: the 5-step Bookmap read, narrated - Dadang: "dari 5 urutan itu
   // bisa gak kalo masukin ke ea dan web gw sebagai narasi tapi di ea dia
   // entri beneran". verdict is BookmapTriggerDirection()'s literal output
   // via g_bmNarrVerdict (see ComputeBookmapNarrative()) - same value that
   // decides whether CheckBookmapTrigger() actually opens a position.
   // v52.74: raw bid/ask iceberg price added (was narrated text only) -
   // Dadang wants a "reload counter" (same iceberg price reappearing after
   // being consumed = a committed hidden player, not a one-off). That's a
   // client-side history check the web dashboard can do for itself once it
   // has the actual price to key on - g_bookmapBidIcePx/AskIcePx already
   // exist (used to draw the chart lines), just weren't exported before.
   json += StringFormat("\"bookmap_read\":{\"wall\":\"%s\",\"cvd\":\"%s\",\"absorption\":\"%s\",\"iceberg\":\"%s\",\"location\":\"%s\",\"verdict\":\"%s\",\"iceberg_bid_px\":%.2f,\"iceberg_ask_px\":%.2f},",
                         g_bmNarrWall, g_bmNarrCvd, g_bmNarrAbsorb, g_bmNarrIceberg, g_bmNarrLocation, g_bmNarrVerdict,
                         g_bookmapBidIcePx, g_bookmapAskIcePx);

   json += "\"location\":{";
   json += StringFormat("\"poc\":%.2f,\"val\":%.2f,\"vah\":%.2f,\"current_price\":%.2f,", pocMt5, valMt5, vahMt5, curPrice);
   json += StringFormat("\"position\":\"%s\",\"distance_to_poc\":%.2f,\"distance_to_poc_pct\":%.1f,",
                         position, distToPoc, distToPocPct);
   // v52.36: same 5-state POC/VA bias as the MT5 panel's "VA Bias" row -
   // see ComputeVaLocation()'s comment (Dadang: "jika di atas poc atau di
   // bawah poc statusnya apa ya mungkin potensi atau apa gitu bro").
   json += StringFormat("\"va_bias\":\"%s\",", ComputeVaLocation());
   json += StringFormat("\"range_24h\":%.2f,\"atr14\":%.2f", range24h, atr14);
   json += "},";

   json += "\"context\":{";
   json += StringFormat("\"htf_bias\":\"%s\",\"flow\":\"%s\",\"liquidity\":\"%s\",\"location\":\"%s\",\"regime\":\"%s\",\"action\":\"%s\"",
                         htfBias, flowDominant, liquidityCtx, position, regime, action);
   json += "},";

   // v52.57: SULTAN web export ("http://localhost:8766/") for today's new EA
   // panel rows - Dadang: "yang udah ada penambahan di ea tadi lo tambah
   // juga di web". Same source functions as the MT5 panel (barrier queues/
   // g_fusion*/MomentumBreakoutText/CandleCountdownSec) - the web dashboard
   // can never disagree with what the EA itself is acting on.
   json += "\"signals\":{";
   // v52.59: "warning" = the same compact multi-TF "AWAS ..." line as the MT5
   // panel's "Barrier" row (BarrierWarningText()) - Dadang: "barrier tidak
   // perlu ditulis besar hanya dijadikan peringatan aja" - web should show
   // ONE short line, not a wall of per-TF boxes. Per-TF breakdown kept too
   // (barrier.h4/h1/m30/m15/m5) in case the frontend wants it later.
   color warnClrUnused; string warnTxt = BarrierWarningText(warnClrUnused);
   json += StringFormat("\"barrier_warning\":\"%s\",", warnTxt);
   // v52.60: barrier is now a QUEUE per TF (Dadang's 2-diagram explanation -
   // a barrier is a whole staircase, not 1 level), exported as a JSON array
   // of {dir,level} instead of a single object.
   json += "\"barrier\":{";
   json += "\"h4\":"  + JsonBarrierQueue(g_h4Queue)  + ",";
   json += "\"h1\":"  + JsonBarrierQueue(g_h1Queue)  + ",";
   json += "\"m30\":" + JsonBarrierQueue(g_m30Queue) + ",";
   json += "\"m15\":" + JsonBarrierQueue(g_m15Queue) + ",";
   json += "\"m5\":"  + JsonBarrierQueue(g_m5Queue)  + ",";
   json += "\"d1\":"  + JsonBarrierQueue(g_d1Queue);   // v52.61: H4's "parent" for the pairing
   json += "},";

   string fusionStatus = "-"; string fusionDirOut = "";
   if(InpUseFusionH1H4)
   {
      if(g_fusionTicket != 0)      { fusionStatus = "IN POSITION (struktural, tunggu H4 flip)"; fusionDirOut = g_fusionDir; }
      else if(g_fusionVrSet)       { fusionStatus = "VR ARMED " + g_fusionDir + " - nunggu retest zona H4"; fusionDirOut = g_fusionDir; }
   }
   json += StringFormat("\"fusion\":{\"enabled\":%s,\"status\":\"%s\",\"dir\":\"%s\"},",
                         InpUseFusionH1H4 ? "true" : "false", fusionStatus, fusionDirOut);

   // v52.96 - switched to the LiveMomentum* trio (candle-open-anchored,
   // display-only) so the web dashboard shows the same corrected reading
   // as the MT5 panel - see the LiveCandleDir()/LiveMomentum* block's
   // comment above for why (Dadang: "namanya momentum bukan cmp yang kita
   // baca"). The dir exported here only feeds display coloring on the
   // web, never entry logic (CheckMomentumEntryTrigger() calls
   // MomentumRatio() directly, untouched by this change).
   // v52.97 - each row now reads its OWN g_stabMom*.dir (the STABILIZED
   // direction, set as a side effect of calling its Live*Text() function
   // just above) instead of a fresh/shared LiveCandleDir() call - with
   // debouncing, the 3 rows can legitimately be mid-transition at
   // different moments, so sharing one dir value across all three (fine
   // when they were CMP-anchored and always identical) would desync the
   // web's color from its own text.
   color momClrUnused;
   string momText = LiveMomentumPriceText(momClrUnused);
   json += StringFormat("\"momentum_m5\":{\"text\":\"%s\",\"dir\":\"%s\"},", momText, g_stabMomPrice.dir);

   // v52.80 - export the 2 Bookmap-confluence momentum rows + Chain Signal
   // for the web dashboard port (Dadang: "kerjakan ke web nya" after
   // confirming they were EA-only so far).
   color momBmClrUnused, momFpClrUnused;
   string momBmText = LiveMomentumBookmapText(momBmClrUnused);
   string momFpText = LiveMomentumFootprintText(momFpClrUnused);
   json += StringFormat("\"momentum_m5_bookmap\":{\"text\":\"%s\",\"dir\":\"%s\"},", momBmText, g_stabMomBookmap.dir);
   json += StringFormat("\"momentum_m5_footprint\":{\"text\":\"%s\",\"dir\":\"%s\"},", momFpText, g_stabMomFootprint.dir);
   json += StringFormat("\"chain_signal\":{\"layer\":%d,\"dir\":\"%s\"},", g_chainSigLayer, g_chainSigMasterDir);
   color cvdDivClrUnused;
   string cvdDivTextForJson = CvdDivergenceText(cvdDivClrUnused);
   json += StringFormat("\"cvd_divergence\":{\"text\":\"%s\",\"status\":\"%s\"},", cvdDivTextForJson, g_cvdDivStatus);
   color ivbClrUnused, dpfClrUnused;
   string ivbTextForJson = IvbText(ivbClrUnused);
   string dpfTextForJson = DailyProfileFramingText(dpfClrUnused);
   json += StringFormat("\"ivb\":{\"text\":\"%s\",\"locked\":%s},", ivbTextForJson, g_ivbLocked ? "true" : "false");
   json += StringFormat("\"daily_profile\":{\"text\":\"%s\"},", dpfTextForJson);
   color volNodeClrUnused, reloadClrUnused;
   string volNodeTextForJson = VolumeNodeText(volNodeClrUnused);
   string reloadTextForJson  = ReloadLevelText(reloadClrUnused);
   json += StringFormat("\"volume_node\":{\"text\":\"%s\"},", volNodeTextForJson);
   json += StringFormat("\"reload_level\":{\"text\":\"%s\"},", reloadTextForJson);

   json += "\"countdown\":{";
   json += StringFormat("\"h4\":%d,\"h1\":%d,\"m30\":%d,\"m15\":%d,\"m5\":%d,\"m1\":%d",
                         CandleCountdownSec(InpMasterTF), CandleCountdownSec(PERIOD_H1), CandleCountdownSec(InpScalpMasterTF),
                         CandleCountdownSec(PERIOD_M15), CandleCountdownSec(InpScalpEntryTF), CandleCountdownSec(PERIOD_M1));
   json += "}";
   json += "},";

   // v53.12 - S&D Zone export for the web dashboard's own "S&D PRICE MAP"
   // (Dadang: "DI WEB KITA JUGA HARUS ADA INI... ROMBAK TOTAL WEB NYA YANG
   // PENTING TETAP PROFESIONAL DAN HIDUP") - same g_zone*/g_sdm*/roadmap
   // data already driving the MT5 chart+panel, forwarded as-is so the web
   // can build pulse/warning-on-zone-entry + a full roadmap list without
   // recomputing anything server-side.
   string zonesJson = "[";
   for(int zi = 0; zi < g_zoneCount; zi++)
   {
      if(zi > 0) zonesJson += ",";
      zonesJson += StringFormat("{\"side\":\"%s\",\"lo\":%.2f,\"hi\":%.2f,\"wall_count\":%d,\"total_lot\":%.1f,\"status\":\"%s\",\"strength\":\"%s\",\"retest_count\":%d,\"absorption_hits\":%d,\"score\":%.0f}",
                                 g_zoneSide[zi], g_zoneLo[zi], g_zoneHi[zi], g_zoneWallCount[zi], g_zoneTotalLot[zi],
                                 g_zoneStatus[zi], ZoneStrengthID(g_zoneScore[zi]), g_zoneRetest[zi], g_zoneAbsorb[zi], g_zoneScore[zi]);
   }
   zonesJson += "]";

   string supplyRoadJson = "[";
   for(int ri = 0; ri < g_supplyRoadCount; ri++)
   {
      if(ri > 0) supplyRoadJson += ",";
      supplyRoadJson += StringFormat("{\"lo\":%.2f,\"hi\":%.2f,\"score\":%.0f,\"strength\":\"%s\"}",
                                      g_supplyRoadLo[ri], g_supplyRoadHi[ri], g_supplyRoadScore[ri], ZoneStrengthID(g_supplyRoadScore[ri]));
   }
   supplyRoadJson += "]";

   string demandRoadJson = "[";
   for(int ri = 0; ri < g_demandRoadCount; ri++)
   {
      if(ri > 0) demandRoadJson += ",";
      demandRoadJson += StringFormat("{\"lo\":%.2f,\"hi\":%.2f,\"score\":%.0f,\"strength\":\"%s\"}",
                                      g_demandRoadLo[ri], g_demandRoadHi[ri], g_demandRoadScore[ri], ZoneStrengthID(g_demandRoadScore[ri]));
   }
   demandRoadJson += "]";

   color sdFocusClrUnused; string sdFocusTxt = FocusText(sdFocusClrUnused);
   json += "\"sd_zones\":{";
   json += StringFormat("\"available\":%s,", g_zoneDataAvailable ? "true" : "false");
   json += "\"zones\":" + zonesJson + ",";
   json += "\"roadmap\":{\"supply\":" + supplyRoadJson + ",\"demand\":" + demandRoadJson + "},";
   json += "\"decision\":{";
   json += StringFormat("\"location\":\"%s\",\"location_text\":\"%s\",\"market_state\":\"%s\",\"setup\":\"%s\",\"reason\":\"%s\",\"reason_text\":\"%s\",\"focus\":\"%s\",",
                         g_sdmLocation, LocationText(g_sdmLocation), g_sdmMarketState, g_sdmSetup,
                         g_sdmReason, ReasonText(g_sdmReason), sdFocusTxt);
   json += StringFormat("\"buyer_pct\":%.0f,\"seller_pct\":%.0f,\"compression\":%s",
                         g_sdmBuyerPct, g_sdmSellerPct, ZoneCompressionActive() ? "true" : "false");
   json += "},";

   // v53.25 - S&D Momentum Break Engine export (v53.18 built MT5-only per
   // "berhenti, tunggu review saya" - Dadang confirmed + asked to wire it
   // to web/AI too: "apa perubahan tadi sudah lo update ke ai web dan web
   // bro yang break out SND tadi? kalo belum lo kerjakan"). Straight
   // passthrough of the same g_sdBrk*/g_sdMarketRead state already
   // driving the MT5 panel's "Break Status" row - never recomputed here.
   json += "\"break\":{";
   json += StringFormat("\"supply_state\":\"%s\",\"supply_momentum\":\"%s\",", g_sdBrkState_S, g_sdBrkMomentum_S);
   json += StringFormat("\"demand_state\":\"%s\",\"demand_momentum\":\"%s\",", g_sdBrkState_D, g_sdBrkMomentum_D);
   json += StringFormat("\"market_read\":\"%s\",\"direction\":\"%s\",", g_sdMarketRead, SDBreakoutDirection());
   json += StringFormat("\"status_text\":\"%s\",\"no_trade_zone\":%s",
                         SDBreakStatusText(), SDNoTradeZoneActive() ? "true" : "false");
   json += "}";
   json += "},";

   json += "\"data_status\":{";
   json += StringFormat("\"bookmap_online\":%s,\"bridge_latency_ms\":%.0f", g_bookmapOnline ? "true" : "false", g_bookmapAgeMs);
   json += "}";
   json += "}";

   int handle = FileOpen("sultan_status.json.tmp", FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI);
   if(handle == INVALID_HANDLE) return;
   FileWriteString(handle, json);
   FileClose(handle);
   // atomic-ish swap - avoid the web server ever reading a half-written file
   FileDelete("sultan_status.json", FILE_COMMON);
   FileMove("sultan_status.json.tmp", FILE_COMMON, "sultan_status.json", FILE_COMMON);

   // v52.85 - DNA Vault: Dadang, 2026-08-23: "semua data harus kerecord
   // setiap gw start sampai off bro karena histori itu yang akan kita
   // pelajari tiap weekend untuk upgrade". Everything EA-computed (Chain
   // Signal, CVD Divergence, IVB, Daily Profile, Volume Node, Reload Level,
   // momentum variants, wall/POC/VAH/VAL, sweep, macro, PnL, etc.) was
   // live-only until now - gone the moment the terminal restarts or the day
   // rolls over. Appends the SAME `json` payload just built above (one line
   // per minute) to a per-day file - whatever gets added to
   // sultan_status.json in the future is archived automatically too,
   // instead of a second hand-maintained log schema slowly drifting out of
   // sync with the live panel like bookmap_live_signal.csv's fields did.
   // reuses `dtNow` already computed near the top of this function (GMT-based minute bucket)
   if(dtNow.min != g_dnaVaultLastMin || dtNow.hour != g_dnaVaultLastHour)
   {
      g_dnaVaultLastMin  = dtNow.min;
      g_dnaVaultLastHour = dtNow.hour;
      string dnaFile = StringFormat("dna_vault_%04d-%02d-%02d.jsonl", dtNow.year, dtNow.mon, dtNow.day);
      int dnaHandle = FileOpen(dnaFile, FILE_READ | FILE_WRITE | FILE_TXT | FILE_COMMON | FILE_ANSI | FILE_SHARE_READ);
      if(dnaHandle != INVALID_HANDLE)
      {
         FileSeek(dnaHandle, 0, SEEK_END);
         FileWriteString(dnaHandle, json + "\n");
         FileClose(dnaHandle);
      }
   }
}

//--- v33: VAH/VAL lines - 2 dashed lines (lighter goldenrod than the solid
//--- POC line) bracketing the 70%-of-volume value area, same offset
//--- conversion + WALL_PREFIX cleanup convention as the wall/POC lines.
// v53.14: Dadang - "ini masih terlalu besar dan mepet chart hilangi aja
// kan sudah ada dipanel dan zona sama garis suplay demand itu apa
// bedanya bro" - the roadmap HLINE layer (full-chart-width lines +
// right-edge text, added v53.3 for exactly this "garis dari kiri
// kekanan" ask) turned out to duplicate the zone BOX (already shows the
// same price range as a colored rectangle, with the fuller lot/diuji/
// serap label) and the panel's own condensed S&D section (FOKUS/Posisi/
// Buyer-Seller) closely enough that the extra text - worst on the
// SEMPIT/compression case, two labels sitting <1 USD apart - read as
// clutter rather than a genuinely different signal. Removed entirely
// (DrawRoadmapLine() + UpdateRoadmapLines() and their 6 SDRM_PREFIX
// chart objects) rather than just shrinking the text again - the zone
// box + panel already carry this data, so there is no more real
// "garis suplay demand" surface left to keep clean.

void UpdateValueAreaLines()
{
   string vahName = WALL_PREFIX + "VAH", vahTxt = WALL_PREFIX + "VAH_TXT";
   string valName = WALL_PREFIX + "VAL", valTxt = WALL_PREFIX + "VAL_TXT";
   if(!g_bookmapOnline || g_bookmapVah <= 0 || g_bookmapVal <= 0 || g_bookmapVah <= g_bookmapVal)
   {
      if(ObjectFind(0, vahName) >= 0) ObjectDelete(0, vahName);
      if(ObjectFind(0, vahTxt)  >= 0) ObjectDelete(0, vahTxt);
      if(ObjectFind(0, valName) >= 0) ObjectDelete(0, valName);
      if(ObjectFind(0, valTxt)  >= 0) ObjectDelete(0, valTxt);
      return;
   }
   double offset = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   // v52.37: pinned to the chart's visible right edge now (see
   // ChartRightEdgeTime()) instead of a fixed bar-count lane - marginPx
   // staggers VAH/VAL/POC (20/45/70px) a bit apart so their text doesn't
   // stack directly on top of each other when VAH/VAL sit close to POC.
   DrawValueAreaLine(vahName, vahTxt, g_bookmapVah + offset, "VAH", 45);
   DrawValueAreaLine(valName, valTxt, g_bookmapVal + offset, "VAL", 70);
}

void DrawValueAreaLine(string name, string textName, double mt5Price, string label, int marginPx = 20)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   // v52.38: OBJPROP_STYLE moved out of the creation-only block so a
   // pre-existing object (leftover from an earlier session) gets its style
   // reasserted every redraw instead of keeping whatever it had at original
   // creation - self-heals stale state, same reasoning as color/width/price
   // already being unconditional.
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASHDOT);
   // v52.39 fix - Dadang: still solid after v52.38, even with STYLE_DASHDOT
   // genuinely being reapplied every cycle (confirmed - not the same bug
   // again). Root cause is an MT5 PLATFORM limitation, not a code bug: the
   // terminal only actually RENDERS a line style's dash pattern when
   // OBJPROP_WIDTH == 1 - any width >= 2 displays solid regardless of what
   // OBJPROP_STYLE is set to. v52.36's "tebalkan" (width 1->2) and this
   // request's "tetap putus-putus" directly conflict on the SAME line -
   // MT5 cannot do both at once. Reverted width to 1 to make the dash
   // pattern actually reappear (the thing he asked for twice), color stays
   // the brighter v52.36 shade so it's still visually distinct from POC's
   // gold even at the thinner width.
   ObjectSetInteger(0, name, OBJPROP_COLOR, C'200,165,75');
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT, StringFormat("%s @ %.2f", label, mt5Price));

   // v52.37: pinned to the chart's visible right edge (see
   // ChartRightEdgeTime()) instead of a fixed bar-count lane - Dadang: "beri
   // nama garis vah dan val dan poc nya di ujung kanan yang keren." Bigger
   // font + brighter label color than before (was 11pt dim tan) so it reads
   // as a proper edge label, not a faint afterthought.
   datetime labelTime = ChartRightEdgeTime(marginPx);
   if(ObjectFind(0, textName) < 0)
   {
      ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, mt5Price);
      ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_RIGHT);
   }
   ObjectSetInteger(0, textName, OBJPROP_TIME, labelTime);
   ObjectSetDouble(0, textName, OBJPROP_PRICE, mt5Price);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, C'240,210,140');
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 13);
   ObjectSetString(0, textName, OBJPROP_TEXT, StringFormat("%s ", label));
}

// v52.75 - iceberg reload counter. Same state-machine as the web side's
// _trackIceReload(): a side that goes ABSENT (price<=0 or size<=0) then
// REAPPEARS at the same price is a hidden player reloading the same level
// (more committed than "still sitting there") - count it. A reappearance
// at a genuinely different price is a new iceberg, not a reload - reset.
int IceReloadCount(int sideIdx, double price, double size)
{
   bool active = (price > 0 && size > 0);
   if(!active)
   {
      g_icePresent[sideIdx] = false;
      return g_iceReloadCount[sideIdx];
   }
   if(g_icePresent[sideIdx])
   {
      if(MathAbs(price - g_iceLastPx[sideIdx]) > 0.05)
      {
         g_iceLastPx[sideIdx]      = price;
         g_iceReloadCount[sideIdx] = 0;
      }
   }
   else
   {
      if(g_iceLastPx[sideIdx] > 0 && MathAbs(price - g_iceLastPx[sideIdx]) <= 0.05)
         g_iceReloadCount[sideIdx]++;
      else
         g_iceReloadCount[sideIdx] = 0;
      g_iceLastPx[sideIdx] = price;
      g_icePresent[sideIdx] = true;
   }
   return g_iceReloadCount[sideIdx];
}

//--- v33: Iceberg markers - IcebergEngine flags a price where far more
//--- volume has TRADED than its DISPLAYED resting size would suggest (a
//--- hidden refilling order). Informational only (no entry gating yet) -
//--- drawn in magenta to stay visually distinct from walls (green/red) and
//--- POC/VA (gold).
void UpdateIcebergLines()
{
   // v35: own lanes (52/56 bars), past POC (40) and VAH/VAL (44/48).
   int bidReloads = IceReloadCount(0, g_bookmapBidIcePx, g_bookmapBidIceSz);
   int askReloads = IceReloadCount(1, g_bookmapAskIcePx, g_bookmapAskIceSz);
   DrawIcebergLine("BIDICE", g_bookmapBidIcePx, g_bookmapBidIceSz, g_bookmapBidIceRatio, "BID", 52, bidReloads);
   DrawIcebergLine("ASKICE", g_bookmapAskIcePx, g_bookmapAskIceSz, g_bookmapAskIceRatio, "ASK", 56, askReloads);
}

void DrawIcebergLine(string key, double bookmapPrice, double size, double ratio, string sideLabel, int barsAhead = 8, int reloads = 0)
{
   string name = WALL_PREFIX + key, textName = WALL_PREFIX + key + "_TXT";
   if(!g_bookmapOnline || bookmapPrice <= 0 || size <= 0)
   {
      if(ObjectFind(0, name) >= 0)     ObjectDelete(0, name);
      if(ObjectFind(0, textName) >= 0) ObjectDelete(0, textName);
      return;
   }
   double offset   = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   double mt5Price = bookmapPrice + offset;
   string reloadSuffix = (reloads > 0) ? StringFormat(" reload x%d", reloads) : "";

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, mt5Price);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrMagenta);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetDouble(0, name, OBJPROP_PRICE, mt5Price);
   ObjectSetString(0, name, OBJPROP_TEXT,
      StringFormat("ICEBERG %s @ %.2f - displayed %.0f, ratio %.1fx%s", sideLabel, mt5Price, size, ratio, reloadSuffix));

   datetime labelTime = TimeCurrent() + PeriodSeconds(_Period) * barsAhead;
   if(ObjectFind(0, textName) < 0)
   {
      ObjectCreate(0, textName, OBJ_TEXT, 0, labelTime, mt5Price);
      ObjectSetInteger(0, textName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, textName, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, textName, OBJPROP_ANCHOR, ANCHOR_LEFT);
   }
   ObjectSetInteger(0, textName, OBJPROP_TIME, labelTime);
   ObjectSetDouble(0, textName, OBJPROP_PRICE, mt5Price);
   ObjectSetInteger(0, textName, OBJPROP_COLOR, clrMagenta);
   ObjectSetInteger(0, textName, OBJPROP_FONTSIZE, 12);
   ObjectSetString(0, textName, OBJPROP_TEXT, StringFormat(" ICEBERG %s (%.1fx)%s", sideLabel, ratio, reloadSuffix));
}

//--- M30 momentum candle. Dadang: "M30 harus close di atas high candle
//--- sebelumnya" (BUY) / "close di bawah low candle sebelumnya" (SELL) -
//--- a genuinely STRONG candle (closes past the prior bar's extreme, not
//--- just past its open/midpoint), read directly from raw M30 OHLC (not
//--- the CMP indicator - this is a separate, stricter momentum check on
//--- top of CMP direction). Naturally "waits for the next M30 candle" with
//--- no extra state needed: shift 1/2 always reference the latest CLOSED
//--- bars, so the result only changes when a new M30 bar actually closes.
bool M30MomentumOk(string dir)
{
   if(!InpUseM30Momentum) return true;
   double prevHigh  = iHigh(_Symbol, InpScalpMasterTF, 2);
   double prevLow   = iLow(_Symbol, InpScalpMasterTF, 2);
   double lastClose = iClose(_Symbol, InpScalpMasterTF, 1);
   if(dir == "BUY")  return lastClose > prevHigh;
   if(dir == "SELL") return lastClose < prevLow;
   return false;
}

//--- Exit companion to M30MomentumOk(): Dadang: "ketika tidak close di atas
//--- high untuk buy dan close di bawah low candle sebelumnya, maka kita
//--- akan TP" - if M30 fails its OWN direction's strong-close test AND
//--- closes with a strong candle the OPPOSITE way, that's a decisive
//--- reversal signal - close the position now instead of waiting for the
//--- slower M15-flip cut-loss to eventually catch up.
void CheckM30MomentumExit()
{
   if(!InpUseM30Momentum) return;
   double prevHigh  = iHigh(_Symbol, InpScalpMasterTF, 2);
   double prevLow   = iLow(_Symbol, InpScalpMasterTF, 2);
   double lastClose = iClose(_Symbol, InpScalpMasterTF, 1);
   bool   m30StrongSell = (lastClose < prevLow);
   bool   m30StrongBuy  = (lastClose > prevHigh);
   if(!m30StrongSell && !m30StrongBuy) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      if((isBuy && m30StrongSell) || (!isBuy && m30StrongBuy))
      {
         if(trade.PositionClose(tk))
            Print("M30 MOMENTUM EXIT ticket=", tk);
      }
   }
}

//--- M5-tested-M30 filter. Dadang: "M30 buy, tunggu 1 candle merah di M5,
//--- abis close-nya tunggu CMP buy M5, baru kita buy" - a genuine test
//--- means an actual RED candle right before the bar that confirms BUY,
//--- not just "CMP state was SELL a moment ago". CORRECTED 2026-08-09:
//--- first version checked CMP-state history (g_scalpEntryPrevDir ==
//--- opposite), but that's nearly a TAUTOLOGY - CMP only has 2 live states
//--- (BUY/SELL), so "was opposite before this flip" is true almost every
//--- single time by construction (verified: 0 behavior change in headless
//--- test, v8 and v9 numbers came out byte-identical). Real candle COLOR
//--- is what actually varies - checks bar[2] (the bar right before the
//--- last CLOSED bar[1], which is the one confirming the current CMP dir).
bool M5TestedM30(string dir)
{
   if(!InpUseM5TestM30) return true;
   double o = iOpen(_Symbol, InpScalpEntryTF, 2);
   double c = iClose(_Symbol, InpScalpEntryTF, 2);
   if(dir == "BUY")  return c < o;   // candle right before the confirming bar was red
   if(dir == "SELL") return c > o;   // ... was green
   return false;
}

//--- Big-TF SNR avoidance, refined 2026-08-09 per Dadang's correction: NOT a
//--- blanket block. Being near a big-TF zone is only "bahaya" (dangerous)
//--- while the zone's own rejection-confirmation TF hasn't broken out yet in
//--- our direction - once it has, that's the classic base-drop-base / rally-
//--- base-rally pattern and IS a valid entry. Pairs (Dadang, verbatim +
//--- confirmed): Weekly->H4, Daily->H1. H4's own pair is M30 - but since
//--- dir passed in here is ALWAYS g_scalpMasterDir (M30's own live CMP, see
//--- OnTick()), that confirmation is already guaranteed by construction -
//--- no separate H4 check needed, H4-zone proximity alone never blocks.
bool NearBigSNR(string dir)
{
   if(!InpAvoidBigSNR) return false;
   double px  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double pip = PipSize();
   int bufIdx = (dir == "BUY") ? 6 : 5;   // resistance ahead for BUY, support ahead for SELL

   // Weekly zone -> confirm via H4's own CMP (g_masterDir, already tracked every tick)
   if(g_hWeekly != INVALID_HANDLE)
   {
      double level = ReadLiveLevel(g_hWeekly, bufIdx);
      if(level > 0 && MathAbs(level - px) / pip <= InpBigSNR_ZonePips && g_masterDir != dir)
         return true;   // near Weekly zone, H4 hasn't confirmed rejection yet - dangerous
   }

   // Daily zone -> confirm via H1's own CMP (dedicated handle, H1 not otherwise used)
   if(g_hDaily != INVALID_HANDLE)
   {
      double level = ReadLiveLevel(g_hDaily, bufIdx);
      if(level > 0 && MathAbs(level - px) / pip <= InpBigSNR_ZonePips)
      {
         datetime tH1;
         string h1Dir = (g_hH1 != INVALID_HANDLE) ? ReadCMP(g_hH1, tH1) : "WAIT";
         if(h1Dir != dir) return true;   // near Daily zone, H1 hasn't confirmed rejection yet
      }
   }

   return false;
}

//--- H1-must-confirm-SCALP gate. Dadang 2026-08-09 verbatim: "jangan cari
//--- sell jika H4 BO buy tapi H1 masih posisi BO buy, kita cari sell ketika
//--- H1 sudah CMP sell... selama Master gw tidak berubah dia akan tetap ke
//--- arah itu" - M30 flipping alone isn't enough evidence to fight H4; H1
//--- (one level up from M30, between M30 and H4) must ALSO have flipped
//--- before hunting the counter-trend direction. Only applies when dir
//--- opposes H4 - WITH-H4 trades need no such gate (nothing to fight).
bool H1ConfirmsScalp(string dir)
{
   if(!InpRequireH1ForScalp) return true;
   if(dir == g_masterDir) return true;         // trading WITH H4 - gate not relevant
   if(g_hH1 == INVALID_HANDLE) return true;    // handle unavailable - don't block
   datetime tH1;
   string h1Dir = ReadCMP(g_hH1, tH1);
   return h1Dir == dir;
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

//--- Sums floating P/L across all open positions matching dirFilter ("BUY"
//--- or "SELL"). Used to gate layering: Dadang 2026-08-09 "dilarang entri
//--- ketika masih minus, kita tambah entri hanya pas plus" - don't ADD a new
//--- layer on top of an already-open position in the same direction while
//--- that direction is still floating negative (anti-averaging-down safety
//--- rule, on top of the wider SL from the MAE-recovery analysis). The very
//--- FIRST entry in a direction is never blocked by this - only additional
//--- layers on top of an existing floating-loss position are.
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

//--- Resets the FIRE/STOP/RESUME cascade state - called whenever H4 (top
//--- regime) flips, so a stale firing-enabled flag from the previous H4
//--- regime can never carry over. M30/M5 direction tracking picks back up
//--- fresh from WAIT on the next tick's ReadCMP() calls.
void ResetCascadeState()
{
   g_m5FiringEnabled = false;
   g_lastM30BarTime  = 0;
   g_lastM5EventTime = 0;
   g_scalpMasterDir  = "WAIT";
   g_scalpEntryDir   = "WAIT";
}

//--- Entry TF flipping AGAINST Master = cut loss immediately, don't wait
//--- for SL/trailing. Re-entry happens naturally once Entry TF realigns
//--- with Master (handled by the normal TryOpen() call in OnTick()).
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

bool TryOpen(string dir, string tag, bool isScalp, datetime parentFlipTime = 0, datetime childFlipTime = 0, double slOverride = 0.0, double tpOverride = 0.0)
{
   if(InpTradeDir == DIR_BUY_ONLY  && dir == "SELL") return false;
   if(InpTradeDir == DIR_SELL_ONLY && dir == "BUY")  return false;

   // v52.47 BARRIER VETO - universal, checked before ANY signal-specific
   // logic below, applies to every entry regardless of which trigger (tag)
   // called TryOpen(). Real block (not a lot-size warning) - Dadang: "jangan
   // maksa SELL yang cuma bolak-balik sebelum valid CMP SELL baru hasil
   // jebol barrier."
   string barrierReason = "";
   if(BarrierVetoes(dir == "BUY", barrierReason))
   {
      Print("ENTRY VETOED (", tag, ") ", dir, ": ", barrierReason);
      return false;
   }

   // v52.72 SWEEP REVERSAL VETO - same universal placement as Barrier Veto
   // above, applies to every entry regardless of which trigger (tag) called
   // TryOpen(). See SweepReversalVeto() for rationale.
   string sweepVetoReason = "";
   if(SweepReversalVeto(dir == "BUY", sweepVetoReason))
   {
      Print("ENTRY VETOED (", tag, ") ", dir, ": ", sweepVetoReason);
      return false;
   }

   if(!SpreadOk()) return false;
   if(InpMaxOpenPos > 0 && CountOpenPositions() >= InpMaxOpenPos) return false;
   if(!InpAllowMultiple && CountOpenPositions(dir) > 0) return false;

   // Anti-averaging-down: don't ADD a layer on top of an already-open
   // position in this direction while it's still floating negative. The
   // first entry (no existing position yet) is never blocked here.
   if(CountOpenPositions(dir) > 0 && FloatingPLForDirection(dir) < 0.0) return false;

   bool   buy    = (dir == "BUY");
   double pip    = PipSize();
   double px     = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // SL: SCALP tier ALWAYS uses a fixed, tight SL (InpScalpSL_Pips) - NEVER
   // structural M30. Root cause found 2026-08-09: a SCALP position trades
   // OPPOSITE of the direction M30 just moved in (that's the cascade
   // condition), so M30's own res/sup on that opposite side is often stale/
   // far behind (M30 was busy making the move that triggered the cascade,
   // not forming a nearby reversal pattern) - this let SCALP losses run up
   // to -578 pips before the M15-flip cut-loss ever caught up. NORMAL tier
   // trades WITH Master's direction, where M30 agreeing gives a genuinely
   // nearby, relevant structural level - keeps its structural SL (payoff
   // 1.72, proven healthy, untouched by this fix).
   // DADANG'S LAW: SL MUST BE STRICTLY AT THE M30 SWING HIGH / SWING LOW WICK!
   // v52.42: slOverride (VA-retest trigger) bypasses the M30-swing computation
   // entirely - the SAFETY MARGIN fallback still applies either way, so a
   // stale/wrong override can never place SL on the wrong side of price.
   double sl = 0.0;
   if(slOverride > 0.0)
   {
      sl = slOverride;
      if(buy  && sl >= px) sl = px - 50.0 * pip;
      if(!buy && sl <= px) sl = px + 50.0 * pip;
   }
   else if(buy)
   {
      // M30 Swing Low: lowest low of recent M30 bars (10 bars)
      int swingLowBar = iLowest(_Symbol, InpScalpMasterTF, MODE_LOW, 10, 1);
      if(swingLowBar >= 0) sl = iLow(_Symbol, InpScalpMasterTF, swingLowBar);

      double liveSup = ReadLiveLevel(g_hScalpMaster, 5); // Buffer 5: Live Support
      if(liveSup > 0 && liveSup < sl) sl = liveSup;

      if(sl >= px || sl == 0.0) sl = px - 50.0 * pip; // Safety margin
   }
   else
   {
      // M30 Swing High: highest high of recent M30 bars (10 bars)
      int swingHighBar = iHighest(_Symbol, InpScalpMasterTF, MODE_HIGH, 10, 1);
      if(swingHighBar >= 0) sl = iHigh(_Symbol, InpScalpMasterTF, swingHighBar);

      double liveRes = ReadLiveLevel(g_hScalpMaster, 6); // Buffer 6: Live Resistance
      if(liveRes > 0 && liveRes > sl) sl = liveRes;

      if(sl <= px || sl == 0.0) sl = px + 50.0 * pip; // Safety margin
   }

   // v53: Dadang - "kita bisa entri sell sampai demand terdekat" - a real
   // SND zone on the opposite side is a genuine target (order flow-backed),
   // strictly better than a fixed pip distance. Same optional-override
   // pattern as slOverride above - default 0.0 means every existing caller
   // keeps its exact prior behavior; only takes effect when the override is
   // actually on the correct side of price (a stale/wrong-side value can
   // never flip a position's TP to the wrong direction).
   double tpPips = isScalp ? InpScalpTP_Pips : InpTP_Pips;   // SCALP gets its own short TP (see input group above)
   double tp;
   if(tpOverride > 0.0 && ((buy && tpOverride > px) || (!buy && tpOverride < px)))
      tp = tpOverride;
   else
      tp = (tpPips > 0) ? (buy ? px + tpPips*pip : px - tpPips*pip) : 0.0;
   double fallbackPips = isScalp ? InpScalpSL_Pips : InpSL_Pips;
   double slPipsActual = (sl > 0) ? MathAbs(px - sl) / pip : fallbackPips;
   double lot    = CalcLot(slPipsActual);

   // v23 Bookmap Absorption warning (live only - g_bookmapOnline is always
   // false during backtests, so this never changes backtest behavior).
   // "BUYER_ABSORBED" = buyers getting soaked up, bearish warning for a BUY.
   // "SELLER_ABSORBED" = sellers getting soaked up, bearish... i.e. bullish
   // warning against a SELL. Reduce lot, don't block - matches the exact
   // pattern already established in bookmap-bridge's own AbsorptionEngine.
   string absorbNote = "";
   if(InpUseBookmapAbsorptionWarning && g_bookmapOnline)
   {
      bool opposesEntry = (buy && g_bookmapAbsorption == "BUYER_ABSORBED") ||
                          (!buy && g_bookmapAbsorption == "SELLER_ABSORBED");
      if(opposesEntry)
      {
         double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         double reduced = lot * InpBookmapAbsorptionLotFactor;
         if(step > 0) reduced = MathFloor(reduced / step) * step;
         lot = MathMax(minLot, reduced);
         absorbNote = StringFormat(" | BOOKMAP WARNING: %s lawan arah, lot dikecilin ke %.2f", g_bookmapAbsorption, lot);
      }
   }

   // v30 POC overextension warning (live only) - Dadang: "garis poc" + wire
   // it into entry sizing. POC = harga dengan volume trade terbanyak sesi
   // ini (value area magnet) - kalau harga udah lari jauh dari POC SEARAH
   // entry yang mau dibuka, itu tanda entry telat/overextended (risiko balik
   // ke value area lebih besar). Warning + kecilin lot, BUKAN block - sama
   // pola persis kayak Absorption di atas, stackable (bisa kena dua-duanya).
   string pocNote = "";
   if(InpUsePocOverextendWarning && g_bookmapOnline && g_bookmapPocPrice > 0 && g_bookmapPrice > 0)
   {
      double pocMt5Price = g_bookmapPocPrice + (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice);
      double distFromPoc = buy ? (px - pocMt5Price) : (pocMt5Price - px);
      if(distFromPoc >= InpPocOverextendUsd)
      {
         double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         double reduced = lot * InpPocOverextendLotFactor;
         if(step > 0) reduced = MathFloor(reduced / step) * step;
         lot = MathMax(minLot, reduced);
         pocNote = StringFormat(" | POC WARNING: harga %.1f USD dari POC %.2f (overextended), lot dikecilin ke %.2f",
                                 distFromPoc, pocMt5Price, lot);
      }

      // v32 POC alignment warning - Dadang: "kalo harga di atas POC kita
      // gimana, kalo di bawah gimana" -> di atas POC = POC jadi support,
      // bias BUY; di bawah POC = POC jadi resistance, bias SELL. Kalau BUY
      // dibuka SEBELUM harga reclaim POC (masih di bawah) atau SELL dibuka
      // sebelum harga lepas POC (masih di atas), value area belum dukung -
      // "belum solid". Beda dari overextend (soal JARAK) - ini soal SISI,
      // berapapun jauhnya. Stackable sama 2 warning di atas.
      if(InpUsePocAlignWarning)
      {
         bool wrongSide = buy ? (px < pocMt5Price) : (px > pocMt5Price);
         if(wrongSide)
         {
            double minLot2 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
            double step2   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
            double reduced2 = lot * InpPocAlignLotFactor;
            if(step2 > 0) reduced2 = MathFloor(reduced2 / step2) * step2;
            lot = MathMax(minLot2, reduced2);
            pocNote += StringFormat(" | POC ALIGN WARNING: %s tapi harga masih %s POC %.2f (belum reclaim), lot dikecilin ke %.2f",
                                     dir, buy ? "DI BAWAH" : "DI ATAS", pocMt5Price, lot);
         }
      }
   }

   // v52.1 Liquidity Support warning (live only) - Dadang 2026-08-17: "lo ada
   // ide buat nambah akurasi dengan data bookmap" -> "ngegate entri gak apa2
   // bro karena masih demo karena gw butuh data" -> confirmed via
   // clarification: WARNING (kecilin lot), bukan block - entry & cut-loss
   // tetap selalu jalan sesuai data yang ada, sama pola persis kayak
   // Absorption/POC di atas. Gak ada wall ATAU iceberg di sisi ENTRY deket
   // harga -> lebih rawan false breakout, kurangi lot (stackable sama 3
   // warning lain). Shared check dengan ComputeConviction() factor #4 lewat
   // HasLiquiditySupport().
   string liqNote = "";
   if(InpUseLiquiditySupportWarning && g_bookmapOnline && !HasLiquiditySupport(buy, px))
   {
      double minLot3 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double step3   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double reduced3 = lot * InpLiquiditySupportLotFactor;
      if(step3 > 0) reduced3 = MathFloor(reduced3 / step3) * step3;
      lot = MathMax(minLot3, reduced3);
      liqNote = StringFormat(" | LIQUIDITY WARNING: gak ada %s wall/iceberg deket harga, lot dikecilin ke %.2f",
                              buy ? "bid" : "ask", lot);
   }

   // v52.2 Bookmap Strong Confirm BOOST (live only) - applied AFTER all 4
   // warnings above, so a trade genuinely well-confirmed by live order flow
   // gets its size restored/boosted even if one unrelated warning nudged it
   // down first - real multi-factor confirmation should win over an
   // isolated caution, not the other way around.
   string boostNote = "";
   if(InpUseLiquidityBoost && g_bookmapOnline && BookmapStrongConfirm(buy, px))
   {
      double minLot4 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      double maxLot4 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
      double step4   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
      double boosted = lot * InpLiquidityBoostLotFactor;
      if(step4 > 0) boosted = MathFloor(boosted / step4) * step4;
      lot = MathMin(maxLot4, MathMax(minLot4, boosted));
      boostNote = StringFormat(" | BOOKMAP CONFIRM: order flow mendukung kuat, lot dinaikin ke %.2f", lot);
   }

   // v52.46 Wall Sweep warning/boost (live only) - see input group comment
   // for full reasoning. BID-side sweep is relevant to a SELL entry (that's
   // the wall a falling price interacts with); ASK-side sweep is relevant
   // to a BUY entry. Stackable with the 4 warnings/boost above.
   string sweepNote = "";
   if(InpUseWallSweepSignal && g_bookmapOnline && g_bmSweepStatus != "NONE" && g_bmSweepSinceSec <= InpWallSweepMaxAgeSec)
   {
      bool sweepRelevant = (g_bmSweepSide == "BID" && !buy) || (g_bmSweepSide == "ASK" && buy);
      if(sweepRelevant && g_bmSweepStatus == "REVERSAL_CONFIRMED")
      {
         double minLot5 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double step5   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         double reduced5 = lot * InpWallSweepWarnLotFactor;
         if(step5 > 0) reduced5 = MathFloor(reduced5 / step5) * step5;
         lot = MathMax(minLot5, reduced5);
         sweepNote = StringFormat(" | WALL SWEEP WARNING: %s %.0f lot REVERSAL_CONFIRMED - wall barusan kebukti kuat, lot dikecilin ke %.2f",
                                   g_bmSweepSide, g_bmSweepSize, lot);
      }
      else if(sweepRelevant && g_bmSweepStatus == "CONTINUATION")
      {
         double minLot5 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double maxLot5 = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
         double step5   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         double boosted5 = lot * InpWallSweepBoostLotFactor;
         if(step5 > 0) boosted5 = MathFloor(boosted5 / step5) * step5;
         lot = MathMin(maxLot5, MathMax(minLot5, boosted5));
         sweepNote = StringFormat(" | WALL SWEEP CONFIRM: %s %.0f lot CONTINUATION - wall barusan kebukti jebol, lot dinaikin ke %.2f",
                                   g_bmSweepSide, g_bmSweepSize, lot);
      }
   }

   string comment = "DD-CR " + tag;
   // Time Law audit trail - Dadang: "lihat TV gw, CMP Master BO buy jam
   // 10:00, kita entri kalau M5 CMP buy terjadi di ATAS jam 10:00" - print
   // both timestamps side by side on every real entry so this can be
   // eyeballed directly against the TradingView reference chart.
   string timeLawNote = (parentFlipTime > 0 && childFlipTime > 0)
      ? StringFormat(" | Parent BO=%s Child BO=%s (child %s parent)",
                      TimeToString(parentFlipTime, TIME_DATE|TIME_MINUTES),
                      TimeToString(childFlipTime, TIME_DATE|TIME_MINUTES),
                      (childFlipTime > parentFlipTime) ? "AFTER" : "!! NOT AFTER !!")
      : "";
   if(trade.PositionOpen(_Symbol, buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, lot, px, sl, tp, comment))
   {
      Print("ENTRY (", tag, ") ", dir, " lot=", lot, " @ ", px, " SL=", sl, " TP=", tp, timeLawNote, absorbNote, pocNote, liqNote, boostNote, sweepNote);
      return true;
   }
   Print("ENTRY FAILED (", tag, ") ", dir, ": ", trade.ResultRetcodeDescription());
   return false;
}

// v52.3: Dadang 2026-08-17 - "kita ngikutin bookmap aja karena tehnikal gw
// kan hanya baca candle" -> confirmed explicitly: Bookmap boleh jadi PEMICU
// entry sendiri, TIDAK wajib nunggu H4/M30/M5 align dulu (beda dari
// BookmapStrongConfirm() di atas, yang cuma nge-boost lot entry yang CMP
// UDAH putusin). Bar-nya sengaja lebih TINGGI dari boost (2/3) karena ini
// jalan TANPA backup CMP sama sekali: butuh iceberg SENDIRIAN (bukti order
// flow paling kuat), ATAU seluruh 3/3 faktor (CVD + Absorption FAVOR +
// Liquidity Support) sekaligus. v52.6: location (step 5) sekarang WAJIB di
// kedua jalur - iceberg kuat pun gak boleh chase harga yang udah extended
// jauh dari POC. Return "" kalau kedua arah gak qualify atau keduanya
// qualify bareng (ambigu, gak ada konsensus arah - skip).
string BookmapTriggerDirection()
{
   if(!g_bookmapOnline) return "";
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // v52.13: EMA-smoothed CVD (InpBookmapCvdSmoothMin), not raw per-tick -
   // "siapa yang dominan" over the last few minutes, not this instant.
   bool buyAllFactors  = (g_bmCvdEma > 0) && (g_bookmapAbsorption == "SELLER_ABSORBED") && HasLiquiditySupport(true, ask);
   bool buyQualifies    = (HasIcebergSupport(true, ask) || buyAllFactors) && BookmapLocationOk(true);

   bool sellAllFactors = (g_bmCvdEma < 0) && (g_bookmapAbsorption == "BUYER_ABSORBED") && HasLiquiditySupport(false, bid);
   bool sellQualifies   = (HasIcebergSupport(false, bid) || sellAllFactors) && BookmapLocationOk(false);

   if(buyQualifies && !sellQualifies) return "BUY";
   if(sellQualifies && !buyQualifies) return "SELL";
   return "";   // neither, or both at once (ambiguous) - no trigger
}

// v52.10: Dadang - "ini sering banget berubah buy n sell n wait gimana mau
// entri nya" - BookmapTriggerDirection() re-evaluates from scratch every
// single tick with zero memory, so a one-tick CVD sign flip or a wall
// blinking in/out of the nearest slot was enough to flip the verdict (and,
// worse, could ALSO flip a real Bookmap-triggered entry - not just the
// display). Fix: require the SAME raw direction to hold continuously for
// InpBookmapConfirmSec before it counts as real - any change (including
// dropping to "") restarts the clock. This is now what BOTH the narrated
// verdict AND CheckBookmapTrigger() actually use - raw BookmapTriggerDirection()
// itself is unchanged/still available, this only adds a persistence gate
// on top of it.
string   g_bmRawDir   = "";
datetime g_bmRawSince = 0;
string BookmapTriggerDirectionStable()
{
   string raw = BookmapTriggerDirection();
   if(raw != g_bmRawDir)
   {
      g_bmRawDir   = raw;
      g_bmRawSince = TimeCurrent();
   }
   if(g_bmRawDir == "") return "";
   if(TimeCurrent() - g_bmRawSince < InpBookmapConfirmSec) return "";   // still building up - not stable yet
   return g_bmRawDir;
}

// v52.6: narrates the SAME 5-step read explained to Dadang (wall -> CVD ->
// absorption -> iceberg -> location), populating g_bmNarr* for the panel
// (UpdatePanel()) and the web dashboard (WriteSultanStatus()). The verdict
// line calls BookmapTriggerDirection() directly - not a re-derived summary -
// so the narrative can never say "BUY SETUP" on a tick where the real
// trigger wouldn't actually fire, or vice versa.
void ComputeBookmapNarrative()
{
   g_bmNarrWall = "-"; g_bmNarrCvd = "-"; g_bmNarrAbsorb = "-";
   g_bmNarrIceberg = "-"; g_bmNarrLocation = "-";
   if(!g_bookmapOnline) { g_bmNarrVerdict = "OFFLINE"; return; }

   double bmOffset = (g_bookmapPrice > 0) ? (SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice) : 0.0;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   //--- 1. Wall - nearest bid/ask (slot 0 = closest to price). Terse on
   //--- purpose (v52.7, see below) - price is already visible elsewhere on
   //--- both panel and web, repeating it here just ate space.
   double bidWallPx = (g_bookmapBidPx[0] > 0) ? g_bookmapBidPx[0] + bmOffset : 0.0;
   double askWallPx = (g_bookmapAskPx[0] > 0) ? g_bookmapAskPx[0] + bmOffset : 0.0;
   if(bidWallPx > 0 && askWallPx > 0)
      g_bmNarrWall = StringFormat("B%.0f/A%.0f", g_bookmapBidSz[0], g_bookmapAskSz[0]);
   else if(bidWallPx > 0)
      g_bmNarrWall = StringFormat("BID %.0fL", g_bookmapBidSz[0]);
   else if(askWallPx > 0)
      g_bmNarrWall = StringFormat("ASK %.0fL", g_bookmapAskSz[0]);

   //--- 2. CVD - who's DOMINANT over the last InpBookmapCvdSmoothMin minutes
   //--- (EMA, v52.13), not the instantaneous tick - this is literally the
   //--- value the verdict decides from, so what's shown = what decides.
   g_bmNarrCvd = StringFormat("%+.0f", g_bmCvdEma);

   //--- 3. Absorption - the test moment (v52.8: tile-sized, was "BUYER ABS")
   if(g_bookmapAbsorption == "" || g_bookmapAbsorption == "NONE") g_bmNarrAbsorb = "-";
   else if(g_bookmapAbsorption == "BUYER_ABSORBED")                g_bmNarrAbsorb = "B-ABS";
   else if(g_bookmapAbsorption == "SELLER_ABSORBED")               g_bmNarrAbsorb = "S-ABS";
   else                                                             g_bmNarrAbsorb = g_bookmapAbsorption;

   //--- 4. Iceberg - strongest single signal, if present
   if(HasIcebergSupport(true, bid))       g_bmNarrIceberg = StringFormat("B%.1fx", g_bookmapBidIceRatio);
   else if(HasIcebergSupport(false, ask)) g_bmNarrIceberg = StringFormat("A%.1fx", g_bookmapAskIceRatio);

   //--- 5. Location vs POC/Value Area (v52.8: tile-sized, was "ABOVE VAH")
   if(g_bookmapPocPrice > 0)
   {
      double px = (bid + ask) / 2.0;
      if(g_bookmapVah > g_bookmapVal && g_bookmapVal > 0)
      {
         double vah = g_bookmapVah + bmOffset, val = g_bookmapVal + bmOffset;
         if(px > vah)      g_bmNarrLocation = "ATAS";
         else if(px < val) g_bmNarrLocation = "BWH";
         else               g_bmNarrLocation = "IN";
      }
      else
         g_bmNarrLocation = "POC";
   }

   //--- Verdict - literally the real (persistence-gated) trigger function,
   //--- not a lookalike copy. v52.10: uses the Stable wrapper now, not the
   //--- raw per-tick check, so this stops flapping BUY/SELL/WAIT on noise.
   // v52.11: while a raw direction is building toward InpBookmapConfirmSec
   // but hasn't crossed it yet, show that instead of a flat "WAIT" - Dadang
   // asked for maximal use of this data, and watching conviction accumulate
   // in real time (instead of it snapping from nothing straight to "SETUP")
   // is a genuinely useful read, not just cosmetic - a "BUY (2s)" that keeps
   // resetting back to 0 tells its own story about how noisy the tape is
   // right now, same as a steadily climbing one tells you a real move is
   // forming. Calls BookmapTriggerDirectionStable() first (which is what
   // updates g_bmRawDir/g_bmRawSince as a side effect) so the two can never
   // disagree about the raw state.
   string trig = BookmapTriggerDirectionStable();
   if(trig != "")
      g_bmNarrVerdict = trig + " SETUP";
   else if(g_bmRawDir != "")
      g_bmNarrVerdict = StringFormat("%s (%ds)", g_bmRawDir, (int)(TimeCurrent() - g_bmRawSince));
   else
      g_bmNarrVerdict = "WAIT";
}

// Called once per tick from OnTick(), independent of the CMP FIRE/STOP/
// RESUME cascade in UpdateStateAndExecute(). Cooldown exists because a
// strong Bookmap condition can stay true for many ticks in a row (unlike a
// CMP fresh-breakout event, which is naturally a one-shot per occurrence) -
// without it this would layer entries every tick while the condition holds.
void CheckBookmapTrigger()
{
   if(!InpUseBookmapTrigger) return;
   if(g_lastBookmapTriggerTime > 0 &&
      (TimeCurrent() - g_lastBookmapTriggerTime) < InpBookmapTriggerCooldownMin * 60) return;

   string dir = BookmapTriggerDirectionStable();   // v52.10: persistence-gated, not raw per-tick
   if(dir == "") return;
   // TradeDir filter / spread / max-positions / anti-averaging-down are all
   // already re-checked inside TryOpen() itself - not duplicated here. Only
   // start the cooldown on a CONFIRMED open, so a rare internal block (wide
   // spread, max positions) doesn't burn the window with no trade to show.
   if(TryOpen(dir, "BOOKMAP-TRIG", false))
   {
      g_lastBookmapTriggerTime = TimeCurrent();
      GlobalVariableSet(GV_BOOKMAP_TRIGGER_TIME, (double)g_lastBookmapTriggerTime);   // v52.11: survive reload
   }
}

//--- v52.42: VA RETEST trigger - Dadang: "kita hanya entri ketika BREAK VAL
//--- ATAU VAH DAN pullback ke area val atau hal atau poc" + "sl kita nanti
//--- di bawah vah atau val dan kalo mereka geser sl kita juga ikut geser" +
//--- "ea harus entri sesuai yang kita diskusikan toh kita pakai demo di mt5
//--- kita bro buat uji". Classic breakout-then-retest: ARM once
//--- ComputeVaLocation() confirms a fresh candle-close breakout (candle
//--- CLOSE, not wick - same doctrine as CMP everywhere else; v52.48: that
//--- close is M30's own, not M5's - see ComputeVaLocation() comment); while armed, watch
//--- LIVE price (a retest entry doesn't need close-confirmation the way a
//--- breakout does - it's entering AT a defensible level with its own
//--- invalidation SL right there, not claiming a new breakout happened) for
//--- a return to within InpVaRetestToleranceUsd of the broken VAH/VAL. Fires
//--- there, SL beyond that level. DISARMS (skips the trade) if VA Bias falls
//--- back out of breakout status before any retest happens - the breakout
//--- already failed, chasing a retest of a dead thesis is worse than no
//--- trade. Called once per tick from OnTick(), independent of the CMP
//--- cascade and CheckBookmapTrigger() - same "own pathway, same TryOpen()
//--- safety rails" pattern as that function.
//---
//--- v52.42: NOT backtested first - Dadang's explicit, informed choice ("kita
//--- pakai demo di mt5 kita bro buat uji"), tested live on the DEMO account
//--- instead. Default OFF (InpUseVaRetestTrigger) - explicit opt-in required.
void CheckVaRetestTrigger()
{
   if(!InpUseVaRetestTrigger) return;
   if(!g_bookmapOnline || g_bookmapVah <= 0 || g_bookmapVal <= 0 || g_bookmapVah <= g_bookmapVal) return;

   double offset  = SymbolInfoDouble(_Symbol, SYMBOL_BID) - g_bookmapPrice;
   double vahMt5  = g_bookmapVah + offset;
   double valMt5  = g_bookmapVal + offset;
   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   string vaLoc   = ComputeVaLocation();

   // --- ARM / DISARM (only while no position from this trigger is open) ---
   // v52.44 bugfix - Dadang: "cek lagi apa sudah akurat, jangan sampai
   // repaint atau tidak akurat." Found: the old FIRE condition ("curPrice
   // within tolerance of VAH/VAL") could be trivially TRUE the instant
   // arming happens, if the breakout candle only closed narrowly beyond
   // VAH/VAL (within the tolerance band itself) - firing immediately with
   // NO real pullback ever having happened. Fixed by tracking
   // g_vaRetestExtreme (highest price since arming for BUY, lowest for
   // SELL) and requiring it to have traveled at least InpVaRetestToleranceUsd
   // beyond the level BEFORE a retest can count - proves price genuinely
   // broke away first, not just "happened to close close enough".
   if(g_vaRetestTicket == 0)
   {
      if(vaLoc == "BUY (breakout)")
      {
         if(g_vaRetestArmedDir != "BUY") g_vaRetestExtreme = curPrice;   // freshly armed - seed the extreme tracker
         g_vaRetestArmedDir = "BUY";
         g_vaRetestExtreme  = MathMax(g_vaRetestExtreme, curPrice);
      }
      else if(vaLoc == "SELL (breakout)")
      {
         if(g_vaRetestArmedDir != "SELL") g_vaRetestExtreme = curPrice;
         g_vaRetestArmedDir = "SELL";
         g_vaRetestExtreme  = MathMin(g_vaRetestExtreme, curPrice);
      }
      else if(g_vaRetestArmedDir != "")
      {
         g_vaRetestArmedDir = "";   // breakout invalidated before retest - disarm
         g_vaRetestExtreme  = 0.0;
      }
   }

   // --- FIRE on retest ---
   if(g_vaRetestArmedDir != "" && g_vaRetestTicket == 0)
   {
      if(g_lastVaRetestTime > 0 && (TimeCurrent() - g_lastVaRetestTime) < InpVaRetestCooldownMin * 60) return;

      if(g_vaRetestArmedDir == "BUY" &&
         g_vaRetestExtreme >= vahMt5 + InpVaRetestToleranceUsd &&   // genuinely broke away first
         curPrice <= vahMt5 + InpVaRetestToleranceUsd)              // and has now pulled back
      {
         // v52.54 fix - Dadang: "sl buy ada di bawah val sl sell ada di atas
         // vah jangan salah". SL anchors to the FAR side of the value area
         // (VAL for BUY, VAH for SELL), not the near/breakout side - gives
         // the trade room through the whole VA, only invalidates on a full
         // reclaim through to the opposite boundary.
         double slLevel = valMt5 - InpVaRetestSlBufferUsd;
         if(TryOpen("BUY", "VARETEST", false, 0, 0, slLevel))
         {
            g_vaRetestTicket   = trade.ResultOrder();   // netting/hedging: position ticket == opening order ticket
            g_lastVaRetestTime = TimeCurrent();
            GlobalVariableSet(GV_VARETEST_TRIGGER_TIME, (double)g_lastVaRetestTime);
            GlobalVariableSet(GV_VARETEST_TICKET, (double)g_vaRetestTicket);   // v52.44: survive reload
            g_vaRetestArmedDir = "";
            g_vaRetestExtreme  = 0.0;
         }
      }
      else if(g_vaRetestArmedDir == "SELL" &&
              g_vaRetestExtreme <= valMt5 - InpVaRetestToleranceUsd &&
              curPrice >= valMt5 - InpVaRetestToleranceUsd)
      {
         double slLevel = vahMt5 + InpVaRetestSlBufferUsd;   // v52.54: far side (VAH), see BUY comment above
         if(TryOpen("SELL", "VARETEST", false, 0, 0, slLevel))
         {
            g_vaRetestTicket   = trade.ResultOrder();
            g_lastVaRetestTime = TimeCurrent();
            GlobalVariableSet(GV_VARETEST_TRIGGER_TIME, (double)g_lastVaRetestTime);
            GlobalVariableSet(GV_VARETEST_TICKET, (double)g_vaRetestTicket);   // v52.44: survive reload
            g_vaRetestArmedDir = "";
            g_vaRetestExtreme  = 0.0;
         }
      }
   }

   // --- Dynamic SL trailing on the open position - Dadang: "kalo mereka
   // geser sl kita juga ikut geser" - tracks VAH (BUY) / VAL (SELL) as they
   // move, ONLY ever tightens (never loosens) the SL, standard trailing
   // convention. InpVaRetestSlTrailStepUsd avoids spamming PositionModify()
   // for sub-tick-sized VAH/VAL wiggle.
   if(g_vaRetestTicket != 0)
   {
      if(!PositionSelectByTicket(g_vaRetestTicket))
      {
         g_vaRetestTicket = 0;   // closed elsewhere (SL/TP hit, manual close, M30-flip cut, etc.)
         GlobalVariableDel(GV_VARETEST_TICKET);   // v52.44: stop tracking a ticket that's no longer open
      }
      else
      {
         bool   isBuyPos = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
         double curSl    = PositionGetDouble(POSITION_SL);
         double curTp    = PositionGetDouble(POSITION_TP);
         double newSl    = isBuyPos ? (valMt5 - InpVaRetestSlBufferUsd) : (vahMt5 + InpVaRetestSlBufferUsd);   // v52.54: far side
         bool   improved = isBuyPos ? (newSl > curSl + InpVaRetestSlTrailStepUsd)
                                     : (newSl < curSl - InpVaRetestSlTrailStepUsd);
         if(improved && trade.PositionModify(g_vaRetestTicket, newSl, curTp))
            Print("VA-RETEST SL trail: ticket=", g_vaRetestTicket, " SL ", curSl, " -> ", newSl);
      }
   }
}

// v52.45: FUSION H1/H4 signal - see input group comment for the full
// mechanism + research citation. Entry TF = H1, Master = H4, confirmation
// TF = M5 (dedicated handle, decoupled from InpScalpEntryTF).
void CheckFusionH1H4Trigger()
{
   if(!InpUseFusionH1H4) return;
   if(g_hH1 == INVALID_HANDLE || g_hFusionM5 == INVALID_HANDLE || g_hMaster == INVALID_HANDLE) return;

   datetime h4ChangeTime, h1ChangeTime, m5ChangeTime;
   string h4Dir = ReadCMP(g_hMaster, h4ChangeTime);
   string h1Dir = ReadCMP(g_hH1, h1ChangeTime);
   string m5Dir = ReadCMP(g_hFusionM5, m5ChangeTime);
   datetime m5EventTime = ReadBreakoutEventTime(g_hFusionM5);
   double curPrice = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // --- Reset the VR cycle whenever H4 itself changes (flip or fresh WAIT->direction) ---
   if(h4Dir == "WAIT")
   {
      if(g_fusionDir != "WAIT") { g_fusionDir = "WAIT"; g_fusionVrSet = false; }
   }
   else if(h4Dir != g_fusionDir || h4ChangeTime != g_fusionMct)
   {
      g_fusionDir = h4Dir; g_fusionMct = h4ChangeTime;
      g_fusionVrSet = false; g_fusionVrTime = 0; g_fusionVrLevel = 0.0;
      g_fusionLastCf = 0; g_fusionVrExtreme = 0.0;
   }

   // --- ARM / FIRE (only while no position from this trigger is open) ---
   if(g_fusionTicket == 0 && g_fusionDir != "WAIT")
   {
      string opp = (g_fusionDir == "BUY") ? "SELL" : "BUY";

      if(!g_fusionVrSet)
      {
         // VR: H1 breakout opposite H4, fresh since H4 set this direction (and since the last CF used up a prior VR cycle)
         if(h1Dir == opp && h1ChangeTime > MathMax(g_fusionMct, g_fusionLastCf))
         {
            g_fusionVrSet     = true;
            g_fusionVrTime    = h1ChangeTime;
            g_fusionVrLevel   = ReadLiveLevel(g_hH1, 4);   // H1's frozen flip-level (buffer 4) - the level CF must cross back through
            g_fusionVrExtreme = curPrice;                  // seed the pullback-extreme tracker
         }
      }
      else
      {
         // Track the pullback extreme since VR armed - proves it genuinely reached H4's zone before CF fires
         g_fusionVrExtreme = (g_fusionDir == "SELL") ? MathMax(g_fusionVrExtreme, curPrice)
                                                      : MathMin(g_fusionVrExtreme, curPrice);

         // CF trigger: INTRABAR - live price crosses back through vr_level, PLUS M5 itself shows
         // a fresh breakout searah (buffer 7 event time moved on) - "pembentukan candle" confirmation.
         bool crossed = (g_fusionDir == "BUY") ? (curPrice >= g_fusionVrLevel) : (curPrice <= g_fusionVrLevel);
         bool m5Ok     = (m5Dir == g_fusionDir) && (m5EventTime > g_fusionLastM5Event);

         if(g_fusionVrLevel > 0.0 && crossed && m5Ok)
         {
            double h4Level = ReadLiveLevel(g_hMaster, 4);   // H4's frozen flip-level - the ZONE CF must have retested

            // v53: real SND zone (from Bookmap, scored, lifecycle-tracked) replaces
            // the flat USD-tolerance band when available - SELL checks a SUPPLY
            // zone (sell into resistance), BUY checks a DEMAND zone (buy into
            // support), matching plain supply/demand theory. Falls back to the
            // old h4Level+/-tolerance check if the zone bridge isn't running.
            double zoneLo = 0.0, zoneHi = 0.0, zoneScore = 0.0;
            bool usedZone = InpUseZoneCFEntry &&
                            ZoneCheck(g_fusionDir == "SELL", g_fusionVrExtreme, zoneLo, zoneHi, zoneScore);
            bool inZone = usedZone ? true :
                          (h4Level > 0.0) &&
                          ((g_fusionDir == "SELL") ? (g_fusionVrExtreme >= h4Level - InpFusionZoneTolUsd)
                                                    : (g_fusionVrExtreme <= h4Level + InpFusionZoneTolUsd));
            bool cooldownOk = (g_fusionLastFireTime == 0) ||
                              ((TimeCurrent() - g_fusionLastFireTime) >= InpFusionCooldownMin * 60);

            if(inZone && cooldownOk)
            {
               // v53: SL anchored to the zone's own far edge (+ the existing
               // emergency-buffer input, now reused as "how far past the zone
               // edge") when a real zone was matched - a genuine invalidation
               // point, not an arbitrary distance from wherever price happens
               // to be right now. Unchanged fallback behavior otherwise.
               double slLevel;
               if(usedZone)
                  slLevel = (g_fusionDir == "BUY") ? (zoneLo - InpFusionEmergencySLUsd)
                                                     : (zoneHi + InpFusionEmergencySLUsd);
               else
                  slLevel = (g_fusionDir == "BUY") ? curPrice - InpFusionEmergencySLUsd
                                                     : curPrice + InpFusionEmergencySLUsd;
               string fusionTag = usedZone ? "FUSION_ZONE_CF" : "FUSION_H1H4";
               if(TryOpen(g_fusionDir, fusionTag, false, 0, 0, slLevel))
               {
                  g_fusionTicket       = trade.ResultOrder();
                  g_fusionLastFireTime = TimeCurrent();
                  GlobalVariableSet(GV_FUSION_TICKET, (double)g_fusionTicket);
                  // TryOpen() attaches a fixed TP (InpTP_Pips) by default - Fusion is
                  // pure structural exit (hold till H4 flips), so strip the TP right
                  // away, keeping only the emergency-backstop SL.
                  if(PositionSelectByTicket(g_fusionTicket))
                     trade.PositionModify(g_fusionTicket, PositionGetDouble(POSITION_SL), 0.0);
                  string zoneNote = usedZone ? StringFormat(" | SND zone=%.2f-%.2f (score %.0f)", zoneLo, zoneHi, zoneScore) : "";
                  Print("FUSION H1/H4 ENTRY (", fusionTag, "): ", g_fusionDir, " @ ", curPrice, zoneNote,
                        " | VR level=", g_fusionVrLevel, " | H4 zone=", h4Level,
                        " | extreme=", g_fusionVrExtreme, " | emergency SL=", slLevel, " | TP=none (struktural)");
               }
            }
            // Whether it fired or not, this VR cycle is consumed - re-arm needs a fresh VR
            g_fusionLastCf = h1ChangeTime;
            g_fusionVrSet  = false;
         }
      }
      g_fusionLastM5Event = m5EventTime;
   }

   // --- Structural exit: close the position the moment H4 itself flips away from it ---
   // NO fixed SL/TP governs this position under normal operation - InpFusionEmergencySLUsd
   // is a backstop only (EA/connection failure), not the intended exit path.
   if(g_fusionTicket != 0)
   {
      if(!PositionSelectByTicket(g_fusionTicket))
      {
         g_fusionTicket = 0;   // closed elsewhere (emergency SL hit, manual close, etc.)
         GlobalVariableDel(GV_FUSION_TICKET);
      }
      else
      {
         bool   isBuyPos = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
         string posDir   = isBuyPos ? "BUY" : "SELL";
         if(h4Dir != "WAIT" && h4Dir != posDir)
         {
            if(trade.PositionClose(g_fusionTicket))
            {
               Print("FUSION H1/H4 STRUCTURAL EXIT: H4 flip -> ", h4Dir, ", posisi ", posDir, " ditutup.");
               g_fusionTicket = 0;
               GlobalVariableDel(GV_FUSION_TICKET);
            }
         }
      }
   }
}

//--- v52.71: MOMENTUM ENTRY - Dadang 2026-08-19, abis trade +16738 poin hari
//--- itu: "ikut arah break out M5 bro karena jika itu terjadi rantainya akan
//--- terbentuk dengan sendirinya, gw udah uji kemaren" - entry FOLLOWS M5's
//--- own CMP direction on every fresh breakout event (buffer 7), gated ONLY
//--- by Momentum(M5) being same-direction and at least NORMAL strength
//--- ("kalo masih weak tidak usah entri"). Deliberately does NOT check H4/
//--- M30 alignment or Rantai depth - Dadang: "gak usah mikir chain ea nya
//--- biar gw yang mikir" (he judges that context manually; the EA's only
//--- job is the momentum gate). Exit is structural: closes the instant M5's
//--- OWN CMP flips direction - Dadang: "kita tp ketika momentum m5 nya
//--- berubah dari buy ke sell atau sebaliknya". BarrierVetoes() still runs
//--- inside TryOpen() same as every other trigger (first check there,
//--- unconditional) - this doesn't bypass it, just skips the H4/M30/Rantai
//--- checks that are specific to the main cascade path.
void CheckMomentumEntryTrigger()
{
   if(!InpUseMomentumEntryTrigger) return;
   if(g_hScalpEntry == INVALID_HANDLE) return;

   // --- structural exit: close the instant M5's own CMP flips direction ---
   if(g_momEntryTicket != 0)
   {
      if(!PositionSelectByTicket(g_momEntryTicket))
      {
         g_momEntryTicket = 0;   // closed elsewhere (SL hit, manual close, etc.)
         GlobalVariableDel(GV_MOMENTUM_TICKET);
      }
      else
      {
         bool     isBuyPos = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
         datetime ct; string curDir = ReadCMP(g_hScalpEntry, ct);
         bool flipped = (curDir == "BUY" || curDir == "SELL") &&
                        ((isBuyPos && curDir == "SELL") || (!isBuyPos && curDir == "BUY"));
         if(flipped)
         {
            if(trade.PositionClose(g_momEntryTicket))
            {
               Print("MOMENTUM ENTRY STRUCTURAL EXIT: M5 CMP flip -> ", curDir, ", posisi ditutup.");
               g_momEntryTicket = 0;
               GlobalVariableDel(GV_MOMENTUM_TICKET);
            }
         }
      }
      return;   // one position at a time from this trigger - nothing else to do this tick
   }

   // --- entry: fresh M5 breakout event + Momentum ratio >= minimum, same direction ---
   datetime evtTime = ReadBreakoutEventTime(g_hScalpEntry);
   if(evtTime == 0 || evtTime == g_momEntryLastEvent) return;   // no new breakout since last time we looked

   string dir; double ratio;
   if(!MomentumRatio(InpScalpEntryTF, g_hScalpEntry, dir, ratio)) return;

   g_momEntryLastEvent = evtTime;   // mark this event handled either way - never retry the same one
   if(ratio < InpMomentumEntryMinRatio)
   {
      Print("MOMENTUM ENTRY skip: ", dir, " breakout tapi ratio ", DoubleToString(ratio, 2), "x masih WEAK (< ", InpMomentumEntryMinRatio, ")");
      return;
   }

   if(TryOpen(dir, "MOM_M5", true))   // isScalp=true - fast momentum-riding entry, short TP/SL tier, real exit is the structural flip above
   {
      g_momEntryTicket = trade.ResultOrder();
      GlobalVariableSet(GV_MOMENTUM_TICKET, (double)g_momEntryTicket);
      Print("MOMENTUM ENTRY fired: ", dir, " ratio=", DoubleToString(ratio, 2), "x");
   }
}

// v52.80 - "CHAIN SIGNAL" staircase layering + explicit GAGAL state. Built
// first in DD_ChainReaction_StorylinePro.v10.pine (same night, v10.3) then
// Dadang redirected: "kita fokus ke ea dan web jangan ke pine" - ported here
// as the correct MT5-first build (Pine's copy stays as-is, this is the
// separate primary implementation).
//
// Dadang: "secara keilmuan gw CF bisa berkali kali... jika signal itu
// muncul lagi di atas kita tambah layer gitu terus bro, kita akan entri
// seperti tangga seperti trading manual gw - contoh entri sell terakhir gw
// signal muncul 3 kali, gw entri nambah entri di harga berbeda." Every
// fresh M5 breakout that agrees with g_scalpMasterDir (M30, "the direction
// actually being traded") is one more rung - gets its OWN persistent chart
// marker (not reused/overwritten - Dadang needs to see the whole staircase
// at once, same reasoning as the Pine version). The chain only INVALIDATES
// when g_scalpMasterDir itself flips (doctrine: "gagal HANYA kalau CMP
// flip", not SL, not a pullback - CLAUDE.md) - that moment draws one
// explicit "SIGNAL GAGAL" marker instead of silently resetting.
//
// NOTE: this is a DIFFERENT concept from the existing "RANTAI N/6" panel
// text (g_chainLen/g_convMode) - RANTAI counts how many TIMEFRAMES
// currently agree (a conviction-depth snapshot), CHAIN SIGNAL counts how
// many times a fresh CF has FIRED for this master cycle (a staircase-entry
// counter). Don't merge them - they answer different questions.
//
// Informational/chart-marker only, same "record first" discipline as every
// other panel feature tonight - NOT wired into TryOpen().
string   g_chainSigMasterDir   = "WAIT";
int      g_chainSigLayer       = 0;
datetime g_chainSigLastBoTime  = 0;

void DrawChainSignalMarker(string dir, int layer, double price, datetime t)
{
   string arrName = WALL_PREFIX + StringFormat("CHAINSIG_%d_A", (int)t);
   string txtName = WALL_PREFIX + StringFormat("CHAINSIG_%d_T", (int)t);
   color  clr = (dir == "BUY") ? PNL_EMERALD : PNL_ROSE;

   ObjectCreate(0, arrName, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, arrName, OBJPROP_ARROWCODE, dir == "BUY" ? 233 : 234);
   ObjectSetInteger(0, arrName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, arrName, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, arrName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, arrName, OBJPROP_HIDDEN, true);

   double offsetPrice = price + (dir == "BUY" ? -1 : 1) * SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 150;
   ObjectCreate(0, txtName, OBJ_TEXT, 0, t, offsetPrice);
   ObjectSetInteger(0, txtName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, txtName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, txtName, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, txtName, OBJPROP_ANCHOR, dir == "BUY" ? ANCHOR_TOP : ANCHOR_BOTTOM);
   ObjectSetString(0, txtName, OBJPROP_TEXT, StringFormat("CHAIN SIGNAL #%d %s @%.2f", layer, dir, price));
}

void DrawChainSignalFailMarker(string failedDir, int failedLayer, datetime t)
{
   string arrName = WALL_PREFIX + StringFormat("CHAINFAIL_%d_A", (int)t);
   string txtName = WALL_PREFIX + StringFormat("CHAINFAIL_%d_T", (int)t);
   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   ObjectCreate(0, arrName, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, arrName, OBJPROP_ARROWCODE, 251);   // X mark
   ObjectSetInteger(0, arrName, OBJPROP_COLOR, clrGray);
   ObjectSetInteger(0, arrName, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, arrName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, arrName, OBJPROP_HIDDEN, true);

   ObjectCreate(0, txtName, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, txtName, OBJPROP_COLOR, clrGray);
   ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, txtName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, txtName, OBJPROP_HIDDEN, true);
   ObjectSetInteger(0, txtName, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetString(0, txtName, OBJPROP_TEXT,
      StringFormat("SIGNAL GAGAL (%s x%d) - CMP FLIP - TUNGGU SIGNAL BARU", failedDir, failedLayer));
}

void UpdateChainSignal()
{
   if(g_scalpMasterDir != g_chainSigMasterDir)
   {
      if(g_chainSigMasterDir != "WAIT" && g_chainSigLayer > 0)
         DrawChainSignalFailMarker(g_chainSigMasterDir, g_chainSigLayer, TimeCurrent());
      g_chainSigMasterDir  = g_scalpMasterDir;
      g_chainSigLayer      = 0;
   }

   if(g_scalpMasterDir == "WAIT") return;

   datetime evtTime = ReadBreakoutEventTime(g_hScalpEntry);
   if(evtTime == 0 || evtTime == g_chainSigLastBoTime) return;
   g_chainSigLastBoTime = evtTime;

   if(g_scalpEntryDir != g_scalpMasterDir) return;   // only same-direction (CF) breakouts count as a rung

   g_chainSigLayer++;
   DrawChainSignalMarker(g_scalpEntryDir, g_chainSigLayer, SymbolInfoDouble(_Symbol, SYMBOL_BID), evtTime);
   Print("CHAIN SIGNAL #", g_chainSigLayer, " ", g_scalpEntryDir, " fired");
   // v53: entry logic moved OUT of here into its own CheckZoneBreakoutEntry()
   // - Dadang: "VR itu cmp juga jadi jangan baku EA harus fleksibel...
   // ketika m5 breakout searah apa aja bisa lo gas". Gating entry on this
   // function's OWN M30-agreement requirement (g_scalpEntryDir ==
   // g_scalpMasterDir, checked above) was itself exactly the kind of rigid
   // extra precondition he's saying to drop - the zone's own score already
   // validates location, M5's breakout direction is the only confirmation
   // needed. This function stays pure display (the "SELL #1/#2 aktif"
   // panel counter), decoupled from whether/how entries fire.
}

//+------------------------------------------------------------------+
//| v53: Dadang - "VR itu cmp juga jadi jngan baku ea harus flexibel
//| makanya kita pakai m5 breakout sebenarnya setiap sampai area snd
//| ketika m5 breakout searah apa aja bisa lo gas karena itu konfirmasi
//| pantulan di SNR dan SND kita". No H4/H1/VR/M30-agreement precondition
//| at all - watches M5's OWN fresh breakout event directly, fires the
//| instant it happens searah with whichever zone price is currently
//| sitting inside (SELL only inside SUPPLY, BUY only inside DEMAND, same
//| pairing as everywhere else this session). The zone's own score gate
//| (InpZoneCFMinScore) IS the location-quality filter - nothing else
//| needs to agree first.
//+------------------------------------------------------------------+
datetime g_zoneBreakoutLastEvent = 0;

void CheckZoneBreakoutEntry()
{
   if(!InpUseZoneCFEntry) return;
   if(g_hScalpEntry == INVALID_HANDLE) return;

   datetime evtTime = ReadBreakoutEventTime(g_hScalpEntry);
   if(evtTime == 0 || evtTime == g_zoneBreakoutLastEvent) return;
   g_zoneBreakoutLastEvent = evtTime;

   datetime dummyT;
   string m5Dir = ReadCMP(g_hScalpEntry, dummyT);
   if(m5Dir == "WAIT") return;

   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double zLo = 0.0, zHi = 0.0, zScore = 0.0;
   bool wantSupply = (m5Dir == "SELL");
   if(ZoneCheck(wantSupply, price, zLo, zHi, zScore))
   {
      double tpEdge = 0.0, tpScore = 0.0;
      bool haveTp = NearestOpposingZone(!wantSupply, price, tpEdge, tpScore);
      double tp = haveTp ? tpEdge : 0.0;

      if(TryOpen(m5Dir, "ZONE_BREAKOUT", false, 0, 0, 0.0, tp))
      {
         string tpNote = haveTp ? StringFormat(" | TP=zona lawan %.2f (score %.0f)", tpEdge, tpScore)
                                  : " | TP=fallback pip (belum ada zona lawan)";
         Print("ZONE BREAKOUT ENTRY: ", m5Dir, " @ ", price,
               " | zone=", zLo, "-", zHi, " (score ", zScore, ")", tpNote);
      }
   }
}

//--- Barrier-BE: uses Scalp Master TF's (M30 by default) own LIVE res/sup -
//--- NOT H4/Master. Dadang: "barriernya kasih M30 aja minimal biar gak
//--- terlalu mepet." Reason H4 alone was too aggressive: H4 forms new V/A
//--- shapes rarely, so its live res/sup often sits STALE - already broken
//--- by price long ago but not yet replaced by a fresh one (a new A-shape
//--- needs a fresh local top+reversal, which H4 rarely produces) - meaning
//--- the "touched barrier" check could stay permanently true right after
//--- entry, firing BE almost instantly. M30 refreshes far more often, so
//--- its level stays a genuine, still-ahead-of-price zone most of the time.
//--- Old local highs/lows price hasn't retested yet = "area pantul" (bounce
//--- zone). Dadang: "setiap sampai barrier pertama sebaiknya langsung set
//--- BE karena itu area pantul balik ke area BO TF entri; kalo TF entri
//--- tidak flip biasanya barrier akan jebol [dan lanjut untung]." So this
//--- doesn't cut the position - it just secures it at breakeven BEFORE a
//--- potential rejection, so if Entry TF later flips (triggering the
//--- normal cut-loss elsewhere), the "loss" is already risk-free. If Entry
//--- TF holds through the barrier instead, the position rides the eventual
//--- breakout with no downside taken. Direction-agnostic: BUY checks live
//--- res ahead, SELL checks live sup ahead - works for NORMAL and SCALP
//--- tier positions alike (barrier is relative to the position's own
//--- direction, not which tier opened it). Falls back to Master (H4) only
//--- if the Scalp tier isn't enabled (no M30 handle available).
void ManageTrailingAndBE() {}
void CheckBarrierBE() {}


//+------------------------------------------------------------------+
//| Close Positions Opposite to New Direction on M30 Reversal        |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Close Positions Opposite to New Direction on M30 Reversal        |
//| DADANG LAW: If M30 position was aligned with H4, DO NOT cut loss  |
//| when M30 flips UNLESS H1 ALSO flips against H4!                 |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Close Positions Opposite to New Direction on M30 Reversal        |
//| DADANG LAW: If M30 position was aligned with H4, DO NOT cut loss  |
//| when M30 flips UNLESS H1 ALSO flips against H4!                 |
//+------------------------------------------------------------------+
void ClosePositionsOppositeTo(string newDir)
{
   // Get H1 CMP direction
   double cmpH1Buf[2];
   string h1Dir = "WAIT";
   if(g_hH1 != INVALID_HANDLE && CopyBuffer(g_hH1, 2, 0, 1, cmpH1Buf) > 0)
   {
      h1Dir = (cmpH1Buf[0] == 1.0) ? "BUY" : ((cmpH1Buf[0] == -1.0) ? "SELL" : "WAIT");
   }

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      long type = PositionGetInteger(POSITION_TYPE);
      bool isBuy  = (type == POSITION_TYPE_BUY);
      bool isSell = (type == POSITION_TYPE_SELL);

      bool isOppositeToNewM30 = (newDir == "BUY" && isSell) || (newDir == "SELL" && isBuy);
      if(!isOppositeToNewM30) continue;

      // DADANG RULE: If M30 position was aligned with H4, DO NOT cut loss on M30 flip UNLESS H1 also flips against H4!
      bool positionWasAlignedWithH4 = (isBuy && g_masterDir == "BUY") || (isSell && g_masterDir == "SELL");
      bool h1OpposesH4              = (isBuy && h1Dir == "SELL") || (isSell && h1Dir == "BUY");

      bool shouldCutLoss = true;
      if(positionWasAlignedWithH4 && !h1OpposesH4)
      {
         shouldCutLoss = false; // HOLD! H1 has not flipped against H4 yet!
      }

      if(shouldCutLoss)
      {
         trade.PositionClose(tk);
      }
   }
}

void UpdateStateAndExecute()
{
   double cmpMasterBuf[2], cmpScalpMasterBuf[2], cmpScalpEntryBuf[2];
   double eventTimeBuf[2], liveSupBuf[2], liveResBuf[2];

   if(CopyBuffer(g_hMaster, 2, 0, 1, cmpMasterBuf) <= 0) return;
   if(CopyBuffer(g_hScalpMaster, 2, 0, 1, cmpScalpMasterBuf) <= 0) return;
   if(CopyBuffer(g_hScalpEntry, 2, 0, 2, cmpScalpEntryBuf) <= 0) return;
   if(CopyBuffer(g_hScalpEntry, 7, 0, 1, eventTimeBuf) <= 0) return;
   if(CopyBuffer(g_hScalpMaster, 5, 0, 1, liveSupBuf) <= 0) return;
   if(CopyBuffer(g_hScalpMaster, 6, 0, 1, liveResBuf) <= 0) return;

   string oldScalpMasterDir = g_scalpMasterDir;

   g_masterDir      = (cmpMasterBuf[0] == 1.0) ? "BUY" : ((cmpMasterBuf[0] == -1.0) ? "SELL" : "WAIT");
   g_scalpMasterDir = (cmpScalpMasterBuf[0] == 1.0) ? "BUY" : ((cmpScalpMasterBuf[0] == -1.0) ? "SELL" : "WAIT");
   g_scalpEntryDir  = (cmpScalpEntryBuf[0] == 1.0) ? "BUY" : ((cmpScalpEntryBuf[0] == -1.0) ? "SELL" : "WAIT");

   datetime m5EventTime = (datetime)eventTimeBuf[0];
   datetime currentM30BarTime = iTime(_Symbol, InpScalpMasterTF, 0);

   //--- 1. REVERSAL / FLIP RULE: Reset Retest State & Cutloss Opposite Positions
   if(oldScalpMasterDir != "WAIT" && g_scalpMasterDir != oldScalpMasterDir)
   {
      ClosePositionsOppositeTo(g_scalpMasterDir);
      g_m30PullbackActive = false;
      g_m30PullbackTime = 0;
      g_m5FiringEnabled = false;
      g_cmpStatus = "NORMAL";
      return;
   }

   //--- 2. DADANG'S LAW: 1 OPPOSITE M30 CANDLE IS THE VR ITSELF!
   // M30 BUY  -> 1 Red Candle M30 (Close < Open) IS THE VR!
   // M30 SELL -> 1 Green Candle M30 (Close > Open) IS THE VR!
   if(currentM30BarTime != g_lastM30BarTime)
   {
      g_lastM30BarTime = currentM30BarTime;

      MqlRates ratesM30[];
      if(CopyRates(_Symbol, InpScalpMasterTF, 1, 1, ratesM30) > 0)
      {
         datetime m30CandleStart = ratesM30[0].time;
         datetime m30CandleClose = m30CandleStart + PeriodSeconds(InpScalpMasterTF);

         if(g_scalpMasterDir == "BUY" && ratesM30[0].close < ratesM30[0].open)
         {
            g_m30PullbackActive = true;
            g_m30PullbackTime = m30CandleClose;
         }
         else if(g_scalpMasterDir == "SELL" && ratesM30[0].close > ratesM30[0].open)
         {
            g_m30PullbackActive = true;
            g_m30PullbackTime = m30CandleClose;
         }
      }
   }

   //--- 3. STATUS ASSIGNMENT FOR CANVAS PANEL (NORMAL / CF)
   if(g_scalpMasterDir != "WAIT" && g_scalpEntryDir == g_scalpMasterDir)
   {
      if(g_m30PullbackActive && g_m30PullbackTime > 0 && m5EventTime >= g_m30PullbackTime)
      {
         g_cmpStatus = "CF"; // VR Completed (via 1 M30 opposite candle) & M5 BO ready!
         g_m5FiringEnabled = true;
      }
      else
      {
         g_cmpStatus = "NORMAL"; // Waiting for 1 M30 opposite candle (VR)
         g_m5FiringEnabled = false;
      }
   }

   //--- 4. FIRE CHECK: Entry allowed ONLY WHEN STATUS == 'CF' AND m5EventTime >= g_m30PullbackTime
   if(m5EventTime != g_lastM5EventTime)
   {
      g_lastM5EventTime = m5EventTime;

      if(InpAllowScalpEntries && g_m5FiringEnabled && g_cmpStatus == "CF" &&
         g_scalpMasterDir != "WAIT" && g_scalpEntryDir == g_scalpMasterDir &&
         g_m30PullbackActive && g_m30PullbackTime > 0 && m5EventTime >= g_m30PullbackTime)
      {
         // Spread Filter
         double spreadPips = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * _Point / PipSize();
         if(InpMaxSpreadPips <= 0 || spreadPips <= InpMaxSpreadPips)
         {
            bool isScalp = (g_scalpMasterDir != g_masterDir); // Against H4
            string tag = isScalp ? StringFormat("SCALP %s>%s", EnumToString(InpScalpMasterTF), EnumToString(InpScalpEntryTF))
                                 : StringFormat("%s>%s>%s", EnumToString(InpMasterTF), EnumToString(InpScalpMasterTF), EnumToString(InpScalpEntryTF));
            
            TryOpen(g_scalpMasterDir, tag, isScalp, g_scalpMasterChangeTime, m5EventTime);
            
            // Consume trigger so next entry requires a new M30 pullback candle (new VR)
            g_m30PullbackActive = false;
         }
      }
   }
}


void OnTick()
{
   ReadBookmapBridge();
   if(InpUseZoneCFEntry || InpShowZonesOnChart)
   {
      ReadZonesCsv();   // v53 - separate pipeline/file from bookmap_live_signal.csv above
      DrawAllZones();
      RefreshDecisionContext(); // v53.10 - reads roadmap arrays DrawAllZones() just rebuilt; UpdatePanel() below depends on this having run first
      UpdateSDBreakEngine();    // v53.18 - reads the same roadmap arrays (S1/D1) - detection/display only, see function comment
   }
   UpdateSweepRecord();   // v52.69: must run right after ReadBookmapBridge() - latches fresh g_bmSweep* into the persistent record
   ReadMacroCorrelation();
   ReadUsdFundamental();
   UpdateCvdEma();   // v52.13: must run AFTER ReadBookmapBridge() (fresh g_bookmapCvd), BEFORE anything below reads g_bmCvdEma
   ComputeConviction();
   ComputeBookmapNarrative();
   UpdatePanel();
   WriteSultanStatus();

   UpdateAllCandleOpenMarkers();   // v52.58: now draws active-barrier markers, not candle-open markers
   UpdateCountdownMiniPanel();     // v52.50

   if(InpUseBarrierVeto)   // v52.47/v52.60 - must run BEFORE any entry logic below
   {
      TryBootstrapAllBarriers();   // v52.63: retries here every tick until it succeeds once (see function comment)
      // v52.64: tags turn on PUSH/PRUNE/FLIP diagnostic Print()s - Dadang: "M30
      // BO BUY... mana M30 nya" - trace exactly what happens to each TF's
      // queue in the Experts log instead of guessing why one looks empty.
      UpdateBarrierTracking(g_hMaster, InpMasterTF, g_h4LastDir, g_h4LastLevel, g_h4Queue, "H4");
      UpdateBarrierTracking(g_hH1, PERIOD_H1, g_h1BarrierLastDir, g_h1BarrierLastLevel, g_h1Queue, "H1");
      UpdateBarrierTracking(g_hScalpMaster, InpScalpMasterTF, g_m30LastDir, g_m30LastLevel, g_m30Queue, "M30");
      UpdateBarrierTracking(g_hExportM15, PERIOD_M15, g_m15LastDir, g_m15LastLevel, g_m15Queue, "M15");   // v52.59: awareness only
      UpdateBarrierTracking(g_hScalpEntry, InpScalpEntryTF, g_m5LastDir, g_m5LastLevel, g_m5Queue, "M5"); // v52.59: awareness only
      UpdateBarrierTracking(g_hExportD1, PERIOD_D1, g_d1LastDir, g_d1LastLevel, g_d1Queue, "D1");         // v52.61: awareness only, H4's "parent"
   }

   UpdateStateAndExecute();
   CheckBookmapTrigger();
   CheckVaRetestTrigger();   // v52.42
   CheckFusionH1H4Trigger();   // v52.45
   CheckMomentumEntryTrigger();   // v52.71
   CheckZoneBreakoutEntry();   // v53
   UpdateChainSignal();   // v52.80
   UpdateCvdDivergence();   // v52.82
   UpdateIVB();   // v52.83
   UpdateDailyProfileFraming();   // v52.83
}
