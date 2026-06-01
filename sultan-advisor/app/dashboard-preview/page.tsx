"use client";

/** Preview publik (mock data) — buat liat tampilan 3D dashboard tanpa login. */

import dynamic from "next/dynamic";
import { DashboardPro } from "@/components/dashboard-pro";

const ThreeBg = dynamic(() => import("@/components/three-bg").then((m) => m.ThreeBg), { ssr: false });
const Chain3DLive = dynamic(() => import("@/components/chain-3d").then((m) => m.Chain3D), { ssr: false });
import { CursorGlow } from "@/components/cursor-glow";

const tfData = [
  { tf: "DAILY", cmp: "BEARISH", vr: "YA", cf: "YA", cfCount: 17, cfType: "LOW", fase: 3 },
  { tf: "H4", cmp: "BEARISH", vr: "YA", cf: "YA", cfCount: 3, cfType: "LOW", fase: 3 },
  { tf: "H1", cmp: "BEARISH", vr: "YA", cf: "", cfCount: 0, cfType: "", fase: 2 },
  { tf: "M30", cmp: "BULLISH", vr: "YA", cf: "", cfCount: 1, cfType: "", fase: 2 },
  { tf: "M15", cmp: "BULLISH", vr: "", cf: "", cfCount: 0, cfType: "", fase: 1 },
  { tf: "M5", cmp: "BEARISH", vr: "", cf: "", cfCount: 0, cfType: "", fase: 1 },
  { tf: "M1", cmp: "", vr: "", cf: "", cfCount: 0, cfType: "", fase: 0 },
];
const aboveLevels = [
  { key: "PDH", short: "PDH", price: 4024.77, stars: 5 },
  { key: "LONDON_H", short: "LdnH", price: 3936.85, stars: 3 },
  { key: "ROUND_ABOVE", short: "↑Rnd", price: 3850, stars: 4 },
];
const belowLevels = [
  { key: "ROUND_BELOW", short: "↓Rnd", price: 3825, stars: 4 },
  { key: "DAILY_OPEN", short: "DOpen", price: 3775, stars: 4 },
  { key: "ASIA_L", short: "AsiaL", price: 3753, stars: 3 },
];

export default function DashboardPreview() {
  const noop = () => {};
  return (
    <div className="min-h-screen bg-transparent text-slate-100">
      <ThreeBg />
      <CursorGlow />
      <DashboardPro
        displayPrice="3840.01"
        livePrice="3840.01"
        priceFlash={null}
        spread="18"
        sess="London"
        tfData={tfData}
        h4Dir="BEARISH"
        hasTFData
        autoGrade={{ grade: "A", reason: "H4 F3 searah Daily + entry near SNR" }}
        buyPct={42}
        sellPct={58}
        cumDelta={-1240}
        momentum="SELL"
        momentumStr="moderate"
        barDeltas={[3, -5, -8, 4, -12, -6, 9, -14]}
        maxBarAbs={14}
        divergence={false}
        nTicks={820}
        aboveLevels={aboveLevels}
        belowLevels={belowLevels}
        atLevel={[]}
        cmpFloat={3840.01}
        tp1Up="3850" tp2Up="3936" tp1Dn="3825" tp2Dn="3775"
        minutesUntilNews={null}
        newsBlackout={false}
        newsApproaching={false}
        nextEventName=""
        nextEventTimeWIB=""
        syncTV={noop} syncing={false} tvStatus="ok" lastSync={Date.now()}
        syncSNR={noop} syncingSNR={false}
        syncNews={noop} syncingNews={false}
        autoSync setAutoSync={noop}
        blink={false} blinkFast={false}
        tvSymbol="XAUUSD" tvSymbolDesc="Gold Spot"
      />
    </div>
  );
}
