# SOP AKAR v3.0 — Chain Reaction Engine
# © Dadang Wahyuono 2025

import MetaTrader5 as mt5
import numpy as np

TF_MAP = {
    'D1':  mt5.TIMEFRAME_D1,
    'H4':  mt5.TIMEFRAME_H4,
    'M30': mt5.TIMEFRAME_M30,
    'M5':  mt5.TIMEFRAME_M5,
    'M1':  mt5.TIMEFRAME_M1,
}

# ─── SNR ──────────────────────────────────────────────────────────────────────

def detect_snr(candles):
    closes = [c['close'] for c in candles]
    resistance = resistance_old = support = support_old = None

    for i in range(len(closes) - 3, -1, -1):
        c1, c2, c3 = closes[i+2], closes[i+1], closes[i]
        if c1 < c2 and c2 >= c3:
            if resistance is None: resistance = c2
            elif resistance_old is None: resistance_old = c2; break

    for i in range(len(closes) - 3, -1, -1):
        c1, c2, c3 = closes[i+2], closes[i+1], closes[i]
        if c1 > c2 and c2 <= c3:
            if support is None: support = c2
            elif support_old is None: support_old = c2; break

    return {'resistance': resistance, 'resistance_old': resistance_old,
            'support': support, 'support_old': support_old}

# ─── CMP ──────────────────────────────────────────────────────────────────────

def detect_cmp(candles, snr, buf):
    if not candles or not snr['resistance'] or not snr['support']:
        return 'NONE'
    last = candles[-1]
    if last['close'] >= snr['resistance'] + buf and last['close'] > last['open']:
        return 'BUY'
    if last['close'] <= snr['support'] - buf and last['close'] < last['open']:
        return 'SELL'
    return 'NONE'

# ─── ATR ──────────────────────────────────────────────────────────────────────

def calc_atr(candles, period=14):
    trs = [c['high'] - c['low'] for c in candles[-period:]]
    return np.mean(trs) if trs else 1.0

# ─── MT5 Data ─────────────────────────────────────────────────────────────────

def get_candles(symbol, tf_str, count=100):
    rates = mt5.copy_rates_from_pos(symbol, TF_MAP[tf_str], 0, count)
    if rates is None:
        return []
    return [{'time': r['time'], 'open': float(r['open']), 'high': float(r['high']),
             'low': float(r['low']), 'close': float(r['close'])} for r in rates]

def get_price(symbol):
    tick = mt5.symbol_info_tick(symbol)
    return (tick.ask + tick.bid) / 2

def get_balance():
    return mt5.account_info().balance

