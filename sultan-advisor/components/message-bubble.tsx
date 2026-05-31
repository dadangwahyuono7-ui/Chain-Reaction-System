"use client";

import { cn } from "@/lib/utils";
import type { UIMessage } from "ai";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ShieldCheckIcon, TrendingUpIcon, AlertOctagonIcon, SearchIcon, LinkIcon, BarChart2Icon, BrainIcon, RefreshCwIcon, CalculatorIcon, DatabaseIcon, TerminalIcon, SettingsIcon, PlayIcon, FolderIcon, FileTextIcon, PencilIcon, CameraIcon, CpuIcon } from "lucide-react";

interface Props {
  message: UIMessage;
  isStreaming?: boolean;
  sessionTitle?: string;
  onInject: (prompt: string) => void;
}

// ─── Tool badge chip ─────────────────────────────────────────────────────────

type ToolPart = {
  type: string;
  toolCallId?: string;
  state?: string;
  input?: Record<string, string>;
  output?: string;
};

const TOOL_META: Record<string, { icon: typeof SearchIcon; color: string; getLabel: (input?: Record<string, string>) => string }> = {
  // Market / Search
  "tool-web_search":         { icon: SearchIcon,     color: "text-blue-400",    getLabel: (i) => i?.query ?? "web search" },
  "tool-fetch_url":          { icon: LinkIcon,       color: "text-violet-400",  getLabel: (i) => i?.url ?? "fetch url" },
  "tool-get_ohlc":           { icon: BarChart2Icon,  color: "text-amber-400",   getLabel: (i) => `OHLC ${i?.tf ?? ""}${i?.bars ? ` ×${i.bars}` : ""}` },
  // Memory
  "tool-save_memory":        { icon: BrainIcon,      color: "text-emerald-400", getLabel: (i) => i?.category ?? "save memory" },
  "tool-search_memories":    { icon: DatabaseIcon,   color: "text-cyan-400",    getLabel: (i) => i?.keyword ?? i?.category ?? "search" },
  // System
  "tool-trigger_sync":       { icon: RefreshCwIcon,  color: "text-indigo-400",  getLabel: () => "TV Sync" },
  "tool-calculate_risk":     { icon: CalculatorIcon, color: "text-orange-400",  getLabel: (i) => `${i?.direction ?? "RISK"} R:R` },
  "tool-get_market_context": { icon: DatabaseIcon,   color: "text-slate-400",   getLabel: () => "read context" },
  // Engine
  "tool-run_engine_check":   { icon: CpuIcon,        color: "text-green-400",   getLabel: () => "MT5 engine" },
  "tool-read_settings":      { icon: SettingsIcon,   color: "text-slate-400",   getLabel: () => "settings" },
  "tool-update_settings":    { icon: SettingsIcon,   color: "text-yellow-400",  getLabel: (i) => i?.key ?? "update setting" },
  "tool-run_backtest":       { icon: PlayIcon,        color: "text-purple-400",  getLabel: () => "backtest" },
  // Full Agent
  "tool-shell_exec":         { icon: TerminalIcon,   color: "text-green-300",   getLabel: (i) => i?.command?.slice(0, 30) ?? "shell" },
  "tool-read_file":          { icon: FileTextIcon,   color: "text-slate-400",   getLabel: (i) => i?.path?.split("\\").pop() ?? "read file" },
  "tool-write_file":         { icon: PencilIcon,     color: "text-yellow-300",  getLabel: (i) => i?.path?.split("\\").pop() ?? "write file" },
  "tool-list_dir":           { icon: FolderIcon,     color: "text-amber-300",   getLabel: (i) => i?.path?.split("\\").pop() ?? "list dir" },
  "tool-screenshot_analyze": { icon: CameraIcon,     color: "text-pink-400",    getLabel: (i) => i?.focus ?? "screenshot" },
};

function ToolBadge({ part }: { part: ToolPart }) {
  const meta = TOOL_META[part.type];
  if (!meta) return null;

  const Icon = meta.icon;
  const label = meta.getLabel(part.input);
  const isDone = part.state === "output-available";

  return (
    <div className={cn(
      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-mono",
      isDone
        ? "bg-slate-800 text-slate-400 border border-slate-700/50"
        : "bg-slate-900 text-slate-500 border border-slate-800/50 animate-pulse",
    )}>
      <Icon className={cn("w-3 h-3 shrink-0", meta.color)} />
      <span className="max-w-[180px] truncate">{label}</span>
      {!isDone && <span className="text-slate-600 ml-0.5">…</span>}
    </div>
  );
}

