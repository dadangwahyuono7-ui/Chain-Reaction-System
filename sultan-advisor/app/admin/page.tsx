"use client";

import { useSession } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TrashIcon, ShieldIcon, UserIcon, CheckCircleIcon, XCircleIcon, LogOutIcon, UserPlusIcon, EyeIcon, EyeOffIcon, BadgeCheckIcon } from "lucide-react";

const ADMIN_EMAIL = "dadangwahyuono@gmail.com";

type User = {
  id: string;
  name: string;
  email: string;
  emailVerified: boolean;
  createdAt: string | number | null;
};

export default function AdminPage() {
  const { data: session, isPending } = useSession();
  const router = useRouter();

  const [users,     setUsers]     = useState<User[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [deleting,  setDeleting]  = useState<string | null>(null);
  const [verifying, setVerifying] = useState<string | null>(null);
  const [msg,       setMsg]       = useState<{ text: string; ok: boolean } | null>(null);

  // Add user form state
  const [showForm,   setShowForm]   = useState(false);
  const [adding,     setAdding]     = useState(false);
  const [showPass,   setShowPass]   = useState(false);
  const [newName,    setNewName]    = useState("");
  const [newEmail,   setNewEmail]   = useState("");
  const [newPass,    setNewPass]    = useState("");

  const isAdmin = session?.user?.email === ADMIN_EMAIL;

  useEffect(() => {
    if (!isPending && !session) { router.push("/login"); return; }
    if (!isPending && session && !isAdmin) { router.push("/dashboard"); return; }
    if (isAdmin) loadUsers();
  }, [isPending, session, isAdmin]);

  async function loadUsers() {
    setLoading(true);
    try {
      const r = await fetch("/api/admin/users");
      if (r.ok) setUsers(await r.json());
    } finally { setLoading(false); }
  }

  async function deleteUser(u: User) {
    if (!confirm(`Hapus akun "${u.name}" (${u.email})?\n\nSemua sesi chat akan dihapus permanen.`)) return;
    setDeleting(u.id); setMsg(null);
    try {
      const r = await fetch(`/api/admin/users?id=${u.id}`, { method: "DELETE" });
      const data = await r.json();
      if (r.ok) { setMsg({ text: `Akun "${u.name}" berhasil dihapus.`, ok: true }); await loadUsers(); }
      else        setMsg({ text: `Gagal: ${data.error ?? "Unknown error"}`, ok: false });
    } catch (e) { setMsg({ text: `Error: ${String(e)}`, ok: false }); }
    finally { setDeleting(null); }
  }

  async function addUser(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim() || !newEmail.trim() || !newPass.trim()) return;
    setAdding(true); setMsg(null);
    try {
      const r = await fetch("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim(), email: newEmail.trim(), password: newPass }),
      });
      const data = await r.json();
      if (r.ok) {
        setMsg({ text: `Akun "${newName.trim()}" berhasil dibuat. Share password ke user.`, ok: true });
        setNewName(""); setNewEmail(""); setNewPass(""); setShowForm(false);
        await loadUsers();
      } else {
        setMsg({ text: `Gagal: ${data.error ?? "Unknown error"}`, ok: false });
      }
    } catch (e) { setMsg({ text: `Error: ${String(e)}`, ok: false }); }
    finally { setAdding(false); }
  }

  if (isPending || loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!isAdmin) return null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">

      {/* Header */}
      <div className="border-b border-slate-800 px-6 py-4 flex items-center gap-3">
        <ShieldIcon className="w-5 h-5 text-purple-400" />
        <span className="font-semibold text-slate-200">Admin Panel</span>
        <span className="text-slate-600 text-sm">· User Management</span>
        <div className="flex-1" />
        <button
          onClick={() => router.push("/dashboard")}
          className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1.5 transition-colors"
        >
          <LogOutIcon className="w-3.5 h-3.5" /> Kembali
        </button>
      </div>

      <div className="max-w-2xl mx-auto px-6 py-8 space-y-5">

        {/* Alert */}
        {msg && (
          <div className={`px-4 py-3 rounded-xl text-sm border flex items-start gap-2 ${
            msg.ok
              ? "bg-emerald-950/50 border-emerald-700/40 text-emerald-300"
              : "bg-red-950/50 border-red-700/40 text-red-300"
          }`}>
            <span>{msg.ok ? "✓" : "✗"}</span>
            <span>{msg.text}</span>
            <button onClick={() => setMsg(null)} className="ml-auto opacity-60 hover:opacity-100">✕</button>
          </div>
        )}

        {/* User list */}
        <div className="bg-slate-900 border border-slate-800/60 rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-800/60 flex items-center gap-2">
            <UserIcon className="w-4 h-4 text-slate-400" />
            <span className="text-sm font-semibold text-slate-200">Akun Terdaftar</span>
            <span className="text-xs text-slate-500 ml-1">({users.length} user)</span>
            <div className="flex-1" />
            {/* Tambah User Button */}
            <button
              onClick={() => { setShowForm(f => !f); setMsg(null); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-all"
            >
              <UserPlusIcon className="w-3.5 h-3.5" />
              Tambah User
            </button>
          </div>

          {/* Add user form — inline */}
          {showForm && (
            <form onSubmit={addUser} className="px-5 py-4 border-b border-slate-800/60 bg-purple-950/20 space-y-3">
              <p className="text-xs font-semibold text-purple-300">Buat akun baru untuk member tim</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wide">Nama</label>
                  <input
                    value={newName}
                    onChange={e => setNewName(e.target.value)}
                    placeholder="Commander Budi"
                    required
                    className="mt-1 w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-100 placeholder:text-slate-600 focus:border-purple-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wide">Email</label>
                  <input
                    type="email"
                    value={newEmail}
                    onChange={e => setNewEmail(e.target.value)}
                    placeholder="budi@gmail.com"
                    required
                    className="mt-1 w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-100 placeholder:text-slate-600 focus:border-purple-500 focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="text-[10px] text-slate-500 uppercase tracking-wide">Password (min 6 karakter)</label>
                <div className="relative mt-1">
                  <input
                    type={showPass ? "text" : "password"}
                    value={newPass}
                    onChange={e => setNewPass(e.target.value)}
                    placeholder="Min 6 karakter"
                    minLength={6}
                    required
                    className="w-full px-3 py-2 pr-10 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-100 placeholder:text-slate-600 focus:border-purple-500 focus:outline-none"
                  />
                  <button type="button" onClick={() => setShowPass(p => !p)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                    {showPass ? <EyeOffIcon className="w-3.5 h-3.5" /> : <EyeIcon className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
              <div className="flex gap-2">
                <button type="submit" disabled={adding}
                  className="flex-1 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-all flex items-center justify-center gap-2">
                  {adding
                    ? <><div className="w-3.5 h-3.5 border border-white/40 border-t-white rounded-full animate-spin" /> Membuat...</>
                    : <><UserPlusIcon className="w-3.5 h-3.5" /> Buat Akun</>
                  }
                </button>
                <button type="button" onClick={() => setShowForm(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded-lg transition-all">
                  Batal
                </button>
              </div>
            </form>
          )}

          {/* User rows */}
          <div className="divide-y divide-slate-800/40">
            {users.length === 0 && (
              <div className="px-5 py-8 text-center text-slate-600 text-sm">Belum ada user</div>
            )}
            {users.map(u => {
              const isMe = u.email === ADMIN_EMAIL;
              const createdAt = u.createdAt
                ? new Date(typeof u.createdAt === "number" ? u.createdAt * 1000 : u.createdAt)
                    .toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" })
                : "–";

              return (
                <div key={u.id} className="flex items-center gap-4 px-5 py-4">
                  {/* Avatar */}
                  <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
                    isMe ? "bg-purple-950 text-purple-300 border border-purple-700/50"
                         : "bg-slate-800 text-slate-300"
                  }`}>
                    {u.name.charAt(0).toUpperCase()}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-slate-200 truncate">{u.name}</span>
                      {isMe && <span className="text-[10px] px-1.5 py-0.5 bg-purple-950 text-purple-400 border border-purple-800/50 rounded-full">Admin</span>}
                    </div>
                    <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5 flex-wrap">
                      <span className="truncate">{u.email}</span>
                      <span>·</span>
                      <span>{createdAt}</span>
                      <span>·</span>
                      {u.emailVerified
                        ? <span className="flex items-center gap-0.5 text-emerald-500"><CheckCircleIcon className="w-3 h-3" /> Aktif</span>
                        : <span className="flex items-center gap-0.5 text-amber-500"><XCircleIcon className="w-3 h-3" /> Belum diverifikasi</span>
                      }
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    {/* Verify button — only for unverified non-admin users */}
                    {!isMe && !u.emailVerified && (
                      <button
                        onClick={async () => {
                          setVerifying(u.id);
                          const r = await fetch(`/api/admin/users?id=${u.id}`, { method: "PATCH" });
                          if (r.ok) { setMsg({ text: `Email "${u.name}" berhasil diverifikasi.`, ok: true }); await loadUsers(); }
                          else setMsg({ text: "Gagal verifikasi.", ok: false });
                          setVerifying(null);
                        }}
                        disabled={verifying === u.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-emerald-400 hover:text-white hover:bg-emerald-500/20 border border-emerald-500/20 hover:border-emerald-500/40 rounded-lg transition-all disabled:opacity-40"
                        title="Verifikasi email manual"
                      >
                        {verifying === u.id
                          ? <div className="w-3 h-3 border border-emerald-400 border-t-transparent rounded-full animate-spin" />
                          : <BadgeCheckIcon className="w-3 h-3" />
                        }
                        Verif
                      </button>
                    )}

                    {/* Delete */}
                    {!isMe ? (
                      <button
                        onClick={() => deleteUser(u)}
                        disabled={deleting === u.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-400 hover:text-white hover:bg-red-500/20 border border-red-500/20 hover:border-red-500/40 rounded-lg transition-all disabled:opacity-40"
                      >
                        {deleting === u.id
                          ? <div className="w-3 h-3 border border-red-400 border-t-transparent rounded-full animate-spin" />
                          : <TrashIcon className="w-3 h-3" />
                        }
                        {deleting === u.id ? "..." : "Hapus"}
                      </button>
                    ) : (
                      <span className="text-xs text-slate-700 px-3 py-1.5">Admin</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <p className="text-center text-xs text-slate-700">
          Hanya <span className="text-slate-500">{ADMIN_EMAIL}</span> yang bisa akses halaman ini.
        </p>
      </div>
    </div>
  );
}
