"use client";

import { useSession } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { ArrowLeftIcon } from "lucide-react";
import JournalTab from "@/components/dashboard/dashboard-components/JournalTab";

export default function JournalPage() {
  const { data: session, isPending } = useSession();
  const router = useRouter();

  if (isPending) return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (!session) { router.push("/login"); return null; }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="sticky top-0 z-10 flex items-center gap-3 px-4 py-3 bg-slate-950/95 backdrop-blur border-b border-slate-800/60">
        <button
          onClick={() => router.push("/dashboard")}
          className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 transition-colors text-sm"
        >
          <ArrowLeftIcon className="w-4 h-4" />
          Dashboard
        </button>
        <span className="text-slate-700">/</span>
        <span className="text-indigo-400 font-semibold text-sm flex items-center gap-1.5">
          <span>📊</span> Trading Journal
        </span>
      </div>
      <div className="max-w-3xl mx-auto px-4 py-6">
        <JournalTab />
      </div>
    </div>
  );
}
