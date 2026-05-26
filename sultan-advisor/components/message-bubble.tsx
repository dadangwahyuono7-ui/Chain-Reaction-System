"use client";

import { cn } from "@/lib/utils";
import type { UIMessage } from "ai";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ShieldCheckIcon, TrendingUpIcon, AlertOctagonIcon } from "lucide-react";

interface Props {
  message: UIMessage;
  isStreaming?: boolean;
  sessionTitle?: string;
  onInject: (prompt: string) => void;
}

export function MessageBubble({ message, isStreaming, onInject }: Props) {
  const textContent = message.parts
    .filter((p) => p.type === "text")
    .map((p) => (p as { type: "text"; text: string }).text)
    .join("");

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-zinc-800 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm whitespace-pre-wrap">
          {textContent}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-1">
        <div className="text-xs text-amber-600 px-1 mb-1 font-semibold tracking-wide">CHAIN REACTION</div>
        <div
          className={cn(
            "bg-zinc-900 border border-zinc-800 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-zinc-100",
            "prose prose-invert prose-sm max-w-none",
            "prose-headings:text-white prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-1",
            "prose-strong:text-white prose-strong:font-semibold",
            "prose-code:text-amber-400 prose-code:bg-zinc-800 prose-code:rounded prose-code:px-1",
            "prose-li:text-zinc-200 prose-p:text-zinc-200 prose-p:leading-relaxed prose-p:my-1",
            "prose-blockquote:border-amber-800 prose-blockquote:text-zinc-400",
            "[&_table]:block [&_table]:overflow-x-auto [&_table]:whitespace-nowrap",
            "[&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-zinc-800 [&_th]:border [&_th]:border-zinc-700",
            "[&_td]:px-3 [&_td]:py-1.5 [&_td]:border [&_td]:border-zinc-700"
          )}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{textContent}</ReactMarkdown>
          {isStreaming && !textContent && (
            <span className="inline-block w-1.5 h-4 bg-amber-500 animate-pulse rounded-sm" />
          )}
        </div>

        {/* Quick follow-up actions */}
        {!isStreaming && textContent && (
          <div className="flex gap-1.5 mt-1.5 pl-1 flex-wrap">
            <button
              onClick={() => onInject("Jalankan guard check lengkap sekarang: barrier, spread, session, news blackout.")}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-zinc-500 hover:text-emerald-400 hover:bg-zinc-800 border border-transparent hover:border-zinc-700 transition-all"
            >
              <ShieldCheckIcon className="w-3 h-3" /> Guard Check
            </button>
            <button
              onClick={() => onInject("Berdasarkan analisis di atas, timeframe mana yang paling matang untuk entry? Urutkan dari paling siap ke paling belum siap.")}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-zinc-500 hover:text-blue-400 hover:bg-zinc-800 border border-transparent hover:border-zinc-700 transition-all"
            >
              <TrendingUpIcon className="w-3 h-3" /> TF Prioritas
            </button>
            <button
              onClick={() => onInject("Apa skenario terburuk dari setup ini? Kapan setup ini dinyatakan GAGAL menurut doktrin?")}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-zinc-500 hover:text-red-400 hover:bg-zinc-800 border border-transparent hover:border-zinc-700 transition-all"
            >
              <AlertOctagonIcon className="w-3 h-3" /> Skenario Gagal
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
