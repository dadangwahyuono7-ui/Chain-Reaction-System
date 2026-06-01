/**
 * /api/fund-data — "Jejak Fund" dari Yahoo Finance.
 * Logic di lib/fund-data.ts (dipakai bareng tool AI get_fund_data).
 */

import { computeFundData } from "@/lib/fund-data";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return Response.json(await computeFundData());
  } catch (e) {
    return Response.json({ ok: false, error: e instanceof Error ? e.message : String(e) }, { status: 500 });
  }
}
