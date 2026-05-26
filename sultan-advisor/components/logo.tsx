import { cn } from "@/lib/utils";

interface LogoProps {
  size?: number;
  className?: string;
}

/** Standalone chain-link icon mark */
export function LogoMark({ size = 32, className }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Outer ring glow */}
      <circle cx="16" cy="16" r="15.25" stroke="#f59e0b" strokeWidth="0.5" strokeOpacity="0.25" />
      {/* Inner ring */}
      <circle cx="16" cy="16" r="12" stroke="#f59e0b" strokeWidth="0.75" strokeOpacity="0.4" />

      {/* Top chain link (rotated oval) */}
      <rect x="9" y="5.5" width="14" height="9" rx="4.5" stroke="#f59e0b" strokeWidth="1.5" fill="none" />
      {/* Bottom chain link */}
      <rect x="9" y="17.5" width="14" height="9" rx="4.5" stroke="#f59e0b" strokeWidth="1.5" fill="none" />

      {/* Center connector — fill gap between links */}
      <rect x="12.5" y="14" width="7" height="4" fill="#0a0a0a" />

      {/* Interlocking bar top→bottom */}
      <line x1="13" y1="14.5" x2="19" y2="14.5" stroke="#f59e0b" strokeWidth="1" />
      <line x1="13" y1="17.5" x2="19" y2="17.5" stroke="#f59e0b" strokeWidth="1" />

      {/* Lightning bolt overlay — center */}
      <path
        d="M17.5 9.5 L14 16.5 H17 L14.5 22.5 L19 15 H16 L18.5 9.5 Z"
        fill="#f59e0b"
        fillOpacity="0.9"
      />
    </svg>
  );
}

/** Full logo: icon + text */
export function LogoFull({
  size = "md",
  className,
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const iconSize = size === "sm" ? 24 : size === "md" ? 36 : 56;
  const titleCls =
    size === "sm"
      ? "text-base font-black leading-none"
      : size === "md"
      ? "text-2xl font-black leading-none"
      : "text-4xl font-black leading-none";
  const subCls =
    size === "sm"
      ? "text-[10px] tracking-[0.2em]"
      : size === "md"
      ? "text-xs tracking-[0.25em]"
      : "text-sm tracking-[0.3em]";

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <LogoMark size={iconSize} />
      <div>
        <div className={cn(titleCls, "text-amber-400 tracking-tighter")}>
          CHAIN REACTION
        </div>
        <div className={cn(subCls, "text-zinc-500 uppercase mt-0.5 font-medium")}>
          XAUUSD · Daily Deploy
        </div>
      </div>
    </div>
  );
}

/** Sidebar compact logo */
export function LogoSidebar() {
  return (
    <div className="flex items-center gap-2">
      <LogoMark size={22} />
      <div>
        <div className="text-xs font-black text-amber-500 tracking-tighter leading-none">
          CHAIN REACTION
        </div>
        <div className="text-[10px] text-zinc-600 leading-none mt-0.5">XAUUSD</div>
      </div>
    </div>
  );
}

/** Login page large logo */
export function LogoLogin() {
  return (
    <div className="flex flex-col items-center gap-4">
      {/* Glowing ring behind icon */}
      <div className="relative">
        <div className="absolute inset-0 rounded-full bg-amber-500/10 blur-xl scale-150" />
        <div className="relative bg-zinc-900 border border-zinc-800 rounded-2xl p-4 shadow-2xl shadow-amber-900/20">
          <LogoMark size={64} />
        </div>
      </div>
      <div className="text-center space-y-1">
        <div className="text-3xl font-black text-amber-400 tracking-tighter">
          CHAIN REACTION
        </div>
        <div className="text-sm font-bold text-white tracking-widest">
          TRADING ADVISOR
        </div>
        <div className="text-xs text-zinc-500 tracking-widest uppercase">
          XAUUSD · Daily Deploy · v4.0 OVERLORD
        </div>
      </div>
    </div>
  );
}
