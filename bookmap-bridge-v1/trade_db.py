"""
Trade database - bookmap-bridge auto-execution (DEMO account).

Every ENTRY and EXIT the MT5 executor makes gets logged here. This is the
"database" Dadang wants: a record to validate whether the Chain Reaction +
order flow doctrine actually produces good signals in practice, not just a
trade journal for its own sake.

SQLite, single file (trades.db), zero external deps.
"""

import os
import sqlite3
import time
from typing import Any, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trades.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction TEXT NOT NULL,
            signal_type TEXT,
            signal_tf TEXT,
            grade TEXT,
            reason TEXT,
            entry_time REAL NOT NULL,
            entry_price REAL NOT NULL,
            sl REAL,
            tp REAL,
            lot REAL,
            mt5_ticket INTEGER,
            status TEXT NOT NULL DEFAULT 'OPEN',
            exit_time REAL,
            exit_price REAL,
            exit_reason TEXT,
            pnl REAL
        )
    """)
    conn.commit()
    conn.close()


def log_entry(direction: str, signal_type: str, signal_tf: str, grade: str, reason: str,
              entry_price: float, sl: float, tp: float, lot: float, mt5_ticket: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("""
        INSERT INTO trades (direction, signal_type, signal_tf, grade, reason, entry_time,
                             entry_price, sl, tp, lot, mt5_ticket, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
    """, (direction, signal_type, signal_tf, grade, reason, time.time(),
          entry_price, sl, tp, lot, mt5_ticket))
    conn.commit()
    trade_id = cur.lastrowid
    conn.close()
    return trade_id


def log_exit(mt5_ticket: int, exit_price: float, exit_reason: str, pnl: float):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE trades SET status='CLOSED', exit_time=?, exit_price=?, exit_reason=?, pnl=?
        WHERE mt5_ticket=? AND status='OPEN'
    """, (time.time(), exit_price, exit_reason, pnl, mt5_ticket))
    conn.commit()
    conn.close()


def get_recent_trades(limit: int = 10) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM trades ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    
    trades = []
    for r in rows:
        t = dict(r)
        entry_t = t.get("entry_time") or time.time()
        exit_t = t.get("exit_time") or time.time()
        dur_sec = max(0, int(exit_t - entry_t)) if t.get("status") == "CLOSED" else max(0, int(time.time() - entry_t))
        hrs, rem = divmod(dur_sec, 3600)
        mins, secs = divmod(rem, 60)
        dur_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        
        entry_p = t.get("entry_price") or 0.0
        exit_p = t.get("exit_price") or entry_p
        dir_mult = 1.0 if t.get("direction") == "BUY" else -1.0
        pts = (exit_p - entry_p) * dir_mult if t.get("status") == "CLOSED" else 0.0
        pts_str = f"{pts:+.1f}" if t.get("status") == "CLOSED" else "-"
        
        sl_p = t.get("sl") or 0.0
        risk = abs(entry_p - sl_p) if sl_p > 0 else 1.0
        reward = abs(exit_p - entry_p)
        rr_ratio = round(reward / risk, 1) if risk > 0 else 1.0
        
        time_struct = time.localtime(entry_t)
        time_str = time.strftime("%H:%M", time_struct)
        
        trades.append({
            "id": t["id"],
            "time": time_str,
            "pair": "XAUUSD",
            "direction": t.get("direction", "BUY"),
            "entry": round(entry_p, 2),
            "exit": round(exit_p, 2) if t.get("status") == "CLOSED" else "-",
            "points": pts_str,
            "rr": f"1:{rr_ratio}",
            "duration": dur_str,
            "reason": t.get("reason") or t.get("exit_reason") or "Chain Reaction Signal",
            "status": t.get("status", "OPEN")
        })
    return trades


def get_stats() -> Dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM trades WHERE status='CLOSED'").fetchall()
    conn.close()
    closed = [dict(r) for r in rows]
    if not closed:
        return {
            "total": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "total_pnl": 0.0, "total_points": 0.0, "avg_rr": "1:1.5",
            "max_dd": 0.0, "balance": 10000.00, "equity": 10000.00
        }
    wins = sum(1 for t in closed if (t["pnl"] or 0) > 0)
    losses = len(closed) - wins
    total_pnl = sum(t["pnl"] or 0 for t in closed)
    
    total_pts = 0.0
    rr_list = []
    peak_pnl = 0.0
    max_dd = 0.0
    running_pnl = 0.0
    
    for t in closed:
        pnl = t.get("pnl") or 0.0
        running_pnl += pnl
        if running_pnl > peak_pnl:
            peak_pnl = running_pnl
        dd = peak_pnl - running_pnl
        if dd > max_dd:
            max_dd = dd
            
        entry_p = t.get("entry_price") or 0.0
        exit_p = t.get("exit_price") or entry_p
        dir_mult = 1.0 if t.get("direction") == "BUY" else -1.0
        total_pts += (exit_p - entry_p) * dir_mult
        
        sl_p = t.get("sl") or 0.0
        risk = abs(entry_p - sl_p) if sl_p > 0 else 1.0
        reward = abs(exit_p - entry_p)
        if risk > 0:
            rr_list.append(reward / risk)
            
    avg_rr_val = round(sum(rr_list) / len(rr_list), 1) if rr_list else 1.5
    base_balance = 10000.00
    current_balance = round(base_balance + total_pnl, 2)
    
    return {
        "total": len(closed),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(closed) * 100, 1),
        "total_pnl": round(total_pnl, 2),
        "total_points": round(total_pts, 1),
        "avg_rr": f"1:{avg_rr_val}",
        "max_dd": round(-abs(max_dd), 1),
        "balance": current_balance,
        "equity": current_balance,
    }

