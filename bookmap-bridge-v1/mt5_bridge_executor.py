"""
MT5 Executor - bookmap-bridge auto-entry (DEMO account).

Dadang: "jangan eksekusi sendiri, lo harus buat mt5 gw entri sesuai signal
karena akan kita jadikan database bro." Every Chain Reaction entry/exit that
cr_master_engine.py fires gets mirrored automatically into MT5 on the DEMO
account, so a real dataset builds up validating the doctrine.

Isolated from the production engine (engine/executor.py, magic_number=2026)
via a DIFFERENT magic number (2027) and comment prefix ("BMR_") - so
positions never mix between the two systems on the same account.

SL PHILOSOPHY (rewritten 2026-08-07, replaces the earlier "technical zone as
SL" approach): Dadang: "gw tidak pernah pakai SL, tapi sistem cut loss pasang
setelah M30 flip, misal M5 gagal - dan gw pasang SL ketika sudah running,
karena SL sering menjebak trader." The REAL cut-loss is doctrine-driven:
get_position_status() (cmp_engine.py) fires EXIT when M5 fails / M30 flips,
which close_position() below executes - that's what "M30 flip -> cut loss"
means in code. The SL price placed ON the broker order is NOT that exit
mechanism - it's a pure financial backstop capped at RISK_PERCENT of balance,
completely decoupled from any chart TF's level, wide enough that ordinary
noise/spoofing can't hunt it. First live trade with a tight M5-zone SL got
stopped in 6 seconds - exactly the "menjebak trader" problem being fixed here.
"""

import MetaTrader5 as mt5

MAGIC_NUMBER = 2027
COMMENT_PREFIX = "BMR"
SYMBOL = "XAUUSD"

FIXED_LOT = 0.02
MAX_LOT = 0.5
RISK_PERCENT = 2.5  # Dadang: "buat 2-3% dari modal aja" - picked the middle of that range
MIN_SL_DIST = 3.0   # USD floor - a technical SL tighter than this isn't trusted
                     # (this is exactly the M5-zone problem that got hunted in 6s -
                     # a WALL-based SL should comfortably clear this)
FALLBACK_SL_DIST = 1.5   # USD - only for TP fallback when tp_hint is unavailable (e.g. VR_SCALP)


def get_xauusd_price() -> float:
    """v37: MT5's own live XAUUSD bid - used to convert Bookmap's GCZ6
    futures price into MT5/XAUUSD scale for the (old) Chain Reaction
    dashboard's header, which was showing the raw unconverted GCZ6 number.
    Dadang: "harga yang di web harus ke konvert ke mt5 juga bro" - the
    Sultan dashboard already did this (WriteSultanStatus() converts on the
    MQL5 side), this brings the same fix to dashboard.html. Returns 0.0 if
    MT5 isn't connected/no tick yet (caller should treat that as "skip
    conversion this cycle", not a hard error)."""
    tick = mt5.symbol_info_tick(SYMBOL)
    return tick.bid if tick else 0.0


def connect() -> bool:
    if not mt5.initialize():
        print("[MT5Executor] MT5 belum jalan / gagal initialize - auto-exec OFF, monitor-only mode.")
        return False
    acc = mt5.account_info()
    if acc is None:
        print("[MT5Executor] MT5 connect tapi belum login - auto-exec OFF, monitor-only mode.")
        return False
    print(f"[MT5Executor] Connected: {acc.login} @ {acc.server} | "
          f"Balance {acc.balance:.2f} {acc.currency} | magic={MAGIC_NUMBER}")
    return True