export function MessageBubble({ message, isStreaming, onInject }: Props) {
  const textContent = message.parts
    .filter((p) => p.type === "text")
    .map((p) => (p as { type: "text"; text: string }).text)
    .join("");

  // Collect all tool call parts
  const toolParts = message.parts.filter(
    (p) => p.type.startsWith("tool-") && TOOL_META[p.type]
  ) as ToolPart[];

  // Parse gambar yang di-embed dari user message sebagai tag khusus
  // Format: [img:url:/uploads/...] atau [img:data:image/png;base64,...]
  const IMG_RE = /\[img:(https?:\/\/[^\]]+|\/uploads\/[^\]]+|data:[^\]]+)\]/g;
  const userImgUrls: string[] = [];
  let textForDisplay = textContent;
  if (message.role === "user") {
    let m: RegExpExecArray | null;
    while ((m = IMG_RE.exec(textContent)) !== null) userImgUrls.push(m[1]);
    textForDisplay = textContent.replace(IMG_RE, "").trim();
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] space-y-1.5">
          {/* Image attachments */}
          {userImgUrls.length > 0 && (
            <div className="flex flex-wrap gap-1.5 justify-end">
              {userImgUrls.map((src, i) => (
                <a key={i} href={src} target="_blank" rel="noopener noreferrer">
                  <img
                    src={src}
                    alt="attachment"
                    className="max-w-[260px] max-h-[200px] rounded-xl object-cover border border-indigo-800/40 hover:opacity-90 transition-opacity"
                  />
                </a>
              ))}
            </div>
          )}
          {/* Text */}
          {textForDisplay && (
            <div className="bg-indigo-950 border border-indigo-900/50 text-slate-100 rounded-2xl rounded-tr-sm px-4 py-3 text-sm whitespace-pre-wrap">
              {textForDisplay}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[88%] space-y-1.5">
        <div className="flex items-center gap-2 px-1 mb-0.5">
          <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 shadow-[0_0_6px_rgba(129,140,248,0.5)]" />
          <span className="text-[10px] text-indigo-400/80 font-semibold tracking-widest uppercase">Chain Reaction</span>
        </div>

        {/* Tool call chips — shown above the answer bubble */}
        {toolParts.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-1 mb-1">
            {toolParts.map((tp, i) => (
              <ToolBadge key={tp.toolCallId ?? i} part={tp} />
            ))}
          </div>
        )}

        <div
          className={cn(
            "bg-slate-900 border border-slate-800/50 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-slate-200",
            "prose prose-invert prose-sm max-w-none",
            "prose-headings:text-slate-100 prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-1",
            "prose-strong:text-slate-100 prose-strong:font-semibold",
            "prose-code:text-indigo-300 prose-code:bg-slate-800 prose-code:rounded prose-code:px-1.5 prose-code:py-0.5",
            "prose-li:text-slate-300 prose-p:text-slate-300 prose-p:leading-relaxed prose-p:my-1",
            "prose-blockquote:border-indigo-500/40 prose-blockquote:text-slate-400",
            "[&_table]:block [&_table]:overflow-x-auto [&_table]:whitespace-nowrap",
            "[&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-slate-800 [&_th]:border [&_th]:border-slate-700/40 [&_th]:text-slate-300",
            "[&_td]:px-3 [&_td]:py-1.5 [&_td]:border [&_td]:border-slate-700/30 [&_td]:text-slate-300"
          )}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // Render gambar inline dari AI (screenshot tool, dll)
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              img: ({ src, alt }: any) => (
                <a href={src} target="_blank" rel="noopener noreferrer" className="block my-2">
                  <img
                    src={src}
                    alt={alt ?? "screenshot"}
                    className="max-w-full rounded-xl border border-slate-700/50 cursor-pointer hover:opacity-90 transition-opacity"
                    style={{ maxHeight: 320 }}
                  />
                </a>
              ),
            }}
          >{textContent}</ReactMarkdown>
          {isStreaming && !textContent && (
            <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse rounded-sm" />
          )}
        </div>

        {/* Quick follow-up actions */}
        {!isStreaming && textContent && (
          <div className="flex gap-1 mt-1 pl-1 flex-wrap">
            <button
              onClick={() => onInject("Jalankan guard check lengkap sekarang: barrier, spread, session, news blackout.")}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] text-slate-500 hover:text-emerald-400 hover:bg-slate-800/50 border border-transparent hover:border-slate-700/40 transition-all"
            >
              <ShieldCheckIcon className="w-3 h-3" /> Guard
            </button>
            <button
              onClick={() => onInject("Berdasarkan analisis di atas, timeframe mana yang paling matang untuk entry? Urutkan dari paling siap ke paling belum siap.")}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] text-slate-500 hover:text-blue-400 hover:bg-slate-800/50 border border-transparent hover:border-slate-700/40 transition-all"
            >
              <TrendingUpIcon className="w-3 h-3" /> Prioritas
            </button>
            <button
              onClick={() => onInject("Apa skenario terburuk dari setup ini? Kapan setup ini dinyatakan GAGAL menurut doktrin?")}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] text-slate-500 hover:text-red-400 hover:bg-slate-800/50 border border-transparent hover:border-slate-700/40 transition-all"
            >
              <AlertOctagonIcon className="w-3 h-3" /> Skenario Gagal
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
