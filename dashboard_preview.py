#!/usr/bin/env python3
"""
CHAIN REACTION v4.0 — DASHBOARD IDEAS PREVIEW
=============================================
Data dummy — tanpa MT5, tanpa engine.
Run : python dashboard_preview.py
Quit: Ctrl+C
"""

import time, math, random
from datetime import datetime
from rich.console import Console, Group as RichGroup
from rich.layout  import Layout
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text
from rich.align   import Align
from rich.live    import Live
from rich.rule    import Rule
from rich         import box as rich_box

console = Console()

# ── PALETTE ────────────────────────────────────────────────────────────────────
MG = "bright_green";  CC = "bright_cyan";  RD = "bright_red";  GD = "gold1"
DG = "grey62";        BG = "bold bright_green";  BC = "bold bright_cyan"
BR = "bold bright_red";  BY = "bold gold1"

_MCHARS = "01アイウエカキクサシスセ▓▒░█◆◈※#@$%ABCDEFabcdef01010110"
_BLOCKS = "▁▂▃▄▅▆▇█"

# ── HELPERS ────────────────────────────────────────────────────────────────────
def _bar(filled, total, fill_color=MG, empty_color="grey19", fill_char="█", empty_char="░"):
    f = max(0, min(int(filled), total))
    return f"[{fill_color}]{fill_char*f}[/][{empty_color}]{empty_char*(total-f)}[/]"

def _htag(n=6):
    return "0x" + "".join(random.choices("0123456789ABCDEF", k=n))

def _rain(width, frame):
    random.seed(frame * 31337 + width)
    out = ""
    for _ in range(width):
        c = random.choice(_MCHARS)
        r = random.random()
        if r < 0.07:   out += f"[bold bright_green]{c}[/]"
        elif r < 0.35: out += f"[green]{c}[/]"
        else:          out += f"[dim green]{c}[/]"
    random.seed()
    return out

def _T(label, addr=None):
    a = addr or _htag()
    return f"[{BC}][ {label} ][/{BC}]  [{DG}]{a}[/{DG}]"

# ── DUMMY DATA ──────────────────────────────────────────────────────────────────
DIRECTION = "SELL"
TF_STATES = {
    "MN1": {"cmp":"SELL","vr":False,"cf":False,"aligned":True,  "sup":3200.0,"res":4800.0},
    "W1":  {"cmp":"SELL","vr":False,"cf":False,"aligned":True,  "sup":4200.0,"res":4700.0},
    "D1":  {"cmp":"SELL","vr":False,"cf":False,"aligned":True,  "sup":4450.0,"res":4600.0},
    "H4":  {"cmp":"SELL","vr":False,"cf":False,"aligned":True,  "sup":4476.0,"res":4543.0},
    "H1":  {"cmp":"SELL","vr":True, "cf":False,"aligned":True,  "sup":4480.0,"res":4520.0},
    "M30": {"cmp":"SELL","vr":False,"cf":False,"aligned":True,  "sup":4485.0,"res":4510.0},
    "M15": {"cmp":"BUY", "vr":True, "cf":False,"aligned":False, "sup":4488.0,"res":4505.0},
    "M5":  {"cmp":"SELL","vr":False,"cf":True, "aligned":False, "sup":4490.0,"res":4500.0},
}
DUMMY_POSITIONS = [
    {"dir":"SELL","lot":0.01,"pnl":8.29,"pips":82.9},
    {"dir":"SELL","lot":0.01,"pnl":6.52,"pips":65.2},
    {"dir":"SELL","lot":0.01,"pnl":8.08,"pips":80.8},
    {"dir":"SELL","lot":0.01,"pnl":8.14,"pips":81.4},
]

# Seed equity history
random.seed(42)
_EQ_BASE = 514.0
_EQ_HIST = [_EQ_BASE]
for _ in range(55):
    _EQ_HIST.append(max(490.0, _EQ_HIST[-1] + random.uniform(-1.2, 2.2)))
random.seed()


