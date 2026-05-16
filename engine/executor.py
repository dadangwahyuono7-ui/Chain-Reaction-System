import MetaTrader5 as mt5
import time
from rich.console import Console

console = Console()

class SultanExecutor:
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

    def execute_strike(self, direction, analyst, lot=0.01, comment="Sultan Strike"):
        """Executes a trade with all Sultan Sniper rules applied."""
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return False, "No Tick Data"
            
        price = tick.ask if direction == "BUY" else tick.bid
        
        # 1. Barrier Guard Check
        passed, msg = self.check_barrier_guard(price, analyst)
        if not passed:
            console.print(f"[bold red]{msg}[/bold red]")
            return False, msg
            
        # 2. SNR Hunter TP
        tp = self.calculate_snr_hunter_tp(direction, analyst, tf_name="M5")
        
        # 3. Napas Lega SL (Wide Stop Loss - 150 pips)
        sl_dist = 15.0 # 150 pips
        sl = price - sl_dist if direction == "BUY" else price + sl_dist
        
        # 4. Check Pyramiding (Only if PnL > 0)
        positions = mt5.positions_get(symbol=self.symbol, magic=self.magic_number)
        if positions:
            total_pnl = sum([p.profit for p in positions])
            if total_pnl <= 0:
                return False, "Pyramid Veto: Current PnL is not positive."

        # 5. Send Order
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": self.magic_number,
            "comment": comment,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"Order Failed: {result.comment}"
            
        return True, f"Strike Executed! Ticket: {result.order}"
