import MetaTrader5 as mt5
import time
from datetime import datetime
import pytz
from rich.console import Console

console = Console()

class ChainReactionExecutor:
    def __init__(self, symbol, magic_number=2026):
        self.symbol = symbol
        self.magic_number = magic_number
        # Defaults — synced each loop via update_settings()
        self.barrier_limit = 3.5
        self.be_protect_pips = 10.0
        self.trail_stop_pips = 5.0
        self.adaptive_tp_scalp_usd = 2.0
        self.fallback_sl_pips = 1.5
        self.drawdown_block_percent = 2.0
        self.max_lot_size = 0.5
        self.session_filter = True
        self.max_spread_points = 30
        self.news_blackout_minutes = 15
        self.news_schedule_wib = []

    def update_settings(self, settings):
        """Sync all runtime config from chain_settings.json each loop."""
        self.barrier_limit = settings.get("barrier_limit", 3.5)
        self.be_protect_pips = settings.get("be_protect_pips", 10.0)
        self.trail_stop_pips = settings.get("trail_stop_pips", 5.0)
        self.adaptive_tp_scalp_usd = settings.get("adaptive_tp_scalp_usd", 2.0)
        self.fallback_sl_pips = settings.get("fallback_sl_pips", 1.5)
        self.drawdown_block_percent = settings.get("drawdown_block_percent", 2.0)
        self.max_lot_size = settings.get("max_lot_size", 0.5)
        self.session_filter = settings.get("session_filter", True)
        self.max_spread_points = settings.get("max_spread_points", 30)
        self.news_blackout_minutes = settings.get("news_blackout_minutes", 15)
        self.news_schedule_wib = settings.get("news_schedule_wib", [])

    # ─────────────────────────── GUARD CHECKS ────────────────────────────────

    def check_barrier_guard(self, price, analyst):
        """Veto if price is > barrier_limit USD from the H4/D1 Master Barrier."""
        master = analyst.states["H4"]
        if master.cmp == "WAIT":
            master = analyst.states["D1"]

        barrier_price = master.sup if master.cmp == "BUY" else master.res
        if barrier_price > 0:
            dist = abs(price - barrier_price)
            if dist > self.barrier_limit:
                return False, f"VETO: Barrier dist {dist:.2f} > {self.barrier_limit} USD"
        return True, "Barrier OK"

    def check_session_and_spread(self):
        """
        Session Filter: only allow execution during London (08–16 UTC) or NY (13–21 UTC).
        Spread Guard: veto if spread exceeds max_spread_points.
        """
        tick = mt5.symbol_info_tick(self.symbol)
        info = mt5.symbol_info(self.symbol)

        # Spread guard
        if tick and info and info.point > 0:
            spread_pts = round((tick.ask - tick.bid) / info.point)
            if spread_pts > self.max_spread_points:
                return False, f"VETO: Spread {spread_pts} pts > {self.max_spread_points} limit"

        # Session filter
        if self.session_filter:
            hour_utc = datetime.now(pytz.utc).hour
            in_london = 8 <= hour_utc < 16
            in_new_york = 13 <= hour_utc < 21
            if not (in_london or in_new_york):
                return False, f"VETO: Outside London/NY sessions (UTC {hour_utc:02d}:xx)"

        return True, "Session & Spread OK"

    def check_news_blackout(self):
        """
        Pause execution within news_blackout_minutes of a scheduled
        high-impact event defined in news_schedule_wib.
        day: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        """
        if not self.news_schedule_wib or self.news_blackout_minutes <= 0:
            return True, "News OK"

        wib = pytz.timezone("Asia/Jakarta")
        now_wib = datetime.now(wib)
        blackout_secs = self.news_blackout_minutes * 60

        for event in self.news_schedule_wib:
            try:
                ev_day = int(event.get("day", -1))
                ev_h, ev_m = [int(x) for x in event.get("time", "00:00").split(":")]
                if ev_day >= 0 and now_wib.weekday() != ev_day:
                    continue
                ev_dt = now_wib.replace(hour=ev_h, minute=ev_m, second=0, microsecond=0)
                diff_secs = abs((now_wib - ev_dt).total_seconds())
                if diff_secs <= blackout_secs:
                    mins_away = int(diff_secs // 60)
                    return False, f"VETO: News blackout {event.get('time')} WIB ({mins_away}min)"
            except Exception:
                continue

        return True, "News OK"

    # ─────────────────────────── LOT SIZING ──────────────────────────────────

    def calculate_risk_lot(self, price, sl, settings):
        """
        Risk-based lot sizing: risk_per_trade_percent of balance / SL distance value.
        Falls back to lot_size from settings if MT5 symbol info unavailable.
        """
        default_lot = settings.get("lot_size", 0.01)
        sl_distance = abs(price - sl)
        if sl_distance < 0.01:
            return default_lot

        acc = mt5.account_info()
        sym = mt5.symbol_info(self.symbol)
        if not acc or not sym:
            return default_lot

        risk_amount = acc.balance * settings.get("risk_per_trade_percent", 1.0) / 100.0
        tick_size = sym.trade_tick_size
        tick_value = sym.trade_tick_value

        if tick_size > 0 and tick_value > 0:
            value_per_lot = (sl_distance / tick_size) * tick_value
            lot = risk_amount / value_per_lot if value_per_lot > 0 else default_lot
        else:
            lot = default_lot

        lot = round(lot, 2)
        min_lot = max(sym.volume_min, 0.01)
        max_lot = min(sym.volume_max, self.max_lot_size)
        return max(min_lot, min(max_lot, lot))

    # ─────────────────────────── TP CALCULATION ──────────────────────────────

    def calculate_snr_hunter_tp(self, direction, analyst, tf_name="M5"):
        """TP mapped to the Minor SNR level of the confirmation timeframe."""
        state = analyst.states[tf_name]
        return state.res if direction == "BUY" else state.sup

    # ─────────────────────────── POSITION MANAGEMENT ─────────────────────────

    def monitor_positions(self, analyst):
        """
        EXIT PROTECTION:
        1. BE Protect       — locks SL to breakeven at be_protect_pips profit.
        2. Trailing Stop    — trails SL by trail_stop_pips once BE is active.
        3. CF Sequence Exit — take profit jika CF tidak dikonfirmasi M15:
             CF_HIGH  : M15 gagal CF (tetap VR) + M5 balik arah → ambil profit
             MINOR_CF : M15 flip jadi VR ke M30 → context berubah → ambil profit
        4. TP Paksa         — force-close if M30 flips counter-direction.
        """
        positions = mt5.positions_get(symbol=self.symbol, magic=self.magic_number)
        if not positions:
            return []

        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return []

        m15 = analyst.states["M15"]
        m5  = analyst.states["M5"]
        m30 = analyst.states["M30"]

        events = []
        for p in positions:
            # Paranoia guard: skip posisi yang magic-nya bukan milik engine
            # (trade manual lo di MT5 magic=0, pasti kelewat)
            if p.magic != self.magic_number:
                continue
            curr_price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
            is_buy  = p.type == mt5.POSITION_TYPE_BUY
            direction = "BUY" if is_buy else "SELL"
            counter   = "SELL" if is_buy else "BUY"
            pips = (curr_price - p.price_open) * 10 if is_buy \
                   else (p.price_open - curr_price) * 10

            # 1. BE Protect
            if pips >= self.be_protect_pips and p.sl != p.price_open:
                mt5.order_send({
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": p.ticket,
                    "symbol": self.symbol,
                    "sl": p.price_open,
                    "tp": p.tp,
                })
                events.append(f"🛡️ BE PROTECT: #{p.ticket} SL locked at entry")

            # 2. Trailing Stop — only active after BE is locked
            elif p.sl >= p.price_open and is_buy:
                trail_dist = self.trail_stop_pips * 0.1  # pips → USD
                new_sl = round(curr_price - trail_dist, 2)
                if new_sl > p.sl:
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": p.ticket,
                        "symbol": self.symbol,
                        "sl": new_sl,
                        "tp": p.tp,
                    })
                    events.append(f"📈 TRAIL: #{p.ticket} SL → {new_sl:.2f}")

            elif p.sl <= p.price_open and not is_buy:
                trail_dist = self.trail_stop_pips * 0.1
                new_sl = round(curr_price + trail_dist, 2)
                if new_sl < p.sl:
                    mt5.order_send({
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": p.ticket,
                        "symbol": self.symbol,
                        "sl": new_sl,
                        "tp": p.tp,
                    })
                    events.append(f"📉 TRAIL: #{p.ticket} SL → {new_sl:.2f}")

            # 3. CF Sequence Exit — validasi kelanjutan CF setelah entry
            comment = p.comment or ""

            if "CF_HIGH" in comment:
                # Masuk di M5 CF saat M15 masih VR.
                # Harapan: M15 ikut break searah (upgrade ke CF_LOW).
                # Jika M15 tetap VR DAN M5 sudah balik arah → CF gagal dikonfirmasi → ambil profit.
                m15_still_vr = m15.cmp == counter  # M15 tidak ikut CF
                m5_reversed  = m5.cmp == counter   # M5 balik ke arah VR
                if m15_still_vr and m5_reversed:
                    self.close_position(p, "TP CF: M15 gagal confirm, M5 reversal")
                    events.append(f"💰 CF EXIT: #{p.ticket} — M15 tdk ikut CF, profit diambil")
                    continue

            elif "MINOR_CF" in comment:
                # Masuk di MINOR_CF saat M15 solid (tidak VR ke M30).
                # Jika M15 tiba-tiba flip jadi VR (counter arah) → context berubah → ambil profit.
                m15_flipped_vr = (m15.cmp == counter and m15.cmp != "WAIT")
                if m15_flipped_vr:
                    self.close_position(p, "TP MINOR_CF: M15 flip VR ke M30")
                    events.append(f"💰 MINOR_CF EXIT: #{p.ticket} — M15 jadi VR, profit diambil")
                    continue

            # 4. TP Paksa — hanya fire kalau H4 DAN M30 dua-duanya counter trade
            # Jika H4 aligned (trade ikut H4), M30 VR ke H4 adalah kondisi NORMAL
            # TP Paksa tidak boleh close trade yang masih punya dukungan H4 master
            h4 = analyst.states["H4"]
            h4_counter  = (h4.cmp != "WAIT" and h4.cmp == counter)   # H4 lawan trade
            m30_counter = (m30.cmp == counter)                         # M30 lawan trade
            if h4_counter and m30_counter:
                # Kedua H4 dan M30 lawan trade = tidak ada macro support = force close
                self.close_position(p, "TP PAKSA: H4+M30 Counter")
                events.append(f"🚪 TP PAKSA: #{p.ticket} H4+M30 Counter — no macro support")

        return events

    def close_position(self, p, reason):
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return
        mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": p.volume,
            "type": mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": p.ticket,
            "price": tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "magic": self.magic_number,
            "comment": reason,
            "type_filling": mt5.ORDER_FILLING_IOC,
        })
        console.print(f"[bold red]🚪 {reason} | #{p.ticket}[/bold red]")

    # ─────────────────────────── EXECUTION ───────────────────────────────────

    def execute_strike(self, direction, analyst, lot=0.0, comment="Chain Strike",
                       tp_price=0.0, sl_price=0.0, settings=None, tp_tf=None, sl_tf=None):
        """
        Execute a trade with the full Chain Reaction rule stack:
        Barrier Guard → Session/Spread → News Blackout → TP → SL →
        Risk Lot → Drawdown Guard → Order Send.
        """
        if settings is None:
            settings = {}

        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return False, "OFFLINE: No Tick Data"

        price = tick.ask if direction == "BUY" else tick.bid

        # 1. Barrier Guard
        ok, msg = self.check_barrier_guard(price, analyst)
        if not ok:
            return False, msg

        # 2. Session & Spread
        ok, msg = self.check_session_and_spread()
        if not ok:
            return False, msg

        # 3. News Blackout
        ok, msg = self.check_news_blackout()
        if not ok:
            return False, msg

        # 4. TP resolution
        # tp_tf comes from signal: CF_LOW targets TF above VR, CF_HIGH targets VR TF itself
        is_adaptive = False
        if tp_price > 0:
            tp = tp_price
        else:
            resolve_tf = tp_tf if tp_tf else "M5"
            tp = self.calculate_snr_hunter_tp(direction, analyst, tf_name=resolve_tf)

            # Adaptive TP: tighten if the resolved TF is very small (scalp conditions)
            if resolve_tf in ("M5", "M15") and tp == 0:
                tp = price + self.adaptive_tp_scalp_usd if direction == "BUY" \
                     else price - self.adaptive_tp_scalp_usd
                is_adaptive = True

        # 5. SL resolution
        # sl_tf = VR TF (level yang menguji CMP), bukan entry TF
        if sl_price > 0:
            sl = sl_price
        else:
            sl_ref = analyst.states.get(sl_tf) if sl_tf else analyst.states["M15"]
            technical_sl = sl_ref.sup if direction == "BUY" else sl_ref.res
            sl = technical_sl if technical_sl > 0 \
                 else (price - self.fallback_sl_pips if direction == "BUY"
                       else price + self.fallback_sl_pips)

        # 6. Dynamic lot sizing (uses SL distance for proper risk %)
        if lot == 0.0:
            lot = self.calculate_risk_lot(price, sl, settings)

        # 7. Drawdown Guard — proportional to balance
        positions = mt5.positions_get(symbol=self.symbol, magic=self.magic_number)
        if positions:
            acc = mt5.account_info()
            balance = acc.balance if acc else 10000.0
            threshold = -(balance * self.drawdown_block_percent / 100.0)
            total_pnl = sum(p.profit for p in positions)
            if total_pnl < threshold:
                return False, f"VETO: Drawdown {total_pnl:.2f} < {threshold:.2f} ({self.drawdown_block_percent}%)"

        # 8. Send order
        import random
        time.sleep(random.uniform(0.1, 0.3))

        result = mt5.order_send({
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
        })

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            err = result.comment if result else "MT5 Connection Error"
            return False, f"FAILED: {err}"

        msg = f"SUCCESS: {direction} {lot}L @ {price:.2f} | SL {sl:.2f} | TP {tp:.2f}"
        if is_adaptive:
            msg += " (Adaptive TP)"
        return True, msg