# ══════════════════════════════════════════════════════════════════════════════
#  PANEL 1 — SIGNAL HEATMAP
# ══════════════════════════════════════════════════════════════════════════════
def build_heatmap(frame):
    BLINK = frame % 2 == 0

    t = Table(
        box=rich_box.SIMPLE_HEAD, expand=True, show_edge=False,
        padding=(0, 1), header_style=f"bold {CC} on grey11",
    )
    t.add_column("TF",    justify="center", width=6)
    t.add_column("CMP",   justify="center", width=12)
    t.add_column("VR",    justify="center", width=12)
    t.add_column("CF",    justify="center", width=12)
    t.add_column("⊕",     justify="center", width=4)

    for tf, st in TF_STATES.items():
        is_master = (tf == "H4")

        # CMP cell
        if st["cmp"] == DIRECTION:
            cmp_cell = f"[bold white on dark_green] ▣ {st['cmp']}  [/]"
        elif st["cmp"] == "WAIT":
            cmp_cell = f"[{DG}]  ──────  [/]"
        else:
            cmp_cell = f"[bold white on dark_red] ✗ {st['cmp']}  [/]"

        # VR cell
        if st["vr"]:
            sym = "⚡ VR ⚡" if BLINK else "·  VR  ·"
            vr_cell = f"[bold white on dark_blue] {sym} [/]"
        else:
            vr_cell = f"[{DG}]  ──────  [/]"

        # CF cell
        if st["cf"]:
            sym = "◉ CF ◉" if BLINK else "● CF ●"
            cf_cell = f"[bold white on dark_green] {sym} [/]"
        else:
            cf_cell = f"[{DG}]  ──────  [/]"

        # Align
        alg = (f"[{MG}]▼[/]" if DIRECTION == "SELL" else f"[{MG}]▲[/]") if st["aligned"] else f"[{RD}]✗[/]"

        row_style = "on grey15" if is_master else ""
        tf_lbl = f"[{BY}]{tf}★[/]" if is_master else f"[{CC}]{tf}[/]"

        t.add_row(tf_lbl, cmp_cell, vr_cell, cf_cell, alg, style=row_style)

    # Summary row
    aligned_n = sum(1 for s in TF_STATES.values() if s["aligned"])
    sync_bar  = _bar(aligned_n, 8, fill_color=MG if aligned_n >= 6 else GD, empty_color="grey19", fill_char="▪", empty_char="·")
    t.add_row(
        f"[{DG}]SYNC[/]",
        f"[{DG}]──────────[/]",
        f"[{DG}]──────────[/]",
        f"[{DG}]──────────[/]",
        f"[{MG}]{aligned_n}/8[/]",
    )

    return Panel(t, title=_T("SIGNAL.HEATMAP"), border_style="magenta", padding=(0, 0))


