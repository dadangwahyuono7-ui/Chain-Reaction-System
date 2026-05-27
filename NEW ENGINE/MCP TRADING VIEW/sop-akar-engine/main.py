#!/usr/bin/env python3
# Chain Reaction Engine — SOP AKAR v3.0
# © Dadang Wahyuono 2025
# Broker: Exness | MT5

import MetaTrader5 as mt5
import time, math
from datetime import datetime
import config
import telegram_bot as tg
from engine import ChainReactionEngine, get_price, get_balance, place_order, close_all, calc_atr, get_candles

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def get_sl(direction, price, atr, sl_mult):
    if direction == 'BUY':  return price - atr * sl_mult
    if direction == 'SELL': return price + atr * sl_mult

def get_tp(direction, h4_snr):
    if direction == 'BUY':  return h4_snr.get('resistance_old') or 0
    if direction == 'SELL': return h4_snr.get('support_old') or 0

def calc_volume(balance, risk_pct, price, sl):
    risk_amount = balance * (risk_pct / 100)
    sl_distance = abs(price - sl)
    if sl_distance == 0: return 0.01
    # XAU/USD: 1 lot = 100 oz, pip value ≈ 1 USD per 0.01 for 1 lot
    lot = risk_amount / (sl_distance * 100)
    return round(max(0.01, min(lot, 10.0)), 2)

def main():
    print("═══════════════════════════════════════")
    print(" Chain Reaction Engine — SOP AKAR v3.0")
    print(" © Dadang Wahyuono 2025")
    print("═══════════════════════════════════════")
    print(f" Symbol     : {config.SYMBOL}")
    print(f" Mode       : {'AUTO TRADE' if config.ENABLE_AUTO_TRADE else 'ALERT ONLY'}")
    print(f" Ninja      : {'ON' if config.ENABLE_NINJA else 'OFF'}")
    print(f" Micro      : {'ON' if config.ENABLE_MICRO else 'OFF'}")
    print(f" Poll       : {config.POLL_SECONDS}s")
    print("═══════════════════════════════════════\n")

    if not mt5.initialize():
        print("❌ MT5 initialize gagal — pastikan MT5 sudah buka dan login!")
        return

    print(f"✅ MT5 konek: {mt5.account_info().server} | Balance: {mt5.account_info().balance:.2f}")

    engine = ChainReactionEngine(config)
    last_signal_key = None
    status_tick = 0

    tg.send(config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID,
            f"🚀 <b>Chain Reaction Engine STARTED</b>\n"
            f"Symbol: {config.SYMBOL}\n"
            f"Mode: {'AUTO TRADE' if config.ENABLE_AUTO_TRADE else 'ALERT ONLY'}")

    while True:
        try:
            signal = engine.update()
            price  = get_price(config.SYMBOL)
            state  = engine.state_str()

            log(f"{state} | Price:{price:.2f}")

            if signal:
                signal_key = f"{signal['type']}-{signal['direction']}-{int(time.time() // 300)}"

                # ── EXIT ──
                if signal['type'] == 'EXIT':
                    log(f"🚨 EXIT — {signal['reason']}")
                    tg.send(config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID,
                            tg.msg_exit(signal['direction'], price, signal['reason']))
                    if config.ENABLE_AUTO_TRADE:
                        close_all(config.SYMBOL)
                        log("✅ Semua posisi ditutup")
                    engine.current_position = None
                    last_signal_key = None

                # ── ENTRY ──
                elif signal_key != last_signal_key:
                    sl_mult = config.PYRAMID_SL_ATR if signal['type'] == 'PYRAMID' else config.NINJA_SL_ATR
                    sl = get_sl(signal['direction'], price, signal['atr'], sl_mult)
                    tp = get_tp(signal['direction'], engine.h4.snr)

                    log(f"⚡ {signal['type']} {signal['direction']} | Entry:{price:.2f} SL:{sl:.2f} TP:{tp:.2f}")

                    tg.send(config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID,
                            tg.msg_signal(signal['type'], signal['direction'],
                                         price, sl, tp or 0, signal['chain']))

                    if config.ENABLE_AUTO_TRADE and signal['type'] in ['PYRAMID', 'NINJA']:
                        balance = get_balance()
                        volume  = calc_volume(balance, config.RISK_PERCENT, price, sl)
                        retcode, order_id = place_order(config.SYMBOL, signal['direction'], volume, sl, tp or 0)
                        if retcode == mt5.TRADE_RETCODE_DONE:
                            log(f"✅ Order #{order_id} placed | Volume:{volume}")
                            engine.current_position = {
                                'type': signal['type'], 'direction': signal['direction'],
                                'entry': price, 'sl': sl, 'tp': tp
                            }
                        else:
                            log(f"❌ Order gagal: retcode {retcode}")

                    last_signal_key = signal_key

            # Status report setiap 30 tick
            status_tick += 1
            if status_tick >= 30:
                tg.send(config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID,
                        tg.msg_status(state, price))
                status_tick = 0

        except Exception as e:
            log(f"❌ Error: {e}")
            tg.send(config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID,
                    f"⚠️ Engine error: {e}")

        time.sleep(config.POLL_SECONDS)

if __name__ == "__main__":
    main()
