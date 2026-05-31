"use client";

import { useEffect, useState, useRef } from "react";
import { PlusIcon, TrashIcon, PencilIcon, CheckIcon, XIcon, SearchIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Session = { id: string; title: string };

interface Props {
  currentId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export function SessionSidebar({ currentId, onSelect, onNew }: Props) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function load() {
    const r = await fetch("/api/sessions");
    setSessions(await r.json());
  }

  useEffect(() => { load(); }, [currentId]);
  useEffect(() => { if (editingId) inputRef.current?.focus(); }, [editingId]);

  async function del(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    await fetch(`/api/sessions/${id}`, { method: "DELETE" });
    if (currentId === id) onNew();
    load();
  }

  async function saveEdit(id: string) {
    const t = editTitle.trim();
    if (t) await fetch(`/api/sessions/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: t }) });
    setEditingId(null);
    load();
  }

  const filtered = sessions.filter((s) => s.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="flex flex-col h-full">

      <div className="mx-3 mb-2 relative">
        <SearchIcon className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-zinc-600" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari..."
          className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-7 pr-2 py-1.5 text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-600" />
      </div>

      <div className="flex-1 overflow-y-auto space-y-0.5 px-2">
        {filtered.map((s) => (
          <div key={s.id} onClick={() => !editingId && onSelect(s.id)}
            className={cn("group flex items-center gap-1 px-2 py-2 rounded-lg cursor-pointer transition-colors text-xs",
              currentId === s.id ? "bg-zinc-800 text-white" : "text-zinc-400 hover:bg-zinc-900 hover:text-white")}>
            {editingId === s.id ? (
              <div className="flex items-center gap-1 flex-1 min-w-0" onClick={(e) => e.stopPropagation()}>
                <input ref={inputRef} value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") saveEdit(s.id); if (e.key === "Escape") setEditingId(null); }}
                  className="flex-1 min-w-0 bg-zinc-700 text-white text-xs rounded px-1.5 py-0.5 focus:outline-none" />
                <button onClick={() => saveEdit(s.id)} className="text-green-400"><CheckIcon className="w-3 h-3" /></button>
                <button onClick={() => setEditingId(null)} className="text-zinc-500"><XIcon className="w-3 h-3" /></button>
              </div>
            ) : (
              <>
                <span className="truncate flex-1">{s.title}</span>
                <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  <button onClick={(e) => { e.stopPropagation(); setEditingId(s.id); setEditTitle(s.title); }} className="p-1 hover:text-blue-400"><PencilIcon className="w-3 h-3" /></button>
                  <button onClick={(e) => del(s.id, e)} className="p-1 hover:text-red-400"><TrashIcon className="w-3 h-3" /></button>
                </div>
              </>
            )}
          </div>
        ))}
        {filtered.length === 0 && <p className="text-xs text-zinc-600 px-2 py-4 text-center">{search ? "Tidak ditemukan" : "Belum ada sesi"}</p>}
      </div>
    </div>
  );
}