def place_order(symbol, direction, volume, sl, tp=0):
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if direction == 'BUY' else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL
    req = {
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': symbol, 'volume': volume, 'type': order_type,
        'price': price, 'sl': sl, 'tp': tp if tp else 0,
        'deviation': 10, 'magic': 230001, 'comment': 'SOP_AKAR_v3',
        'type_time': mt5.ORDER_TIME_GTC, 'type_filling': mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(req)
    return result.retcode, result.order

def close_all(symbol):
    positions = mt5.positions_get(symbol=symbol)
    for pos in (positions or []):
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(symbol)
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        req = {
            'action': mt5.TRADE_ACTION_DEAL, 'symbol': symbol,
            'volume': pos.volume, 'type': close_type, 'position': pos.ticket,
            'price': price, 'deviation': 10, 'magic': 230001,
            'comment': 'CLOSE_SOP_AKAR', 'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_IOC,
        }
        mt5.order_send(req)

# ─── Engine State ─────────────────────────────────────────────────────────────

class TFState:
    def __init__(self, name):
        self.name = name
        self.cmp = 'NONE'
        self.snr = {}
        self.rt_marker = False
        self.cf = False
        self.active = False

    def reset(self):
        self.rt_marker = False
        self.cf = False

    def update(self, candles, parent_cmp, buf):
        self.snr = detect_snr(candles)
        self.cmp = detect_cmp(candles, self.snr, buf)
        self.active = self.cmp != 'NONE'

        if parent_cmp == 'NONE':
            return

        if self.cmp != 'NONE' and self.cmp != parent_cmp:
            self.rt_marker = True

        self.cf = self.rt_marker and self.cmp == parent_cmp

class ChainReactionEngine:
    def __init__(self, config):
        self.cfg = config
        self.symbol = config.SYMBOL
        self.buf = config.BREAKOUT_BUFFER

        self.daily = TFState('DAILY')
        self.h4    = TFState('H4')
        self.m30   = TFState('M30')
        self.m5    = TFState('M5')
        self.m1    = TFState('M1')

        self.prev_daily_cmp = 'NONE'
        self.prev_h4_cmp    = 'NONE'

        # Ninja state
        self.m5_rt_ninja = False
        self.m5_last_ninja = 'NONE'
        self.m30_cf_ninja_override = False

        self.current_position = None
        self.last_signal_key  = None

    def _reset_cascade(self):
        for tf in [self.m30, self.m5, self.m1]:
            tf.reset()
        self.m5_rt_ninja = False
        self.m5_last_ninja = 'NONE'
        self.m30_cf_ninja_override = False

    def update(self):
        # Fetch all candles
        d  = get_candles(self.symbol, 'D1',  50)
        h4 = get_candles(self.symbol, 'H4',  50)
        m30= get_candles(self.symbol, 'M30', 100)
        m5 = get_candles(self.symbol, 'M5',  100)
        m1 = get_candles(self.symbol, 'M1',  100)

        # DAILY
        self.daily.snr = detect_snr(d)
        self.daily.cmp = detect_cmp(d, self.daily.snr, self.buf)
        daily_cmp = self.daily.cmp

        if daily_cmp != self.prev_daily_cmp and daily_cmp != 'NONE':
            self.h4.reset()
            self.prev_daily_cmp = daily_cmp

        # H4
        self.h4.snr = detect_snr(h4)
        self.h4.cmp = detect_cmp(h4, self.h4.snr, self.buf)
        h4_cmp = self.h4.cmp

        if h4_cmp != self.prev_h4_cmp and h4_cmp != 'NONE':
            self._reset_cascade()
            self.prev_h4_cmp = h4_cmp

        if daily_cmp != 'NONE' and h4_cmp != 'NONE':
            if h4_cmp != daily_cmp: self.h4.rt_marker = True
            self.h4.cf = self.h4.rt_marker and h4_cmp == daily_cmp

        # M30
        self.m30.update(m30, h4_cmp, self.buf)

        # M5
        self.m5.snr = detect_snr(m5)
        self.m5.cmp = detect_cmp(m5, self.m5.snr, self.buf)
        m5_cmp = self.m5.cmp
        m30_cmp = self.m30.cmp

        if m30_cmp != 'NONE' and m5_cmp != 'NONE':
            if m5_cmp != m30_cmp:
                self.m5.rt_marker = True
                if not self.m5_rt_ninja:
                    self.m5_rt_ninja = True
                    self.m5_last_ninja = m5_cmp
            self.m5.cf = self.m5.rt_marker and m5_cmp == m30_cmp
            if self.m5_rt_ninja and m5_cmp == m30_cmp and m5_cmp != self.m5_last_ninja:
                self.m30_cf_ninja_override = True

        # M1
        self.m1.update(m1, self.m5.cmp, self.buf)

        return self.detect_signal(m5)

    def detect_signal(self, m5_candles):
        h4_dir = self.h4.cmp

        # EXIT
        if self.current_position:
            pos_dir = self.current_position['direction']
            if (pos_dir == 'BUY' and self.m1.cmp == 'SELL') or \
               (pos_dir == 'SELL' and self.m1.cmp == 'BUY'):
                return {'type': 'EXIT', 'direction': pos_dir, 'reason': 'M1 breakout berlawanan'}

        # PYRAMID
        for direction in (['BUY'] if h4_dir == 'BUY' else ['SELL'] if h4_dir == 'SELL' else []):
            ok = all([
                self.m30.active, self.m30.rt_marker, self.m30.cf, self.m30.cmp == direction,
                self.m5.active,  self.m5.rt_marker,  self.m5.cf,  self.m5.cmp == direction,
                self.m1.active,  self.m1.rt_marker,  self.m1.cf,  self.m1.cmp == direction,
            ])
            if ok:
                atr = calc_atr(m5_candles)
                return {'type': 'PYRAMID', 'direction': direction, 'atr': atr, 'chain': '100%'}

        # NINJA
        if self.cfg.ENABLE_NINJA and h4_dir != 'NONE':
            ninja_dir = self.m30.cmp if self.m30.cmp != h4_dir and self.m30.cmp != 'NONE' else None
            if ninja_dir and self.m30.rt_marker and self.m30_cf_ninja_override \
               and self.m1.active and self.m1.cmp == ninja_dir:
                atr = calc_atr(m5_candles)
                return {'type': 'NINJA', 'direction': ninja_dir, 'atr': atr, 'chain': 'N/A'}

        # MICRO
        if self.cfg.ENABLE_MICRO and h4_dir != 'NONE':
            if self.m30.cmp == h4_dir and not self.m30.rt_marker and self.m30.active:
                return {'type': 'MICRO', 'direction': h4_dir, 'atr': 0, 'chain': '33%'}

        return None

    def chain_progress(self):
        count = sum([self.h4.cf, self.m30.cf, self.m5.cf])
        return f"{int(count * 33.33)}%"

    def state_str(self):
        def tf(s): return f"{s.cmp}{'(RT)' if s.rt_marker else ''}{'(CF)' if s.cf else ''}"
        return (f"DAILY:{self.daily.cmp} | H4:{tf(self.h4)} | "
                f"M30:{tf(self.m30)} | M5:{tf(self.m5)} | M1:{tf(self.m1)} | "
                f"Chain:{self.chain_progress()}")
