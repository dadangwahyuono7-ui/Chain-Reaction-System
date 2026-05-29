import { cn } from "@/lib/utils";

interface LogoProps {
  size?: number;
  className?: string;
}

/** Mark minimalis — 3 node menaik terhubung (CMP→VR→CF chain). Clean institutional. */
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
      <rect x="1" y="1" width="30" height="30" rx="8" fill="#0e1420" stroke="#243049" strokeWidth="1" />
      {/* chain line */}
      <path d="M8 22 L16 16 L24 10" stroke="#4f7cff" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" strokeOpacity="0.65" />
      {/* node 1 (CMP) */}
      <circle cx="8" cy="22" r="2.6" fill="#1e293b" stroke="#4f7cff" strokeWidth="1.5" />
      {/* node 2 (VR) */}
      <circle cx="16" cy="16" r="2.6" fill="#1e293b" stroke="#4f7cff" strokeWidth="1.5" />
      {/* node 3 (CF) — accent terang */}
      <circle cx="24" cy="10" r="3.1" fill="#4f7cff" />
    </svg>
  );
}

/** Logo penuh: mark + wordmark mixed-case */
export function LogoFull({
  size = "md",
  className,
}: {
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const iconSize = size === "sm" ? 26 : size === "md" ? 38 : 58;
  const titleCls =
    size === "sm" ? "text-base" : size === "md" ? "text-2xl" : "text-4xl";
  const subCls =
    size === "sm" ? "text-[10px]" : size === "md" ? "text-[11px]" : "text-sm";

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <LogoMark size={iconSize} />
      <div className="leading-none">
        <div className={cn(titleCls, "font-semibold tracking-tight text-slate-100")}>
          Chain<span className="text-indigo-400">Reaction</span>
        </div>
        <div className={cn(subCls, "text-slate-500 tracking-wide mt-1 font-medium")}>
          XAUUSD · Daily Deploy
        </div>
      </div>
    </div>
  );
}

/** Sidebar compact logo */
export function LogoSidebar() {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark size={26} />
      <div className="leading-none">
        <div className="text-sm font-semibold tracking-tight text-slate-100">
          Chain<span className="text-indigo-400">Reaction</span>
        </div>
        <div className="text-[10px] text-slate-500 mt-1 tracking-wide">XAUUSD</div>
      </div>
    </div>
  );
}

/** Login page large logo */
export function LogoLogin() {
  return (
    <div className="flex flex-col items-center gap-5">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl shadow-black/40">
        <LogoMark size={60} />
      </div>
      <div className="text-center space-y-2">
        <div className="text-3xl font-semibold tracking-tight text-slate-100">
          Chain<span className="text-indigo-400">Reaction</span>
        </div>
        <div className="text-sm font-medium text-slate-300 tracking-wide">
          Trading Advisor
        </div>
        <div className="text-xs text-slate-600 tracking-wide">
          XAUUSD · Daily Deploy
        </div>
      </div>
    </div>
  );
}