# ══════════════════════════════════════════════════════════════════════════════
#  PANEL 2 — NEURAL SIGNAL FLOW
# ══════════════════════════════════════════════════════════════════════════════
def build_neural_flow(frame):
    BLINK = frame % 2 == 0

    def node(label, active, bg, fire=False):
        if fire:
            sym = "⚡" if BLINK else "◉"
            return f"[bold white on {bg}] {sym} {label} {sym} [/]"
        if active:
            sym = "◉" if BLINK else "●"
            return f"[bold white on {bg}] {sym} {label} [/]"
        return f"[{DG}][ ○ {label} ][/]"

    def pipe(active, color=MG):
        return f"[{color}] ══► [/]" if active else f"[{DG}] ──► [/]"

    macro_ok = all(TF_STATES[t]["cmp"] == DIRECTION for t in ["MN1","W1","D1"])
    h4_ok    = TF_STATES["H4"]["cmp"]  == DIRECTION
    h1_ok    = TF_STATES["H1"]["cmp"]  == DIRECTION or TF_STATES["H1"]["vr"]
    m30_ok   = TF_STATES["M30"]["cmp"] == DIRECTION
    m15_vr   = TF_STATES["M15"]["vr"]
    m5_cf    = TF_STATES["M5"]["cf"]

    strength = sum([macro_ok, h4_ok, m30_ok, m15_vr, m5_cf])
    str_col  = MG if strength >= 4 else GD if strength >= 2 else RD
    str_bar  = _bar(strength * 2, 10, fill_color=str_col, empty_color="grey19", fill_char="▰", empty_char="▱")

    # Status tags
    def tag(ok, yes_txt, no_txt):
        return f"[{MG}]{yes_txt}[/]" if ok else f"[{DG}]{no_txt}[/]"

    cf_label = (
        f"[blink bold bright_green] ⚡ CF::FIRE ⚡ [/]" if BLINK and m5_cf
        else f"[bold bright_green] ◉ CF READY  [/]" if m5_cf
        else f"[{DG}]standby...[/]"
    )

    lines = [
        Text.from_markup(f"  [{DG}]{'─'*46}[/]"),
        Text.from_markup(
            f"  {node('MACRO', macro_ok, 'dark_green')}"
            f"{pipe(macro_ok, GD)}"
            f"{node('H4 ★ MASTER', h4_ok, 'dark_goldenrod')}"
            f"  {tag(h4_ok, f'DIR::{DIRECTION} ▼', 'WAIT...')}"
        ),
        Text.from_markup(f"  [{DG}]{'─'*46}[/]"),
        Text(""),
        Text.from_markup(
            f"  [{DG}]           ↓[/]\n"
            f"  {node('H1', h1_ok, 'dark_blue')}"
            f"{pipe(h1_ok)}"
            f"{node('M30', m30_ok, 'dark_green')}"
            f"  {tag(m30_ok, 'CMP locked ✅', 'waiting M30...')}"
        ),
        Text(""),
        Text.from_markup(
            f"  [{DG}]                    ↓[/]\n"
            f"  {node('M15', m15_vr, 'dark_blue')}"
            f"{pipe(m15_vr, CC)}"
            f"{node('M5', m5_cf, 'dark_green', fire=m5_cf)}"
            f"  {cf_label}"
        ),
        Text(""),
        Text.from_markup(f"  [{DG}]{'─'*46}[/]"),
        Text.from_markup(
            f"  [{DG}]CHAIN STRENGTH[/]  {str_bar}  [{str_col}]{strength}/5[/]"
            f"   [{DG}]ALIGN[/] [{MG}]{sum(s['aligned'] for s in TF_STATES.values())}/8[/]"
        ),
    ]

    border = (MG if BLINK else "green") if m5_cf else (CC if m15_vr else DG)
    return Panel(RichGroup(*lines), title=_T("NEURAL.FLOW"), border_style=border, padding=(0, 1))


