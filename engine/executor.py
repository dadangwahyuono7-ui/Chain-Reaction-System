import MetaTrader5 as mt5
import time
from rich.console import Console

console = Console()

class ChainReactionExecutor:
    def __init__(self, symbol, magic_number=2026):
        self.symbol = symbol
        self.magic_number = magic_number
        self.barrier_limit = 3.5 # 35 pips in Gold (0.1 = 1 pip)

    def check_barrier_guard(self, price, analyst):
        """
        Barrier Guard 35-pip:
        Veto if price is > 35 pips from the Master Barrier (H4/D1).
        """
        # Use H4 as Master Barrier
        master = analyst.states["H4"]
        if master.cmp == "WAIT":
            master = analyst.states["D1"] # Fallback to D1
            
        barrier_price = master.sup if master.cmp == "BUY" else master.res
        
        if barrier_price > 0:
            dist = abs(price - barrier_price)
            if dist > self.barrier_limit:
                return False, f"VETO: Price too far from Barrier ({dist:.2f} > {self.barrier_limit})"
        
        return True, "Barrier OK"

    def calculate_snr_hunter_tp(self, direction, analyst, tf_name="M5"):
        """
        SNR Hunter TP:
        TP is mapped to the Minor SNR level of the confirmation timeframe.
        """
        state = analyst.states[tf_name]
        tp_price = state.res if direction == "BUY" else state.sup
        return tp_price

    def monitor_positions(self, analyst):
        """
        EXIT PROTECTION LAW:
        1. BE Protect: 10 pip trigger.
        2. TP Paksa: M30 fails new BO or hang detected.
        """
        positions = mt5.positions_get(symbol=self.symbol, magic=self.magic_number)
        if not positions:
            return []

        events = []
        for p in positions:
            # Calculate current profit in pips (Gold: 0.1 = 1 pip)
            curr_price = mt5.symbol_info_tick(self.symbol).bid if p.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(self.symbol).ask
            pips = (curr_price - p.price_open) * 10 if p.type == mt5.POSITION_TYPE_BUY else (p.price_open - curr_price) * 10
            
            # 1. BE Protect: 10 pip trigger
            if pips >= 10.0 and p.sl != p.price_open:
                # Move SL to Breakeven
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": p.ticket,
                    "symbol": self.symbol,
                    "sl": p.price_open,
                    "tp": p.tp,
                }
                mt5.order_send(request)
                events.append(f"🛡️ BE PROTECT: Ticket {p.ticket}")

            # 2. TP PAKSA: M30 fails to make new BO
            m30 = analyst.states["M30"]
            if (p.type == mt5.POSITION_TYPE_BUY and m30.cmp == "SELL") or \
               (p.type == mt5.POSITION_TYPE_SELL and m30.cmp == "BUY"):
                self.close_position(p, "TP PAKSA: M30 Counter")
                events.append(f"🚪 EXIT: TP PAKSA M30 Counter")
        
        return events

    def close_position(self, p, reason):
        tick = mt5.symbol_info_tick(self.symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": p.ticket,
            "price": tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "magic": self.magic_number,
            "comment": reason,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        mt5.order_send(request)
        console.print(f"[bold red]🚪 EXIT: {reason} | Ticket {p.ticket}[/bold red]")

    def execute_strike(self, direction, analyst, lot=0.01, comment="Chain Strike", tp_price=0.0, sl_price=0.0):
        """Executes a trade with all Chain Reaction rules applied."""
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return False, "OFFLINE: No Tick Data"
            
        price = tick.ask if direction == "BUY" else tick.bid
        
        # 1. Barrier Guard Check
        passed, msg = self.check_barrier_guard(price, analyst)
        if not passed:
            return False, f"VETO: {msg}"
            
        # 2. TP HIERARCHY LAW / Custom TP
        is_adaptive = False
        if tp_price > 0:
            tp = tp_price
        else:
            m15 = analyst.states["M15"]
            m30 = analyst.states["M30"]
            trigger_tf = "M5"
            tp = self.calculate_snr_hunter_tp(direction, analyst, tf_name=trigger_tf)
            
            # ADAPTIVE TP
            if m15.status == "VR" or m30.status == "VR":
                scalp_tp = price + 2.0 if direction == "BUY" else price - 2.0
                if tp > 0:
                    tp = min(tp, scalp_tp) if direction == "BUY" else max(tp, scalp_tp)
                else:
                    tp = scalp_tp
                is_adaptive = True

        # 3. TECHNICAL SL / Custom SL
        if sl_price > 0:
            sl = sl_price
        else:
            trigger_tf = "M5"
            trigger_state = analyst.states[trigger_tf]
            technical_sl = trigger_state.sup if direction == "BUY" else trigger_state.res
            sl = technical_sl if technical_sl > 0 else (price - 1.5 if direction == "BUY" else price + 1.5)

        # 4. Check Pyramiding
        positions = mt5.positions_get(symbol=self.symbol, magic=self.magic_number)
        if positions:
            total_pnl = sum([p.profit for p in positions])
            if total_pnl < -10.0:
                 return False, "VETO: Deep Drawdown Layering Blocked"

        # 5. Send Order
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "magic": self.magic_number,
            "comment": comment,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        import random
        time.sleep(random.uniform(0.1, 0.3))
        
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err_msg = result.comment if result else "MT5 Connection Error"
            return False, f"FAILED: {err_msg}"
            
        res_msg = f"SUCCESS: {direction} Strike at {price:.2f}"
        if is_adaptive: res_msg += " (Adaptive TP)"
        return True, res_msg
