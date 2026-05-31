import { cn } from "@/lib/utils";

interface LogoProps {
  size?: number;
  className?: string;
}

/** Commander Dadang — Chain Reaction Logo
 *  Vivid purple ring + bright neon eyes + chain nodes
 *  High contrast for dark backgrounds
 */
export function LogoMark({ size = 32, className }: LogoProps) {
  return (
    <div className={cn("relative overflow-hidden rounded-[14px] dp-logo-container border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.2)] bg-[#0f172a]", className)} style={{ width: size, height: size }}>
      <img src="/logo.png" alt="Chain Reaction Logo" className="w-full h-full object-cover" />
      <div className="dp-logo-sweep" />
    </div>
  );
}

/** Logo penuh: mark + wordmark */
export function LogoFull({ size = "md", className }: { size?: "sm"|"md"|"lg"; className?: string }) {
  const iconSize = size === "sm" ? 30 : size === "md" ? 44 : 68;
  const titleCls = size === "sm" ? "text-base" : size === "md" ? "text-2xl" : "text-4xl";
  const subCls   = size === "sm" ? "text-[10px]" : size === "md" ? "text-[11px]" : "text-sm";
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <LogoMark size={iconSize} />
      <div className="leading-none">
        <div className={cn(titleCls, "font-semibold tracking-tight text-slate-100")}>
          Chain<span className="text-purple-400">Reaction</span>
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
      <LogoMark size={36} className="shrink-0" />
      <div className="leading-none">
        <div className="text-sm font-semibold tracking-tight text-slate-100">
          Chain<span className="text-emerald-400">Reaction</span>
        </div>
        <div className="text-[10px] text-emerald-400/60 mt-0.5 tracking-wide font-medium">Commander Dadang</div>
      </div>
    </div>
  );
}

/** Login page large logo */
export function LogoLogin() {
  return (
    <div className="flex flex-col items-center gap-5">
      <LogoMark size={130} className="drop-shadow-2xl" />
      <div className="text-center space-y-2">
        <div className="text-3xl font-bold tracking-tight text-slate-100">
          Chain<span className="text-emerald-400">Reaction</span>
        </div>
        <div className="text-sm font-medium text-emerald-300/80 tracking-wide">
          Commander Dadang · AI Advisor
        </div>
        <div className="text-xs text-slate-600 tracking-wide">
          XAUUSD · Daily Deploy System
        </div>
      </div>
    </div>
  );
}