# ══════════════════════════════════════════════════════════════════════════════
#  PANEL 3 — EQUITY CURVE  ← yang disukai bro
# ══════════════════════════════════════════════════════════════════════════════
def build_equity_curve(frame):
    # Animate live equity
    live_eq = _EQ_HIST[-1] + math.sin(frame * 0.22) * 1.5 + math.cos(frame * 0.09) * 0.9

    hist  = _EQ_HIST[-50:] + [live_eq]
    mn    = min(hist)
    mx_h  = max(hist)
    rng   = mx_h - mn if mx_h != mn else 1.0
    ROWS  = 6

    # ASCII chart
    chart = []
    for row in range(ROWS - 1, -1, -1):
        lo   = mn + rng * row / ROWS
        hi   = mn + rng * (row + 1) / ROWS
        line = ""
        for i, val in enumerate(hist):
            is_last = (i == len(hist) - 1)
            if val >= hi:
                ch = f"[bold {MG}]█[/]" if is_last else f"[{MG}]█[/]"
            elif val >= lo:
                frac = (val - lo) / (rng / ROWS)
                blk  = _BLOCKS[min(int(frac * 8), 7)]
                ch   = f"[bold {MG}]{blk}[/]" if is_last else f"[green]{blk}[/]"
            else:
                ch   = f"[grey19]░[/]"
            line += ch
        # Y-axis labels
        if row == ROWS - 1: y_lbl = f" [{DG}]{mx_h:>7.2f}[/]"
        elif row == ROWS//2: y_lbl = f" [{DG}]{(mn+rng*0.5):>7.2f}[/]"
        elif row == 0:       y_lbl = f" [{DG}]{mn:>7.2f}[/]"
        else:                y_lbl = ""
        chart.append(Text.from_markup(line + y_lbl))

    # X-axis
    chart.append(Text.from_markup(
        f"[{DG}]{'─' * len(hist)}[/]"
        f"  [{DG}]← {len(hist)} candles[/]"
    ))

    pnl     = live_eq - _EQ_BASE
    pnl_col = MG if pnl >= 0 else RD
    eq_col  = MG if live_eq >= _EQ_BASE else RD
    peak_dd = mx_h - live_eq

    # Stats bar
    stats_t = Table(box=None, expand=True, show_header=False, padding=(0, 2))
    stats_t.add_column("", justify="left",  ratio=1)
    stats_t.add_column("", justify="left",  ratio=1)
    stats_t.add_column("", justify="left",  ratio=1)
    stats_t.add_column("", justify="left",  ratio=1)
    stats_t.add_row(
        Text.from_markup(f"[{DG}]EQ[/]  [{eq_col}]{live_eq:.2f}[/]"),
        Text.from_markup(f"[{DG}]PnL[/] [{pnl_col}]{'+' if pnl>=0 else ''}{pnl:.2f}[/]"),
        Text.from_markup(f"[{DG}]PEAK[/] [{MG}]{mx_h:.2f}[/]"),
        Text.from_markup(f"[{DG}]DD[/]  [{RD}]{peak_dd:.2f}[/]"),
    )

    # PnL progress bar
    pnl_fill = min(int(abs(pnl) / 30 * 44), 44)
    pnl_bar  = _bar(pnl_fill, 44, fill_color=pnl_col, empty_color="grey19", fill_char="▓", empty_char="░")

    content = RichGroup(*chart, Text(""), stats_t, Text.from_markup(f"  {pnl_bar}"))
    border  = (MG if frame % 2 == 0 else "green") if pnl >= 0 else RD
    return Panel(content, title=_T("EQUITY.CURVE"), border_style=border, padding=(0, 0))


# ══════════════════════════════════════════════════════════════════════════════
#  PANEL 4 — P&L OSCILLOSCOPE  ← yang disukai bro
# ══════════════════════════════════════════════════════════════════════════════
def build_oscilloscope(frame):
    WIDTH  = 48
    ROWS   = 6
    total  = sum(p["pnl"] for p in DUMMY_POSITIONS)
    tot_col = MG if total > 0 else RD

    # Waveform — composite sine
    wave = []
    for x in range(WIDTH):
        t   = x / WIDTH * 6 * math.pi + frame * 0.28
        val = (math.sin(t) * 0.45
               + math.sin(t * 1.9 + 0.8) * 0.30
               + math.cos(t * 0.6 + 1.2) * 0.25)
        lvl = int((val + 1) / 2 * (ROWS * 8 - 1))
        wave.append(max(0, min(ROWS * 8 - 1, lvl)))

    # Draw rows top → bottom
    osc_lines = []
    mid_row   = ROWS // 2
    for row in range(ROWS - 1, -1, -1):
        line = ""
        for lvl in wave:
            row_lvl = lvl // 8
            sub_lvl = lvl % 8
            if row_lvl > row:
                line += f"[{tot_col}]█[/]"
            elif row_lvl == row:
                line += f"[green]{_BLOCKS[sub_lvl]}[/]"
            else:
                # center line
                if row == mid_row:
                    line += f"[grey35]─[/]"
                else:
                    line += f"[grey19] [/]"
        # center marker
        suffix = f"  [{DG}]── 0 ──[/]" if row == mid_row else ""
        osc_lines.append(Text.from_markup(f" {line}{suffix}"))

    # Position table
    pos_t = Table(box=None, expand=True, show_header=False, padding=(0, 1), show_edge=False)
    pos_t.add_column("",  width=5,  justify="center")
    pos_t.add_column("",  width=5,  justify="center")
    pos_t.add_column("",  width=7,  justify="right")
    pos_t.add_column("",  width=8,  justify="right")
    pos_t.add_column("",  ratio=1)

    max_pnl = max(p["pnl"] for p in DUMMY_POSITIONS) if DUMMY_POSITIONS else 1
    for p in DUMMY_POSITIONS:
        d_col   = MG if p["dir"] == DIRECTION else RD
        fill    = int(p["pnl"] / max_pnl * 10)
        mini_b  = _bar(fill, 10, fill_color=MG, empty_color="grey19", fill_char="▪", empty_char="·")
        pos_t.add_row(
            f"[bold white on dark_green] {p['dir'][:1]} [/]",
            f"[white]{p['lot']}L[/]",
            f"[{MG}]+{p['pips']:.1f}p[/]",
            f"[{MG}]+{p['pnl']:.2f}$[/]",
            mini_b,
        )

    # Separator + total
    sep  = Text.from_markup(f" [{DG}]{'─'*42}[/]")
    tot_bar   = _bar(int(total / (max_pnl * len(DUMMY_POSITIONS)) * 44), 44,
                     fill_color=tot_col, empty_color="grey19", fill_char="█", empty_char="░")
    total_txt = Text.from_markup(
        f"  [{DG}]TOTAL P&L[/]  [{tot_col}]{'+'if total>=0 else ''}{total:.2f}$[/]"
        f"  [{tot_col}]{'▲' if total >= 0 else '▼'}[/]"
    )

    border = (MG if frame % 2 == 0 else "green") if total > 0 else RD
    content = RichGroup(*osc_lines, Text(""), pos_t, sep, total_txt, Text.from_markup(f"  {tot_bar}"))
    return Panel(content, title=_T("PnL.OSCILLOSCOPE"), border_style=border, padding=(0, 0))