def _catastrophic_sl_price(direction: str, price: float, lot: float) -> float:
    """Wide, purely financial backstop - the price at which THIS lot's loss
    equals RISK_PERCENT of balance. NOT tied to any chart TF zone (that's the
    whole point - a technical-zone SL is exactly what gets hunted). Used for
    CF/VR_SCALP entries, which have no robust technical level to lean on."""
    acc = mt5.account_info()
    sym = mt5.symbol_info(SYMBOL)
    if not acc or not sym or lot <= 0:
        dist = FALLBACK_SL_DIST
    else:
        risk_amount = acc.balance * RISK_PERCENT / 100.0
        tick_size = sym.trade_tick_size
        tick_value = sym.trade_tick_value
        value_per_price_unit = (tick_value / tick_size) if tick_size > 0 and tick_value > 0 else 0
        dist = (risk_amount / lot) / value_per_price_unit if value_per_price_unit > 0 else FALLBACK_SL_DIST

    dist = max(dist, MIN_SL_DIST)
    return round(price - dist if direction == "BUY" else price + dist, 2)


def _risk_based_lot_for_sl(price: float, sl: float) -> float:
    """Given a TRUSTED technical SL (e.g. wall invalidation - Dadang: "sl di
    bawah area wall itu juga ok", walls are real liquidity, not a tiny minor-
    SNR that gets hunted), size the lot so loss at that SL = RISK_PERCENT of
    balance - same $ risk target as the catastrophic backstop, just driven by
    a real technical level instead of a synthetic wide distance."""
    sl_distance = abs(price - sl)
    acc = mt5.account_info()
    sym = mt5.symbol_info(SYMBOL)
    if not acc or not sym:
        return FIXED_LOT
    risk_amount = acc.balance * RISK_PERCENT / 100.0
    tick_size = sym.trade_tick_size
    tick_value = sym.trade_tick_value
    if tick_size <= 0 or tick_value <= 0:
        return FIXED_LOT
    value_per_lot = (sl_distance / tick_size) * tick_value
    lot = risk_amount / value_per_lot if value_per_lot > 0 else FIXED_LOT
    lot = round(lot, 2)
    min_lot = max(sym.volume_min, 0.01)
    max_lot = min(sym.volume_max, MAX_LOT)
    return max(min_lot, min(max_lot, lot))


def execute_entry(direction: str, signal_type: str, sl_price_hint: float = 0.0, lot_multiplier: float = 1.0):
    """Places a market order on the DEMO account. Returns dict {ticket, price, sl, tp, lot} or None.
    lot_multiplier < 1.0 when Absorption warns against this entry (Dadang: "BUY
    WARNING, buyer mulai ter-absorb, kurangi lot") - entry still fires, smaller size.

    NO TP (2026-08-07) - Dadang: "JANGAN TP KECUALI ADA SIGNAL SELL... gw
    trading gak pernah TP 10 pip." A wall-based/absorption-based TP kept
    closing winning positions early then re-entering at the top right before
    a pullback - textbook whipsaw. Exit is 100% doctrine-driven
    (get_position_status() -> close_position()), never a broker price target.

    sl_price_hint: a real technical level (currently only WALL_ENTRY provides
    this - the wall's invalidation point) that's TRUSTED as the SL if it clears
    MIN_SL_DIST. Otherwise (CF/VR_SCALP, no sl_price_hint) falls back to the
    wide RISK_PERCENT-of-balance catastrophic backstop, decoupled from any
    chart level - the real cut-loss for those is doctrine-driven, this SL
    should rarely fire."""
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        print("[MT5Executor] No tick data, skip entry.")
        return None

    price = tick.ask if direction == "BUY" else tick.bid
    use_technical_sl = bool(sl_price_hint and sl_price_hint > 0 and
                             abs(price - sl_price_hint) >= MIN_SL_DIST)
    lot = _risk_based_lot_for_sl(price, sl_price_hint) if use_technical_sl else FIXED_LOT

    if lot_multiplier != 1.0:
        sym = mt5.symbol_info(SYMBOL)
        min_lot = max(sym.volume_min, 0.01) if sym else 0.01
        lot = max(min_lot, round(lot * lot_multiplier, 2))

    sl = round(sl_price_hint, 2) if use_technical_sl else _catastrophic_sl_price(direction, price, lot)
    comment = f"{COMMENT_PREFIX}_{signal_type}"[:31]  # MT5 comment field caps at 31 chars

    result = mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": 0.0,  # no take-profit order - see docstring
        "deviation": 20,  # points of slippage tolerance - without this, ANY price
                          # movement between fetching tick and order processing
                          # silently rejects the order (caught live: close_position
                          # failing with generic "MT5 connection error")
        "magic": MAGIC_NUMBER,
        "comment": comment,
        "type_filling": mt5.ORDER_FILLING_IOC,
    })

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        err = result.comment if result else f"MT5 connection error ({mt5.last_error()})"
        print(f"[MT5Executor] ENTRY FAILED: {err}")
        return None

    print(f"[MT5Executor] ENTRY {direction} {lot}L @ {price:.2f} SL {sl:.2f} TP none (doktrin-driven) #{result.order}")
    return {"ticket": result.order, "price": price, "sl": sl, "tp": None, "lot": lot}


