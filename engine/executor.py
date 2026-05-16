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
            return

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
                console.print(f"[bold yellow]🛡️ BE PROTECT ACTIVATED for Ticket {p.ticket}[/bold yellow]")

            # 2. TP PAKSA: M30 fails to make new BO
            # If we are in a trade for a while and M30 doesn't confirm momentum
            m30 = analyst.states["M30"]
            # Simplified: If M30 direction is against position, Close!
            if (p.type == mt5.POSITION_TYPE_BUY and m30.cmp == "SELL") or \
               (p.type == mt5.POSITION_TYPE_SELL and m30.cmp == "BUY"):
                self.close_position(p, "TP PAKSA: M30 Counter-Trend Detected")

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

    def execute_strike(self, direction, analyst, lot=0.01, comment="Chain Strike"):
        """Executes a trade with all Chain Reaction rules applied."""
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return False, "No Tick Data"
            
        price = tick.ask if direction == "BUY" else tick.bid
        
        # 1. Barrier Guard Check
        passed, msg = self.check_barrier_guard(price, analyst)
        if not passed:
            console.print(f"[bold red]{msg}[/bold red]")
            return False, msg
            
        # 2. TP HIERARCHY LAW: Mapping TP to the trigger TF SNR
        # DOKTRIN: Jika M15 sudah VR, TP harus lebih pendek (Quick Scalp)
        m15 = analyst.states["M15"]
        m30 = analyst.states["M30"]
        
        # Determine base TP
        trigger_tf = "M5"
        tp = self.calculate_snr_hunter_tp(direction, analyst, tf_name=trigger_tf)
        
        # ADAPTIVE TP: If M15 or M30 is in VR against Master, we play it safe
        if m15.status == "VR" or m30.status == "VR":
            # Shorten TP to 20 pips instead of SNR hunter if SNR is too far
            scalp_tp = price + 2.0 if direction == "BUY" else price - 2.0
            if tp > 0:
                tp = min(tp, scalp_tp) if direction == "BUY" else max(tp, scalp_tp)
            else:
                tp = scalp_tp
            console.print("[bold yellow]⚠️ ADAPTIVE TP: Deep VR detected. Shortening target.[/bold yellow]")
        
        # 3. TECHNICAL SL: Below Trigger TF SNR
        trigger_state = analyst.states[trigger_tf]
        technical_sl = trigger_state.sup if direction == "BUY" else trigger_state.res
        sl = technical_sl if technical_sl > 0 else (price - 1.5 if direction == "BUY" else price + 1.5)

        # 4. Check Pyramiding
        positions = mt5.positions_get(symbol=self.symbol, magic=self.magic_number)
        if positions:
            total_pnl = sum([p.profit for p in positions])
            if total_pnl < -10.0:
                 return False, f"Pyramid Veto: Account in Drawdown ({total_pnl:.2f})"

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
            return False, f"Order Failed: {err_msg}"
            
        return True, f"Strike Executed! Ticket: {result.order} | TP: {tp:.2f} | SL: {sl:.2f}"
