"use client";

import { useState } from "react";
import { signUp } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { CopyIcon, CheckIcon } from "lucide-react";

const ENV_CONTENT = `# ── Local Qwen3 (PC rumah — kalau ada llama.cpp) ──
LLM_API_KEY=local
LLM_BASE_URL=http://localhost:8080/v1
LLM_MODEL=qwen3-8b-q4.gguf

# ── Cloud Claude (otomatis kalau local mati) ───────
BLUEPACK_API_KEY=bluepack_23e73139fb11516b891d44000f1375e8a88d1a6b5786a3e8
BLUEPACK_BASE_URL=https://ai.bluepack.my.id/v1
BLUEPACK_MODEL=claude-3-5-haiku-20241022

# ── Auth ───────────────────────────────────────────
BETTER_AUTH_SECRET=sultan_sniper_secret_2024_xauusd_chain_reaction
BETTER_AUTH_URL=http://localhost:3002

# ── Database ───────────────────────────────────────
DATABASE_URL=./sultan.db

# ── FRED API ───────────────────────────────────────
FRED_API_KEY=26cfd00d7779120d151509fb3ef9f810`;

export default function SetupPage() {
  const router = useRouter();
  const [name, setName]       = useState("Commander Dadang");
  const [email, setEmail]     = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied]   = useState(false);

  async function handleSetup(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const result = await signUp.email({ name, email, password });
    if (result.error) {
      setError(result.error.message ?? "Gagal membuat akun.");
      setLoading(false);
    } else {
      router.push("/dashboard");
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(ENV_CONTENT);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-xl space-y-6">

        {/* Header */}
        <div className="text-center">
          <div className="text-4xl font-black text-amber-500 tracking-tighter mb-1">SULTAN</div>
          <div className="text-sm font-bold text-white tracking-widest mb-1">INITIAL SETUP</div>
          <div className="text-xs text-zinc-500">Buat akun Commander sekali saja</div>
        </div>

        {/* ── ENV CONFIG SECTION ───────────────────────────────────────────── */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800 bg-zinc-900/80">
            <div>
              <span className="text-[11px] font-black font-mono text-amber-400 tracking-widest">STEP 1 — .env.local</span>
              <p className="text-[10px] text-zinc-600 mt-0.5">Copy ini → buat file <code className="text-zinc-400">.env.local</code> di folder <code className="text-zinc-400">sultan-advisor/</code></p>
            </div>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all border"
              style={copied
                ? { background: "rgba(52,211,153,0.15)", borderColor: "rgba(52,211,153,0.4)", color: "#34d399" }
                : { background: "rgba(245,158,11,0.1)", borderColor: "rgba(245,158,11,0.3)", color: "#f59e0b" }}
            >
              {copied
                ? <><CheckIcon className="w-3 h-3" /> COPIED!</>
                : <><CopyIcon className="w-3 h-3" /> COPY</>}
            </button>
          </div>
          <pre className="px-4 py-3 text-[10px] font-mono text-zinc-300 overflow-x-auto leading-relaxed whitespace-pre">
            {ENV_CONTENT}
          </pre>
        </div>

        {/* ── ACCOUNT FORM ─────────────────────────────────────────────────── */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <div className="mb-4">
            <span className="text-[11px] font-black font-mono text-amber-400 tracking-widest">STEP 2 — BUAT AKUN</span>
            <p className="text-[10px] text-zinc-600 mt-0.5">Setelah <code className="text-zinc-400">.env.local</code> siap, buat akun Commander di bawah</p>
          </div>
          <form onSubmit={handleSetup} className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs text-zinc-400 uppercase tracking-wider">Nama Commander</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} required
                className="w-full bg-zinc-950 border border-zinc-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-amber-700 transition-colors" />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-zinc-400 uppercase tracking-wider">Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                className="w-full bg-zinc-950 border border-zinc-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-amber-700 transition-colors"
                placeholder="commander@sultan.id" />
            </div>
            <div className="space-y-2">
              <label className="text-xs text-zinc-400 uppercase tracking-wider">Access Code</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8}
                className="w-full bg-zinc-950 border border-zinc-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-amber-700 transition-colors"
                placeholder="Min. 8 karakter" />
            </div>
            {error && <p className="text-red-400 text-xs">{error}</p>}
            <button type="submit" disabled={loading}
              className="w-full bg-amber-500 hover:bg-amber-400 text-black font-bold rounded-lg h-11 text-sm transition-colors disabled:opacity-50">
              {loading ? "Membuat akun..." : "⚡ AKTIVASI SISTEM"}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-[10px] text-zinc-700 font-mono">
          CHAIN REACTION v4.0 OVERLORD · XAUUSD · Commander Dadang Wahyuono
        </p>

      </div>
    </div>
  );
}