def close_position(ticket: int, reason: str = ""):
    """Closes an open position by ticket. Returns dict {price, pnl} or None.
    `reason` is only for the caller's own logging/trade_db (unlimited length
    there) - the MT5 comment field itself stays a short fixed tag. This
    broker (ICMarketsSC-Demo) silently rejects close orders with a comment
    longer than a few characters ("Invalid comment argument") even though
    open orders happily accept up to 31 - caught live trying to close a
    duplicate position with a full reason string as the comment."""
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        print(f"[MT5Executor] Position #{ticket} udah gak ada / udah ketutup (SL/TP kena duluan).")
        return None

    p = positions[0]
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        return None
    price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask

    result = mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": p.volume,
        "type": mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "position": p.ticket,
        "price": price,
        "deviation": 20,  # see execute_entry - without this, a moved price silently rejects
        "magic": MAGIC_NUMBER,
        "comment": "exit",
        "type_filling": mt5.ORDER_FILLING_IOC,
    })

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        err = result.comment if result else f"MT5 connection error ({mt5.last_error()})"
        print(f"[MT5Executor] EXIT FAILED #{ticket}: {err}")
        return None

    pnl = p.profit
    print(f"[MT5Executor] EXIT #{ticket} @ {price:.2f} | PnL {pnl:+.2f} | {reason}")
    return {"price": price, "pnl": pnl}


def get_open_position_dict():
    """Any currently open position with our magic number, reshaped into the
    same dict shape master_engine.active_position uses, or None. Used at
    startup to reconcile in-memory tracking with reality - without this, a
    process restart while a position is still open loses track of it (fresh
    active_position=None) and fires a DUPLICATE entry next time the same
    signal condition is still true. Caught live: two identical BUY entries
    166 seconds apart, exactly one restart cycle in between."""
    positions = mt5.positions_get(symbol=SYMBOL)
    for p in positions or []:
        if p.magic == MAGIC_NUMBER:
            direction = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
            return {
                "dir": direction, "tf": "M5", "entry_time": p.time,
                "mt5_ticket": p.ticket, "entry_price": p.price_open,
                "sl": p.sl, "tp": p.tp, "lot": p.volume,
            }
    return None


def is_position_open(ticket: int) -> bool:
    """True if this ticket still has an open position on the broker. Used to
    detect SL/TP hitting on its own (broker closes it directly) BEFORE our own
    doctrine-based exit condition ever fires - without this check, our
    internal active_position/DB state goes stale and out of sync with reality."""
    positions = mt5.positions_get(ticket=ticket)
    return bool(positions)


def check_orphaned_close(ticket: int):
    """Position might already be gone because SL/TP hit on its own (not via our
    close_position call) - check MT5 history to recover the real exit price/pnl
    for logging, instead of silently losing that trade's outcome."""
    deals = mt5.history_deals_get(position=ticket)
    if not deals:
        return None
    closing = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
    if not closing:
        return None
    d = closing[-1]
    return {"price": d.price, "pnl": d.profit}
