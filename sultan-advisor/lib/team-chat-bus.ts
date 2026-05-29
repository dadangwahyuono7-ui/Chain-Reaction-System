import { EventEmitter } from "events";

export type ChatMessage = {
  id: string;
  userId: string;
  userName: string;
  text: string;
  createdAt: number; // epoch ms
};

export type BusEvent =
  | { type: "message"; message: ChatMessage }
  | { type: "presence"; online: string[] };

// Singleton across hot-reload / route modules via globalThis
type BusState = {
  emitter: EventEmitter;
  // userName -> jumlah koneksi aktif (1 user bisa buka >1 tab)
  online: Map<string, number>;
};

const g = globalThis as typeof globalThis & { __teamChatBus?: BusState };

if (!g.__teamChatBus) {
  const emitter = new EventEmitter();
  emitter.setMaxListeners(0); // banyak SSE listener
  g.__teamChatBus = { emitter, online: new Map() };
}

const state = g.__teamChatBus;

export const chatBus = state.emitter;

export function broadcast(event: BusEvent) {
  state.emitter.emit("event", event);
}

function presenceList(): string[] {
  return Array.from(state.online.keys()).sort();
}

/** Tandai 1 koneksi user online; return fungsi cleanup saat disconnect. */
export function addPresence(userName: string): () => void {
  state.online.set(userName, (state.online.get(userName) ?? 0) + 1);
  broadcast({ type: "presence", online: presenceList() });
  return () => {
    const n = (state.online.get(userName) ?? 1) - 1;
    if (n <= 0) state.online.delete(userName);
    else state.online.set(userName, n);
    broadcast({ type: "presence", online: presenceList() });
  };
}

export function getOnline(): string[] {
  return presenceList();
}