# ══════════════════════════════════════════════════════════════════════════════
#  LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
def make_layout():
    layout = Layout()
    layout.split_column(
        Layout(name="header",   size=4),
        Layout(name="top_row",  size=16),
        Layout(name="bot_row",  size=18),
        Layout(name="footer",   size=3),
    )
    layout["top_row"].split_row(
        Layout(name="heatmap", ratio=5),
        Layout(name="neural",  ratio=5),
    )
    layout["bot_row"].split_row(
        Layout(name="equity",  ratio=5),
        Layout(name="oscillo", ratio=5),
    )
    return layout


def update_preview(layout, frame):
    BLINK = frame % 2 == 0
    spin  = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"][frame % 10]

    # ── Header ────────────────────────────────────────────────────────────────
    rain = _rain(55, frame)
    h1 = Text.assemble(
        (f" {spin} ", f"bold {MG}"),
        ("CHAIN_REACTION::", f"bold {MG}"),
        ("OVERLORD_v4.0 ", BC),
        (" ── ", DG),
        ("CMDR::DADANG  ", BY),
        (" ── ", DG),
        ("XAUUSD  ", "white"),
        ("4487.84", BG),
        (" / ", DG),
        ("4487.92", BR),
        ("  ──  ", DG),
        (datetime.now().strftime("%H:%M:%S"), BC),
        (" WIB", "grey74"),
        ("  ── ", DG),
        ("[ PREVIEW MODE — DATA DUMMY ]", f"bold {RD}" if BLINK else RD),
    )
    layout["header"].update(Panel(
        RichGroup(Align.center(h1), Text.from_markup(f"  {rain}")),
        style=f"bold {MG}", padding=(0, 0),
    ))

    # ── Panels ────────────────────────────────────────────────────────────────
    layout["heatmap"].update(build_heatmap(frame))
    layout["neural"].update(build_neural_flow(frame))
    layout["equity"].update(build_equity_curve(frame))
    layout["oscillo"].update(build_oscilloscope(frame))

    # ── Footer ────────────────────────────────────────────────────────────────
    layout["footer"].update(Panel(
        Text.from_markup(f"  {_rain(90, frame+5555)}"),
        border_style="green", padding=(0, 0),
    ))


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    layout = make_layout()
    print("\033[?25l", end="", flush=True)  # hide cursor
    try:
        with Live(layout, refresh_per_second=5, screen=True) as live:
            frame = 0
            while True:
                update_preview(layout, frame)
                live.update(layout)
                time.sleep(0.2)
                frame += 1
    except KeyboardInterrupt:
        pass
    finally:
        print("\033[?25h", end="", flush=True)
        console.print(f"\n[{MG}]>> PREVIEW CLOSED. main.py tidak tersentuh.[/]")
