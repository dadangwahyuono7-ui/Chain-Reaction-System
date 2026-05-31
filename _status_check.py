import sys
sys.stdout.reconfigure(encoding="utf-8")
from engine.connection import connect_mt5
from engine.core import SacredDoctrineAnalyst, DailyDeployAnalyst
import MetaTrader5 as mt5

if connect_mt5():
    a = SacredDoctrineAnalyst('XAUUSD', master_tf='H4')
    d = DailyDeployAnalyst('XAUUSD')
    a.update()
    d.update(a)

    tick = mt5.symbol_info_tick('XAUUSD')
    print(f"PRICE: {tick.bid:.2f}")
    print()

    for n in ['D1','H4','H1','M30','M15','M5']:
        st = a.states[n]
        print(f"{n:4s}: CMP={st.cmp:4s}  SUP={st.sup:.2f}  RES={st.res:.2f}  VR={str(st.vr_occurred):5s}  CF#={st.cf_count}  status={st.status}")

    print()
    scan = a.get_active_cmp_scan()
    if scan:
        print("=== ACTIVE VR SETUPS ===")
        for s in scan:
            grade  = s['grade']
            cmp_tf = s['cmp_tf']
            dirn   = s['direction']
            vr_tf  = s['vr_tf']
            sig    = s['signal']
            entry  = s['entry_tf']
            strn   = s['setup_strength']
            danger = s['danger_level']
            cfcnt  = s['cf_count']
            ext_tp = s.get('extended_tp') or '-'
            print(f"  [{grade}] {cmp_tf} {dirn} | VR={vr_tf} | {sig} | entry={entry} | {strn} | danger={danger} | CF#={cfcnt} | extTP={ext_tp}")
    else:
        print("Tidak ada active VR setup saat ini.")

    print()
    sig = a.get_strike_signal()
    if sig:
        print(f"CHAIN SIGNAL: {sig['action']} {sig['type']} grade={sig['grade']} entry={sig['tf']} SL={sig['sl_tf']} TP={sig['tp_tf']}")
        print(f"  reason: {sig['reason']}")
    else:
        print("CHAIN SIGNAL: None (menunggu setup)")

    print()
    best = d.get_best_signal()
    if best:
        print(f"DD BEST: {best['action']} {best['layer']} {best['type']} risk={best['risk']} danger={best['danger_level']} CF#={best['cf_count']}")
        print(f"  reason: {best['reason']}")
    else:
        print("DD BEST: None")

    print()
    print("=== DD ALL ACTIVE SIGNALS ===")
    if d.active_signals:
        for s in d.active_signals:
            print(f"  {s['layer']:12s} {s['action']:4s} {s['type']:8s} risk={s['risk']:7s} danger={s['danger_level']} CF#={s['cf_count']}")
    else:
        print("  (kosong)")

    regime, regime_reason = a.get_market_regime()
    print()
    print(f"MARKET REGIME: {regime} — {regime_reason}")

    mt5.shutdown()
