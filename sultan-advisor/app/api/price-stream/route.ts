/* eslint-disable @typescript-eslint/no-explicit-any */
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

const PRICE_EXPR = `(function(){
  try {
    var q = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model().mainSeries();
    var last = q.data().bars().last();
    return last ? last.value[4].toFixed(2) : null;
  } catch(e) { return null; }
})()`;

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return new Response("Unauthorized", { status: 401 });

  const encoder  = new TextEncoder();
  let cancelled  = false;
  let cdpClient: any = null;

  const stream = new ReadableStream({
    async start(controller) {
      const send = (data: object) => {
        try { controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`)); }
        catch { /* stream already closed */ }
      };

      try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const CDP = require("chrome-remote-interface");

        const list = await CDP.List({ port: 9222 });
        const tab  = list.find((t: any) => t.url?.includes("tradingview.com/chart"));

        if (!tab) {
          send({ error: "No TradingView chart tab found" });
          controller.close();
          return;
        }

        cdpClient = await CDP({ target: tab.id, port: 9222 });
        await cdpClient.Runtime.enable();

        // Tick every 1 second
        while (!cancelled) {
          try {
            const r = await cdpClient.Runtime.evaluate({
              expression:    PRICE_EXPR,
              returnByValue: true,
              timeout:       2000,
            });
            const price: string | null = r.result?.value ?? null;
            if (price) send({ price });
          } catch { /* ignore single eval failure — keep looping */ }

          await new Promise<void>((res) => setTimeout(res, 1000));
        }
      } catch (err: any) {
        try { send({ error: String(err?.message ?? err) }); } catch { /* ignore */ }
      } finally {
        if (cdpClient) { try { await cdpClient.close(); } catch { /* ignore */ } }
        try { controller.close(); } catch { /* ignore */ }
      }
    },
    cancel() { cancelled = true; },
  });

  return new Response(stream, {
    headers: {
      "Content-Type":      "text/event-stream",
      "Cache-Control":     "no-cache, no-transform",
      "Connection":        "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
