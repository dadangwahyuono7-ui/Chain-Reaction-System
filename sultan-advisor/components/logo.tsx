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
  const s = size;
  return (
    <svg
      width={s} height={s}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        {/* Vivid purple ring gradient */}
        <linearGradient id="cr-ring" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#a855f7"/>
          <stop offset="50%" stopColor="#c084fc"/>
          <stop offset="100%" stopColor="#7c3aed"/>
        </linearGradient>
        {/* Background fill — brighter purple so it stands out on dark sidebar */}
        <radialGradient id="cr-bg" cx="50%" cy="45%" r="60%">
          <stop offset="0%" stopColor="#3b1f7a"/>
          <stop offset="100%" stopColor="#1e0f4a"/>
        </radialGradient>
        {/* Hood fill */}
        <linearGradient id="cr-hood" x1="24" y1="4" x2="24" y2="38" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#4c2a9e"/>
          <stop offset="100%" stopColor="#1e0f4a"/>
        </linearGradient>
        {/* Visor */}
        <linearGradient id="cr-visor" x1="17" y1="17" x2="31" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#2a1660"/>
          <stop offset="100%" stopColor="#160c38"/>
        </linearGradient>
        {/* Eye glow */}
        <filter id="cr-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="1.2" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        {/* Outer glow for entire logo */}
        <filter id="cr-outer-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="1.5" result="blur"/>
          <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>

      {/* Outer bright ring — high contrast purple, thick & vivid */}
      <circle cx="24" cy="24" r="22" fill="url(#cr-bg)" stroke="url(#cr-ring)" strokeWidth="3.5"/>

      {/* Inner purple tint */}
      <circle cx="24" cy="20" r="14" fill="#7c3aed" opacity="0.08"/>

      {/* Hood body */}
      <path
        d="M24 5 C13 8 9 16 9 25 L9 31 C9 31 14 29 18 29 L18 37 C18 39 20.5 40 24 40 C27.5 40 30 39 30 37 L30 29 C34 29 39 31 39 31 L39 25 C39 16 35 8 24 5Z"
        fill="url(#cr-hood)"
        stroke="#4c1d95"
        strokeWidth="0.7"
      />

      {/* Hood center ridge */}
      <path d="M22 9 C23 6.5 24 5.5 24 5.5 C24 5.5 25 6.5 26 9"
        stroke="#6d28d9" strokeWidth="1" strokeLinecap="round" fill="none"/>

      {/* Shoulder plates */}
      <path d="M9 27 C6 26 5.5 29 7 32 L9 31Z" fill="#1e1040" stroke="#4c1d95" strokeWidth="0.5"/>
      <path d="M39 27 C42 26 42.5 29 41 32 L39 31Z" fill="#1e1040" stroke="#4c1d95" strokeWidth="0.5"/>

      {/* Face visor plate */}
      <path
        d="M17 20.5 C17 17 20 15 24 15 C28 15 31 17 31 20.5 L31 28.5 C31 32 28 34 24 34 C20 34 17 32 17 28.5Z"
        fill="url(#cr-visor)"
        stroke="#5b21b6"
        strokeWidth="0.7"
      />
      {/* Visor horizontal lines (tactical look) */}
      <line x1="17.5" y1="21.5" x2="30.5" y2="21.5" stroke="#2e1065" strokeWidth="0.4" opacity="0.8"/>
      <line x1="17.5" y1="25" x2="30.5" y2="25" stroke="#2e1065" strokeWidth="0.4" opacity="0.6"/>

      {/* LEFT EYE — vivid neon purple */}
      <ellipse cx="20.5" cy="22" rx="3" ry="1.8" fill="#8b5cf6" filter="url(#cr-glow)" opacity="0.7"/>
      <ellipse cx="20.5" cy="22" rx="2" ry="1.2" fill="#a855f7"/>
      <ellipse cx="20.5" cy="22" rx="1" ry="0.65" fill="#ddd6fe"/>
      <ellipse cx="20" cy="21.7" rx="0.35" ry="0.25" fill="white" opacity="0.9"/>

      {/* RIGHT EYE — vivid neon purple */}
      <ellipse cx="27.5" cy="22" rx="3" ry="1.8" fill="#8b5cf6" filter="url(#cr-glow)" opacity="0.7"/>
      <ellipse cx="27.5" cy="22" rx="2" ry="1.2" fill="#a855f7"/>
      <ellipse cx="27.5" cy="22" rx="1" ry="0.65" fill="#ddd6fe"/>
      <ellipse cx="27" cy="21.7" rx="0.35" ry="0.25" fill="white" opacity="0.9"/>

      {/* AI label */}
      <rect x="20.5" y="27" width="7" height="4.5" rx="1" fill="#1e1040" stroke="#4c1d95" strokeWidth="0.4"/>
      <text x="24" y="30.5" textAnchor="middle" fontSize="3.8" fontWeight="900"
        fontFamily="monospace" fill="#c084fc" letterSpacing="0.5">AI</text>

      {/* CMP→VR→CF chain nodes at bottom — vivid */}
      <circle cx="16.5" cy="42.5" r="1.8" fill="#7c3aed" opacity="0.9"/>
      <circle cx="24"   cy="43.5" r="2.2" fill="#a855f7" filter="url(#cr-glow)"/>
      <circle cx="31.5" cy="42.5" r="1.8" fill="#7c3aed" opacity="0.9"/>
      <line x1="18.3" y1="42.8" x2="21.8" y2="43.3" stroke="#c084fc" strokeWidth="1" opacity="0.8"/>
      <line x1="26.2" y1="43.3" x2="29.7" y2="42.8" stroke="#c084fc" strokeWidth="1" opacity="0.8"/>

      {/* Circuit sparks L */}
      <path d="M10 19 L7.5 19 L7.5 15.5" stroke="#7c3aed" strokeWidth="0.8" fill="none" opacity="0.7"/>
      <circle cx="7.5" cy="15.5" r="1" fill="#a855f7" opacity="0.9"/>
      {/* Circuit sparks R */}
      <path d="M38 19 L40.5 19 L40.5 15.5" stroke="#7c3aed" strokeWidth="0.8" fill="none" opacity="0.7"/>
      <circle cx="40.5" cy="15.5" r="1" fill="#a855f7" opacity="0.9"/>

      {/* Top glow dot on ring */}
      <circle cx="24" cy="1.5" r="1.2" fill="#c084fc" opacity="0.8"/>
    </svg>
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
      {/* Glow wrapper — makes logo pop on dark sidebar */}
      <div className="relative shrink-0">
        <div className="absolute -inset-1 rounded-full blur-lg opacity-80"
          style={{ background: "radial-gradient(circle, rgba(192,132,252,0.6), transparent 70%)" }}/>
        <div className="absolute inset-0 rounded-full blur-sm opacity-40"
          style={{ background: "rgba(168,85,247,0.8)" }}/>
        <LogoMark size={36} className="relative drop-shadow-lg" />
      </div>
      <div className="leading-none">
        <div className="text-sm font-semibold tracking-tight text-slate-100">
          Chain<span className="text-purple-400">Reaction</span>
        </div>
        <div className="text-[10px] text-purple-400/60 mt-0.5 tracking-wide font-medium">Commander Dadang</div>
      </div>
    </div>
  );
}

/** Login page large logo */
export function LogoLogin() {
  return (
    <div className="flex flex-col items-center gap-5">
      <div className="relative">
        {/* Layered glow */}
        <div className="absolute inset-0 rounded-full blur-3xl opacity-70 scale-125"
          style={{ background: "radial-gradient(circle, rgba(168,85,247,0.5), transparent 70%)" }}/>
        <div className="absolute inset-0 rounded-full blur-xl opacity-50 scale-110"
          style={{ background: "radial-gradient(circle, rgba(124,58,237,0.8), transparent 70%)" }}/>
        <LogoMark size={130} className="relative drop-shadow-2xl" />
      </div>
      <div className="text-center space-y-2">
        <div className="text-3xl font-bold tracking-tight text-slate-100">
          Chain<span className="text-purple-400">Reaction</span>
        </div>
        <div className="text-sm font-medium text-purple-300/80 tracking-wide">
          Commander Dadang · AI Advisor
        </div>
        <div className="text-xs text-slate-600 tracking-wide">
          XAUUSD · Daily Deploy System
        </div>
      </div>
    </div>
  );
}
