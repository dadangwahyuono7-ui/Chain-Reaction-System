"use client";

import { useState } from "react";
import { signIn } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { LogoLogin } from "@/components/logo";
import { EyeIcon, EyeOffIcon } from "lucide-react";
import dynamic from "next/dynamic";

const ThreeBg = dynamic(() => import("@/components/three-bg").then(m => m.ThreeBg), { ssr: false });
import { CursorGlow } from "@/components/cursor-glow";

export default function LoginPage() {
  const router = useRouter();
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);
  const [showPw,   setShowPw]   = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const result = await signIn.email({ email, password });
    if (result.error) {
      setError("Commander ID atau Access Code salah.");
      setLoading(false);
    } else {
      router.push("/dashboard");
    }
  }

  return (
    <div className="min-h-screen bg-transparent flex items-center justify-center p-4 relative overflow-hidden">

      {/* WebGL 3D wireframe background */}
      <ThreeBg />
      <CursorGlow />

      {/* Background grid */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(#f59e0b 1px, transparent 1px), linear-gradient(90deg, #f59e0b 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* Ambient glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-sm space-y-8">

        {/* Logo */}
        <LogoLogin />

        {/* Card */}
        <div className="bg-zinc-900/80 backdrop-blur border border-zinc-800 rounded-2xl p-6 shadow-2xl shadow-black/50">

          <p className="text-xs text-zinc-500 text-center mb-6 uppercase tracking-widest">
            Commander Access
          </p>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs text-zinc-400 uppercase tracking-wider font-medium">
                Commander ID
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-zinc-800/80 border border-zinc-700 text-white rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-amber-600 focus:bg-zinc-800 transition-all placeholder:text-zinc-600"
                placeholder="commander@chain.id"
                autoComplete="email"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-zinc-400 uppercase tracking-wider font-medium">
                Access Code
              </label>
              <div className="relative">
                <input
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full bg-zinc-800/80 border border-zinc-700 text-white rounded-xl px-4 py-2.5 pr-11 text-sm focus:outline-none focus:border-amber-600 focus:bg-zinc-800 transition-all placeholder:text-zinc-600"
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(p => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-amber-400 transition-colors"
                  tabIndex={-1}
                >
                  {showPw ? <EyeOffIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 bg-red-950/60 border border-red-800/50 rounded-xl px-3 py-2">
                <span className="text-red-400 text-sm">⚠</span>
                <p className="text-red-400 text-xs">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-amber-500 hover:bg-amber-400 active:bg-amber-600 text-black font-black rounded-xl h-11 text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed tracking-wide shadow-lg shadow-amber-900/30 hover:shadow-amber-800/40"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  VERIFIKASI...
                </span>
              ) : (
                "MASUK"
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-zinc-700">
          Sistem terbatas — Commander Dadang only
        </p>

      </div>
    </div>
  );
}
