"use client";

import { useState } from "react";
import { signUp } from "@/lib/auth-client";
import { useRouter } from "next/navigation";

export default function SetupPage() {
  const router = useRouter();
  const [name, setName] = useState("Commander Dadang");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center">
          <div className="text-4xl font-black text-amber-500 tracking-tighter mb-1">SULTAN</div>
          <div className="text-sm font-bold text-white tracking-widest mb-1">INITIAL SETUP</div>
          <div className="text-xs text-zinc-500">Buat akun Commander sekali saja</div>
        </div>

        <form onSubmit={handleSetup} className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs text-zinc-400 uppercase tracking-wider">Nama Commander</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required
              className="w-full bg-zinc-900 border border-zinc-800 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-amber-700 transition-colors" />
          </div>
          <div className="space-y-2">
            <label className="text-xs text-zinc-400 uppercase tracking-wider">Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              className="w-full bg-zinc-900 border border-zinc-800 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-amber-700 transition-colors"
              placeholder="commander@sultan.id" />
          </div>
          <div className="space-y-2">
            <label className="text-xs text-zinc-400 uppercase tracking-wider">Access Code</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8}
              className="w-full bg-zinc-900 border border-zinc-800 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-amber-700 transition-colors"
              placeholder="Min. 8 karakter" />
          </div>
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <button type="submit" disabled={loading}
            className="w-full bg-amber-500 hover:bg-amber-400 text-black font-bold rounded-lg h-11 text-sm transition-colors disabled:opacity-50">
            {loading ? "Membuat akun..." : "AKTIVASI SISTEM"}
          </button>
        </form>
      </div>
    </div>
  );
}
